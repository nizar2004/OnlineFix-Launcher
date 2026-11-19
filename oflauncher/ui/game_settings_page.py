"""Per-game settings page."""

from __future__ import annotations

from pathlib import Path

from gi.repository import Adw, Gtk

from .. import config, proton, shortcuts
from ..library import library
from ..models import FIX_LABELS, FIX_PRESETS, Game


class GameSettingsPage(Adw.NavigationPage):
    __gtype_name__ = "OFLGameSettingsPage"

    def __init__(self, window) -> None:
        super().__init__(title="Game Settings")
        self.window = window
        self.game_name = ""
        self._loading = False

        header = Adw.HeaderBar()

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)

        group_general = Adw.PreferencesGroup(title="General")
        self.name_row = Adw.EntryRow(title="Name")
        group_general.add(self.name_row)

        group_launch = Adw.PreferencesGroup(title="Launch")
        self.exe_row = Adw.ActionRow(title="Executable", subtitle="")
        exe_btn = Gtk.Button(label="Choose")
        exe_btn.add_css_class("flat")
        exe_btn.connect("clicked", self._on_choose_exe)
        self.exe_row.add_suffix(exe_btn)
        self.prefix_row = Adw.ActionRow(title="Wine prefix", subtitle="")
        prefix_btn = Gtk.Button(label="Choose")
        prefix_btn.add_css_class("flat")
        prefix_btn.connect("clicked", self._on_choose_prefix)
        self.prefix_row.add_suffix(prefix_btn)
        prefix_reset_btn = Gtk.Button(label="Reset")
        prefix_reset_btn.add_css_class("flat")
        prefix_reset_btn.connect("clicked", self._on_reset_prefix)
        self.prefix_row.add_suffix(prefix_reset_btn)
        group_launch.add(self.exe_row)
        group_launch.add(self.prefix_row)

        self.runner_row = Adw.ComboRow(title="Runner", model=Gtk.StringList.new(["Proton", "Wine"]))
        self.proton_row = Adw.ComboRow(title="Proton version")
        self.refresh_protons()
        self.runner_row.connect("notify::selected", self._on_runner_changed)
        group_launch.add(self.runner_row)
        group_launch.add(self.proton_row)

        group_fix = Adw.PreferencesGroup(title="Multiplayer fix")
        self.fix_row = Adw.ComboRow(title="Fix type", model=Gtk.StringList.new([FIX_LABELS[k] for k in ("onlinefix", "freetp", "custom", "none")]))
        self.fix_row.connect("notify::selected", self._on_fix_changed)
        group_fix.add(self.fix_row)

        group_env = Adw.PreferencesGroup(title="Overrides and environment")
        self.overrides_row = Adw.EntryRow(title="WINEDLLOVERRIDES")
        self.extra_env_row = Adw.EntryRow(title="Extra environment (KEY=value; comma separated)")
        group_env.add(self.overrides_row)
        group_env.add(self.extra_env_row)

        group_steam = Adw.PreferencesGroup(title="Steam")
        self.steam_row = Adw.EntryRow(title="Steam App ID (for covers, ProtonDB)")
        steam_btn = Gtk.Button(label="Search")
        steam_btn.add_css_class("flat")
        steam_btn.connect("clicked", self._on_search_steam)
        self.steam_row.add_suffix(steam_btn)
        group_steam.add(self.steam_row)

        group_shortcuts = Adw.PreferencesGroup(title="Shortcuts")
        self.desktop_row = Adw.SwitchRow(title="Desktop shortcut")
        self.menu_row = Adw.SwitchRow(title="Application menu shortcut")
        group_shortcuts.add(self.desktop_row)
        group_shortcuts.add(self.menu_row)

        page = Adw.PreferencesPage()
        page.add(group_general)
        page.add(group_launch)
        page.add(group_fix)
        page.add(group_env)
        page.add(group_steam)
        page.add(group_shortcuts)

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(page)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(scroll)
        self.set_child(view)

    # -- helpers ---------------------------------------------------------------
    def refresh_protons(self) -> None:
        protons = ["(app default)"] + proton.list_protons()
        self.proton_row.set_model(Gtk.StringList.new(protons))

    def show(self, name: str) -> None:
        game = library.get(name)
        if not game:
            return
        self.game_name = name
        self._loading = True
        self.set_title(f"{name} — Settings")

        self.name_row.set_text(game.name)
        self.exe_row.set_subtitle(game.executable or "—")
        self.prefix_row.set_subtitle(game.prefix_path or "(default: next to the game)")

        self.runner_row.set_selected(0 if game.runner == "proton" else 1)
        protons = ["(app default)"] + proton.list_protons()
        idx = protons.index(game.proton_version) if game.proton_version in protons else 0
        self.proton_row.set_selected(idx)

        keys = ("onlinefix", "freetp", "custom", "none")
        self.fix_row.set_selected(keys.index(game.fix_type) if game.fix_type in keys else 0)
        self.overrides_row.set_text(game.effective_overrides())
        self.extra_env_row.set_text(
            ", ".join(f"{k}={v}" for k, v in game.parse_extra_env().items())
        )
        self.steam_row.set_text(str(game.steam_id) if game.steam_id else "")
        self.desktop_row.set_active(game.desktop_shortcut)
        self.menu_row.set_active(game.menu_shortcut)
        self.refresh_protons()
        self._loading = False

    # -- events ---------------------------------------------------------------
    def _on_runner_changed(self, row, _):
        self.proton_row.set_sensitive(row.get_selected() == 0)

    def _on_fix_changed(self, row, _):
        if self._loading:
            return
        keys = ("onlinefix", "freetp", "custom", "none")
        self.overrides_row.set_text(FIX_PRESETS.get(keys[row.get_selected()], ""))

    def _on_choose_exe(self, *_):
        chooser = Gtk.FileChooserNative.new(
            "Choose executable", self.window, Gtk.FileChooserAction.OPEN, "Select", "Cancel"
        )
        f = Gtk.FileFilter()
        f.set_name("Windows executables")
        f.add_pattern("*.exe")
        chooser.add_filter(f)
        chooser.set_modal(True)
        chooser.connect("response", self._on_exe_chosen)
        chooser.show()

    def _on_exe_chosen(self, dialog, response):
        if response != Gtk.ResponseType.ACCEPT:
            return
        file = dialog.get_file()
        if not file:
            return
        path = file.get_path()
        self.exe_row.set_subtitle(path)
        if not self.prefix_row.get_subtitle() or self.prefix_row.get_subtitle().startswith("("):
            self.prefix_row.set_subtitle(str(Path(path).parent / "Prefix"))

    def _on_choose_prefix(self, *_):
        chooser = Gtk.FileChooserNative.new(
            "Choose prefix folder", self.window, Gtk.FileChooserAction.SELECT_FOLDER, "Select", "Cancel"
        )
        chooser.set_modal(True)
        chooser.connect("response", self._on_prefix_chosen)
        chooser.show()

    def _on_prefix_chosen(self, dialog, response):
        if response != Gtk.ResponseType.ACCEPT:
            return
        file = dialog.get_file()
        if file:
            self.prefix_row.set_subtitle(file.get_path())

    def _on_reset_prefix(self, *_):
        game = library.get(self.game_name)
        if game:
            from ..library import default_prefix_for

            self.prefix_row.set_subtitle(default_prefix_for(game.game_dir, game.name))

    def _on_search_steam(self, *_):
        name = self.name_row.get_text().strip()
        if not name:
            return
        results = steam_search(name)
        self.steam_row.set_text(str(results[0][0]) if results else "")

    # -- save -------------------------------------------------------------------
    def _on_save(self, *_):
        game = library.get(self.game_name)
        if not game:
            return
        new_name = self.name_row.get_text().strip()
        if not new_name:
            self.window.toast("Name cannot be empty")
            return

        old_shortcuts = (game.desktop_shortcut, game.menu_shortcut)
        old_name = game.name

        game.name = new_name
        game.executable = self.exe_row.get_subtitle() or game.executable
        prefix = self.prefix_row.get_subtitle() or ""
        game.prefix_path = "" if prefix.startswith("(") else prefix
        game.runner = "proton" if self.runner_row.get_selected() == 0 else "wine"
        protons = ["(app default)"] + proton.list_protons()
        sel = self.proton_row.get_selected()
        game.proton_version = "" if sel == 0 else protons[sel]

        keys = ("onlinefix", "freetp", "custom", "none")
        game.fix_type = keys[self.fix_row.get_selected()]
        game.overrides = self.overrides_row.get_text().strip()
        game.extra_env = ", ".join(
            part.strip() for part in self.extra_env_row.get_text().split(",") if "=" in part
        )
        try:
            game.steam_id = int(self.steam_row.get_text().strip()) if self.steam_row.get_text().strip() else None
        except ValueError:
            game.steam_id = None
        game.desktop_shortcut = self.desktop_row.get_active()
        game.menu_shortcut = self.menu_row.get_active()

        if old_name != new_name:
            library.rename(old_name, new_name)
        library.update(game)
        shortcuts.sync(game)
        self.game_name = new_name
        self.window.refresh_library()
        self.window.toast("Game settings saved")
        self.window.nav_view.pop()
        self.window.open_detail(new_name)


def steam_search(term: str):
    from .. import steam

    return steam.search(term)
