"""Main application window: sidebar navigation + content pages."""

from __future__ import annotations

from pathlib import Path

from pathlib import Path

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from .. import __version__, config, icons, installer, steam
from ..library import default_prefix_for, library
from ..models import Game
from ..runner import runner
from .add_dialog import AddGameDialog
from .detail_page import DetailPage
from .downloads_page import DownloadsPage
from .game_settings_page import GameSettingsPage
from .library_page import LibraryPage
from .log_window import LogWindow
from .proton_page import ProtonPage
from .settings import SettingsDialog


class MainWindow(Adw.ApplicationWindow):
    __gtype_name__ = "OFLMainWindow"

    def __init__(self, app) -> None:
        super().__init__(application=app, title="OnlineFix Launcher")
        self.set_default_size(1040, 660)
        self.set_size_request(720, 480)

        self.app = app
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        self.split = Adw.NavigationSplitView()
        self.split.set_min_sidebar_width(216)
        self.split.set_max_sidebar_width(240)
        self.split.set_sidebar_width_fraction(0.22)
        self.toast_overlay.set_child(self.split)

        self.nav_view = Adw.NavigationView()
        content_shell = Adw.NavigationPage(title="Content", child=self.nav_view)
        self.split.set_content(content_shell)
        self.split.set_sidebar(self._build_sidebar())

        # Pages
        self.library_page = LibraryPage(self)
        self.library_page.set_tag("library")
        self.nav_view.add(self.library_page)

        self.detail_page = DetailPage(self)
        self.detail_page.set_tag("detail")

        self.game_settings_page = GameSettingsPage(self)
        self.game_settings_page.set_tag("game-settings")

        self.downloads_page = DownloadsPage(self)
        self.downloads_page.set_tag("downloads")

        self.proton_page = ProtonPage(self)
        self.proton_page.set_tag("runners")

        self.nav_view.connect("pushed", lambda *_: self._sync_nav_selection())
        self.nav_view.connect("popped", lambda *_: self._sync_nav_selection())

        # Shortcuts
        controller = Gtk.ShortcutController()
        controller.set_scope(Gtk.ShortcutScope.LOCAL)
        for accel, action in (("Escape", "win.go-up"), ("<Control>o", "win.add-game"), ("<Control>f", "win.search")):
            trigger = Gtk.ShortcutTrigger.parse_string(accel)
            action_obj = Gtk.NamedAction.new(action)
            controller.add_shortcut(Gtk.Shortcut.new(trigger, action_obj))
        self.add_controller(controller)

        self.install_actions()

        self.log_window: LogWindow | None = None

    # -- sidebar --------------------------------------------------------------
    def _build_sidebar(self) -> Adw.NavigationPage:
        page = Adw.NavigationPage(title="OnlineFix Launcher")

        header = Adw.HeaderBar()
        title_box = Gtk.Box(spacing=8)
        title_box.append(icons.image("logo", 24))
        label = Gtk.Label(label="OnlineFix Launcher")
        label.add_css_class("title-4")
        title_box.append(label)
        header.set_title_widget(title_box)

        self.nav_list = Gtk.ListBox()
        self.nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav_list.add_css_class("navigation-sidebar")
        self.nav_list.set_margin_top(6)
        self.nav_list.set_margin_start(6)
        self.nav_list.set_margin_end(6)

        self.row_library = self._nav_row("library", "Library")
        self.row_downloads = self._nav_row("download", "Downloads")
        self.row_runners = self._nav_row("monitor", "Runners")
        self.row_settings = self._nav_row("settings", "Settings")
        self.nav_list.append(self.row_library)
        self.nav_list.append(self.row_downloads)
        self.nav_list.append(self.row_runners)
        self.nav_list.append(self.row_settings)
        self.nav_list.connect("row-activated", self._on_nav_activated)

        version_label = Gtk.Label(label=f"v{__version__}")
        version_label.add_css_class("dim-label")
        version_label.add_css_class("caption")
        version_label.set_margin_bottom(10)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self.nav_list)
        content.set_valign(Gtk.Align.FILL)
        version_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        version_box.set_valign(Gtk.Align.END)
        version_box.set_vexpand(True)
        version_box.append(version_label)
        content.append(version_box)

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(content)
        page.set_child(view)
        return page

    def _nav_row(self, icon: str, title: str) -> Adw.ActionRow:
        row = Adw.ActionRow(title=title)
        row.add_prefix(icons.image(icon, 18))
        row.add_css_class("nav-row")
        return row

    def _on_nav_activated(self, _list, row):
        if row is self.row_library:
            self.nav_view.pop_to_page(self.library_page)
        elif row is self.row_downloads:
            self._push_unique(self.downloads_page)
            self.downloads_page.ensure_webview()
            self.downloads_page.refresh()
        elif row is self.row_runners:
            self._push_unique(self.proton_page)
            self.proton_page.refresh()
        elif row is self.row_settings:
            dialog = SettingsDialog(self)
            dialog.present(self)

    def _push_unique(self, page: Adw.NavigationPage) -> None:
        tag = page.get_tag()
        existing = self.nav_view.find_page(tag)
        if existing:
            self.nav_view.pop_to_page(existing)
        else:
            self.nav_view.push(page)

    def _sync_nav_selection(self):
        visible = self.nav_view.get_visible_page()
        if visible is None or visible is self.library_page:
            self.nav_list.select_row(self.row_library)
        elif visible is self.proton_page:
            self.nav_list.select_row(self.row_runners)
        elif visible is self.detail_page or visible is self.game_settings_page:
            self.nav_list.select_row(self.row_library)

    # -- actions ---------------------------------------------------------------
    def install_actions(self) -> None:
        add_action = Gio.SimpleAction.new("add-game", None)
        add_action.connect("activate", lambda *_: self.open_add_dialog())
        self.add_action(add_action)

        search_action = Gio.SimpleAction.new("search", None)
        search_action.connect("activate", lambda *_: self.library_page.search.grab_focus())
        self.add_action(search_action)

        up_action = Gio.SimpleAction.new("go-up", None)
        up_action.connect("activate", self._on_go_up)
        self.add_action(up_action)

        kill_action = Gio.SimpleAction.new("kill-game", None)
        kill_action.connect("activate", lambda *_: self.kill_running_game())
        self.add_action(kill_action)

    def _on_go_up(self, *_):
        if self.nav_view.get_visible_page() not in (None, self.library_page):
            self.nav_view.pop()

    # -- public API used by pages ------------------------------------------------
    def refresh_library(self) -> None:
        self.library_page.refresh()

    def open_detail(self, name: str) -> None:
        self.detail_page.show(name)
        self._push_unique(self.detail_page)

    def open_game_settings(self, name: str) -> None:
        self.game_settings_page.show(name)
        self._push_unique(self.game_settings_page)

    def open_add_dialog(self) -> None:
        dialog = AddGameDialog(self)
        dialog.present(self)

    def open_log(self) -> None:
        if self.log_window is None:
            self.log_window = LogWindow()
        self.log_window.present()

    def open_settings(self) -> None:
        SettingsDialog(self).present(self)

    def toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast.new(message))

    # -- game lifecycle -----------------------------------------------------------
    def launch_game(self, name: str, debug: bool = False) -> None:
        game = library.get(name)
        if not game:
            return
        try:
            runner.start(game, debug=debug)
            self.toast(f"Launching {name}{' (debug)' if debug else ''}")
        except Exception as exc:
            self.toast(str(exc))
            return
        self.open_log()
        self.detail_page.refresh_state()

    def kill_running_game(self) -> None:
        """Kill whatever game is running — tracked by this instance or another one."""
        from ..runner import kill_recorded_game

        name = runner.current.game_name if runner.current else None
        if not name:
            name = kill_recorded_game()
        if not name:
            self.toast("No game is running")
            return
        runner.stop()
        kill_recorded_game()
        self.toast(f"Stopping {name}…")

    def install_from_archive(self, archive: str) -> None:
        """Ask where to install a downloaded archive, then install + add it."""
        if not Path(archive).exists():
            self.toast("Downloaded file is missing")
            return
        suggested = config.settings.get("installs_dir")
        chooser = Gtk.FileChooserNative.new(
            f"Install {Path(archive).name} to…", self, Gtk.FileChooserAction.SELECT_FOLDER, "Install Here", "Cancel"
        )
        chooser.set_modal(True)
        folder = Gio.File.new_for_path(suggested)
        if folder.query_exists(None):
            chooser.set_current_folder(folder)
        chooser.connect("response", self._on_install_dir_chosen, archive)
        chooser.show()

    def _on_install_dir_chosen(self, dialog, response, archive: str) -> None:
        if response != Gtk.ResponseType.ACCEPT:
            return
        file = dialog.get_file()
        if not file:
            return
        parent = Path(file.get_path())
        self.toast("Installing…")

        def worker():
            ok, message = installer.extract_archive(archive, parent)
            GLib.idle_add(self._after_install, ok, message, archive)

        import threading

        threading.Thread(target=worker, daemon=True).start()

    def _after_install(self, ok: bool, message: str, archive: str) -> bool:
        if not ok:
            self.toast(f"Install failed: {message}")
            return False
        dest = Path(message)
        exe = installer.find_main_executable(str(dest))
        if not exe:
            self.toast(f"Extracted to {dest.name} — no .exe found")
            self.refresh_library()
            return False

        base_name = dest.name
        name = base_name
        n = 2
        while library.exists(name):
            name = f"{base_name} ({n})"
            n += 1

        game = Game(
            name=name,
            executable=exe,
            game_dir=str(dest),
            prefix_path=default_prefix_for(str(dest), name),
            runner=config.settings.get("default_runner", "proton"),
            proton_version=config.settings.get("default_proton", ""),
            fix_type=config.settings.get("default_fix_type", "onlinefix"),
        )
        library.add(game)
        self.refresh_library()
        self.toast(f"{name} added to your library")

        from . import shortcuts as shortcuts_mod

        shortcuts_mod.sync(game)

        def cover_done(app_id, path):
            if path:
                library.set_banner(name, str(path))
                self.refresh_library()

        steam.fetch_in_thread(name, config.COVERS_DIR / name, cover_done)
        return False

    def confirm_remove(self, name: str) -> None:
        dialog = Adw.AlertDialog.new(f"Remove {name}?", "The launcher entry and shortcuts will be removed.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        del_prefix = Gtk.CheckButton(label="Also delete the Wine prefix")
        del_files = Gtk.CheckButton(label="Also delete the game folder")
        box.append(del_prefix)
        box.append(del_files)
        dialog.set_extra_child(box)

        def on_choose(_dlg, result):
            try:
                response = _dlg.choose_finish(result)
            except Exception:
                return
            if response != "remove":
                return
            self._do_remove(name, del_prefix.get_active(), del_files.get_active())

        dialog.choose(self, None, on_choose)

    def _do_remove(self, name: str, delete_prefix: bool, delete_files: bool) -> None:
        from . import shortcuts as shortcuts_mod

        game = library.get(name)
        if game:
            if runner.running and runner.current and runner.current.game_name == name:
                runner.stop()
            shortcuts_mod.remove_all_for(game)
            if delete_prefix and game.prefix_path and Path(game.prefix_path).exists():
                import shutil

                shutil.rmtree(game.prefix_path, ignore_errors=True)
            if delete_files and game.game_dir and Path(game.game_dir).exists():
                import shutil

                shutil.rmtree(game.game_dir, ignore_errors=True)
        library.remove(name)
        self.refresh_library()
        if self.nav_view.get_visible_page() in (self.detail_page, self.game_settings_page):
            self.nav_view.pop()
        self.toast(f"{name} removed")

    # -- runner wiring ---------------------------------------------------------------
    def wire_runner(self) -> None:
        runner.on_output = self._on_runner_output
        runner.on_exit = self._on_runner_exit
        runner.on_state = self._on_runner_state

    def _on_runner_output(self, line: str) -> None:
        if self.log_window is None:
            self.log_window = LogWindow()
        self.log_window.append(line)

    def _on_runner_exit(self, name: str, code: int) -> None:
        def update() -> bool:
            self.refresh_library()
            if self.detail_page.game_name == name:
                self.detail_page.refresh_state()
            self.toast(f"{name} exited ({code})" if name != "?" else "Game exited")
            return False

        from gi.repository import GLib

        GLib.idle_add(update)

    def _on_runner_state(self, running: bool) -> None:
        def update() -> bool:
            self.detail_page.refresh_state()
            self.library_page.set_running(running)
            return False

        from gi.repository import GLib

        GLib.idle_add(update)
