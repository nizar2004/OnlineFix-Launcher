"""Theme: dark style, accent color and small CSS refinements."""

from __future__ import annotations

from gi.repository import Adw, Gdk, Gtk

ACCENT = "#7c6cff"          # violet — the launcher's identity color

CSS = b"""
/* Cards */
.game-card {
    border-radius: 14px;
    background: rgba(255,255,255,0.04);
    padding: 6px;
}
.game-card:hover {
    background: rgba(255,255,255,0.09);
}
.game-card:selected {
    background: alpha(@accent_color, 0.25);
}

.card-cover {
    border-radius: 10px;
    background: #20242e;
}

.card-caption {
    font-weight: 700;
    font-size: 12.5px;
    padding: 5px 2px 1px 2px;
}

/* Big detail cover */
.detail-cover {
    border-radius: 18px;
    background: #20242e;
}

/* Pills */
.pill {
    border-radius: 999px;
    padding: 2px 10px;
    font-size: 11.5px;
    font-weight: 700;
    background: rgba(255,255,255,0.08);
    color: alpha(@window_fg_color, 0.85);
}
.pill-accent {
    background: alpha(@accent_color, 0.22);
    color: @accent_color;
}

/* Play button */
.play-button {
    font-weight: 800;
    font-size: 15px;
    padding: 10px 26px;
}

.stop-button {
    font-weight: 800;
    font-size: 15px;
    padding: 10px 26px;
}

/* Nav rows */
.nav-row {
    border-radius: 10px;
    margin: 1px 8px;
    padding: 6px 4px;
}

/* Log view */
.log-view {
    font-family: monospace;
    font-size: 12px;
}

/* Running dot */
.running-dot {
    color: @success_color;
}
"""


def init(style_manager: Adw.StyleManager) -> None:
    """Apply dark scheme, accent color and the CSS provider."""
    style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
    try:
        style_manager.set_accent_color(Adw.AccentColor.VIOLET)
    except AttributeError:  # older libadwaita
        pass

    provider = Gtk.CssProvider()
    provider.load_from_string(CSS.decode("utf-8"))
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
