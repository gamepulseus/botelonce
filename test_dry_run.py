"""
Smoke test del bot: comprueba API + formateo SIN publicar a Telegram.

Uso:
    python test_dry_run.py

Lo que hace:
1. Verifica estado de cuenta API-Football.
2. Lista fixtures en vivo (filtrados por LEAGUES).
3. Para cada fixture en vivo, descarga eventos y muestra los mensajes
   formateados en consola (NO los envía a Telegram).
4. Si no hay partidos en vivo, lista los partidos del día.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from api_client import APIFootballClient, APIFootballError
from config import config, LEAGUE_NAMES
from formatter import (
    msg_card, msg_goal, msg_halftime, msg_match_finished, msg_match_started,
    msg_penalty_awarded, msg_second_half, msg_substitution, msg_var,
)
from state import StateStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("test")


def show(msg: str) -> None:
    print("\n" + "=" * 60)
    print(msg)
    print("=" * 60)


def main() -> int:
    log.info("=== Smoke test (dry-run) ===")

    # No requiere Telegram ni validación completa; forzamos dummy si falta
    if not config.api_key:
        log.error("API_FOOTBALL_KEY no configurado")
        return 1

    api = APIFootballClient(config)

    # 1) Estado de cuenta
    try:
        status = api.get_account_status()
        s = status.get("subscription", {})
        r = status.get("requests", {})
        log.info(
            "Cuenta: plan=%s activo=%s | requests hoy: %s / %s",
            s.get("plan"), s.get("active"), r.get("current"), r.get("limit_day"),
        )
    except APIFootballError as e:
        log.error("Error obteniendo status: %s", e)
        return 1

    # 2) Live fixtures
    log.info("Consultando partidos en vivo (ligas: %s)...", config.leagues)
    try:
        live = api.get_live_fixtures(config.leagues)
    except APIFootballError as e:
        log.error("Error en get_live_fixtures: %s", e)
        live = []

    log.info("Partidos en vivo: %d", len(live))

    if not live:
        log.info("No hay partidos en vivo. Probando con partidos del día...")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            today_fixtures = api.get_fixtures_by_date(today, config.leagues)
        except APIFootballError as e:
            log.error("Error en get_fixtures_by_date: %s", e)
            return 1

        log.info("Partidos hoy (UTC): %d", len(today_fixtures))
        for fx in today_fixtures[:5]:
            fid = fx.get("fixture", {}).get("id")
            league = fx.get("league", {})
            teams = fx.get("teams", {})
            status_short = fx.get("fixture", {}).get("status", {}).get("short", "")
            log.info(
                "  #%s [%s] %s vs %s — status=%s",
                fid,
                LEAGUE_NAMES.get(league.get("id"), league.get("name", "?")),
                teams.get("home", {}).get("name"),
                teams.get("away", {}).get("name"),
                status_short,
            )
        # Tomar el primero para probar formateo aunque no esté en vivo
        if today_fixtures:
            sample = today_fixtures[0]
            show(msg_match_started(sample))
            show(msg_match_finished(sample))
            show(msg_halftime(sample))
            show(msg_second_half(sample))
        return 0

    # 3) Para cada partido en vivo, mostrar eventos
    for fx in live[:3]:  # limitamos a 3 para no saturar la cuota
        fid = fx["fixture"]["id"]
        league = fx.get("league", {})
        teams = fx.get("teams", {})
        log.info(
            "Procesando fixture #%s [%s] %s vs %s (status=%s)",
            fid,
            LEAGUE_NAMES.get(league.get("id"), league.get("name", "?")),
            teams.get("home", {}).get("name"),
            teams.get("away", {}).get("name"),
            fx.get("fixture", {}).get("status", {}).get("short", ""),
        )

        try:
            events = api.get_fixture_events(fid)
        except APIFootballError as e:
            log.warning("  No se pudieron obtener eventos: %s", e)
            continue

        log.info("  Eventos: %d", len(events))

        # Mostrar ejemplo de cada tipo de evento
        seen_types = set()
        for ev in events:
            t = (ev.get("type") or "") + "|" + (ev.get("detail") or "")
            if t in seen_types:
                continue
            seen_types.add(t)

            try:
                if ev.get("type") == "Goal":
                    show(msg_goal(ev, fx))
                elif ev.get("type") == "Card":
                    show(msg_card(ev, fx))
                elif ev.get("type") == "subst":
                    show(msg_substitution(ev, fx))
                elif ev.get("type") == "Var":
                    show(msg_var(ev, fx))
            except Exception as e:
                log.error("  Error formateando evento %s: %s", t, e)

        # Mostrar siempre también los mensajes de estado
        show(msg_match_started(fx))
        show(msg_halftime(fx))
        show(msg_second_half(fx))
        show(msg_match_finished(fx))

    log.info("=== Smoke test OK ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
