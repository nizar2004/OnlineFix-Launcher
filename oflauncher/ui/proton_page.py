"""Proton runners page: list, download GE-Proton, open folder."""

from __future__ import annotations

import subprocess
from pathlib import Path

from gi.repository import Adw, GLib, Gtk

from .. import icons, proton
from ..library import run_in_thread


class ProtonPage(Adw.NavigationPage):
    __gtype_name__ = "OFLProtonPage"

    def __init__(self, window) -> None:
        super().__init__(title="Runners")
        self.window = window

        header = Adw.HeaderBar()
        refresh = Gtk.Button()
        refresh.set_child(Adw.ButtonContent(icon_name="", label="Refresh"))
        box_btn = Gtk.Box(spacing=6)
        box_btn.append(icons.image("refresh", 16))
        box_btn.append(Gtk.Label(label="Refresh"))
        refresh.set_child(box_btn)
        refresh.connect("clicked", lambda *_: self.refresh())
        header.pack_start(refresh)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.add_css_class("boxed-list")

        self.progress_row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.progress_row_box.set_visible(False)
        self.progress_label = Gtk.Label(label="")
        self.progress_label.add_css_class("dim-label")
        self.progress_label.set_xalign(0)
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_hexpand(True)
        self.progress_row_box.append(self.progress_label)
        self.progress_row_box.append(self.progress_bar)

        download_btn = Gtk.Button()
        dl_box = Gtk.Box(spacing=6)
        dl_box.append(icons.image("download", 16))
        dl_box.append(Gtk.Label(label="Download latest GE-Proton"))
        download_btn.set_child(dl_box)
        download_btn.add_css_class("suggested-action")
        download_btn.connect("clicked", self._on_download)

        install_group = Adw.PreferencesGroup(title="GE-Proton", description="Latest build from GloriousEggroll.")
        install_group.add(download_btn)
        install_group.add(self.progress_row_box)

        installed_group = Adw.PreferencesGroup(title="Installed runners")
        installed_group.add(self.list_box)

        open_btn = Gtk.Button(label="Open compatibilitytools.d")
        open_btn.add_css_class("flat")
        open_btn.set_halign(Gtk.Align.CENTER)
        open_btn.connect("clicked", self._on_open_dir)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_margin_top(18)
        content.set_margin_bottom(24)
        content.set_margin_start(18)
        content.set_margin_end(18)
        content.append(install_group)
        content.append(installed_group)
        content.append(open_btn)

        clamp = Adw.Clamp(maximum_size=720, tightening_threshold=600)
        clamp.set_child(content)
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(clamp)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(scroll)
        self.set_child(view)

    def refresh(self) -> None:
        while (child := self.list_box.get_first_child()) is not None:
            self.list_box.remove(child)
        versions = proton.list_protons()
        if not versions:
            empty = Adw.ActionRow(
                title="No Proton builds installed",
                subtitle="Download GE-Proton to run games, or install system Wine.",
            )
            self.list_box.append(empty)
        for name in versions:
            path = proton.compat_dir() / name
            row = Adw.ActionRow(title=name, subtitle=str(path))
            badge = Gtk.Label(label="Proton")
            badge.add_css_class("pill")
            badge.add_css_class("pill-accent")
            row.add_suffix(badge)
            self.list_box.append(row)
        wine = proton.system_wine()
        if wine:
            row = Adw.ActionRow(title="System Wine", subtitle=wine)
            badge = Gtk.Label(label="Wine")
            badge.add_css_class("pill")
            row.add_suffix(badge)
            self.list_box.append(row)

    def _on_open_dir(self, *_):
        d = proton.ensure_compat_dir()
        subprocess.Popen(["xdg-open", str(d)])

    # -- download -------------------------------------------------------------
    def _on_download(self, *_):
        if self.progress_row_box.get_visible():
            return
        self.window.toast("Looking up the latest GE-Proton release…")

        def worker():
            info = proton.latest_ge_info()
            GLib.idle_add(self._start_download, info)

        run_in_thread(worker)

    def _start_download(self, info) -> bool:
        if not info or not info.get("url"):
            self.window.toast("Could not fetch release info (network?)")
            return False
        self.progress_row_box.set_visible(True)
        self.progress_bar.set_fraction(0.0)
        self.progress_label.set_text(f"Downloading {info['name']}…")
        self._cancelled = False

        def progress(fraction, text):
            GLib.idle_add(self._update_progress, fraction, text)

        def done(ok, message):
            GLib.idle_add(self._finish_download, ok, message)

        def cancelled():
            return self._cancelled

        run_in_thread(proton.download_and_install, info["url"], progress, done, cancelled)
        return False

    def _update_progress(self, fraction: float, text: str) -> bool:
        self.progress_bar.set_fraction(max(0.0, min(1.0, fraction)))
        self.progress_label.set_text(text)
        return False

    def _finish_download(self, ok: bool, message: str) -> bool:
        self.progress_row_box.set_visible(False)
        if ok:
            self.window.toast("GE-Proton installed")
        else:
            self.window.toast(f"Install failed: {message}")
        self.refresh()
        return False
