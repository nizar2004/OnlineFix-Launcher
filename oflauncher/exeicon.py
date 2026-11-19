"""Best-effort icon extraction from Windows executables (optional icoextract)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from gi.repository import GdkPixbuf, Gio, GLib

from . import config, icons


def _icons_dir() -> Path:
    d = config.DATA_DIR / "icons"
    d.mkdir(parents=True, exist_ok=True)
    return d


def extract_icon(exe_path: str, game_name: str) -> Optional[Path]:
    """Extract the main icon of a .exe into DATA_DIR/icons/<name>.ico.

    Returns None when icoextract is unavailable or extraction fails.
    """
    try:
        from icoextract import IconExtractor  # type: ignore
    except ImportError:
        return None
    if not exe_path or not Path(exe_path).exists():
        return None
    dest = _icons_dir() / f"{game_name}.ico"
    try:
        IconExtractor(exe_path).export_icon(str(dest), num=0)
        return dest if dest.exists() else None
    except Exception:
        return None


def app_icon_png() -> Optional[Path]:
    """Path to the launcher's PNG icon, generating one from the bundled SVG."""
    dest = _icons_dir() / "oflauncher.png"
    if dest.exists():
        return dest
    try:
        svg = icons.ICONS["logo"].encode("utf-8")
        stream = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(svg))
        pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(stream, 256, 256, True, None)
        pixbuf.savev(str(dest), "png", [], [])
        return dest
    except Exception:
        return None
