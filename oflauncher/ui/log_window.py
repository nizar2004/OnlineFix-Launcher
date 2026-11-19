"""Log window: live process output."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from gi.repository import Adw, GLib, Gtk

from .. import config


class LogWindow(Adw.Window):
    def __init__(self) -> None:
        super().__init__(title="Log", default_width=760, default_height=520)
        self.buffer = Gtk.TextBuffer()
        self.view = Gtk.TextView(buffer=self.buffer)
        self.view.set_editable(False)
        self.view.set_cursor_visible(False)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.set_monospace(True)
        self.view.add_css_class("log-view")
        self.view.set_left_margin(10)
        self.view.set_right_margin(10)
        self.view.set_top_margin(8)
        self.view.set_bottom_margin(8)

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.view)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        clear_btn = Gtk.Button(label="Clear")
        clear_btn.add_css_class("flat")
        clear_btn.connect("clicked", self._on_clear)
        save_btn = Gtk.Button(label="Save…")
        save_btn.add_css_class("flat")
        save_btn.connect("clicked", self._on_save)

        header = Adw.HeaderBar()
        header.pack_start(clear_btn)
        header.pack_end(save_btn)

        view_layout = Adw.ToolbarView()
        view_layout.add_top_bar(header)
        view_layout.set_content(scroll)
        self.set_content(view_layout)

        self._file_path = config.LOGS_DIR / f"session-{datetime.now():%Y%m%d-%H%M%S}.log"

    def append(self, line: str) -> None:
        def do_append() -> bool:
            end = self.buffer.get_end_iter()
            self.buffer.insert(end, line + "\n", -1)
            mark = self.buffer.create_mark(None, self.buffer.get_end_iter(), False)
            self.view.scroll_mark_onscreen(mark)
            self.buffer.delete_mark(mark)
            return False

        GLib.idle_add(do_append)
        try:
            if config.settings.get("keep_log_file", True):
                self._file_path.parent.mkdir(parents=True, exist_ok=True)
                with self._file_path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except Exception:
            pass

    def _on_clear(self, *_):
        self.buffer.set_text("", -1)

    def _on_save(self, *_):
        chooser = Gtk.FileChooserNative.new(
            "Save log", self, Gtk.FileChooserAction.SAVE, "Save", "Cancel"
        )
        chooser.set_modal(True)
        chooser.set_current_name(f"onlinеfix-launcher-{datetime.now():%Y%m%d-%H%M%S}.log".replace("е", "e"))
        chooser.connect("response", self._on_save_response)
        chooser.show()

    def _on_save_response(self, dialog, response):
        if response != Gtk.ResponseType.ACCEPT:
            return
        file = dialog.get_file()
        if not file:
            return
        path = file.get_path()
        text = self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)
        try:
            Path(path).write_text(text, encoding="utf-8")
        except Exception:
            pass
