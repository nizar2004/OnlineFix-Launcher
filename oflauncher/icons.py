"""Inline SVG icon set — ships with the app so no icon theme is required."""

from __future__ import annotations

from typing import Dict

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

_STROKE = "#c8cfdd"


def _nav(body: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
        f'<g fill="{_STROKE}">{body.replace("__C__", _STROKE)}</g></svg>'
    )


ICONS: Dict[str, str] = {
    "logo": """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
      <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#8b7bff"/><stop offset="1" stop-color="#5b8cff"/>
      </linearGradient></defs>
      <rect x="4" y="14" width="56" height="36" rx="14" fill="url(#g)"/>
      <path d="M20 28v10M15 33h10" stroke="#ffffff" stroke-width="4" stroke-linecap="round"/>
      <circle cx="43" cy="30" r="3.4" fill="#ffffff"/><circle cx="50" cy="37" r="3.4" fill="#ffffff"/>
    </svg>""",
    "library": _nav("""<path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H8a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5.5A1.5 1.5 0 0 1 4 18.5v-13Zm8-.5h6.5A1.5 1.5 0 0 1 20 6.5v11a1.5 1.5 0 0 1-1.5 1.5H12V5Zm2 2v10h2.5v-10H14Zm-8 .5v9H7v-9H6Z" />"""),
    "download": _nav("""<path d="M12 3a1 1 0 0 1 1 1v8.6l2.3-2.3a1 1 0 1 1 1.4 1.4l-4 4a1 1 0 0 1-1.4 0l-4-4a1 1 0 1 1 1.4-1.4L11 12.6V4a1 1 0 0 1 1-1ZM5 18a1 1 0 0 1 1-1h12a1 1 0 1 1 0 2H6a1 1 0 0 1-1-1Z"/>"""),
    "settings": _nav("""<path d="M10.6 3h2.8l.4 2.2c.6.2 1.2.5 1.7.9l2.1-.8 1.4 2.4-1.6 1.5c.1.6.1 1.2 0 1.8l1.6 1.5-1.4 2.4-2.1-.8c-.5.4-1.1.7-1.7.9L13.4 19h-2.8l-.4-2.2a6 6 0 0 1-1.7-.9l-2.1.8-1.4-2.4 1.6-1.5a6 6 0 0 1 0-1.8L5 9.5l1.4-2.4 2.1.8c.5-.4 1.1-.7 1.7-.9L10.6 3Zm1.4 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5Z"/>"""),
    "play": _nav("""<path d="M7 5.1c0-.9 1-1.5 1.8-1L18 10.1c.8.5.8 1.6 0 2l-9.2 5.9c-.8.5-1.8-.1-1.8-1V5.1Z"/>"""),
    "stop": _nav("""<rect x="6" y="6" width="12" height="12" rx="2"/>"""),
    "debug": _nav("""<path d="M12 4a4 4 0 0 1 4 4v1h2a1 1 0 1 1 0 2h-2v2h2a1 1 0 1 1 0 2h-2v1a4 4 0 0 1-8 0v-1H6a1 1 0 1 1 0-2h2v-2H6a1 1 0 1 1 0-2h2V8a4 4 0 0 1 4-4Zm-2 5h4V8a2 2 0 1 0-4 0v1Zm0 2v2h4v-2h-4Zm0 4v1a2 2 0 1 0 4 0v-1h-4Z"/>"""),
    "folder": _nav("""<path d="M4 6a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6Z"/>"""),
    "trash": _nav("""<path d="M9 3h6a1 1 0 0 1 1 1v1h4a1 1 0 1 1 0 2h-1l-.8 12a2 2 0 0 1-2 1.9H7.8a2 2 0 0 1-2-1.9L5 7H4a1 1 0 0 1 0-2h4V4a1 1 0 0 1 1-1Zm1 2v1h4V5h-4ZM8 8l.6 12h6.8L16 8H8Z"/>"""),
    "edit": _nav("""<path d="m14.5 4.5 5 5L9 20H4v-5L14.5 4.5Zm1.4-1.4a2 2 0 0 1 2.8 0l2.2 2.2a2 2 0 0 1 0 2.8l-1 1-5-5 1-1Z"/>"""),
    "close": _nav("""<path d="M6 6l12 12M18 6 6 18" stroke="__C__" stroke-width="2.2" stroke-linecap="round" fill="none"/>"""),
    "back": _nav("""<path d="M11 5a1 1 0 0 1 .7 1.7L7.4 11H19a1 1 0 1 1 0 2H7.4l4.3 4.3A1 1 0 1 1 10.3 18.7l-6-6a1 1 0 0 1 0-1.4l6-6A1 1 0 0 1 11 5Z" transform="translate(0,-1)"/>"""),
    "search": _nav("""<path d="M10.5 3a7.5 7.5 0 1 1-4.7 13.4l-3.1 3a1 1 0 0 1-1.4-1.4l3-3.1A7.5 7.5 0 0 1 10.5 3Zm0 2a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11Z" transform="translate(1,0)"/>"""),
    "refresh": _nav("""<path d="M12 4a8 8 0 0 1 7.4 5H21a1 1 0 0 1 .8 1.6L19 14.4a1 1 0 0 1-1.6 0l-2.8-3.8A1 1 0 0 1 15.4 9h1.6A6 6 0 1 0 18 12a1 1 0 1 1 2 .4A8 8 0 1 1 12 4Z"/>"""),
    "external": _nav("""<path d="M14 4h5a1 1 0 0 1 1 1v5a1 1 0 1 1-2 0V7.4l-6.3 6.3a1 1 0 0 1-1.4-1.4L16.6 6H14a1 1 0 1 1 0-2ZM6 6h4a1 1 0 0 1 0 2H7a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-3a1 1 0 1 1 2 0v3a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V9a3 3 0 0 1 3-3Z"/>"""),
    "gamepad": _nav("""<path d="M7 7h10a5 5 0 0 1 5 5c0 2.8-2 5-4.6 5-1.6 0-2.7-.9-3.6-2H10.2c-.9 1.1-2 2-3.6 2C4 17 2 14.8 2 12a5 5 0 0 1 5-5Zm1 3a1 1 0 0 0-1 1v.6h-.6a1 1 0 1 0 0 2H7v.4a1 1 0 1 0 2 0v-.4h.4a1 1 0 1 0 0-2H9v-.6a1 1 0 0 0-1-1Zm8.5.5a1.2 1.2 0 1 0 0 2.4 1.2 1.2 0 0 0 0-2.4Zm2.6 2.6a1.2 1.2 0 1 0 0 2.4 1.2 1.2 0 0 0 0-2.4Z"/>"""),
    "steam": _nav("""<path d="M12 3a9 9 0 0 1 9 9 9 9 0 0 1-9 9 9 9 0 0 1-8.7-6.8l3.5 1.5a2.6 2.6 0 1 0 2.5-3.3l-3.4-1.4A9 9 0 0 1 12 3Zm3.2 4.2a2.3 2.3 0 1 0 0 4.6 2.3 2.3 0 0 0 0-4.6Zm0 1a1.3 1.3 0 1 1 0 2.6 1.3 1.3 0 0 1 0-2.6Z"/>"""),
    "check": _nav("""<path d="M19.3 6.3a1 1 0 0 1 0 1.4l-8.5 8.5a1 1 0 0 1-1.4 0l-4.7-4.7a1 1 0 1 1 1.4-1.4l4 4 7.8-7.8a1 1 0 0 1 1.4 0Z"/>"""),
    "env": _nav("""<path d="M8.7 4.3a1 1 0 0 1 0 1.4L5.4 9l3.3 3.3a1 1 0 1 1-1.4 1.4l-4-4a1 1 0 0 1 0-1.4l4-4a1 1 0 0 1 1.4 0Zm6.6 0a1 1 0 0 1 1.4 0l4 4a1 1 0 0 1 0 1.4l-4 4a1 1 0 1 1-1.4-1.4L18.6 9l-3.3-3.3a1 1 0 0 1 0-1.4Z"/>"""),
    "monitor": _nav("""<path d="M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-5v2h3a1 1 0 1 1 0 2H8a1 1 0 1 1 0-2h3v-2H6a2 2 0 0 1-2-2V5Z"/>"""),
    "clock": _nav("""<path d="M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18Zm0 2a7 7 0 1 0 0 14 7 7 0 0 0 0-14Zm1 2v4.6l3 1.7a1 1 0 1 1-1 1.7l-3.5-2A1 1 0 0 1 11 12V7a1 1 0 1 1 2 0Z"/>"""),
}


_CACHE: Dict[str, Gdk.Paintable] = {}


def paintable(name: str, size: int = 24) -> Gdk.Paintable:
    """Load an inline icon as a paintable (cached)."""
    key = f"{name}@{size}"
    if key in _CACHE:
        return _CACHE[key]
    svg = ICONS.get(name, ICONS["gamepad"])
    data = GLib.Bytes.new(svg.encode("utf-8"))
    stream = Gio.MemoryInputStream.new_from_bytes(data)
    pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(stream, size, size, True, None)
    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
    _CACHE[key] = texture
    return texture


def image(name: str, size: int = 24) -> Gtk.Image:
    img = Gtk.Image.new_from_paintable(paintable(name, size))
    img.set_pixel_size(size)
    return img


def logo_paintable(size: int = 64) -> Gdk.Paintable:
    return paintable("logo", size)
