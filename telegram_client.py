"""
Cliente de Telegram.

Publica mensajes en el canal configurado usando la Bot API oficial.
Soporta MarkdownV2 y HTML.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

log = logging.getLogger(__name__)


class TelegramError(Exception):
    pass


class TelegramClient:
    """Cliente mínimo de la Bot API de Telegram."""

    BASE = "https://api.telegram.org"

    def __init__(self, token: str, channel: str):
        if not token:
            raise TelegramError("TELEGRAM_BOT_TOKEN vacío")
        if not channel:
            raise TelegramError("TELEGRAM_CHANNEL vacío")
        self.token = token.strip()
        self.channel = channel.strip()
        self.session = requests.Session()

    # ------------------------------------------------------------------ #
    def _call(self, method: str, payload: dict, retries: int = 3) -> dict:
        url = f"{self.BASE}/bot{self.token}/{method}"
        last_err = None
        for attempt in range(retries):
            try:
                r = self.session.post(url, json=payload, timeout=15)
            except requests.RequestException as e:
                last_err = e
                time.sleep(2 ** attempt)
                continue

            if r.status_code == 429:
                # Telegram rate-limit: respetar retry_after
                try:
                    retry_after = r.json().get("parameters", {}).get("retry_after", 5)
                except ValueError:
                    retry_after = 5
                log.warning("Telegram 429: esperando %ss", retry_after)
                time.sleep(retry_after + 1)
                continue

            try:
                data = r.json()
            except ValueError:
                last_err = TelegramError(f"Respuesta no JSON: {r.text[:200]}")
                time.sleep(2 ** attempt)
                continue

            if not data.get("ok"):
                last_err = TelegramError(
                    f"Telegram error: {data.get('description')} (code {data.get('error_code')})"
                )
                # 400 = mensaje mal formateado; no reintentar
                if r.status_code == 400:
                    raise last_err
                time.sleep(2 ** attempt)
                continue

            return data["result"]

        raise last_err or TelegramError("Fallo desconocido llamando a Telegram")

    # ------------------------------------------------------------------ #
    def send_message(self, text: str, parse_mode: str = "HTML") -> dict:
        """Envía un mensaje de texto al canal."""
        payload = {
            "chat_id": self.channel,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        return self._call("sendMessage", payload)

    def test_connection(self) -> bool:
        """Verifica que el bot exista y pueda escribir al canal."""
        try:
            me = self._call("getMe", {})
            log.info("Bot conectado: @%s (%s)", me.get("username"), me.get("first_name"))
        except Exception as e:
            log.error("getMe falló: %s", e)
            return False

        try:
            self.send_message(
                "✅ <b>Bot de fútbol en línea</b>\n\n"
                "El bot se ha iniciado correctamente y publicará "
                "eventos en vivo aquí.",
            )
            return True
        except TelegramError as e:
            log.error(
                "No se pudo escribir al canal %s: %s\n"
                "Asegúrate de que el bot sea administrador del canal.",
                self.channel, e,
            )
            return False
