"""Downloads page: a small built-in browser plus a download manager.

Games are downloaded from community sources directly inside the launcher —
no external browser needed — and installed to a folder of your choice.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import gi

gi.require_version("WebKit", "6.0")

from gi.repository import Adw, Gio, GLib, Gtk, WebKit

from .. import config, icons, installer, steam
from ..library import default_prefix_for, library
from ..models import Game

HOME_URL = "https://online-fix.me/"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.4 Safari/605.1.15"
)

START_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  body { font-family: sans-serif; background: #15171f; color: #e8ebf2;
         display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
  .card { text-align: center; max-width: 520px; padding: 32px; }
  h1 { font-size: 22px; margin: 0 0 6px; }
  p { color: #9aa3b5; line-height: 1.5; }
  .links { display: flex; flex-direction: column; gap: 10px; margin-top: 22px; }
  a { display: block; padding: 12px 18px; border-radius: 12px; text-decoration: none;
      background: #232838; color: #e8ebf2; font-weight: 600; border: 1px solid #2e3547; }
  a:hover { background: #2b3145; }
  .hint { font-size: 12px; color: #6b7383; margin-top: 20px; }
</style></head>
<body><div class="card">
  <h1>Download games</h1>
  <p>Use the address bar above to visit any game source.
     Downloads are captured by the launcher and installed to your games folder.</p>
  <div class="links">
    <a href="https://online-fix.me/">online-fix.me</a>
  </div>
  <p class="hint">Only download games you legally own.</p>
</div></body></html>
"""


class DownloadItem:
    def __init__(self, download: WebKit.Download, path: Path, row: Adw.ActionRow):
        self.download = download
        self.path = path
        self.row = row
        self.progress = Gtk.ProgressBar()
        self.progress.set_pulse_step(0.08)


class DownloadsPage(Adw.NavigationPage):
    __gtype_name__ = "OFLDownloadsPage"

    def __init__(self, window) -> None:
        super().__init__(title="Downloads")
        self.window = window
        self._webview: WebKit.WebView | None = None
        self._items: list[DownloadItem] = []

        # -- header / browser controls --------------------------------------
        self.url_entry = Gtk.Entry()
        self.url_entry.set_hexpand(True)
        self.url_entry.set_placeholder_text("Search or enter address…")
        self.url_entry.connect("activate", self._on_url_activate)

        header = Adw.HeaderBar()
        header.set_title_widget(self.url_entry)

        self.back_btn = Gtk.Button()
        self.back_btn.set_icon_name("go-previous-symbolic")
        self.back_btn.set_tooltip_text("Back")
        self.back_btn.connect("clicked", lambda *_: self._webview and self._webview.go_back())
        self.forward_btn = Gtk.Button()
        self.forward_btn.set_icon_name("go-next-symbolic")
        self.forward_btn.set_tooltip_text("Forward")
        self.forward_btn.connect("clicked", lambda *_: self._webview and self._webview.go_forward())
        self.reload_btn = Gtk.Button()
        self.reload_btn.set_icon_name("view-refresh-symbolic")
        self.reload_btn.set_tooltip_text("Reload")
        self.reload_btn.connect("clicked", lambda *_: self._webview and self._webview.reload())
        self.home_btn = Gtk.Button()
        self.home_btn.set_icon_name("go-home-symbolic")
        self.home_btn.set_tooltip_text("Home")
        self.home_btn.connect("clicked", lambda *_: self._load_home())
        header.pack_start(self.back_btn)
        header.pack_start(self.forward_btn)
        header.pack_start(self.reload_btn)
        header.pack_end(self.home_btn)

        # -- downloads shelf ---------------------------------------------------
        self.save_dir_label = Gtk.Label()
        self.save_dir_label.add_css_class("dim-label")
        self.save_dir_label.set_ellipsize(3)
        self.save_dir_label.set_hexpand(True)
        self.save_dir_label.set_xalign(0)

        change_btn = Gtk.Button(label="Change")
        change_btn.add_css_class("flat")
        change_btn.connect("clicked", self._on_change_dir)

        save_box = Gtk.Box(spacing=8)
        icon = icons.image("folder", 16)
        save_box.append(icon)
        save_box.append(self.save_dir_label)
        save_box.append(change_btn)

        self.downloads_list = Gtk.ListBox()
        self.downloads_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.downloads_list.add_css_class("boxed-list")
        self.downloads_list.set_placeholder(self._empty_placeholder())

        downloads_scroll = Gtk.ScrolledWindow()
        downloads_scroll.set_child(self.downloads_list)
        downloads_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        downloads_scroll.set_max_content_height(180)
        downloads_scroll.set_propagate_natural_height(True)

        shelf_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        shelf_inner.set_margin_top(12)
        shelf_inner.set_margin_bottom(12)
        shelf_inner.set_margin_start(16)
        shelf_inner.set_margin_end(16)
        shelf_inner.append(save_box)
        shelf_inner.append(downloads_scroll)

        self.shelf = Gtk.Revealer()
        self.shelf.set_child(shelf_inner)
        self.shelf.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.shelf.set_reveal_child(False)

        # -- webview -----------------------------------------------------------
        self.web_overlay = Gtk.Overlay()

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(self.web_overlay)
        content_box.append(self.shelf)

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(content_box)
        self.set_child(view)

    # -- webview lifecycle -------------------------------------------------------
    def ensure_webview(self) -> WebKit.WebView:
        if self._webview is not None:
            return self._webview

        settings = WebKit.Settings()
        settings.set_user_agent(USER_AGENT)
        settings.set_enable_developer_extras(False)
        self._webview = WebKit.WebView(settings=settings)
        self._webview.set_hexpand(True)
        self._webview.set_vexpand(True)

        self._webview.connect("load-changed", self._on_load_changed)
        self._webview.connect("load-failed", self._on_load_failed)
        self._webview.connect("create", self._on_create)
        self._webview.connect("decide-policy", self._on_decide_policy)

        # In WebKitGTK 6.0 downloads start on the network session.
        session = self._webview.get_network_session()
        if session is not None:
            session.connect("download-started", self._on_download_started)

        self.web_overlay.set_child(self._webview)
        self._load_home()
        return self._webview

    def _load_home(self) -> None:
        web = self.ensure_webview()
        web.load_html(START_HTML, HOME_URL)
        self.url_entry.set_text("")

    # -- navigation ----------------------------------------------------------------
    def _on_url_activate(self, entry: Gtk.Entry):
        text = entry.get_text().strip()
        if not text or self._webview is None:
            return
        if "://" not in text:
            if " " in text or "." not in text:
                text = "https://online-fix.me/?s=" + GLib.uri_escape_string(text, None, False)
            else:
                text = "https://" + text
        self._webview.load_uri(text)

    def _on_load_changed(self, webview, event):
        if event == WebKit.LoadEvent.STARTED:
            self.url_entry.set_text(webview.get_uri() or "")
        elif event == WebKit.LoadEvent.FINISHED:
            self.url_entry.set_text(webview.get_uri() or "")

    def _on_load_failed(self, webview, event, failing_uri, error):
        # Show a friendly page for navigation failures; ignore subresource errors.
        if event in (WebKit.LoadEvent.STARTED, WebKit.LoadEvent.COMMITTED):
            html = f"<body style='font-family:sans-serif;background:#15171f;color:#e8ebf2;display:flex;align-items:center;justify-content:center;height:95vh'><div style='text-align:center'><h2>Could not load</h2><p style='color:#9aa3b5'>{GLib.markup_escape_text(failing_uri, -1)}</p></div></body>"
            webview.load_alternate_html(html, failing_uri, failing_uri)
            return True
        return False

    def _on_create(self, webview, navigation_action):
        uri = navigation_action.get_navigation_action().get_original_uri()
        if uri:
            GLib.idle_add(self._webview.load_uri, uri)
        return None

    # -- downloads -------------------------------------------------------------------
    def _on_decide_policy(self, webview, decision, decision_type):
        """Turn file responses into launcher downloads."""
        if decision_type == WebKit.PolicyDecisionType.RESPONSE:
            try:
                response = decision.get_response()
                mime = (response.get_mime_type() or "").lower()
                headers = response.get_http_headers()
                disposition = (headers.get_one("Content-Disposition") or "") if headers else ""
                is_attachment = "attachment" in disposition.lower()
                is_download = (
                    mime == ""
                    or mime.startswith(("application/octet-stream", "application/zip", "application/x-rar", "application/x-7z", "application/x-cd-image", "application/vnd.rar"))
                    or mime.endswith((".zip", ".rar", ".7z", ".iso"))
                )
                if is_attachment or is_download:
                    WebKit.policy_decision_download(decision)
                    return True
            except Exception:
                pass
            decision.use()
            return True
        decision.use()
        return True

    def _on_download_started(self, session, download: WebKit.Download):
        dest_dir = self._download_dir()
        suggested = download.get_suggested_name() or "download.bin"
        dest = dest_dir / suggested
        n = 2
        while dest.exists():
            dest = dest_dir / f"{dest.stem} ({n}){dest.suffix}"
            n += 1

        row = Adw.ActionRow(title=suggested, subtitle=f"Saving to {dest_dir}")
        progress = Gtk.ProgressBar()
        progress.set_size_request(140, -1)
        progress.set_valign(Gtk.Align.CENTER)
        row.add_suffix(progress)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.add_css_class("flat")
        cancel_btn.add_css_class("destructive-action")
        cancel_btn.connect("clicked", lambda *_: download.cancel())
        row.add_suffix(cancel_btn)

        self.downloads_list.append(row)
        self.shelf.set_reveal_child(True)
        item = DownloadItem(download, dest, row)
        self._items.append(item)

        download.connect("notify::received-data-bytes", self._on_progress, item)
        download.connect("finished", self._on_download_finished, item)
        download.connect("failed", self._on_download_failed, item)

        # WebKit asks where to save.
        def decide_destination(dl, suggested_name):
            dl.set_destination("file://" + str(dest))
            return True

        download.connect("decide-destination", decide_destination)

    def _on_progress(self, download, _pspec, item: DownloadItem):
        received = download.get_received_data_bytes()
        estimated = download.get_estimated_content_bytes()
        if estimated > 0:
            item.progress.set_fraction(min(1.0, received / estimated))
        else:
            item.progress.pulse()

    def _on_download_finished(self, download, item: DownloadItem):
        item.progress.set_fraction(1.0)
        self._remove_row_controls(item, keep_row=True)
        item.row.set_subtitle(f"Downloaded: {item.path}")

        install_btn = Gtk.Button(label="Install…")
        install_btn.add_css_class("suggested-action")
        install_btn.connect("clicked", self._on_install_clicked, item)
        item.row.add_suffix(install_btn)

        open_btn = Gtk.Button(label="Folder")
        open_btn.add_css_class("flat")
        open_btn.connect("clicked", lambda *_: self._open_path(item.path.parent))
        item.row.add_suffix(open_btn)

        self.window.toast(f"Download finished: {item.path.name}")
        self.shelf.set_reveal_child(True)

    def _on_download_failed(self, download, error, item: DownloadItem):
        item.row.set_subtitle(f"Failed: {error.message if hasattr(error, 'message') else error}")
        self._remove_row_controls(item, keep_row=True)

    def _remove_row_controls(self, item: DownloadItem, keep_row: bool) -> None:
        # Buttons live as suffixes; rebuild the row suffixes by removing them.
        child = item.row.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            if isinstance(child, (Gtk.Button, Gtk.ProgressBar)):
                item.row.remove(child)
            child = nxt

    def _on_install_clicked(self, btn, item: DownloadItem):
        self.window.install_from_archive(str(item.path))

    def _open_path(self, path: Path) -> None:
        import subprocess

        subprocess.Popen(["xdg-open", str(path)])

    def _empty_placeholder(self) -> Gtk.Widget:
        label = Gtk.Label(label="No downloads yet")
        label.add_css_class("dim-label")
        label.set_margin_top(8)
        label.set_margin_bottom(8)
        return label

    # -- save location --------------------------------------------------------------
    def _download_dir(self) -> Path:
        return Path(config.settings.get("downloads_dir") or (config.DATA_DIR / "Downloads"))

    def refresh(self) -> None:
        self.save_dir_label.set_text(f"Save downloads to: {self._download_dir()}")

    def _on_change_dir(self, *_):
        chooser = Gtk.FileChooserNative.new(
            "Choose download location", self.window, Gtk.FileChooserAction.SELECT_FOLDER, "Select", "Cancel"
        )
        chooser.set_modal(True)
        chooser.set_current_folder(Gio.File.new_for_path(str(self._download_dir())))
        chooser.connect("response", self._on_dir_chosen)
        chooser.show()

    def _on_dir_chosen(self, dialog, response):
        if response != Gtk.ResponseType.ACCEPT:
            return
        file = dialog.get_file()
        if not file:
            return
        config.settings.set("downloads_dir", file.get_path())
        config.settings.save()
        self.refresh()
        self.window.toast("Download location updated")
