"""Application paths and JSON-backed settings/game storage."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict

APP_DIR_NAME = "OnlineFixLauncher"

# All XDG paths can be rooted elsewhere (used by tests and screenshot tooling).
_HOME = Path(os.environ.get("ONLINEFIX_LAUNCHER_DATA_HOME", str(Path.home())))

CONFIG_DIR = _HOME / ".config" / APP_DIR_NAME
CACHE_DIR = _HOME / ".cache" / APP_DIR_NAME
STATE_DIR = _HOME / ".local" / "state" / APP_DIR_NAME
DATA_DIR = _HOME / ".local" / "share" / APP_DIR_NAME

COVERS_DIR = CACHE_DIR / "covers"
LOGS_DIR = STATE_DIR / "logs"

SETTINGS_FILE = CONFIG_DIR / "settings.json"
GAMES_FILE = CONFIG_DIR / "games.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "installs_dir": str(DATA_DIR / "Games"),
    "downloads_dir": str(DATA_DIR / "Downloads"),
    "default_runner": "proton",          # proton | wine
    "default_proton": "",                # empty = newest installed
    "default_fix_type": "onlinefix",
    "keep_log_file": True,
}


def ensure_dirs() -> None:
    for d in (CONFIG_DIR, CACHE_DIR, COVERS_DIR, STATE_DIR, LOGS_DIR, DATA_DIR):
        d.mkdir(parents=True, exist_ok=True)


class JsonStore:
    """Small thread-safe JSON object store."""

    def __init__(self, path: Path, defaults: Dict[str, Any] | None = None) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = dict(defaults or {})
        self.load()

    def load(self) -> None:
        with self._lock:
            try:
                if self.path.exists():
                    self._data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except Exception:
                # Corrupt file: keep defaults rather than crash the launcher.
                self._data = dict(self._data)

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def as_dict(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)


settings = JsonStore(SETTINGS_FILE, DEFAULT_SETTINGS)
