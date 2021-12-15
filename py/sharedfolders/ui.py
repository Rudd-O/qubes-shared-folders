#!/usr/bin/python3

import os
import re
import subprocess
from typing import Any, Optional, Union

import gi  # type: ignore

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, Gtk, Gdk, GObject  # type: ignore

from sharedfolders import (
    RESPONSES,
    get_vm_list,
    DecisionMatrix,
    Response,
    ConnectToFolderPolicy,
    is_disp,
)


def search_for_ui_file(file: str) -> str:
    for trial in [
        os.path.join("ui", file),
        os.path.join("/usr/share/qubes-shared-folders/ui", file),
    ]:
        if os.path.exists(trial):
            return trial
    raise FileNotFoundError(file)


def in_list(model: Gtk.ListStore, string: str) -> Union[int, bool]:
    for n, v in enumerate(model):
        if v[0] == string:
            return n
    return False


def ensure_in_list(model: Gtk.ListStore, string: str) -> int:
    inlist = in_list(model, string)
    if inlist is False:
        model.append((string,))
        return len(model) - 1
    else:
        return inlist


def add_css(css: bytes) -> None:
    prov = Gtk.CssProvider()
    ctx = Gtk.StyleContext()
    ctx.add_provider_for_screen(
        Gdk.Display.get_default_screen(Gdk.Display.get_default()),
        prov,
        Gtk.STYLE_PROVIDER_PRIORITY_USER,
    )
    prov.load_from_data(css)


class AuthorizationDialog(object):

    response = RESPONSES.DENY_ONETIME

    def __init__(self, client: str, server: str, folder: str):
        builder = Gtk.Builder()
        builder.add_from_file(search_for_ui_file("authorization-dialog.ui"))
        self.builder = builder

        add_css(
            b"""
            .folder {
                background-color: @theme_unfocused_base_color;
                border: 1px solid @borders;
                border-radius: 8px;
                padding: 8px;
            }
            .action-area {
                border-top: 1px solid @borders;
            }
            .action-area button.left {
                border-right: 1px solid @borders;
                border-radius: 0;
            }
            .action-area button.right {
                border-left: 1px solid @borders;
                border-radius: 0;
            }
            .main-face {
                padding: 18px;
                padding-left: 28px;
                padding-right: 28px;
                padding-bottom: 0;
            }
         """
        )

        self.dialog = builder.get_object("dialog")
        self.dialog.set_title("Folder share request from %(client)s" % locals())
        self.builder.connect_signals(self)
        if is_disp(client) or is_disp(server):
            self.builder.get_object("option_remember").set_sensitive(False)
        self.builder.get_object("option_deny").set_active(True)
        self.builder.get_object("text").set_markup(
            self.builder.get_object("text").get_label() % locals()
        )
        self.builder.get_object("explanation").set_markup(
            self.builder.get_object("explanation").get_label() % locals()
        )
        folder_label = self.builder.get_object("folder")
        folder_label.set_text(folder)
        folder_label.get_style_context().add_class("folder")
        self.builder.get_object("dialog-action-area").get_style_context().add_class(
            "action-area"
        )
        self.builder.get_object("main-face").get_style_context().add_class("main-face")
        self.builder.get_object("ok").get_style_context().add_class("right")
        self.builder.get_object("folder-share-manager").get_style_context().add_class(
            "left"
        )
        self.collect_response()
        self.prior_remember_active = None
        self.prior_remember_sensitive = None

    def open_folder_share_manager(self, *unused_args):
        subprocess.call(["bash", "-c", "qvm-folder-share-manager & disown -h"])

    def block_selected(self, radio: Gtk.RadioButton) -> None:
        if radio.get_active():
            self.prior_remember_active = self.builder.get_object(
                "option_remember"
            ).get_active()
            self.prior_remember_sensitive = self.builder.get_object(
                "option_remember"
            ).get_sensitive()
            self.builder.get_object("option_remember").set_active(True)
            self.builder.get_object("option_remember").set_sensitive(False)
        else:
            self.builder.get_object("option_remember").set_active(
                self.prior_remember_active
            )
            self.builder.get_object("option_remember").set_sensitive(
                self.prior_remember_sensitive
            )

    def show_all(self) -> None:
        self.dialog.show_all()

    def closed(self, *unused_args: Any) -> None:
        Gtk.main_quit()

    def destroyed(self, *unused_args: Any) -> None:
        Gtk.main_quit()

    def collect_response(self) -> None:
        table = [
            ("option_deny", RESPONSES.DENY_ONETIME),
            ("option_allow", RESPONSES.ALLOW_ONETIME),
            ("option_block", RESPONSES.BLOCK),
        ]
        for objn, resp in table:
            if self.builder.get_object(objn).get_active():
                self.response = resp
        if not self.response.is_block():
            if self.builder.get_object("option_remember").get_active():
                if self.response is RESPONSES.ALLOW_ONETIME:
                    self.response = RESPONSES.ALLOW_ALWAYS
                elif self.response is RESPONSES.DENY_ONETIME:
                    self.response = RESPONSES.DENY_ALWAYS

    def dialog_response_cb(self, unused_dialog: Any, response: int) -> None:
        if response == 1:
            assert 0, "Folder share manager not implemented"
        elif response == -4:
            # User closed the dialog, we exit with the default response.
            self.dialog.destroy()
        elif response == 0:
            # User made an affirmative choice.
            self.collect_response()
            self.dialog.destroy()

    def run(self) -> Response:
        self.show_all()
        Gtk.main()
        return self.response


class FolderShareManager(Gtk.Window):  # type: ignore
    starting_decision_matrix = DecisionMatrix()
    working_decision_matrix = DecisionMatrix()

    def __init__(self, matrix: Optional[DecisionMatrix] = None) -> None:
        self.vm_list = Gtk.ListStore()
        Gtk.Window.__init__(self)
        GObject.signal_new(
            "save", self, GObject.SIGNAL_RUN_LAST, GObject.TYPE_PYOBJECT, ()
        )

        self.set_default_size(600, 400)
        self.set_title("Folder share manager")
        self.set_border_width(0)
        self.connect("delete-event", self.close_attempt)
        self.connect("destroy", self.quit)

        add_css(
            b"""
            .individual-settings-container {
                background-color: @theme_unfocused_base_color;
                border: 1px solid @borders;
                border-radius: 8px;
            }
            .individual-settings-row {
                border-bottom: 1px solid @borders;
                padding-top: 8px;
                padding-bottom: 8px;
                padding-left: 12px;
                padding-right: 12px;
            }
            .add-button {
                margin: 8px;
                margin-right: 12px;
            }
         """
        )
        self.settings_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.settings_container.set_spacing(8)

        l = Gtk.Label("Allowed")
        l.set_markup("<b>Allowed</b>")
        l.set_xalign(0.0)
        self.settings_container.add(l)

        self.allowed_shares_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        icon = Gio.ThemedIcon(name="list-add")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        button = Gtk.Button()
        button.get_style_context().add_class("add-button")
        button.set_halign(Gtk.Align.END)
        button.add(image)
        button.connect(
            "clicked", lambda *_: self.add_row(self.allowed_shares_list, "", "", "")
        )
        self.allowed_shares_list.add(button)
        allowed_shares_list_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        allowed_shares_list_container.add(self.allowed_shares_list)
        allowed_shares_list_container.get_style_context().add_class(
            "individual-settings-container"
        )
        self.settings_container.add(allowed_shares_list_container)

        l = Gtk.Label("Denied")
        l.set_markup("<b>Denied</b>")
        l.set_xalign(0.0)
        self.settings_container.add(l)

        self.denied_shares_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        icon = Gio.ThemedIcon(name="list-add")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        image.show()
        button = Gtk.Button()
        button.get_style_context().add_class("add-button")
        button.set_halign(Gtk.Align.END)
        button.add(image)
        button.connect(
            "clicked", lambda *_: self.add_row(self.denied_shares_list, "", "", "")
        )
        self.denied_shares_list.add(button)
        denied_shares_list_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        denied_shares_list_container.add(self.denied_shares_list)
        denied_shares_list_container.get_style_context().add_class(
            "individual-settings-container"
        )
        self.settings_container.add(denied_shares_list_container)

        scrolledwindow = Gtk.ScrolledWindow()
        scrolledwindow.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolledwindow.add(self.settings_container)
        scrolledwindow.set_border_width(18)
        self.add(scrolledwindow)

        header = Gtk.HeaderBar()
        header.set_title(self.get_title())
        header.set_has_subtitle(False)
        self.set_titlebar(header)

        icon = Gio.ThemedIcon(name="document-save-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        save = Gtk.Button()
        save.set_tooltip_text("Exit saving settings changes")
        save.add(image)
        image.show()

        def destroy_if_successful() -> None:
            if not self.emit("delete-event", Gdk.Event(Gdk.EventType.DELETE)):
                self.destroy()

        save.connect("clicked", lambda *_: destroy_if_successful())
        header.pack_end(save)

        icon = Gio.ThemedIcon(name="document-revert-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        revert = Gtk.Button()
        revert.set_tooltip_text("Revert changes")
        revert.add(image)
        image.show()
        revert.connect("clicked", lambda *_: self.revert())
        header.pack_start(revert)

        if matrix is None:
            self.starting_decision_matrix = DecisionMatrix.load()
        else:
            self.starting_decision_matrix = matrix

        self.revert()

    def revert(self) -> None:
        self.working_decision_matrix = self.starting_decision_matrix.copy()
        self.display_decision_matrix(self.working_decision_matrix)

    def update_working_decision_matrix(self) -> None:
        for f, decision in list(self.working_decision_matrix.items()):
            if decision.response.is_onetime():
                continue
            del self.working_decision_matrix[f]
        for obj, response in [
            (self.allowed_shares_list, RESPONSES.ALLOW_ALWAYS),
            (self.denied_shares_list, RESPONSES.DENY_ALWAYS),
        ]:
            for row in obj.get_children():
                try:
                    source, target, folder, _ = row.get_children()
                except ValueError:
                    # This is the add button row.  We ignore it.
                    continue
                source = source.get_model()[int(source.get_active())][0]
                target = target.get_model()[int(target.get_active())][0]
                folder = folder.get_text()
                self.working_decision_matrix.add_decision(
                    source, target, folder, response
                )
        self.starting_decision_matrix = self.working_decision_matrix.copy()

    def save(self) -> None:
        exc = None
        try:
            self.update_working_decision_matrix()
        except Exception as e:
            exc = e
            title = "Policy error"
            message = "One of your share policies has a problem:\n\n%s" % e
        try:
            self.working_decision_matrix.save()
            ConnectToFolderPolicy.apply_policy_changes_from(
                self.working_decision_matrix
            )
        except Exception as f:
            exc = f
            title = "Problem while saving"
            message = "There was an error saving or enabling policy changes:\n\n%s" % f

        if exc is not None:
            d = Gtk.MessageDialog(
                self,
                Gtk.DialogFlags.DESTROY_WITH_PARENT,
                Gtk.MessageType.ERROR,
                Gtk.ButtonsType.CLOSE,
            )
            d.set_markup("""<big><b>%s</b></big>""" % title)
            d.format_secondary_text("%s" % message)
            d.show_all()
            d.set_modal(True)
            d.connect("response", lambda *_: d.destroy())
            raise exc

    def clear_rows(self) -> None:
        for obj in [self.allowed_shares_list, self.denied_shares_list]:
            for row in obj.get_children():
                if not isinstance(row, Gtk.Button):
                    obj.remove(row)
                    row.destroy()

    def display_decision_matrix(self, matrix: DecisionMatrix) -> None:
        self.starting_decision_matrix = matrix
        self.working_decision_matrix = matrix.copy()
        self.clear_rows()
        for x in self.working_decision_matrix.values():
            if not x.response.is_onetime():
                if x.response.is_allow():
                    obj = self.allowed_shares_list
                else:
                    obj = self.denied_shares_list
                self.add_row(obj, x.source, x.target, x.folder)

    def get_vm_list(self) -> Gtk.ListStore:
        if len(self.vm_list) == 0:
            v = get_vm_list()
            self.vm_list = Gtk.ListStore(str)
            for x in v:
                self.vm_list.append((x,))
        return self.vm_list

    def add_row(
        self, towhat: Gtk.Box, source_s: str, target_s: str, folder_s: str
    ) -> None:
        share_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        share_row.get_style_context().add_class("individual-settings-row")
        share_row.set_spacing(6)
        source = Gtk.ComboBox()
        source.set_model(self.get_vm_list())
        if source_s:
            source.set_active(ensure_in_list(source.get_model(), source_s))
        cell = Gtk.CellRendererText()
        source.pack_start(cell, False)
        source.add_attribute(cell, "text", 0)

        target = Gtk.ComboBox()
        target.set_model(self.get_vm_list())
        cell = Gtk.CellRendererText()
        target.pack_start(cell, False)
        target.add_attribute(cell, "text", 0)
        if target_s:
            target.set_active(ensure_in_list(target.get_model(), target_s))

        path = Gtk.Entry()
        path.set_hexpand(True)
        if folder_s:
            path.set_text(folder_s)

        def delete_row() -> None:
            towhat.remove(share_row)
            share_row.destroy()

        icon = Gio.ThemedIcon(name="list-remove")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        delete = Gtk.Button()
        delete.add(image)
        image.show()
        delete.connect("clicked", lambda *_: delete_row())

        for x in [source, target, path, delete]:
            share_row.add(x)
            x.show()
        towhat.add(share_row)
        share_row.show()
        source.grab_focus()

        add_button = [x for x in towhat.get_children() if isinstance(x, Gtk.Button)][0]
        towhat.reorder_child(add_button, len(towhat.get_children()) - 1)

        # use this for the dialog that asks for folder share authorization!
        # https://developer.gnome.org/hig/patterns/feedback/dialogs.html

        # use the boxed lists pattern for folder share manager, splitting
        # the controls into two rows, top are the source and target VM,
        # bottom the folder entry and the allow/block button with an indicator
        # next to it.  and figure out how to change the color of the slider to
        # red when it is disabled (blocked)
        # https://developer.gnome.org/hig/patterns/containers/boxed-lists.html

    def show_all(self) -> None:
        Gtk.Window.show_all(self)

    def close_attempt(self, *unused_args: Any) -> bool:
        try:
            self.save()
            return False
        except Exception:
            return True

    def quit(self, *unused_args: Any) -> None:
        Gtk.main_quit()

    def run(self) -> None:
        self.show_all()
        Gtk.main()


# gi.require_version("Notify", "0.7")
# from gi.repository import Notify
# class FIXME(Gtk.Window):
## Notification example code!
# def __init__(self):
# Gtk.Window.__init__(self, title="Hello World")
# Gtk.Window.set_default_size(self, 640, 480)
# Notify.init("Simple GTK3 Application")

# self.box = Gtk.Box(spacing=6)
# self.add(self.box)

# self.button = Gtk.Button(label="Click Here")
# self.button.set_halign(Gtk.Align.CENTER)
# self.button.set_valign(Gtk.Align.CENTER)
# self.button.connect("clicked", self.on_button_clicked)
# self.box.pack_start(self.button, True, True, 0)

# def on_button_clicked(self, widget):
# n = Notify.Notification.new("Simple GTK3 Application", "Hello World !!")
# n.show()
