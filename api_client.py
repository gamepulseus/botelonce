"""
Cliente de la API-Football v3.

Encapsula las llamadas HTTP y normaliza la respuesta.
Documentación: https://www.api-football.com/documentation-v3
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import requests

from config import Config

log = logging.getLogger(__name__)


class APIFootballError(Exception):
    """Error devuelto por la API-Football."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class APIFootballClient:
    """Cliente HTTP para los endpoints /fixtures y /fixtures/events."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.base_url = cfg.api_url.rstrip("/")
        self.headers = {"x-apisports-key": cfg.api_key}
        self.timeout = 15
        # Rate-limit suave local: no más de una llamada cada 0.6s
        self._min_interval = 0.6
        self._last_call_ts = 0.0
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    # ------------------------------------------------------------------ #
    # Núcleo
    # ------------------------------------------------------------------ #
    def _get(self, endpoint: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """GET genérico. Devuelve la lista 'response' de la API."""
        # Throttle local
        elapsed = time.time() - self._last_call_ts
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call_ts = time.time()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise APIFootballError(f"Error de red llamando a {endpoint}: {e}") from e

        if r.status_code == 429:
            raise APIFootballError("Rate limit alcanzado (429)", status_code=429)

        if r.status_code >= 500:
            raise APIFootballError(
                f"Error servidor API-Football ({r.status_code})", status_code=r.status_code
            )

        if r.status_code != 200:
            raise APIFootballError(
                f"HTTP {r.status_code} en {endpoint}: {r.text[:200]}",
                status_code=r.status_code,
            )

        try:
            data = r.json()
        except ValueError as e:
            raise APIFootballError(f"Respuesta no JSON: {e}") from e

        if data.get("errors"):
            # errors puede ser dict o list
            err = data["errors"]
            # Caso común: {"response": ["..."]}
            if isinstance(err, dict) and "response" in err:
                err = err["response"]
            raise APIFootballError(f"API-Football errors: {err}")

        return data.get("response", []) or []

    # ------------------------------------------------------------------ #
    # Endpoints de alto nivel
    # ------------------------------------------------------------------ #
    def get_live_fixtures(self, league_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """
        Devuelve los partidos en vivo.
        Filtra por league_ids si se pasa (los IDs deben estar en la lista).
        """
        # El endpoint ?live=all devuelve todos los partidos live.
        # Si hay muchas ligas activas, conviene filtrar cliente-side para no agotar cuota.
        all_live = self._get("/fixtures", {"live": "all"})
        if not league_ids:
            return all_live
        wanted = set(league_ids)
        return [
            f for f in all_live
            if f.get("league", {}).get("id") in wanted
        ]

    def get_fixtures_by_date(
        self, date_iso: str, league_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Devuelve partidos de una fecha YYYY-MM-DD.
        Útil para pre-cargar IDs del día y pre-publicar horarios.
        """
        params = {"date": date_iso, "timezone": self.cfg.timezone}
        results = self._get("/fixtures", params)
        if league_ids:
            wanted = set(league_ids)
            results = [f for f in results if f.get("league", {}).get("id") in wanted]
        return results

    def get_fixture_events(self, fixture_id: int) -> List[Dict[str, Any]]:
        """Devuelve todos los eventos (goles, tarjetas, cambios, VAR) de un partido."""
        return self._get("/fixtures/events", {"fixture": fixture_id})

    def get_fixture(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        """Devuelve un único fixture por ID (con statistics, lineups, etc. opcional)."""
        results = self._get("/fixtures", {"id": fixture_id})
        return results[0] if results else None

    def get_account_status(self) -> Dict[str, Any]:
        """Estado de la cuenta: plan, límite diario, requests restantes."""
        return self._get("/status", {})

    def get_lineups(self, fixture_id: int) -> List[Dict[str, Any]]:
        """
        Devuelve las alineaciones de ambos equipos para un partido.
        Vacío si aún no se han publicado (típicamente 30-60 min antes del partido).
        """
        return self._get("/fixtures/lineups", {"fixture": fixture_id})

    def get_statistics(self, fixture_id: int) -> List[Dict[str, Any]]:
        """
        Devuelve las estadísticas de ambos equipos para un partido.
        Solo disponible cuando el partido ha comenzado.
        """
        return self._get("/fixtures/statistics", {"fixture": fixture_id})
