"""Game library: add/remove/update games, persistence and scanning."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from gi.repository import GLib

from . import config
from .models import Game


def scan_executables(game_dir: str) -> List[str]:
    """Find .exe files in the folder (top level first, then one level deep)."""
    root = Path(game_dir)
    found: List[str] = []
    if not root.is_dir():
        return found
    for p in sorted(root.glob("*.exe")):
        found.append(str(p))
    for p in sorted(root.glob("*/*.exe")):
        found.append(str(p))
    # Deduplicate, keep order.
    seen = set()
    unique = []
    for f in found:
        if f.lower() not in seen:
            seen.add(f.lower())
            unique.append(f)
    return unique


class Library:
    """In-memory game collection backed by games.json."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._games: Dict[str, Game] = {}
        self.store = config.JsonStore(config.GAMES_FILE, {})
        self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        data = self.store.as_dict()
        for name, params in data.items():
            try:
                self._games[name] = Game.from_dict(params)
            except Exception:
                continue

    def _persist(self) -> None:
        for key, value in self._games.items():
            self.store.set(key, value.to_dict())
        self.store.save()

    # -- queries ----------------------------------------------------------
    def names(self) -> List[str]:
        with self._lock:
            return sorted(self._games.keys(), key=str.casefold)

    def get(self, name: str) -> Optional[Game]:
        with self._lock:
            return self._games.get(name)

    def all(self) -> List[Game]:
        with self._lock:
            return [self._games[n] for n in self.names()]

    def exists(self, name: str) -> bool:
        with self._lock:
            return name in self._games

    # -- mutations ----------------------------------------------------------
    def add(self, game: Game) -> None:
        with self._lock:
            self._games[game.name] = game
            self._persist()

    def remove(self, name: str) -> None:
        with self._lock:
            self._games.pop(name, None)
            self.store.set(name, None)
            self._persist()
            # Drop the null entry completely.
            with self.store._lock:  # noqa: SLF001 - same package
                self.store._data.pop(name, None)
            self.store.save()

    def rename(self, old: str, new: str) -> bool:
        with self._lock:
            if old not in self._games or not new or new in self._games:
                return False
            game = self._games.pop(old)
            game.name = new
            self._games[new] = game
            self.store.set(old, None)
            self._persist()
            with self.store._lock:  # noqa: SLF001
                self.store._data.pop(old, None)
            self.store.save()
            return True

    def update(self, game: Game) -> None:
        with self._lock:
            if game.name in self._games:
                self._games[game.name] = game
                self._persist()

    def touch_played(self, name: str, seconds: int) -> None:
        with self._lock:
            game = self._games.get(name)
            if game:
                game.playtime += max(0, seconds)
                game.last_played = int(time.time())
                self._persist()

    def set_banner(self, name: str, path: str) -> None:
        with self._lock:
            game = self._games.get(name)
            if game:
                game.banner = path
                self._persist()


def format_playtime(seconds: int) -> str:
    if seconds <= 0:
        return "Never played"
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours:
        return f"{hours} h {minutes} min"
    return f"{minutes} min"


def default_prefix_for(game_dir: str, name: str) -> str:
    """The prefix lives next to the game, like the original launcher."""
    base = Path(game_dir) if game_dir else config.settings.get("installs_dir")
    return str(Path(base) / "Prefix")


def run_in_thread(fn: Callable[[], None], *args, **kwargs) -> None:
    """Run fn in a daemon thread; helper for blocking I/O."""

    def wrapper() -> None:
        try:
            fn(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - background safety net
            GLib.idle_add(_report_thread_error, exc)

    threading.Thread(target=wrapper, daemon=True).start()


def _report_thread_error(exc: Exception) -> None:
    print(f"[background error] {exc}", flush=True)
    return False


library = Library()
