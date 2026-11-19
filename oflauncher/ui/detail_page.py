"""Game detail page: cover, actions and info."""

from __future__ import annotations

import subprocess
from pathlib import Path

from gi.repository import Adw, Gtk

from .. import config, icons, proton, shortcuts
from ..library import format_playtime, library
from ..models import FIX_LABELS, Game
from ..runner import runner
from .library_page import load_cover_paintable


class DetailPage(Adw.NavigationPage):
    __gtype_name__ = "OFLDetailPage"

    def __init__(self, window) -> None:
        super().__init__(title="Game")
        self.window = window
        self.game_name: str = ""

        self.cover_box = Gtk.Box()
        self.cover_box.set_size_request(250, 375)
        self.cover_box.set_valign(Gtk.Align.START)
        self.cover = Gtk.Picture()
        self.cover.set_size_request(250, 375)
        self.cover.add_css_class("detail-cover")
        self.cover.set_content_fit(Gtk.ContentFit.COVER)
        self.cover_box.append(self.cover)

        self.title_label = Gtk.Label()
        self.title_label.add_css_class("title-2")
        self.title_label.set_xalign(0)
        self.title_label.set_wrap(True)

        self.pill_box = Gtk.Box(spacing=6)
        self.pill_fix = Gtk.Label()
        self.pill_fix.add_css_class("pill")
        self.pill_fix.add_css_class("pill-accent")
        self.pill_runner = Gtk.Label()
        self.pill_runner.add_css_class("pill")
        self.pill_running = Gtk.Label(label="Running")
        self.pill_running.add_css_class("pill")
        self.pill_running.set_visible(False)

        self.info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Buttons
        self.play_btn = self._icon_button("play", "Play", self._on_play)
        self.play_btn.add_css_class("suggested-action")
        self.play_btn.add_css_class("play-button")

        self.stop_btn = self._icon_button("stop", "Stop", lambda *_: runner.stop())
        self.stop_btn.add_css_class("destructive-action")
        self.stop_btn.add_css_class("stop-button")
        self.stop_btn.set_visible(False)

        self.debug_btn = self._icon_button("debug", "Debug", self._on_debug)

        self.log_btn = self._icon_button("env", "Log", lambda *_: window.open_log())

        settings_btn = self._icon_button("edit", "Settings", lambda *_: window.open_game_settings(self.game_name))
        folder_btn = self._icon_button("folder", "Folder", self._on_folder)
        steam_btn = self._icon_button("steam", "Steam", self._on_steam)
        protondb_btn = self._icon_button("external", "ProtonDB", self._on_protondb)
        remove_btn = self._icon_button("trash", "Remove", self._on_remove)
        remove_btn.add_css_class("destructive-action")

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.append(self.play_btn)
        actions.append(self.stop_btn)
        actions.append(self.debug_btn)
        actions.append(self.log_btn)

        links = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        links.append(settings_btn)
        links.append(folder_btn)
        links.append(steam_btn)
        links.append(protondb_btn)
        links.append(remove_btn)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right.set_hexpand(True)
        right.set_valign(Gtk.Align.CENTER)
        right.append(self.title_label)
        right.append(self.pill_box)
        right.append(self.info_box)
        right.append(actions)
        right.append(links)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=28)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.append(self.cover_box)
        content.append(right)

        clamp = Adw.Clamp(maximum_size=880, tightening_threshold=700)
        clamp.set_child(content)

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(clamp)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        header = Adw.HeaderBar()
        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(scroll)
        self.set_child(view)

    def _icon_button(self, icon: str, label: str, handler) -> Gtk.Button:
        btn = Gtk.Button()
        box = Gtk.Box(spacing=6)
        box.append(icons.image(icon, 16))
        box.append(Gtk.Label(label=label))
        btn.set_child(box)
        btn.connect("clicked", handler)
        return btn

    # -- population ---------------------------------------------------------
    def show(self, name: str) -> None:
        self.game_name = name
        game = library.get(name)
        if not game:
            return
        self.set_title(name)
        self.title_label.set_text(name)

        paintable = load_cover_paintable(game.banner)
        if paintable:
            self.cover.set_paintable(paintable)
        else:
            self.cover.set_paintable(icons.paintable("gamepad", 96))

        for pill in (self.pill_fix, self.pill_runner):
            self.pill_box.remove(pill)
        self.pill_fix.set_text(FIX_LABELS.get(game.fix_type, game.fix_type))
        self.pill_runner.set_text("Proton" if game.runner == "proton" else "Wine")
        self.pill_box.append(self.pill_fix)
        self.pill_box.append(self.pill_runner)

        while (child := self.info_box.get_first_child()) is not None:
            self.info_box.remove(child)

        proton_name = game.proton_version or (proton.list_protons() or ["Default"])[0] if game.runner == "proton" else "System Wine"
        rows = [
            ("clock", format_playtime(game.playtime)),
            ("folder", game.executable or "—"),
            ("monitor", f"Runner: {'Proton · ' + proton_name if game.runner == 'proton' else 'Wine'}"),
        ]
        if game.prefix_path:
            rows.insert(1, ("env", f"Prefix: {game.prefix_path}"))
        for icon_name, text in rows:
            row = Gtk.Box(spacing=8)
            row.append(icons.image(icon_name, 16))
            label = Gtk.Label(label=text)
            label.set_ellipsize(3)
            label.set_single_line_mode(True)
            label.add_css_class("dim-label")
            row.append(label)
            self.info_box.append(row)

        self.refresh_state()

    def refresh_state(self) -> None:
        is_current = runner.running and runner.current and runner.current.game_name == self.game_name
        self.play_btn.set_visible(not is_current)
        self.stop_btn.set_visible(bool(is_current))
        self.pill_running.set_visible(bool(is_current))
        if is_current:
            self.play_btn.set_visible(False)
        else:
            self.play_btn.set_visible(True)

    # -- actions ------------------------------------------------------------
    def _on_play(self, *_):
        self.window.launch_game(self.game_name, debug=False)

    def _on_debug(self, *_):
        self.window.launch_game(self.game_name, debug=True)

    def _on_folder(self, *_):
        game = library.get(self.game_name)
        if game and game.game_dir and Path(game.game_dir).is_dir():
            subprocess.Popen(["xdg-open", game.game_dir])

    def _on_steam(self, *_):
        game = library.get(self.game_name)
        if game and game.steam_id:
            subprocess.Popen(["xdg-open", f"https://store.steampowered.com/app/{game.steam_id}"])

    def _on_protondb(self, *_):
        game = library.get(self.game_name)
        if game and game.steam_id:
            subprocess.Popen(["xdg-open", f"https://www.protondb.com/app/{game.steam_id}"])

    def _on_remove(self, *_):
        self.window.confirm_remove(self.game_name)
