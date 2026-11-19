#!/usr/bin/env python3
"""Developer tool: drive the launcher UI and save PNG screenshots.

Usage:
    python3 tools/screenshot.py [output-dir]

Uses an isolated profile (ONLINEFIX_LAUNCHER_DATA_HOME) so the real
configuration is never touched. Requires a display (X11, Wayland or broadway).
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROFILE = Path("/tmp/ofl-screenshot-profile")
os.environ["ONLINEFIX_LAUNCHER_DATA_HOME"] = str(PROFILE)

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from oflauncher import config  # noqa: E402
from oflauncher.library import library  # noqa: E402
from oflauncher.models import Game  # noqa: E402
from oflauncher.ui.add_dialog import AddGameDialog  # noqa: E402
from oflauncher.ui.main_window import MainWindow  # noqa: E402
from oflauncher.ui.settings import SettingsDialog  # noqa: E402

W, H = 1120, 700


def make_cover(name: str, initials: str, c1: str, c2: str) -> str:
    """Generate a gradient cover with initials; returns path."""
    from gi.repository import GdkPixbuf, Gio

    covers = config.COVERS_DIR
    covers.mkdir(parents=True, exist_ok=True)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="900" viewBox="0 0 600 900">
      <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/>
      </linearGradient></defs>
      <rect width="600" height="900" fill="url(#g)"/>
      <circle cx="300" cy="380" r="150" fill="rgba(255,255,255,0.12)"/>
      <text x="300" y="440" font-family="sans-serif" font-size="150" font-weight="800"
            fill="#ffffff" text-anchor="middle">{initials}</text>
      <text x="300" y="700" font-family="sans-serif" font-size="52" font-weight="700"
            fill="#ffffff" text-anchor="middle" opacity="0.92">{name}</text>
    </svg>"""
    stream = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(svg.encode()))
    pixbuf = GdkPixbuf.Pixbuf.new_from_stream(stream, None)
    path = covers / f"{name}.png"
    pixbuf.savev(str(path), "png", [], [])
    return str(path)


def seed_games() -> None:
    from oflauncher import steam

    demos = [
        ("Nebula Drift", "ND", "#5b8cff", "#8b7bff"),
        ("Hollow Protocol", "HP", "#f2a51a", "#d9534f"),
        ("Star Vanguards", "SV", "#2dd4bf", "#3b82f6"),
    ]
    for name, ini, c1, c2 in demos:
        path = None
        try:
            _appid, path = steam.search_and_fetch_cover(name, config.COVERS_DIR / name)
        except Exception:
            path = None
        if not path:
            path = make_cover(name, ini, c1, c2)
        library.add(
            Game(
                name=name,
                executable=f"/tmp/games/{name}/Game.exe",
                game_dir=f"/tmp/games/{name}",
                fix_type="onlinefix",
                banner=str(path),
            )
        )


class Shooter:
    def __init__(self) -> None:
        self.app = Adw.Application(application_id="io.github.nizar2004.OnlineFixLauncher.Screenshots")
        self.window: MainWindow | None = None
        self.step = 0

    # -- helpers ---------------------------------------------------------------
    def shoot(self, widget: Gtk.Widget, name: str, w: int, h: int) -> None:
        try:
            paintable = Gtk.WidgetPaintable.new(widget)
            snapshot = Gtk.Snapshot()
            paintable.snapshot(snapshot, w, h)
            node = snapshot.to_node()
            if node is None:
                print(f"  !! {name}: empty render node")
                return
            import cairo

            surface = cairo.ImageSurface(cairo.Format.ARGB32, w, h)
            cr = cairo.Context(surface)
            node.draw(cr)
            surface.write_to_png(str(OUT_DIR / name))
            print(f"  saved {name}")
        except Exception as exc:
            print(f"  !! {name}: {exc}")

    def run(self) -> int:
        self.app.connect("activate", self.on_activate)
        return self.app.run([])

    # -- flow -------------------------------------------------------------------
    def on_activate(self, app):
        self.window = MainWindow(app)
        self.window.set_default_size(W, H)
        self.window.refresh_library()
        self.window.present()
        GLib.timeout_add(800, self.sequence)
        GLib.timeout_add(120_000, self._timeout_quit)

    def _timeout_quit(self):
        print("  !! timeout reached, quitting")
        self.app.quit()
        return False

    def sequence(self) -> bool:
        self.step += 1
        w = self.window
        if w is None:
            return False
        print(f"step {self.step}")

        if self.step == 1:  # empty state, then library with games
            self.shoot(w, "01-empty-library.png", W, H)
            seed_games()
            w.refresh_library()
            GLib.timeout_add(700, self.sequence)
            return False
        if self.step == 2:  # library grid
            self.shoot(w, "02-library.png", W, H)
            GLib.timeout_add(500, self.sequence)
            return False
        if self.step == 3:  # game detail
            w.open_detail(library.names()[0])
            GLib.timeout_add(700, self._shot_and(lambda: w.nav_view.pop(), "03-game-detail.png"))
            return False
        if self.step == 4:  # add game dialog
            self.dialog = AddGameDialog(w)
            self.dialog.present(w)
            GLib.timeout_add(800, self._shot_and(lambda: self.dialog.force_close(), "04-add-game.png", 560, 560, self.dialog))
            return False
        if self.step == 5:  # per-game settings
            w.open_game_settings(library.names()[0])
            GLib.timeout_add(700, self._shot_and(lambda: w.nav_view.pop(), "05-game-settings.png"))
            return False
        if self.step == 6:  # downloads / browser
            w._push_unique(w.downloads_page)
            w.downloads_page.ensure_webview()
            w.downloads_page.refresh()
            GLib.timeout_add(2500, self._shot_and(lambda: None, "06-downloads.png"))
            return False
        if self.step == 7:  # runners
            w._push_unique(w.proton_page)
            w.proton_page.refresh()
            GLib.timeout_add(700, self._shot_and(lambda: None, "07-runners.png"))
            return False
        if self.step == 8:  # app settings dialog
            self.settings = SettingsDialog(w)
            self.settings.present(w)
            GLib.timeout_add(900, self._shot_and(lambda: self.settings.force_close(), "08-app-settings.png", 620, 660, self.settings))
            return False
        if self.step == 9:
            # leave the window on the library page
            w.nav_view.pop_to_page(w.library_page)
            print("screenshots complete")
            self.app.quit()
            return False
        return False

    def _shot_and(self, then, name: str, w=..., h=..., widget=None):
        def inner() -> bool:
            target = self.window if widget is None else widget
            width = W if (w is ...) else w
            height = H if (h is ...) else h
            self.shoot(target, name, width, height)
            then()
            GLib.timeout_add(500, self.sequence)
            return False

        return inner


if __name__ == "__main__":
    raise SystemExit(Shooter().run())
