"""
Test con un partido histórico real (Villarreal 5-1 Atletico Madrid, fixture 1391198).
Verifica que todos los mensajes se formatean correctamente.
NO publica a Telegram.
"""
import logging
import sys

from api_client import APIFootballClient, APIFootballError
from config import config
from formatter import (
    msg_card, msg_goal, msg_halftime, msg_match_finished, msg_match_started,
    msg_second_half, msg_substitution, msg_var,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("historical_test")

FIXTURE_ID = 1391198  # Villarreal 5-1 Atletico Madrid


def main() -> int:
    api = APIFootballClient(config)

    try:
        fixture = api.get_fixture(FIXTURE_ID)
    except APIFootballError as e:
        log.error("Error obteniendo fixture: %s", e)
        return 1

    if not fixture:
        log.error("Fixture %s no encontrado", FIXTURE_ID)
        return 1

    log.info("Fixture: %s vs %s", 
             fixture['teams']['home']['name'],
             fixture['teams']['away']['name'])

    # Mostrar todos los tipos de mensaje de estado
    print("\n" + "█" * 70)
    print("MENSAJE INICIO PARTIDO:")
    print("█" * 70)
    print(msg_match_started(fixture))

    print("\n" + "█" * 70)
    print("MENSAJE MEDIO TIEMPO:")
    print("█" * 70)
    print(msg_halftime(fixture))

    print("\n" + "█" * 70)
    print("MENSAJE SEGUNDA MITAD:")
    print("█" * 70)
    print(msg_second_half(fixture))

    print("\n" + "█" * 70)
    print("MENSAJE FIN PARTIDO:")
    print("█" * 70)
    print(msg_match_finished(fixture))

    # Obtener eventos y formatear
    try:
        events = api.get_fixture_events(FIXTURE_ID)
    except APIFootballError as e:
        log.error("Error obteniendo eventos: %s", e)
        return 1

    log.info("Eventos: %d", len(events))

    # Mostrar cada tipo de evento al menos una vez
    seen_types = set()
    for ev in events:
        t = ev.get("type", "") + "|" + ev.get("detail", "")
        if t in seen_types:
            continue
        seen_types.add(t)

        print("\n" + "█" * 70)
        print(f"EVENTO: type={ev.get('type')} detail={ev.get('detail')}")
        print("█" * 70)

        try:
            if ev.get("type") == "Goal":
                print(msg_goal(ev, fixture))
            elif ev.get("type") == "Card":
                print(msg_card(ev, fixture))
            elif ev.get("type") == "subst":
                print(msg_substitution(ev, fixture))
            elif ev.get("type") == "Var":
                print(msg_var(ev, fixture))
            else:
                print(f"(tipo no manejado: {ev.get('type')})")
        except Exception as e:
            log.error("Error formateando evento: %s", e)
            import traceback
            traceback.print_exc()

    print("\n" + "█" * 70)
    print(f"Tipos únicos procesados: {len(seen_types)}")
    print("█" * 70)
    for t in sorted(seen_types):
        print(f"  - {t}")

    log.info("=== Test histórico OK ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
