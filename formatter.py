"""
Formateo de mensajes para Telegram.

Diseño de mensajes:
- Todas las notificaciones incluyen el BLOQUE DE MARCADOR completo
  (local + goles vs goles + visita), de modo que el lector sepa en todo
  momento cómo va el partido.
- Estructura visual en bloques separados por línea en blanco:
    ┌─ Encabezado (emoji + tipo de evento + minuto)
    ├─ Liga (bandera + nombre + jornada)
    ├─ Marcador (equipos con goles)
    └─ Detalle del evento (jugador, equipo, etc.)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import LEAGUE_NAMES, flag_for_country


# ---------------------------------------------------------------------- #
# Helpers internos
# ---------------------------------------------------------------------- #
def _esc(s) -> str:
    """Escapa caracteres HTML especiales. Acepta str, dict o None."""
    if s is None:
        return ""
    if isinstance(s, dict):
        # API-Football a veces devuelve {'id': N, 'name': '...'}
        s = s.get("name", "")
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _player_name(player) -> str:
    """
    Extrae el nombre del jugador de forma robusta.
    Siempre devuelve un string (nunca None o vacío).
    Si no hay nombre conocido, devuelve 'Jugador no identificado'.
    """
    if player is None:
        return "Jugador no identificado"
    if isinstance(player, dict):
        name = (player.get("name") or "").strip()
        if name:
            return _esc(name)
        # A veces el dict viene sin 'name' pero con 'id'
        if player.get("id"):
            return f"Jugador #{player.get('id')}"
        return "Jugador no identificado"
    if isinstance(player, str):
        name = player.strip()
        if name:
            return _esc(name)
        return "Jugador no identificado"
    return "Jugador no identificado"


def _team_name(team) -> str:
    """Extrae el nombre del equipo de forma robusta."""
    if team is None:
        return "?"
    if isinstance(team, dict):
        return _esc(team.get("name", "?")) or "?"
    return _esc(str(team))


def _goals_str(goals: Dict[str, Any], side: str) -> str:
    """Devuelve el número de goles de un lado como string ('0', '1', '2'...)."""
    if not goals:
        return "0"
    g = goals.get(side)
    return str(g) if g is not None else "0"


def _minute_str(event: Dict[str, Any]) -> str:
    """Devuelve '45'+3' o '72'' según el evento."""
    t = event.get("time", {}) or {}
    minute = t.get("elapsed", "?")
    extra = t.get("extra")
    if extra:
        return f"{minute}+{extra}'"
    return f"{minute}'"


def _translate_round(round_: str) -> str:
    """
    Traduce el nombre de la jornada/ronda de la API al español.
    Ejemplos:
      "Regular Season - 38" -> "J38"
      "2nd Qualifying Round" -> "2ª Ronda Clasificatoria"
      "Final" -> "Final"
      "Semi-finals" -> "Semifinales"
    """
    if not round_:
        return ""

    # Caso 1: "Regular Season - N" -> "JN"
    if "Regular Season" in round_:
        try:
            num = int(round_.split("-")[-1].strip())
            return f"J{num}"
        except (ValueError, IndexError):
            return "Temporada regular"

    # Caso 2: "Clausura - N" / "Apertura - N" / "Final Series - N"
    # (común en Sudamérica: Venezuela, Argentina, Colombia, etc.)
    for stage in ("Clausura", "Apertura", "Final Series", "Torneo Apertura",
                  "Torneo Clausura", "Primeira Liga"):
        if stage in round_:
            try:
                num = int(round_.split("-")[-1].strip())
                return f"{stage} J{num}"
            except (ValueError, IndexError):
                return stage

    # Diccionario de traducciones de rondas de copa
    round_translations = {
        # Qualifying rounds
        "1st Qualifying Round": "1ª Ronda Clasificatoria",
        "2nd Qualifying Round": "2ª Ronda Clasificatoria",
        "3rd Qualifying Round": "3ª Ronda Clasificatoria",
        "Qualifying Round": "Ronda Clasificatoria",
        "Play-off Round": "Ronda de Play-off",
        # Group stage
        "Group Stage": "Fase de Grupos",
        "Group 1": "Grupo 1",
        "Group 2": "Grupo 2",
        "Group 3": "Grupo 3",
        "Group 4": "Grupo 4",
        "Group 5": "Grupo 5",
        "Group 6": "Grupo 6",
        "Group 7": "Grupo 7",
        "Group 8": "Grupo 8",
        "Group A": "Grupo A",
        "Group B": "Grupo B",
        "Group C": "Grupo C",
        "Group D": "Grupo D",
        "Group E": "Grupo E",
        "Group F": "Grupo F",
        "Group G": "Grupo G",
        "Group H": "Grupo H",
        # Knockout
        "Round of 16": "Octavos de Final",
        "8th Finals": "Octavos de Final",
        "Quarter-finals": "Cuartos de Final",
        "Quarter-final": "Cuarto de Final",
        "Semi-finals": "Semifinales",
        "Semi-final": "Semifinal",
        "Final": "Final",
        # Repechaje / 3rd place
        "3rd Place Final": "Tercer Lugar",
        # League stages específicos
        "Promotion Group": "Grupo de Ascenso",
        "Relegation Group": "Grupo de Descenso",
        "Championship Round": "Ronda Campeonato",
        "Relegation Round": "Ronda de Descenso",
    }

    # Buscar traducción exacta
    if round_ in round_translations:
        return round_translations[round_]

    # Buscar traducción parcial (ej: "Quarter-finals - Leg 1")
    for eng, esp in round_translations.items():
        if eng in round_:
            # Manejar "Leg 1" / "Leg 2" -> "Ida" / "Vuelta"
            result = round_.replace(eng, esp)
            result = result.replace("Leg 1", "Ida")
            result = result.replace("Leg 2", "Vuelta")
            return result.strip(" -")

    # Si no hay traducción, devolver original escapado
    return round_


def _league_line(fixture: Dict[str, Any]) -> str:
    """
    Línea compacta de la liga:
      🇪🇸 La Liga · J38
      🏆 UEFA Champions League · Semifinal - Ida
    """
    league = fixture.get("league", {}) or {}
    lid = league.get("id")
    name = LEAGUE_NAMES.get(lid, league.get("name", "Liga"))
    country = league.get("country", "")
    flag = flag_for_country(country)
    round_ = league.get("round", "")

    round_translated = _translate_round(round_)
    round_short = f" · {_esc(round_translated)}" if round_translated else ""

    return f"{flag} <b>{_esc(name)}</b>{round_short}"


def _scoreboard_block(fixture: Dict[str, Any], highlight_team_id: Optional[int] = None) -> str:
    """
    Bloque de marcador destacado. Todo en <code> para que la alineación
    monoespaciada se respete en Telegram.

    Formato:

        🏠 Villarreal         2
           Atletico Madrid    1

    Si highlight_team_id está set, antepone ► al equipo que marcó/recibió
    la tarjeta / hizo el cambio.
    """
    teams = fixture.get("teams", {}) or {}
    home = teams.get("home", {}) or {}
    away = teams.get("away", {}) or {}
    goals = fixture.get("goals", {}) or {}

    home_name = home.get("name", "?")
    away_name = away.get("name", "?")
    home_g = _goals_str(goals, "home")
    away_g = _goals_str(goals, "away")

    # Marcador que marca el equipo protagonista del evento
    home_marker = "►" if highlight_team_id and home.get("id") == highlight_team_id else " "
    away_marker = "►" if highlight_team_id and away.get("id") == highlight_team_id else " "

    # Alinear nombres: usar el más largo como referencia
    max_len = max(len(home_name), len(away_name))
    home_padded = home_name.ljust(max_len)
    away_padded = away_name.ljust(max_len)

    # Escapar después de pad (ljust no añade caracteres HTML)
    home_esc = _esc(home_padded)
    away_esc = _esc(away_padded)

    # Construcción en monoespaciado para alineación perfecta
    # Usamos <code>...</code> en cada línea para que Telegram respete espacios
    return (
        f"<code>{home_marker}🏠 {home_esc}   {home_g}</code>\n"
        f"<code>{away_marker}   {away_esc}   {away_g}</code>"
    )


# Traducciones de status.long de la API
STATUS_LONG_TRANSLATIONS = {
    "Not Started": "Por empezar",
    "First Half": "Primera mitad",
    "Halftime": "Medio tiempo",
    "Second Half": "Segunda mitad",
    "Extra Time": "Prórroga",
    "Penalty Shootout": "Tanda de penaltis",
    "Match Finished": "Partido finalizado",
    "Match Finished After Extra Time": "Finalizado tras prórroga",
    "Match Finished After Penalty": "Finalizado tras penaltis",
    "Match Suspended": "Partido suspendido",
    "Match Interrupted": "Partido interrumpido",
    "Match Postponed": "Partido aplazado",
    "Match Cancelled": "Partido cancelado",
    "Match Abandoned": "Partido abandonado",
    "To Be Defined": "Por definir",
}


def _translate_status_long(s: str) -> str:
    """Traduce el status.long de la API al español."""
    if not s:
        return ""
    return STATUS_LONG_TRANSLATIONS.get(s, s)


def _status_pill(fixture: Dict[str, Any]) -> str:
    """Devuelve una etiqueta de estado del partido: EN VIVO / FINAL / HT / 2H..."""
    status = fixture.get("fixture", {}).get("status", {}) or {}
    short = status.get("short", "")
    elapsed = status.get("elapsed")

    if short in {"1H", "2H", "LIVE"}:
        minute = elapsed if elapsed else "?"
        return f"🔴 EN VIVO · {minute}'"
    if short == "HT":
        return "⏸️ MEDIO TIEMPO"
    if short == "ET":
        return f"🟠 PRÓRROGA · {elapsed}'"
    if short == "P":
        return "🥅 PENALTIS"
    if short in {"FT", "FIN", "AET", "PEN"}:
        if short == "AET":
            return "✅ FINAL · PRÓRROGA"
        if short == "PEN":
            return "✅ FINAL · PENALTIS"
        return "✅ FINAL"
    if short == "NS":
        return "⏳ POR EMPEZAR"
    if short in {"PST", "CANC", "ABD"}:
        return "⚠️ SUSPENDIDO"
    return f"· {short}"


# ---------------------------------------------------------------------- #
# Mensajes por tipo de evento
# ---------------------------------------------------------------------- #
def msg_match_started(fixture: Dict[str, Any]) -> str:
    """Mensaje de inicio de partido."""
    league_line = _league_line(fixture)
    scoreboard = _scoreboard_block(fixture)

    venue = (fixture.get("fixture", {}) or {}).get("venue", {}) or {}
    venue_name = venue.get("name", "")
    venue_city = venue.get("city", "")
    venue_parts = [p for p in [venue_name, venue_city] if p]
    venue_str = f"\n📍 {_esc(' · '.join(venue_parts))}" if venue_parts else ""

    return (
        f"🟢 <b>¡COMIENZA EL PARTIDO!</b>\n"
        f"\n"
        f"{league_line}\n"
        f"\n"
        f"{scoreboard}\n"
        f"\n"
        f"<i>🔴 EN VIVO · 1'</i>{venue_str}"
    )


def msg_match_finished(fixture: Dict[str, Any]) -> str:
    """Mensaje de fin de partido con resultado final."""
    league_line = _league_line(fixture)
    scoreboard = _scoreboard_block(fixture)
    status = _status_pill(fixture)

    status_extra = _translate_status_long(
        (fixture.get("fixture", {}).get("status", {}) or {}).get("long", "")
    )

    return (
        f"🔴 <b>FINAL DEL PARTIDO</b>\n"
        f"\n"
        f"{league_line}\n"
        f"\n"
        f"{scoreboard}\n"
        f"\n"
        f"<i>{status}</i>\n"
        f"<i>{_esc(status_extra)}</i>"
    )


def msg_halftime(fixture: Dict[str, Any]) -> str:
    """Mensaje de medio tiempo."""
    league_line = _league_line(fixture)
    scoreboard = _scoreboard_block(fixture)

    return (
        f"⏸️ <b>MEDIO TIEMPO</b>\n"
        f"\n"
        f"{league_line}\n"
        f"\n"
        f"{scoreboard}\n"
        f"\n"
        f"<i>Descanso. Vuelven pronto para la segunda mitad.</i>"
    )


def msg_second_half(fixture: Dict[str, Any]) -> str:
    """Arranque segunda mitad."""
    league_line = _league_line(fixture)
    scoreboard = _scoreboard_block(fixture)

    return (
        f"▶️ <b>ARRANCA LA SEGUNDA MITAD</b>\n"
        f"\n"
        f"{league_line}\n"
        f"\n"
        f"{scoreboard}\n"
        f"\n"
        f"<i>¡Vuelve el juego!</i>"
    )


def msg_goal(event: Dict[str, Any], fixture: Dict[str, Any]) -> str:
    """
    Mensaje de gol. Ejemplo:

        ⚽ ¡GOOOOL! · 34'

        🇪🇸 La Liga · J38

          🏠 Villarreal      2
            Atletico Madrid  1

        👤 A. Pérez
        🎯 Villarreal (Local)
        🅰️ Asistencia: N. Pepe
    """
    league_line = _league_line(fixture)

    # Equipo que marca
    scoring_team = event.get("team", {}) or {}
    scoring_team_id = scoring_team.get("id")
    scoring_team_name = _team_name(scoring_team)

    # ¿Es local o visitante?
    home = (fixture.get("teams", {}) or {}).get("home", {}) or {}
    is_home = scoring_team_id == home.get("id")
    side_label = "🏠 Local" if is_home else "✈️ Visitante"

    # Marcador con el equipo que marca resaltado
    scoreboard = _scoreboard_block(fixture, highlight_team_id=scoring_team_id)

    # Jugador
    player = event.get("player")
    player_name = _player_name(player)

    # Asistencia
    assist = event.get("assist")
    assist_name_str = ""
    if isinstance(assist, dict):
        assist_name_str = (assist.get("name") or "").strip()
    elif isinstance(assist, str):
        assist_name_str = assist.strip()
    assist_line = f"\n🅰️ Asistencia: {_esc(assist_name_str)}" if assist_name_str else ""

    # Tipo de gol
    detail_type = event.get("detail", "Normal Goal")
    goal_emoji = "⚽"
    goal_label = "¡GOOOOL!"
    if detail_type == "Own Goal":
        goal_emoji = "🥅"
        goal_label = "GOL EN CONTRA"
    elif detail_type == "Penalty":
        goal_emoji = "🎯"
        goal_label = "GOL DE PENALTI"
    elif detail_type == "Missed Penalty":
        goal_emoji = "❌"
        goal_label = "¡PENALTI FALLADO!"

    minute = _minute_str(event)

    return (
        f"{goal_emoji} <b>{goal_label}</b> · {minute}\n"
        f"\n"
        f"{league_line}\n"
        f"\n"
        f"{scoreboard}\n"
        f"\n"
        f"👤 {player_name}\n"
        f"🎯 {scoring_team_name} ({side_label}){assist_line}"
    )


def msg_card(event: Dict[str, Any], fixture: Dict[str, Any]) -> str:
    """Mensaje de tarjeta (amarilla / roja)."""
    league_line = _league_line(fixture)

    team = (event.get("team", {}) or {})
    team_id = team.get("id")
    team_name = _team_name(team)

    scoreboard = _scoreboard_block(fixture, highlight_team_id=team_id)
    player = event.get("player")
    player_name = _player_name(player)
    minute = _minute_str(event)
    detail = event.get("detail", "")

    if detail == "Yellow Card":
        emoji = "🟨"
        label = "TARJETA AMARILLA"
    elif detail == "Red Card":
        emoji = "🟥"
        label = "TARJETA ROJA"
    elif detail == "Second Yellow card":
        emoji = "🟨➡️🟥"
        label = "SEGUNDA AMARILLA → ROJA"
    else:
        emoji = "🃏"
        label = _esc(detail) or "TARJETA"

    return (
        f"{emoji} <b>{label}</b> · {minute}\n"
        f"\n"
        f"{league_line}\n"
        f"\n"
        f"{scoreboard}\n"
        f"\n"
        f"👤 {player_name}\n"
        f"🎯 {team_name}"
    )


def msg_substitution(event: Dict[str, Any], fixture: Dict[str, Any]) -> str:
    """Mensaje de cambio."""
    league_line = _league_line(fixture)

    team = (event.get("team", {}) or {})
    team_id = team.get("id")
    team_name = _team_name(team)

    scoreboard = _scoreboard_block(fixture, highlight_team_id=team_id)

    # API-Football en eventos 'subst':
    #   - 'player' = jugador que SALE (titular que abandona el campo)
    #   - 'assist' = jugador que ENTRA (suplente que ingresa)
    # (Confirmado con datos reales de Villarreal vs Atletico 5-1, fixture 1391198)
    out = event.get("player")    # quien sale
    out_name = _player_name(out)
    inn = event.get("assist")    # quien entra
    inn_name = _player_name(inn)
    minute = _minute_str(event)

    return (
        f"🔄 <b>CAMBIO</b> · {minute}\n"
        f"\n"
        f"{league_line}\n"
        f"\n"
        f"{scoreboard}\n"
        f"\n"
        f"⬆️ Entra: <b>{inn_name}</b>\n"
        f"⬇️ Sale: {out_name}\n"
        f"🎯 {team_name}"
    )


def msg_var(event: Dict[str, Any], fixture: Dict[str, Any]) -> str:
    """Mensaje de evento VAR."""
    league_line = _league_line(fixture)
    scoreboard = _scoreboard_block(fixture)
    minute = _minute_str(event)
    detail = event.get("detail", "Revisión VAR")

    # En VAR el jugador puede no estar identificado, pero igual lo mostramos
    player = event.get("player")
    player_name = _player_name(player)
    player_line = f"\n👤 {player_name}"

    return (
        f"📺 <b>VAR</b> · {minute}\n"
        f"\n"
        f"{league_line}\n"
        f"\n"
        f"{scoreboard}\n"
        f"\n"
        f"⚖️ {_esc(detail)}{player_line}"
    )


def msg_penalty_awarded(event: Dict[str, Any], fixture: Dict[str, Any]) -> str:
    """Penalti señalado (antes de saber si es gol)."""
    league_line = _league_line(fixture)
    team = (event.get("team", {}) or {})
    team_id = team.get("id")
    team_name = _team_name(team)
    scoreboard = _scoreboard_block(fixture, highlight_team_id=team_id)
    minute = _minute_str(event)

    return (
        f"🎯 <b>PENALTI SEÑALADO</b> · {minute}\n"
        f"\n"
        f"{league_line}\n"
        f"\n"
        f"{scoreboard}\n"
        f"\n"
        f"🎯 {team_name} ejecutará el penalti"
    )


def msg_penalty_shootout(event: Dict[str, Any], fixture: Dict[str, Any]) -> str:
    """
    Mensaje para un lanzamiento de la tanda de penaltis.
    Muestra el marcador ACUMULADO de la tanda (de fixture.score.penalty).
    """
    league_line = _league_line(fixture)
    minute = _minute_str(event)

    # Equipo que lanza
    team = (event.get("team") or {})
    team_id = team.get("id")
    team_name = _team_name(team)
    teams = (fixture.get("teams") or {})
    home = (teams.get("home") or {})
    away = (teams.get("away") or {})
    is_home = team_id == home.get("id")
    side_label = "🏠 Local" if is_home else "✈️ Visitante"

    # Marcador del partido (tiempo reglamentario + prórroga)
    scoreboard = _scoreboard_block(fixture, highlight_team_id=team_id)

    # Marcador de la tanda de penaltis (de fixture.score.penalty)
    score_data = (fixture.get("score") or {})
    pen_score = (score_data.get("penalty") or {})
    pen_home = pen_score.get("home")
    pen_away = pen_score.get("away")

    # Construir marcador de penaltis solo si hay datos
    penalty_block = ""
    if pen_home is not None and pen_away is not None:
        home_short = home.get("name", "?")[:14]
        away_short = away.get("name", "?")[:14]
        penalty_block = (
            f"\n"
            f"<code>─────────────────────────</code>\n"
            f"<code>🎯 Tanda: {home_short:<14} {pen_home} - {pen_away} {away_short:<14}</code>"
        )

    # Jugador
    player = event.get("player")
    player_name = _player_name(player)

    # Tipo de lanzamiento
    detail_type = event.get("detail", "")
    if detail_type == "Missed Penalty":
        emoji = "❌"
        label = "PENALTI FALLADO"
        result_line = f"💥 {player_name} falló su lanzamiento"
    else:
        # Penalty convertido
        emoji = "✅"
        label = "PENALTI CONVERTIDO"
        result_line = f"⚽ {player_name} anotó"

    return (
        f"{emoji} <b>{label}</b> · {minute}\n"
        f"\n"
        f"{league_line}\n"
        f"\n"
        f"{scoreboard}"
        f"{penalty_block}\n"
        f"\n"
        f"{result_line}\n"
        f"🎯 {team_name} ({side_label})"
    )


# ---------------------------------------------------------------------- #
# Alineaciones y estadísticas
# ---------------------------------------------------------------------- #
def _format_lineup_team(team_data: Dict[str, Any]) -> str:
    """
    Formatea la alineación de un equipo en bloques por línea de la formación.
    Ejemplo:

        🏠 Villarreal (4-4-2) · DT: Marcelino

        🧤 A. Tenas
        🛡️ S. Mourino  P. Navarro  ...
        🎯 A. Pérez  G. Mikautadze
    """
    team = (team_data.get("team") or {})
    team_name = _esc(team.get("name", "?"))
    formation = team_data.get("formation") or "?"
    coach = (team_data.get("coach") or {}).get("name", "")
    coach_str = f" · DT: {_esc(coach)}" if coach else ""

    # Colores del equipo (opcional, para info)
    colors = team.get("colors") or {}

    starters = team_data.get("startXI") or []
    subs = team_data.get("substitutes") or []

    lines = []
    lines.append(f"<b>{team_name}</b> ({_esc(formation)}){coach_str}")
    lines.append("")

    # Organizar titulares por su posición en el grid
    # El grid viene como "fila:columna", ej: "1:1", "2:4"
    rows = {}
    for entry in starters:
        p = (entry or {}).get("player") or {}
        grid = p.get("grid") or "0:0"
        try:
            row_num = int(grid.split(":")[0])
        except (ValueError, IndexError):
            row_num = 0
        rows.setdefault(row_num, []).append(p)

    # Iconos por fila: 1 = portero, 2+ = jugadores de campo
    row_labels = {1: "🧤", 2: "🛡️", 3: "🛡️", 4: "🛡️", 5: "🎯"}
    for row_num in sorted(rows.keys()):
        players = rows[row_num]
        emoji = row_labels.get(row_num, "⚽")
        names = "  ".join(_esc(p.get("name", "?")) for p in players)
        lines.append(f"{emoji} {names}")

    # Algunos suplentes (primeros 5)
    if subs:
        sub_names = ", ".join(_esc((s or {}).get("player", {}).get("name", "?")) for s in subs[:5])
        lines.append("")
        lines.append(f"📋 Banquillo: {sub_names}")

    return "\n".join(lines)


def msg_lineups(fixture: Dict[str, Any], lineups: List[Dict[str, Any]]) -> str:
    """
    Mensaje con las alineaciones oficiales de ambos equipos.

    Formato:
        📋 ALINEACIONES OFICIALES

        🇪🇸 La Liga · J38

        🏠 Villarreal (4-4-2) · DT: Marcelino

        🧤 A. Tenas
        🛡️ S. Mourino  P. Navarro  ...
        🎯 A. Pérez  G. Mikautadze

        ✈️ Atletico Madrid (4-3-3) · DT: Simeone

        🧤 Oblak
        🛡️ ...
        🎯 ...
    """
    league_line = _league_line(fixture)

    # Identificar cuál es local y cuál visitante
    teams = (fixture.get("teams") or {})
    home = (teams.get("home") or {})
    away = (teams.get("away") or {})
    home_id = home.get("id")
    away_id = away.get("id")

    home_lineup = None
    away_lineup = None
    for lu in lineups:
        team = (lu.get("team") or {})
        if team.get("id") == home_id:
            home_lineup = lu
        elif team.get("id") == away_id:
            away_lineup = lu

    # Si no se pudo distinguir, tomar en orden
    if not home_lineup and lineups:
        home_lineup = lineups[0]
    if not away_lineup and len(lineups) > 1:
        away_lineup = lineups[1]

    parts = [
        "📋 <b>ALINEACIONES OFICIALES</b>",
        "",
        league_line,
        "",
    ]

    if home_lineup:
        parts.append(f"🏠 {_format_lineup_team(home_lineup)}")
        parts.append("")

    if away_lineup:
        parts.append(f"✈️ {_format_lineup_team(away_lineup)}")

    return "\n".join(parts)


def _stat_value(stat: Dict[str, Any]) -> str:
    """Devuelve el valor de una stat como string, manejando None."""
    v = stat.get("value")
    if v is None:
        return "-"
    return str(v)


def _stats_row(label: str, home_val: str, away_val: str) -> str:
    """
    Formatea una fila de stats alineada. Ejemplo:

        Posesión (%)       48    52
    """
    # Padding para alinear el label
    label_padded = label.ljust(18)
    # Padding para los valores
    home_padded = home_val.rjust(5)
    away_padded = away_val.ljust(5)
    return f"<code>{label_padded}{home_padded}  -  {away_padded}</code>"


def msg_match_stats(
    fixture: Dict[str, Any],
    statistics: List[Dict[str, Any]],
    events: List[Dict[str, Any]] = None,
) -> str:
    """
    Mensaje de resumen final con estadísticas completas.

    Formato:
        📊 RESUMEN DEL PARTIDO

        🇪🇸 La Liga · J38

         🏠 Villarreal        5
            Atletico Madrid   1

        📈 ESTADÍSTICAS
        Posesión (%)       48    52
        Tiros totales      14    9
        Tiros a puerta      8    4
        Córners             5    9
        Faltas              3   12
        Tarjetas 🟨         0    1
        xG               2.48  1.16
        Pases %           86%   88%

        ⚽ GOLES
        30' 🎯 D. Parejo (pen) — Villarreal
        34' ⚽ A. Pérez — Villarreal
        ...
    """
    league_line = _league_line(fixture)
    scoreboard = _scoreboard_block(fixture)

    parts = [
        "📊 <b>RESUMEN DEL PARTIDO</b>",
        "",
        league_line,
        "",
        scoreboard,
        "",
        "📈 <b>ESTADÍSTICAS</b>",
        "",
    ]

    # Las stats vienen como:
    # [{"team": {...}, "statistics": [{"type": "Ball Possession", "value": "48%"}, ...]}, ...]
    home_stats = {}
    away_stats = {}
    teams = (fixture.get("teams") or {})
    home_id = (teams.get("home") or {}).get("id")
    away_id = (teams.get("away") or {}).get("id")

    for team_stats in statistics:
        team = (team_stats.get("team") or {})
        if team.get("id") == home_id:
            for s in (team_stats.get("statistics") or []):
                home_stats[s.get("type")] = _stat_value(s)
        elif team.get("id") == away_id:
            for s in (team_stats.get("statistics") or []):
                away_stats[s.get("type")] = _stat_value(s)

    # Si no se pudieron mapear por ID, asumir orden [home, away]
    if not home_stats and statistics:
        for s in (statistics[0].get("statistics") or []):
            home_stats[s.get("type")] = _stat_value(s)
    if not away_stats and len(statistics) > 1:
        for s in (statistics[1].get("statistics") or []):
            away_stats[s.get("type")] = _stat_value(s)

    # Lista de stats a mostrar (label amigable, tipo API)
    stats_to_show = [
        ("Posesión (%)",       "Ball Possession"),
        ("Tiros totales",      "Total Shots"),
        ("Tiros a puerta",     "Shots on Goal"),
        ("Tiros fuera",        "Shots off Goal"),
        ("Córners",            "Corner Kicks"),
        ("Faltas",             "Fouls"),
        ("Tarjetas 🟨",        "Yellow Cards"),
        ("Tarjetas 🟥",        "Red Cards"),
        ("Fueras de juego",    "Offsides"),
        ("Atajadas archero",   "Goalkeeper Saves"),
        ("Pases correctos %",  "Passes %"),
        ("xG (goles esper.)",  "expected_goals"),
    ]

    for label, stat_type in stats_to_show:
        home_val = home_stats.get(stat_type, "-")
        away_val = away_stats.get(stat_type, "-")
        parts.append(_stats_row(label, home_val, away_val))

    # Listar goles si tenemos eventos
    if events:
        goals = [e for e in events if e.get("type") == "Goal"]
        # Filtrar goles válidos (omitir Missed Penalty)
        goals = [g for g in goals if g.get("detail") != "Missed Penalty"]
        if goals:
            parts.append("")
            parts.append("⚽ <b>GOLES</b>")
            for g in goals:
                minute = _minute_str(g)
                player = _esc(g.get("player", ""))
                detail = g.get("detail", "Normal Goal")
                team_name = _esc((g.get("team") or {}).get("name", "?"))

                if detail == "Penalty":
                    icon = "🎯"
                    detail_str = " (pen)"
                elif detail == "Own Goal":
                    icon = "🥅"
                    detail_str = " (autogol)"
                else:
                    icon = "⚽"
                    detail_str = ""

                parts.append(f"<code>{minute:>5}</code>  {icon} {player}{detail_str} — {team_name}")

    return "\n".join(parts)
