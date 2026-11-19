"""Data models for games and fix presets."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

# WINEDLLOVERRIDES presets, mirroring what the fixes need to load.
FIX_PRESETS: Dict[str, str] = {
    "none": "",
    "onlinefix": "onlinefix=n,b",
    "freetp": "dinput8=n,b",
    "custom": "",
}

FIX_LABELS: Dict[str, str] = {
    "none": "No fix",
    "onlinefix": "OnlineFix",
    "freetp": "FreeTP",
    "custom": "Custom",
}


@dataclass
class Game:
    name: str
    executable: str = ""
    game_dir: str = ""
    prefix_path: str = ""
    runner: str = "proton"            # proton | wine
    proton_version: str = ""          # empty = newest installed / app default
    fix_type: str = "onlinefix"
    overrides: str = ""
    extra_env: str = ""               # KEY=value lines
    steam_id: Optional[int] = None
    banner: str = ""                  # path to the cover image
    icon: str = ""                    # path to extracted .ico/.png
    playtime: int = 0                 # seconds
    last_played: int = 0              # unix epoch
    desktop_shortcut: bool = False
    menu_shortcut: bool = False
    notes: str = ""
    added_at: int = field(default_factory=lambda: int(time.time()))

    def effective_overrides(self) -> str:
        if self.overrides:
            return self.overrides
        return FIX_PRESETS.get(self.fix_type, "")

    def parse_extra_env(self) -> Dict[str, str]:
        env: Dict[str, str] = {}
        for line in (self.extra_env or "").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key:
                env[key] = value.strip()
        return env

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Game":
        valid = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in valid})
