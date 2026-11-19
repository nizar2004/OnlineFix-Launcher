"""Desktop and application-menu shortcuts."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import List

from . import config
from .models import Game

LAUNCHER_EXEC = "onlinefix-launcher"
APP_ID = "io.github.nizar2004.OnlineFixLauncher"


def _launcher_executable() -> str:
    """Prefer an installed binary, fall back to python + script path."""
    if shutil.which(LAUNCHER_EXEC):
        return LAUNCHER_EXEC
    script = Path(__file__).resolve().parent.parent / "main.py"
    return f"python3 {script}"


def desktop_dir() -> Path:
    xdg = os.environ.get("XDG_DESKTOP_DIR")
    if xdg:
        return Path(xdg)
    user_dirs = Path.home() / ".config" / "user-dirs.dirs"
    if user_dirs.exists():
        for line in user_dirs.read_text().splitlines():
            if line.strip().startswith("XDG_DESKTOP_DIR"):
                value = line.partition("=")[2].strip().strip('"')
                value = os.path.expandvars(value.replace("$HOME", str(Path.home())))
                return Path(value)
    return Path.home() / "Desktop"


def applications_dir() -> Path:
    return Path.home() / ".local" / "share" / "applications"


def _desktop_entry(game: Game) -> str:
    exec_cmd = f'{_launcher_executable()} --launch "{game.name}"'
    icon = game.icon or (config.DATA_DIR / "icons" / "oflauncher.png")
    icon = str(icon) if Path(icon).exists() else APP_ID
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={game.name}\n"
        "Comment=Play with OnlineFix Launcher\n"
        f"Exec={exec_cmd}\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=Game;\n"
        f"StartupWMClass={APP_ID}\n"
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def set_desktop_shortcut(game: Game, enabled: bool) -> bool:
    path = desktop_dir() / f"{game.name}.desktop"
    if enabled:
        try:
            _write(path, _desktop_entry(game))
            os.chmod(path, 0o755)
            return True
        except Exception:
            return False
    path.unlink(missing_ok=True)
    return True


def set_menu_shortcut(game: Game, enabled: bool) -> bool:
    path = applications_dir() / f"{game.name}.desktop"
    if enabled:
        try:
            _write(path, _desktop_entry(game))
            subprocess.run(["update-desktop-database", str(applications_dir())], check=False)
            return True
        except Exception:
            return False
    path.unlink(missing_ok=True)
    return True


def sync(game: Game) -> None:
    """Apply the shortcut flags stored on the game."""
    set_desktop_shortcut(game, game.desktop_shortcut)
    set_menu_shortcut(game, game.menu_shortcut)


def remove_all_for(game: Game) -> None:
    set_desktop_shortcut(game, False)
    set_menu_shortcut(game, False)
