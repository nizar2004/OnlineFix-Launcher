"""Application settings dialog (libadwaita preferences) and About."""

from __future__ import annotations

from pathlib import Path

from gi.repository import Adw, Gtk

from .. import __version__, config, proton
from ..library import library
from ..models import FIX_LABELS


class SettingsDialog(Adw.PreferencesDialog):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window

        page = Adw.PreferencesPage()
        self.add(page)

        # -- folders ---------------------------------------------------------
        folders = Adw.PreferencesGroup(title="Folders")
        self.installs_row = self._dir_row("Games folder", config.settings.get("installs_dir"), "installs_dir")
        self.downloads_row = self._dir_row("Downloads folder", config.settings.get("downloads_dir"), "downloads_dir")
        folders.add(self.installs_row)
        folders.add(self.downloads_row)
        page.add(folders)

        # -- defaults ----------------------------------------------------------
        defaults = Adw.PreferencesGroup(title="Defaults", description="Used when adding new games.")
        self.runner_row = Adw.ComboRow(title="Default runner", model=Gtk.StringList.new(["Proton", "Wine"]))
        self.runner_row.set_selected(0 if config.settings.get("default_runner") == "proton" else 1)
        self.runner_row.connect("notify::selected", self._on_runner_changed)

        protons = ["(newest installed)"] + proton.list_protons()
        self.proton_row = Adw.ComboRow(title="Default Proton", model=Gtk.StringList.new(protons))
        saved = config.settings.get("default_proton", "")
        if saved in protons:
            self.proton_row.set_selected(protons.index(saved))
        self.proton_row.connect("notify::selected", self._on_proton_changed)

        fixes = [FIX_LABELS[k] for k in ("onlinefix", "freetp", "custom", "none")]
        self.fix_row = Adw.ComboRow(title="Default fix", model=Gtk.StringList.new(fixes))
        keys = ("onlinefix", "freetp", "custom", "none")
        saved_fix = config.settings.get("default_fix_type", "onlinefix")
        if saved_fix in keys:
            self.fix_row.set_selected(keys.index(saved_fix))
        self.fix_row.connect("notify::selected", self._on_fix_changed)

        defaults.add(self.runner_row)
        defaults.add(self.proton_row)
        defaults.add(self.fix_row)
        page.add(defaults)

        # -- behavior ----------------------------------------------------------
        behavior = Adw.PreferencesGroup(title="Behavior")
        self.log_row = Adw.SwitchRow(title="Keep log files", subtitle="Write game output under ~/.local/state")
        self.log_row.set_active(bool(config.settings.get("keep_log_file", True)))
        self.log_row.connect("notify::active", self._on_log_changed)
        behavior.add(self.log_row)
        page.add(behavior)

        # -- about -------------------------------------------------------------
        about_group = Adw.PreferencesGroup()
        about_btn = Gtk.Button(label="About OnlineFix Launcher")
        about_btn.add_css_class("flat")
        about_btn.set_halign(Gtk.Align.CENTER)
        about_btn.connect("clicked", self._on_about)
        about_group.add(about_btn)
        page.add(about_group)

    # -- rows -----------------------------------------------------------------
    def _dir_row(self, title: str, value: str, key: str) -> Adw.ActionRow:
        row = Adw.ActionRow(title=title, subtitle=value)
        btn = Gtk.Button(label="Change")
        btn.add_css_class("flat")
        btn.connect("clicked", self._on_change_dir, key, row)
        row.add_suffix(btn)
        return row

    def _on_change_dir(self, btn, key: str, row: Adw.ActionRow):
        chooser = Gtk.FileChooserNative.new(
            "Choose folder", self.window, Gtk.FileChooserAction.SELECT_FOLDER, "Select", "Cancel"
        )
        chooser.set_modal(True)
        chooser.connect("response", self._on_dir_chosen, key, row)
        chooser.show()

    def _on_dir_chosen(self, dialog, response, key: str, row: Adw.ActionRow):
        if response != Gtk.ResponseType.ACCEPT:
            return
        file = dialog.get_file()
        if not file:
            return
        path = file.get_path()
        config.settings.set(key, path)
        config.settings.save()
        row.set_subtitle(path)

    def _on_runner_changed(self, row, _):
        config.settings.set("default_runner", "proton" if row.get_selected() == 0 else "wine")
        config.settings.save()

    def _on_proton_changed(self, row, _):
        model = row.get_model()
        value = model.get_string(row.get_selected())
        config.settings.set("default_proton", "" if row.get_selected() == 0 else value)
        config.settings.save()

    def _on_fix_changed(self, row, _):
        keys = ("onlinefix", "freetp", "custom", "none")
        config.settings.set("default_fix_type", keys[row.get_selected()])
        config.settings.save()

    def _on_log_changed(self, row, _):
        config.settings.set("keep_log_file", row.get_active())
        config.settings.save()

    def _on_about(self, *_):
        from .. import APP_NAME, APP_ID

        about = Adw.AboutDialog()
        about.set_application_name(APP_NAME)
        about.set_application_icon(APP_ID)
        about.set_version(__version__)
        about.set_comments("Run games with community multiplayer fixes on Linux.")
        about.set_website("https://github.com/nizar2004/OnlineFix-Launcher")
        about.set_issue_url("https://github.com/nizar2004/OnlineFix-Launcher/issues")
        about.set_license_type(Gtk.License.MIT_X11)
        about.set_developer_name("nizar2004")
        about.present(self.window)
