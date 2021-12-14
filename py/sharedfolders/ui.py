#!/usr/bin/python3


import os
from typing import Any

import gi  # type: ignore

gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")

# from gi.repository import Notify


from gi.repository import Gtk  # type: ignore

from sharedfolders import (
    is_disp,
    RESPONSE_ALLOW_ALWAYS,
    RESPONSE_ALLOW_ONETIME,
    RESPONSE_DENY_ALWAYS,
    RESPONSE_DENY_ONETIME,
    RESPONSE_BLOCK,
    Response,
)


def search_for_ui_file(file: str) -> str:
    for trial in [
        os.path.join("ui", file),
        os.path.join("/usr/share/qubes-shared-folders/ui", file),
    ]:
        if os.path.exists(trial):
            return trial
    raise FileNotFoundError(file)


class AuthorizationDialog(object):

    response: Response = RESPONSE_DENY_ONETIME

    def __init__(self, client: str, server: str, folder: str):
        builder = Gtk.Builder()
        builder.add_from_file(search_for_ui_file("authorization-dialog.ui"))
        # builder.connect_signals()
        self.builder = builder
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
        self.builder.get_object("folder").set_text(folder)
        self.collect_response()
        self.prior_remember_active = None
        self.prior_remember_sensitive = None

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
            ("option_deny", RESPONSE_DENY_ONETIME),
            ("option_allow", RESPONSE_ALLOW_ONETIME),
            ("option_block", RESPONSE_BLOCK),
        ]
        for objn, resp in table:
            if self.builder.get_object(objn).get_active():
                self.response = resp
        if self.response is not RESPONSE_BLOCK:
            if self.builder.get_object("option_remember").get_active():
                if self.response is RESPONSE_ALLOW_ONETIME:
                    self.response = RESPONSE_ALLOW_ALWAYS
                elif self.response is RESPONSE_DENY_ONETIME:
                    self.response = RESPONSE_DENY_ALWAYS

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
