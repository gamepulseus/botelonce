"""
Manejo de estado persistente del bot.

Mantiene:
- fixtures activos y su último estado conocido (status short, score, halftime flag)
- IDs de eventos ya publicados por fixture (para deduplicar)

El estado se guarda en JSON para sobrevivir reinicios.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Set

log = logging.getLogger(__name__)


@dataclass
class FixtureState:
    fixture_id: int
    last_status_short: str = ""  # NS, 1H, HT, 2H, ET, BT, P, SUSP, INT, LIVE, ABD, PST, CANC, FIN, AET, PEN
    last_home_goals: int = -1
    last_away_goals: int = -1
    halftime_announced: bool = False
    second_half_announced: bool = False
    started_announced: bool = False
    finished_announced: bool = False
    lineups_announced: bool = False
    stats_announced: bool = False
    published_event_keys: Set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {
            "fixture_id": self.fixture_id,
            "last_status_short": self.last_status_short,
            "last_home_goals": self.last_home_goals,
            "last_away_goals": self.last_away_goals,
            "halftime_announced": self.halftime_announced,
            "second_half_announced": self.second_half_announced,
            "started_announced": self.started_announced,
            "finished_announced": self.finished_announced,
            "lineups_announced": self.lineups_announced,
            "stats_announced": self.stats_announced,
            "published_event_keys": sorted(self.published_event_keys),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FixtureState":
        return cls(
            fixture_id=d["fixture_id"],
            last_status_short=d.get("last_status_short", ""),
            last_home_goals=d.get("last_home_goals", -1),
            last_away_goals=d.get("last_away_goals", -1),
            halftime_announced=d.get("halftime_announced", False),
            second_half_announced=d.get("second_half_announced", False),
            started_announced=d.get("started_announced", False),
            finished_announced=d.get("finished_announced", False),
            lineups_announced=d.get("lineups_announced", False),
            stats_announced=d.get("stats_announced", False),
            published_event_keys=set(d.get("published_event_keys", [])),
        )


class StateStore:
    """Persistencia JSON del estado del bot."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._fixtures: Dict[int, FixtureState] = {}
        self._load()

    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for fid_str, fstate_dict in data.get("fixtures", {}).items():
                fid = int(fid_str)
                self._fixtures[fid] = FixtureState.from_dict(fstate_dict)
            log.info("Estado cargado: %d fixtures", len(self._fixtures))
        except Exception as e:
            log.error("Error cargando estado desde %s: %s", self.path, e)

    def _save(self) -> None:
        data = {
            "fixtures": {
                str(fid): fs.to_dict() for fid, fs in self._fixtures.items()
            }
        }

        # Asegurar que el directorio padre existe (fallback automático)
        parent_dir = os.path.dirname(self.path)
        if parent_dir and not os.path.isdir(parent_dir):
            # El directorio configurado no existe (ej: /data sin volumen).
            # Caer a un state.json local en el directorio de trabajo.
            log.warning(
                "Directorio %s no existe. Usando state.json local.",
                parent_dir or "/data",
            )
            self.path = "state.json"

        tmp_path = self.path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)
        except (OSError, IOError) as e:
            log.error("No se pudo guardar estado en %s: %s", self.path, e)
            # Último recurso: state.json en cwd
            if self.path != "state.json":
                self.path = "state.json"
                try:
                    with open(self.path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    log.info("Estado guardado en state.json (fallback).")
                except Exception as e2:
                    log.error("También falló el fallback: %s", e2)

    # ------------------------------------------------------------------ #
    def get(self, fixture_id: int) -> FixtureState:
        with self._lock:
            if fixture_id not in self._fixtures:
                self._fixtures[fixture_id] = FixtureState(fixture_id=fixture_id)
            return self._fixtures[fixture_id]

    def has(self, fixture_id: int) -> bool:
        with self._lock:
            return fixture_id in self._fixtures

    def update(self, fixture_id: int, mutator) -> None:
        """Aplica mutator(FixtureState) y guarda."""
        with self._lock:
            fs = self._fixtures.setdefault(
                fixture_id, FixtureState(fixture_id=fixture_id)
            )
            mutator(fs)
            self._save()

    def cleanup_old(self, keep_ids: set) -> int:
        """Elimina fixtures que ya no están activos ni se han visto hoy."""
        with self._lock:
            before = len(self._fixtures)
            self._fixtures = {
                fid: fs for fid, fs in self._fixtures.items() if fid in keep_ids
            }
            removed = before - len(self._fixtures)
            if removed:
                self._save()
            return removed

    def all_fixtures(self) -> Dict[int, FixtureState]:
        with self._lock:
            return dict(self._fixtures)
