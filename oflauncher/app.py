"""Application bootstrap: Adw.Application, single instance, CLI flags."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Adw, GdkPixbuf, Gio, GLib, Gtk  # noqa: E402

from . import APP_ID, APP_NAME, __version__, config  # noqa: E402
from .theme import init as init_theme  # noqa: E402
from .ui.main_window import MainWindow  # noqa: E402


def _icon_candidates() -> list[Path]:
    """Possible locations of the application icon."""
    here = Path(__file__).resolve()
    root = here.parent.parent
    return [
        root / "data" / "icon.png",
        Path("/usr/share/icons/hicolor/512x512/apps/io.github.nizar2004.OnlineFixLauncher.png"),
        Path("/usr/share/pixmaps/onlinefix-launcher.png"),
    ]


class OnlineFixLauncherApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.window: Optional[MainWindow] = None
        self._pending_launch: Optional[str] = None

        self.add_main_option(
            "launch",
            ord("l"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            "Launch a game by name",
            "NAME",
        )
        self.add_main_option(
            "kill",
            ord("k"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Kill the game currently started by the launcher",
            None,
        )
        self._pending_kill = False

    # -- lifecycle ---------------------------------------------------------------
    def do_startup(self):
        config.ensure_dirs()
        init_theme(self.get_style_manager())
        self._set_icon()
        Adw.Application.do_startup(self)

    def _set_icon(self) -> None:
        """Use the bundled icon for every window of the application."""
        for candidate in _icon_candidates():
            if not candidate.exists():
                continue
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(candidate))
                Gtk.Window.set_default_icon(pixbuf)
                return
            except Exception:
                continue
        try:
            Gtk.Window.set_default_icon_name("applications-games-symbolic")
        except Exception:
            pass

    def do_activate(self):
        if self.window is None:
            self.window = MainWindow(self)
            self.window.wire_runner()
        self.window.refresh_library()

        if self._pending_kill and not self._pending_launch:
            # Kill and quit silently — useful for scripts and shortcuts.
            from .runner import runner

            runner.stop()
            self._pending_kill = False
            if self.window is not None:
                self.window.destroy()
                self.window = None
            self.quit()
            return

        self.window.present()

        if self._pending_launch:
            name, self._pending_launch = self._pending_launch, None
            self.window.launch_game(name, debug=False)

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        options = command_line.get_options_dict()
        if options.contains("launch"):
            self._pending_launch = options.lookup_value("launch").get_string()
        if options.contains("kill"):
            self._pending_kill = True
        self.activate()
        return 0

    def do_shutdown(self):
        if self.window and getattr(self.window, "_runner", None):
            pass
        Adw.Application.do_shutdown(self)


def main(argv: list[str] | None = None) -> int:
    app = OnlineFixLauncherApp()
    GLib.set_application_name(APP_NAME)
    GLib.set_prgname(APP_ID)
    return app.run(argv if argv is not None else sys.argv)
