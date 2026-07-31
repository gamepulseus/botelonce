"""
Configuración global del bot.
Carga variables desde el entorno (o archivo .env) y define constantes.
"""
import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

# Carga .env si existe (no falla si no está)
load_dotenv()


def _parse_int_list(raw: str) -> List[int]:
    """Convierte '39,140,135' -> [39, 140, 135]."""
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


@dataclass
class Config:
    # API-Football
    api_key: str = field(default_factory=lambda: os.getenv("API_FOOTBALL_KEY", ""))
    api_url: str = field(
        default_factory=lambda: os.getenv(
            "API_FOOTBALL_URL", "https://v3.football.api-sports.io"
        )
    )

    # Telegram
    tg_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    tg_channel: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_CHANNEL", "")
    )

    # Comportamiento
    poll_interval: int = field(
        default_factory=lambda: int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
    )
    leagues: List[int] = field(
        default_factory=lambda: _parse_int_list(
            os.getenv("LEAGUES", "39,140,135,78,61")
        )
    )
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "UTC"))
    language: str = field(default_factory=lambda: os.getenv("LANGUAGE", "es"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    state_file: str = field(
        default_factory=lambda: os.getenv("STATE_FILE", "state.json")
    )

    def validate(self) -> None:
        """Lanza ValueError si falta configuración crítica."""
        errors = []
        if not self.api_key:
            errors.append("API_FOOTBALL_KEY no configurado")
        if not self.tg_token:
            errors.append("TELEGRAM_BOT_TOKEN no configurado")
        if not self.tg_channel:
            errors.append("TELEGRAM_CHANNEL no configurado")
        if not self.leagues:
            errors.append("LEAGUES vacío")
        if errors:
            raise ValueError(
                "Configuración incompleta. Revisa tu archivo .env:\n  - "
                + "\n  - ".join(errors)
            )


# Diccionario de ligas soportadas (para mostrar nombre bonito)
LEAGUE_NAMES = {
    # Top 5 Europa
    39: "Premier League",
    140: "La Liga",
    135: "Serie A",
    78: "Bundesliga",
    61: "Ligue 1",
    # Competiciones UEFA de clubes
    2: "UEFA Champions League",
    3: "UEFA Europa League",
    848: "UEFA Conference League",
    # Competiciones de selecciones
    4: "Eurocopa",
    5: "UEFA Nations League",
    # Copas nacionales
    7: "FA Cup",
    # Conmebol
    13: "Copa Libertadores",
    11: "Copa Sudamericana",
    # Sudamérica domésticas
    71: "Brasileirão",
    128: "Primera División Argentina",
    299: "Primera División Venezuela",
    # Otras
    253: "MLS",
    262: "Liga MX",
}

# Banderas aproximadas por país (para emojis)
COUNTRY_FLAGS = {
    "England": "🏴",  # bandera Inglaterra (no es ISO, emoji compuesto)
    "Spain": "🇪🇸",
    "Italy": "🇮🇹",
    "Germany": "🇩🇪",
    "France": "🇫🇷",
    "Portugal": "🇵🇹",
    "Netherlands": "🇳🇱",
    "Brazil": "🇧🇷",
    "Argentina": "🇦🇷",
    "Colombia": "🇨🇴",
    "Mexico": "🇲🇽",
    "USA": "🇺🇸",
    "Uruguay": "🇺🇾",
    "Chile": "🇨🇱",
    "Peru": "🇵🇪",
    "Ecuador": "🇪🇨",
    "Paraguay": "🇵🇾",
    "Bolivia": "🇧🇴",
    "Venezuela": "🇻🇪",
    "Europe": "🇪🇺",
    "Conmebol": "🌎",
    "World": "🌍",
    "Brazil": "🇧🇷",
}


def flag_for_country(country: str) -> str:
    """Devuelve el emoji de bandera para un país dado, o vacío si no hay."""
    if not country:
        return ""
    return COUNTRY_FLAGS.get(country, "🌐")


# Instancia global
config = Config()
