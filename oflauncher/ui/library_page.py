"""The library page: search, game cards grid and the empty state."""

from __future__ import annotations

from pathlib import Path

from gi.repository import Adw, Gdk, GLib, Gtk

from .. import icons
from ..models import Game

COVER_W, COVER_H = 150, 225


def load_cover_paintable(path: str) -> Gdk.Paintable | None:
    if not path or not Path(path).exists():
        return None
    try:
        data = GLib.Bytes.new(Path(path).read_bytes())
        return Gdk.Texture.new_from_bytes(data)
    except Exception:
        return None


class GameCard(Gtk.Box):
    """A cover card in the library grid."""

    __gtype_name__ = "OFLGameCard"

    def __init__(self, game: Game, on_activate) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("game-card")
        self.game = game

        # Fixed-size wrapper keeps cards at a consistent portrait size.
        self.cover_box = Gtk.Box()
        self.cover_box.set_size_request(COVER_W, COVER_H)

        self.picture = Gtk.Picture()
        self.picture.set_size_request(COVER_W, COVER_H)
        self.picture.add_css_class("card-cover")
        self.picture.set_content_fit(Gtk.ContentFit.COVER)
        self.cover_box.append(self.picture)
        self.set_cover(game.banner)

        self.caption = Gtk.Label(label=game.name)
        self.caption.add_css_class("card-caption")
        self.caption.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        self.caption.set_single_line_mode(True)

        self.append(self.cover_box)
        self.append(self.caption)

        click = Gtk.GestureClick()
        click.connect("released", self._clicked)
        self.add_controller(click)

        self._on_activate = on_activate

    def _clicked(self, gesture, n, x, y):
        self._on_activate(self.game)

    def set_cover(self, path: str) -> None:
        paintable = load_cover_paintable(path)
        if paintable:
            self.picture.set_paintable(paintable)
        else:
            self.picture.set_paintable(icons.paintable("gamepad", 64))


class LibraryPage(Adw.NavigationPage):
    """Root page of the content area."""

    __gtype_name__ = "OFLLibraryPage"

    def __init__(self, window) -> None:
        super().__init__(title="Library")
        self.window = window

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Search your library…")
        self.search.set_hexpand(True)
        self.search.set_size_request(280, -1)
        self.search.connect("search-changed", self._on_search_changed)

        header = Adw.HeaderBar()
        header.set_title_widget(self.search)
        header.pack_start(self._make_add_button())

        # Global stop button — visible only while a game is running.
        self.stop_btn = Gtk.Button(label="Stop")
        self.stop_btn.add_css_class("destructive-action")
        self.stop_btn.add_css_class("flat")
        self.stop_btn.set_visible(False)
        self.stop_btn.set_tooltip_text("Kill the running game")
        self.stop_btn.connect("clicked", lambda *_: window.kill_running_game())
        header.pack_end(self.stop_btn)

        # Grid
        self.flow = Gtk.FlowBox()
        self.flow.set_valign(Gtk.Align.START)
        self.flow.set_max_children_per_line(6)
        self.flow.set_min_children_per_line(2)
        self.flow.set_column_spacing(14)
        self.flow.set_row_spacing(16)
        self.flow.set_margin_top(18)
        self.flow.set_margin_bottom(24)
        self.flow.set_margin_start(24)
        self.flow.set_margin_end(24)
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_filter_func(self._filter_card)

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.flow)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # Empty state
        self.empty = Adw.StatusPage()
        self.empty.set_title("Your library is empty")
        self.empty.set_description(
            "Add games you own to your library to organize them and manage their settings."
        )
        self.empty.set_paintable(icons.paintable("logo", 96))
        self.empty_action = Gtk.Button(label="Add a Game")
        self.empty_action.add_css_class("pill")
        self.empty_action.add_css_class("suggested-action")
        self.empty_action.add_css_class("play-button")
        self.empty_action.connect("clicked", self._on_empty_action)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.append(self.empty_action)
        self.empty.set_child(box)
        self._empty_is_search = False

        overlay = Gtk.Overlay()
        overlay.set_child(scroll)
        overlay.add_overlay(self.empty)
        self.empty.set_halign(Gtk.Align.CENTER)
        self.empty.set_valign(Gtk.Align.CENTER)

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(overlay)
        self.set_child(view)

    def _make_add_button(self) -> Gtk.Widget:
        btn = Gtk.Button()
        content = Adw.ButtonContent(icon_name="list-add-symbolic", label="Add Game")
        btn.set_child(content)
        btn.add_css_class("suggested-action")
        btn.connect("clicked", lambda *_: self.window.open_add_dialog())
        return btn

    # -- population ---------------------------------------------------------
    def set_running(self, running: bool) -> None:
        self.stop_btn.set_visible(running)

    def refresh(self) -> None:
        child = self.flow.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.flow.remove(child)
            child = nxt

        from .. import library as library_module

        for game in library_module.library.all():
            card = GameCard(game, self._open_game)
            self.flow.append(card)
        self._update_empty()

    def _on_search_changed(self, *_args) -> None:
        self.flow.invalidate_filter()
        self._update_empty()

    def _update_empty(self) -> None:
        query = self.search.get_text().strip().casefold()
        has_games = False
        has_matches = False
        child = self.flow.get_first_child()
        while child:
            card = child.get_child()
            if isinstance(card, GameCard):
                has_games = True
                has_matches |= query in card.game.name.casefold()
            child = child.get_next_sibling()

        self._empty_is_search = has_games and not has_matches
        if self._empty_is_search:
            self.empty.set_title("No games found")
            self.empty.set_description("Try a different search term or clear your search.")
            self.empty_action.set_label("Clear Search")
        else:
            self.empty.set_title("Your library is empty")
            self.empty.set_description(
                "Add games you own to your library to organize them and manage their settings."
            )
            self.empty_action.set_label("Add a Game")
        self.empty.set_visible(not has_matches)

    def _on_empty_action(self, *_args) -> None:
        if self._empty_is_search:
            self.search.set_text("")
        else:
            self.window.open_add_dialog()

    def _filter_card(self, card: Gtk.FlowBoxChild) -> bool:
        query = self.search.get_text().strip().lower()
        game_card = card.get_child()
        if not isinstance(game_card, GameCard):
            return False
        return query in game_card.game.name.lower()

    def _open_game(self, game: Game) -> None:
        self.window.open_detail(game.name)
