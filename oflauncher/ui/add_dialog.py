"""Add-a-game wizard: folder → executable → fix type & cover."""

from __future__ import annotations

from pathlib import Path

from gi.repository import Adw, Gtk

from .. import config, exeicon, icons, steam
from ..library import default_prefix_for, library, scan_executables
from ..models import FIX_LABELS, FIX_PRESETS, Game


class AddGameDialog(Adw.Dialog):
    def __init__(self, window) -> None:
        super().__init__(title="Add a Game")
        self.window = window
        self.game_dir = ""
        self.executables: list[str] = []
        self.chosen_exe = ""
        self.search_results: list[tuple[int, str]] = []
        self.chosen_app_id: int | None = None

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.add_named(self._page_folder(), "folder")
        self.stack.add_named(self._page_executable(), "exe")
        self.stack.add_named(self._page_finalize(), "final")

        self.back_btn = Gtk.Button(label="Back")
        self.back_btn.add_css_class("flat")
        self.back_btn.connect("clicked", self._on_back)
        self.next_btn = Gtk.Button(label="Next")
        self.next_btn.add_css_class("suggested-action")
        self.next_btn.connect("clicked", self._on_next)

        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom.set_margin_top(10)
        bottom.set_margin_bottom(14)
        bottom.set_margin_start(16)
        bottom.set_margin_end(16)
        bottom.set_halign(Gtk.Align.END)
        bottom.append(self.back_btn)
        bottom.append(self.next_btn)

        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        view.add_top_bar(header)
        view.set_content(self.stack)
        view.add_bottom_bar(bottom)

        self.set_child(view)
        self.set_content_width(560)
        self.set_content_height(540)

    # -- page 1: folder -------------------------------------------------------
    def _page_folder(self) -> Gtk.Widget:
        page = Adw.StatusPage()
        page.set_title("Choose a game folder")
        page.set_description(
            "Pick the folder that contains the game.\n"
            "The launcher will scan it for executables."
        )
        page.set_paintable(icons.paintable("folder", 96))

        self.folder_label = Gtk.Label(label="No folder selected")
        self.folder_label.add_css_class("dim-label")
        self.folder_label.set_ellipsize(3)

        choose = Gtk.Button(label="Choose Folder")
        choose.add_css_class("suggested-action")
        choose.add_css_class("pill")
        choose.connect("clicked", self._on_choose_folder)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_halign(Gtk.Align.CENTER)
        box.append(self.folder_label)
        box.append(choose)
        page.set_child(box)
        return page

    def _on_choose_folder(self, *_):
        chooser = Gtk.FileChooserNative.new(
            "Choose game folder", self.window, Gtk.FileChooserAction.SELECT_FOLDER, "Select", "Cancel"
        )
        chooser.set_modal(True)
        chooser.connect("response", self._on_folder_chosen)
        chooser.show()

    def _on_folder_chosen(self, dialog, response):
        if response != Gtk.ResponseType.ACCEPT:
            return
        file = dialog.get_file()
        if not file:
            return
        self.game_dir = file.get_path()
        self.folder_label.set_text(self.game_dir)
        self.executables = scan_executables(self.game_dir)
        self.next_btn.set_sensitive(bool(self.executables))
        if not self.executables:
            self.window.toast("No .exe files found in that folder")

    # -- page 2: executable ---------------------------------------------------
    def _page_executable(self) -> Gtk.Widget:
        self.name_entry = Adw.EntryRow()
        self.name_entry.set_title("Game name")
        name_list = Gtk.ListBox()
        name_list.set_selection_mode(Gtk.SelectionMode.NONE)
        name_list.add_css_class("boxed-list")
        name_list.append(self.name_entry)

        self.exe_list = Gtk.ListBox()
        self.exe_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.exe_list.add_css_class("boxed-list")

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.exe_list)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        wrapper.set_margin_top(18)
        wrapper.set_margin_bottom(6)
        wrapper.set_margin_start(18)
        wrapper.set_margin_end(18)
        wrapper.append(name_list)
        wrapper.append(scroll)
        return wrapper

    # -- page 3: fix + cover --------------------------------------------------
    def _page_finalize(self) -> Gtk.Widget:
        self.fix_combo = Adw.ComboRow()
        self.fix_combo.set_title("Multiplayer fix")
        model = Gtk.StringList.new([FIX_LABELS[k] for k in ("onlinefix", "freetp", "custom", "none")])
        self.fix_combo.set_model(model)
        self.fix_combo.set_selected(0)
        self.fix_combo.connect("notify::selected", self._on_fix_changed)

        self.overrides_entry = Adw.EntryRow()
        self.overrides_entry.set_title("WINEDLLOVERRIDES")

        self.steam_list = Gtk.ListBox()
        self.steam_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.steam_list.add_css_class("boxed-list")

        search_btn = Gtk.Button(label="Search Steam covers")
        search_btn.add_css_class("flat")
        search_btn.set_halign(Gtk.Align.START)
        search_btn.connect("clicked", self._on_search_steam)

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.steam_list)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        group = Adw.PreferencesGroup(title="Fix", description="Overrides are applied when the game starts.")
        group.add(self.fix_combo)
        group.add(self.overrides_entry)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(18)
        box.set_margin_bottom(6)
        box.set_margin_start(18)
        box.set_margin_end(18)
        box.append(group)
        box.append(search_btn)
        box.append(scroll)
        return box

    def _on_fix_changed(self, row, _):
        keys = ("onlinefix", "freetp", "custom", "none")
        key = keys[row.get_selected()]
        self.overrides_entry.set_text(FIX_PRESETS.get(key, ""))

    def _on_search_steam(self, *_):
        name = self.name_entry.get_text().strip()
        if not name:
            return
        self.search_results = steam.search(name)
        while (child := self.steam_list.get_first_child()) is not None:
            self.steam_list.remove(child)
        self.chosen_app_id = None
        for app_id, title in self.search_results:
            row = Adw.ActionRow(title=title, subtitle=f"App {app_id}")
            check = Gtk.CheckButton()
            check.connect("toggled", self._on_pick_steam, app_id)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            self.steam_list.append(row)

    def _on_pick_steam(self, check, app_id):
        if check.get_active():
            self.chosen_app_id = app_id

    # -- navigation -----------------------------------------------------------
    def present(self, parent=None):  # noqa: D102 - PyGObject override
        self.open_add_flow()
        super().present(parent)

    def open_add_flow(self) -> None:
        self.stack.set_visible_child_name("folder")
        self.back_btn.set_visible(False)
        self.next_btn.set_sensitive(True)
        self.next_btn.set_label("Next")

    def _on_back(self, *_):
        name = self.stack.get_visible_child_name()
        if name == "exe":
            self.stack.set_visible_child_name("folder")
            self.back_btn.set_visible(False)
        elif name == "final":
            self.stack.set_visible_child_name("exe")
            self.next_btn.set_label("Next")

    def _on_next(self, *_):
        name = self.stack.get_visible_child_name()
        if name == "folder":
            if not self.executables:
                return
            self._fill_exe_page()
            self.stack.set_visible_child_name("exe")
            self.back_btn.set_visible(True)
        elif name == "exe":
            self.chosen_exe = self._selected_exe()
            if not self.chosen_exe:
                self.window.toast("Select an executable")
                return
            title = self.name_entry.get_text().strip()
            if not title:
                self.window.toast("Enter a game name")
                return
            if library.exists(title):
                self.window.toast("A game with this name already exists")
                return
            self._on_search_steam()
            self.stack.set_visible_child_name("final")
            self.next_btn.set_label("Add Game")
        elif name == "final":
            self._create_game()

    def _fill_exe_page(self) -> None:
        while (child := self.exe_list.get_first_child()) is not None:
            self.exe_list.remove(child)
        self.exe_checks: list[tuple[Gtk.CheckButton, str]] = []
        first = None
        for exe in self.executables:
            check = Gtk.CheckButton()
            row = Adw.ActionRow(title=Path(exe).name, subtitle=exe)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            check.connect("toggled", self._on_pick_exe, exe)
            self.exe_list.append(row)
            self.exe_checks.append((check, exe))
            if first is None:
                first = check
        if first:
            first.set_active(True)
        guessed = Path(self.game_dir).name or "New Game"
        self.name_entry.set_text(guessed)

    def _on_pick_exe(self, check, exe):
        if check.get_active():
            self.chosen_exe = exe

    def _selected_exe(self) -> str:
        for check, exe in self.exe_checks:
            if check.get_active():
                return exe
        return ""

    # -- creation -------------------------------------------------------------
    def _create_game(self) -> None:
        name = self.name_entry.get_text().strip()
        if not name or library.exists(name):
            return
        keys = ("onlinefix", "freetp", "custom", "none")
        fix_type = keys[self.fix_combo.get_selected()]

        game = Game(
            name=name,
            executable=self.chosen_exe,
            game_dir=self.game_dir,
            prefix_path=default_prefix_for(self.game_dir, name),
            runner=config.settings.get("default_runner", "proton"),
            proton_version=config.settings.get("default_proton", ""),
            fix_type=fix_type,
            overrides=self.overrides_entry.get_text().strip(),
            steam_id=self.chosen_app_id,
        )
        library.add(game)
        shortcuts.sync(game)

        icon = exeicon.extract_icon(self.chosen_exe, name)
        if icon:
            game.icon = str(icon)
            library.update(game)

        # Cover art (optional, in background)
        def done(app_id, path):
            if path:
                library.set_banner(name, str(path))
                self.window.refresh_library()
                self.window.toast("Cover art downloaded")
            self.window.refresh_library()

        steam.fetch_in_thread(name, config.COVERS_DIR / name, done)

        self.force_close()
        self.window.refresh_library()
        self.window.toast(f"{name} added to your library")
