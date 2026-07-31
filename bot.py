"""
Bot de Telegram para resultados de fútbol en vivo.

Estrategia:
1. Cada POLL_INTERVAL segundos, lista fixtures en vivo (filtrados por LEAGUES).
2. Para cada fixture:
   - Compara su status short con el último conocido.
   - Detecta: arranco (NS → 1H), medio tiempo (1H → HT), segunda mitad (HT → 2H),
     fin (→ FIN, AET, PEN).
   - Llama a /fixtures/events y compara con eventos ya publicados:
     goles, tarjetas, cambios, VAR, penaltis señalados.
3. Publica solo eventos nuevos al canal de Telegram.
4. Persiste estado en disco para sobrevivir reinicios.
"""
from __future__ import annotations

import logging
import signal
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

from api_client import APIFootballClient, APIFootballError
from config import config
from formatter import (
    msg_card,
    msg_goal,
    msg_halftime,
    msg_lineups,
    msg_match_finished,
    msg_match_started,
    msg_match_stats,
    msg_penalty_awarded,
    msg_penalty_shootout,
    msg_second_half,
    msg_substitution,
    msg_var,
)
from state import FixtureState, StateStore
from telegram_client import TelegramClient, TelegramError

# ---------------------------------------------------------------------- #
# Logging
# ---------------------------------------------------------------------- #
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("bot")


# ---------------------------------------------------------------------- #
# Estados de fixture que nos interesan
# ---------------------------------------------------------------------- #
STATUS_NOT_STARTED = {"NS", "TBD"}  # Not Started
STATUS_FIRST_HALF = {"1H"}
STATUS_HALFTIME = {"HT"}
STATUS_SECOND_HALF = {"2H"}
STATUS_EXTRA_TIME = {"ET"}
STATUS_BREAK_EXTRA = {"BT"}
STATUS_PENALTIES = {"P", "PEN"}  # Tanda de penaltis en curso
STATUS_SUSPENDED = {"SUSP", "INT"}
STATUS_LIVE_GENERIC = {"LIVE"}
STATUS_FINISHED = {"FT", "FIN", "AET", "PEN"}
STATUS_CANCELLED = {"PST", "CANC", "ABD", "AWD", "WO"}


def event_key(event: Dict[str, Any]) -> str:
    """
    Genera una clave única para deduplicar un evento.
    Usa tipo + minuto + jugador + equipo para distinguir.
    """
    t = event.get("time", {})
    # player y assist pueden ser dict {'id', 'name'} o None
    p = event.get("player") or {}
    a = event.get("assist") or {}
    p_id = p.get("id") if isinstance(p, dict) else p
    a_id = a.get("id") if isinstance(a, dict) else a
    return (
        f"{event.get('type', '')}|"
        f"{event.get('detail', '')}|"
        f"{t.get('elapsed', '')}|"
        f"{t.get('extra', '')}|"
        f"{event.get('team', {}).get('id', '')}|"
        f"{p_id}|"
        f"{a_id}"
    )


# ---------------------------------------------------------------------- #
# Bot
# ---------------------------------------------------------------------- #
class FootballBot:
    def __init__(self):
        config.validate()
        self.cfg = config
        self.api = APIFootballClient(config)
        self.tg = TelegramClient(config.tg_token, config.tg_channel)
        self.state = StateStore(config.state_file)
        self._stop = False

    # ------------------------------------------------------------------ #
    def stop(self, *_):
        log.info("Señal de parada recibida. Cerrando bot...")
        self._stop = True

    # ------------------------------------------------------------------ #
    def run(self) -> None:
        log.info("=== Bot de fútbol iniciando ===")
        log.info("Ligas: %s", self.cfg.leagues)
        log.info("Poll interval: %ds", self.cfg.poll_interval)
        log.info("Canal Telegram: %s", self.cfg.tg_channel)

        # Test conexión Telegram
        if not self.tg.test_connection():
            log.error(
                "No se pudo conectar el bot al canal. Revisa token y permisos."
            )
            sys.exit(1)

        log.info("Bot listo. Comenzando loop principal.")

        # Capturar señales para cerrar limpio
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        while not self._stop:
            try:
                self._tick()
            except APIFootballError as e:
                log.error("Error de API: %s", e)
                if "429" in str(e):
                    log.warning("Rate limit API. Durmiendo 30s extra.")
                    time.sleep(30)
            except TelegramError as e:
                log.error("Error de Telegram: %s", e)
            except Exception as e:
                log.error("Error inesperado en tick: %s", e)
                log.debug(traceback.format_exc())

            # Esperar hasta el próximo tick
            slept = 0
            while slept < self.cfg.poll_interval and not self._stop:
                time.sleep(1)
                slept += 1

        log.info("Bot detenido.")

    # ------------------------------------------------------------------ #
    def _tick(self) -> None:
        """Una iteración del loop principal."""
        from datetime import datetime, timedelta, timezone

        # 1) Listar partidos en vivo
        try:
            live = self.api.get_live_fixtures(self.cfg.leagues)
        except APIFootballError as e:
            log.error("get_live_fixtures falló: %s", e)
            live = []

        log.debug("Live fixtures (filtrados): %d", len(live))

        # 2) Procesar cada fixture en vivo
        active_ids = set()
        live_ids = set()
        for fx in live:
            fid = fx.get("fixture", {}).get("id")
            if not fid:
                continue
            active_ids.add(fid)
            live_ids.add(fid)
            try:
                self._process_fixture(fx)
            except Exception as e:
                log.error("Error procesando fixture %s: %s", fid, e)
                log.debug(traceback.format_exc())

        # 2.5) Verificar partidos que estábamos siguiendo y ya NO están en vivo.
        # Esto es CRÍTICO para detectar el final del partido, porque la API
        # remueve el partido de /fixtures?live=all cuando termina (status=FT).
        # Sin este paso, el bot nunca vería la transición 2H → FT.
        seen_fixtures = self.state.all_fixtures()
        for fid, fs_state in seen_fixtures.items():
            if fid in live_ids:
                continue  # aún está en vivo, ya procesado arriba
            # Si el partido estaba siendo seguido (tenía status previo) y NO
            # lo habíamos anunciado como terminado, consultamos su estado actual.
            if not fs_state.last_status_short:
                continue  # nunca lo vimos, ignorar
            if fs_state.finished_announced:
                continue  # ya anunciamos el final

            # Solo verificar partidos que estaban en un estado "en vivo"
            # (1H, HT, 2H, ET, BT, P, LIVE) en el último tick
            if fs_state.last_status_short not in (
                STATUS_FIRST_HALF | STATUS_HALFTIME | STATUS_SECOND_HALF
                | STATUS_EXTRA_TIME | STATUS_BREAK_EXTRA | STATUS_PENALTIES
                | STATUS_LIVE_GENERIC
            ):
                continue

            log.info(
                "Fixture %s ya no está en vivo (último status=%s). Verificando si terminó.",
                fid, fs_state.last_status_short,
            )
            try:
                fx = self.api.get_fixture(fid)
                if fx:
                    self._process_fixture(fx)
            except APIFootballError as e:
                log.warning("No se pudo verificar fixture %s: %s", fid, e)
            except Exception as e:
                log.error("Error verificando fixture terminado %s: %s", fid, e)

        # 3) Buscar partidos próximos (NS) para detectar alineaciones
        # Solo hacerlo cada cierto tiempo (no en cada tick) para ahorrar cuota
        now = datetime.now(timezone.utc)
        # Consultar partidos del día de hoy + mañana (para cubrir zonas horarias)
        try:
            today_str = now.strftime("%Y-%m-%d")
            upcoming = self.api.get_fixtures_by_date(today_str, self.cfg.leagues)
        except APIFootballError as e:
            log.warning("get_fixtures_by_date falló: %s", e)
            upcoming = []

        # Filtrar solo los que están por empezar en las próximas 3 horas
        cutoff = now + timedelta(hours=3)
        for fx in upcoming:
            status_short = (fx.get("fixture", {}).get("status", {}) or {}).get("short", "")
            if status_short not in STATUS_NOT_STARTED:
                continue
            fid = fx.get("fixture", {}).get("id")
            if not fid or fid in active_ids:
                continue

            # Parsear fecha del partido
            date_str = fx.get("fixture", {}).get("date", "")
            try:
                match_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            # Solo procesar si el partido empieza en las próximas 3h
            if not (now <= match_dt <= cutoff):
                continue

            active_ids.add(fid)
            try:
                self._check_lineups(fx)
            except Exception as e:
                log.error("Error revisando alineaciones de %s: %s", fid, e)
                log.debug(traceback.format_exc())

        # 4) Limpieza de estados antiguos
        seen_ids = set(self.state.all_fixtures().keys())
        keep = active_ids | seen_ids
        if len(seen_ids) > 300:
            removed = self.state.cleanup_old(keep)
            if removed:
                log.info("Limpieza de estado: %d fixtures eliminados", removed)

    # ------------------------------------------------------------------ #
    def _check_lineups(self, fixture: Dict[str, Any]) -> None:
        """
        Revisa si ya se publicaron alineaciones para un partido próximo.
        Solo consulta /fixtures/lineups si no las hemos enviado todavía.
        """
        fid = fixture["fixture"]["id"]
        fs = self.state.get(fid)

        if fs.lineups_announced:
            return  # ya las enviamos

        try:
            lineups = self.api.get_lineups(fid)
        except APIFootballError as e:
            log.warning("get_lineups(%s) falló: %s", fid, e)
            return

        # La API devuelve [] si las alineaciones aún no se han publicado
        if not lineups or len(lineups) < 2:
            return

        # Verificar que tengan formation (no es un placeholder vacío)
        has_formation = all(
            (lu.get("formation") for lu in lineups)
        )
        if not has_formation:
            return

        # ¡Alineaciones disponibles! Publicar
        log.info("Alineaciones disponibles para fixture %s. Publicando.", fid)
        self._post(msg_lineups(fixture, lineups))
        self.state.update(fid, lambda s: setattr(s, "lineups_announced", True))

    # ------------------------------------------------------------------ #
    def _process_fixture(self, fixture: Dict[str, Any]) -> None:
        """Detecta cambios de estado y nuevos eventos para un fixture."""
        fid = fixture["fixture"]["id"]
        status = fixture.get("fixture", {}).get("status", {}) or {}
        status_short = status.get("short", "")
        goals = fixture.get("goals", {}) or {}
        home_g = goals.get("home") if goals else None
        away_g = goals.get("away") if goals else None
        home_g = home_g if home_g is not None else 0
        away_g = away_g if away_g is not None else 0

        fs = self.state.get(fid)
        is_new_fixture = not self.state.has(fid) or fs.last_status_short == ""
        prev_status = fs.last_status_short
        prev_home = fs.last_home_goals
        prev_away = fs.last_away_goals

        log.debug(
            "Fixture %s: status %s -> %s | score %d-%d -> %d-%d | new=%s",
            fid, prev_status, status_short, prev_home, prev_away, home_g, away_g,
            is_new_fixture,
        )

        # ----- Si es la primera vez que vemos este fixture Y ya está en curso,
        # marcamos started/halftime/second_half como anunciados para no
        # inundar el canal con notificaciones retroactivas. ----- #
        if is_new_fixture and status_short not in STATUS_NOT_STARTED:
            log.info(
                "Fixture %s detectado en curso (status=%s). "
                "Marcando eventos previos como ya publicados.",
                fid, status_short,
            )
            self.state.update(
                fid,
                lambda s: (
                    setattr(s, "started_announced", True),
                    setattr(s, "halftime_announced", True),
                    setattr(s, "second_half_announced", True),
                ),
            )

        # ----- Detección de transiciones de status ----- #
        # Inicio de partido (→ 1H o LIVE)
        # Anunciar si llegamos a un estado "en vivo" y no lo habíamos anunciado.
        # No requerir prev_status == NS porque a veces el bot se pierde ese tick.
        if (
            not fs.started_announced
            and not is_new_fixture  # CRÍTICO: no publicar en primer contacto
            and status_short in STATUS_FIRST_HALF.union(STATUS_LIVE_GENERIC)
        ):
            self._post(msg_match_started(fixture))
            self.state.update(fid, lambda s: setattr(s, "started_announced", True))

        # Segunda mitad (→ 2H)
        # Anunciar si llegamos a 2H y no lo habíamos anunciado.
        # No requerimos que prev_status sea exactamente HT porque a veces
        # la API salta de 1H a 2H sin pasar por HT, o el bot se pierde el HT.
        if (
            not fs.second_half_announced
            and not is_new_fixture  # no publicar en primer contacto
            and status_short in STATUS_SECOND_HALF
        ):
            self._post(msg_second_half(fixture))
            self.state.update(
                fid,
                lambda s: (
                    setattr(s, "second_half_announced", True),
                    setattr(s, "halftime_announced", True),  # marcar HT como anunciado también
                ),
            )

        # Medio tiempo (1H → HT)
        # Anunciar si detectamos HT y no lo habíamos anunciado.
        if (
            not fs.halftime_announced
            and not is_new_fixture  # no publicar en primer contacto
            and status_short in STATUS_HALFTIME
        ):
            self._post(msg_halftime(fixture))
            self.state.update(fid, lambda s: setattr(s, "halftime_announced", True))

        # Fin de partido (→ FT, AET, PEN)
        # Anunciar si llegamos a FINISHED y no lo habíamos anunciado.
        # No publicar si es primer contacto (is_new_fixture) para no inundar
        # el canal con finales ya ocurridos al arrancar el bot.
        if (
            not fs.finished_announced
            and not is_new_fixture  # no publicar en primer contacto
            and status_short in STATUS_FINISHED
        ):
            self._post(msg_match_finished(fixture))
            self.state.update(fid, lambda s: setattr(s, "finished_announced", True))
            # Enviar resumen con estadísticas (en segundo plano, no bloqueante)
            try:
                self._send_match_stats(fixture, fid)
            except Exception as e:
                log.error("Error enviando stats para fixture %s: %s", fid, e)
        elif (
            is_new_fixture
            and status_short in STATUS_FINISHED
            and not fs.finished_announced
        ):
            # Si llegamos al bot y el partido ya terminó, marcar como anunciado
            # sin publicar nada.
            log.info(
                "Fixture %s ya finalizado (%s). Marcando sin publicar.",
                fid, status_short,
            )
            self.state.update(fid, lambda s: setattr(s, "finished_announced", True))

        # ----- Detección de goles (fallback: si el marcador cambia
        # y no encontramos evento de gol, igualmente avisamos) ----- #
        # Esto se maneja vía eventos más abajo, pero como salvaguarda:
        # (omitido: ya disparamos el evento Goal desde /fixtures/events)

        # ----- Actualizar estado conocido ----- #
        self.state.update(
            fid,
            lambda s: (
                setattr(s, "last_status_short", status_short),
                setattr(s, "last_home_goals", home_g),
                setattr(s, "last_away_goals", away_g),
            ),
        )

        # ----- Solo consultar eventos si el partido ya empezó ----- #
        if status_short in STATUS_NOT_STARTED:
            return

        try:
            events = self.api.get_fixture_events(fid)
        except APIFootballError as e:
            log.warning("get_fixture_events(%s) falló: %s", fid, e)
            return

        self._process_events(events, fixture, fid, is_new_fixture=is_new_fixture)

    # ------------------------------------------------------------------ #
    def _process_events(
        self,
        events: List[Dict[str, Any]],
        fixture: Dict[str, Any],
        fixture_id: int,
        is_new_fixture: bool = False,
    ) -> None:
        """
        Publica solo los eventos nuevos.

        - Marca eventos como publicados ANTES de enviar (evita duplicados
          si el envío falla o si el siguiente tick llega antes de tiempo).
        - Para goles, espera 3s y refresca el fixture para tener el marcador
          actualizado (la API a veces tarda en reflejar el nuevo marcador).
        - Si is_new_fixture=True, marca todos como publicados sin enviar.
        """
        if not events:
            return

        fs = self.state.get(fixture_id)
        new_keys: List[str] = []

        # Filtrar solo los eventos realmente nuevos
        for ev in events:
            key = event_key(ev)
            if key in fs.published_event_keys:
                continue
            new_keys.append(key)

        if not new_keys:
            return

        # Marcar TODOS los nuevos como publicados ANTES de enviar.
        # Esto evita duplicados si el envío falla o si llega el siguiente
        # tick antes de que terminemos.
        self.state.update(
            fixture_id,
            lambda s: s.published_event_keys.update(new_keys),
        )

        if is_new_fixture:
            log.info(
                "Fixture %s: %d eventos preexistentes marcados como publicados",
                fixture_id, len(new_keys),
            )
            return  # no publicar eventos viejos

        # Para cada evento nuevo, formatear y publicar.
        # Si es un gol, refrescar el fixture para tener marcador actualizado.
        refreshed_fixture = None
        for ev in events:
            key = event_key(ev)
            if key not in new_keys:
                continue  # ya estaba publicado antes

            # Si es un gol, refrescar el fixture la primera vez
            # para tener el marcador actualizado (la API a veces tarda).
            if ev.get("type") == "Goal" and ev.get("detail") != "Missed Penalty":
                if refreshed_fixture is None:
                    # Pequeña pausa para que la API actualice el marcador
                    time.sleep(2)
                    refreshed_fixture = self._refresh_fixture(fixture_id)
                    if refreshed_fixture:
                        # Usar el fixture refrescado para este y los siguientes
                        fixture = refreshed_fixture
                        log.debug("Fixture %s refrescado antes de publicar gol.", fixture_id)

            msg = self._format_event(ev, fixture)
            if msg is None:
                continue
            self._post(msg)

        # Si hubo algún gol, el fixture ya quedó refrescado arriba.
        if refreshed_fixture is not None:
            log.debug("Fixture %s: goles publicados con marcador actualizado.", fixture_id)

    # ------------------------------------------------------------------ #
    def _refresh_fixture(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        """
        Consulta fresca del fixture para tener el marcador más actualizado.
        Útil antes de publicar un gol (la API a veces tarda en reflejarlo).
        """
        try:
            return self.api.get_fixture(fixture_id)
        except APIFootballError as e:
            log.warning("get_fixture(%s) falló al refrescar: %s", fixture_id, e)
            return None

    # ------------------------------------------------------------------ #
    def _format_event(
        self, event: Dict[str, Any], fixture: Dict[str, Any]
    ) -> Optional[str]:
        """Devuelve el mensaje formateado o None si no nos interesa."""
        ev_type = (event.get("type") or "").strip()
        detail = (event.get("detail") or "").strip()

        # Detectar si estamos en tanda de penaltis:
        # - El status del partido es P o PEN, O
        # - El minuto del evento es >= 120 (después de prórroga)
        status_short = (fixture.get("fixture", {}).get("status", {}) or {}).get("short", "")
        event_minute = (event.get("time", {}) or {}).get("elapsed", 0) or 0
        in_penalty_shootout = (
            status_short in STATUS_PENALTIES
            or (event_minute >= 120 and ev_type == "Goal")
        )

        # En tanda de penaltis, los goles tipo "Penalty" o "Missed Penalty"
        # se formatean distinto (con marcador de la tanda acumulado)
        if in_penalty_shootout and ev_type == "Goal" and detail in {"Penalty", "Missed Penalty"}:
            return msg_penalty_shootout(event, fixture)

        # Gol normal (incluye penaltis convertidos en tiempo reglamentario,
        # autogoles; excluye penaltis fallados)
        if ev_type == "Goal":
            return msg_goal(event, fixture)

        # Tarjeta
        if ev_type == "Card":
            return msg_card(event, fixture)

        # Cambio
        if ev_type == "subst":
            return msg_substitution(event, fixture)

        # VAR
        if ev_type == "Var":
            return msg_var(event, fixture)

        # Penalti señalado
        if ev_type == "Var" and "penalt" in detail.lower():
            return msg_penalty_awarded(event, fixture)

        log.debug("Evento no manejado: type=%s detail=%s", ev_type, detail)
        return None

    # ------------------------------------------------------------------ #
    def _send_match_stats(self, fixture: Dict[str, Any], fixture_id: int) -> None:
        """
        Obtiene estadísticas y eventos finales del partido, y publica
        un mensaje de resumen completo.
        """
        fs = self.state.get(fixture_id)
        if fs.stats_announced:
            return  # ya enviamos las stats

        # Pequeña pausa para dar tiempo a la API a actualizar todas las stats
        time.sleep(3)

        # Obtener estadísticas
        try:
            statistics = self.api.get_statistics(fixture_id)
        except APIFootballError as e:
            log.warning("get_statistics(%s) falló: %s", fixture_id, e)
            statistics = []

        # Obtener eventos (goles, tarjetas, etc.)
        try:
            events = self.api.get_fixture_events(fixture_id)
        except APIFootballError as e:
            log.warning("get_fixture_events(%s) falló: %s", fixture_id, e)
            events = []

        if not statistics:
            log.info(
                "Fixture %s: no hay estadísticas disponibles, omitiendo resumen.",
                fixture_id,
            )
            self.state.update(fixture_id, lambda s: setattr(s, "stats_announced", True))
            return

        msg = msg_match_stats(fixture, statistics, events)
        self._post(msg)
        self.state.update(fixture_id, lambda s: setattr(s, "stats_announced", True))
        log.info("Resumen con stats publicado para fixture %s", fixture_id)

    # ------------------------------------------------------------------ #
    def _post(self, text: str) -> None:
        """Publica un mensaje en el canal de Telegram."""
        try:
            self.tg.send_message(text, parse_mode="HTML")
            log.info("Publicado: %s", text.split("\n", 1)[0][:80])
        except TelegramError as e:
            log.error("No se pudo publicar mensaje: %s", e)
            log.debug("Mensaje fallido:\n%s", text)


# ---------------------------------------------------------------------- #
# Entry point
# ---------------------------------------------------------------------- #
def main() -> None:
    try:
        bot = FootballBot()
    except ValueError as e:
        log.error(str(e))
        log.error("Copia .env.example a .env y completa los valores.")
        sys.exit(1)

    bot.run()


if __name__ == "__main__":
    main()
