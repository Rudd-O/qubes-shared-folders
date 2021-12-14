#!/usr/bin/python3

import base64
import errno
import glob
import hashlib
import json
import logging
import os
import re
import subprocess
import sys


RESPONSE_ALLOW_ONETIME = "ALLOW_ONETIME"
RESPONSE_DENY_ONETIME = "DENY_ONETIME"
RESPONSE_ALLOW_ALWAYS = "ALLOW_ALWAYS"
RESPONSE_DENY_ALWAYS = "DENY_ALWAYS"
RESPONSE_BLOCK = "BLOCK"
RESPONSE_ALLOW_PREFIX = "ALLOW"
RESPONSE_DENY_PREFIX = "DENY"
POLICY_DB = "/etc/qubes/shared-folders/policy.db"
PATH_MAX = 4096
VM_NAME_MAX = 64
# from qubes.vm package in dom0
VM_REGEX = "^[a-zA-Z][a-zA-Z0-9_-]*$"


logger = logging.getLogger(__name__)


def contains(needle, haystack):
    """Check if the needle path is contained in the haystack path."""
    needle = os.path.abspath(needle)
    haystack = os.path.abspath(haystack)
    if not needle.endswith(os.path.sep):
        needle = needle + os.path.sep
    if not haystack.endswith(os.path.sep):
        haystack = haystack + os.path.sep
    if needle == haystack:
        return True
    if (needle).startswith(haystack):
        return True
    return False


def setup_logging():
    logging.basicConfig(level=logging.INFO if os.getenv("DEBUG") else logging.WARNING)


def check_target_is_dom0():
    return (
        os.getenv("QREXEC_REQUESTED_TARGET_TYPE") == "name"
        and os.getenv("QREXEC_REQUESTED_TARGET") == "dom0"
    ) or (
        os.getenv("QREXEC_REQUESTED_TARGET_TYPE") == "keyword"
        and os.getenv("QREXEC_REQUESTED_TARGET_KEYWORD") == "adminvm"
    )


def base_to_str(binarydata):
    data = base64.b64decode(binarydata)
    return data.decode("utf-8")


def fatal(message, exitstatus=4):
    print("fatal:", message, file=sys.stderr)
    sys.exit(exitstatus)


def reject(message):
    fatal(message, errno.EINVAL)


def deny():
    print("Request refused", file=sys.stderr)
    sys.exit(errno.EACCES)


def is_disp(vm):
    return re.match("^disp[0-9]+$", vm)


def validate_target_vm(target):
    if not target:
        raise ValueError(target)
    if re.match(VM_REGEX, target) is None:
        raise ValueError(target)
    vm_list = subprocess.check_output(
        ["qvm-ls", "--raw-list"], universal_newlines=True
    ).splitlines()
    if "dom0" in vm_list:
        vm_list.remove("dom0")
    if target not in vm_list:
        # Exit early without continuing, no access, because the VM does not exist.
        deny()


def validate_path(folder):
    if len(folder) > PATH_MAX:
        raise ValueError(folder)
    if os.path.abspath(folder) != folder:
        raise ValueError(folder)


def fingerprint_decision(source, target, folder):
    fingerprint = hashlib.sha256()
    fingerprint.update(source.encode("utf-8"))
    fingerprint.update(b"\0")
    fingerprint.update(target.encode("utf-8"))
    fingerprint.update(b"\0")
    fingerprint.update(folder.encode("utf-8"))
    fingerprint.update(b"\0")
    return fingerprint.hexdigest()[:32]


def ctf_policy(fingerprint):
    return "/etc/qubes-rpc/policy/ruddo.ConnectToFolder+%s" % fingerprint


def grant_for(source, target, fingerprint):
    fn = ctf_policy(fingerprint)
    if os.path.isfile(fn):
        return
    logger.info("Creating %s", fn)
    with open(fn + ".tmp", "w") as f:
        f.write("%s %s allow" % (source, target))
    os.chmod(fn + ".tmp", 0o664)
    os.rename(fn + ".tmp", fn)


def revoke_for(source, target, fingerprint):
    fn = ctf_policy(fingerprint)
    try:
        os.unlink(fn)
        logger.info("Removing %s", fn)
    except FileNotFoundError:
        pass


def load_decision_matrix():
    try:
        with open(POLICY_DB, "r") as db:
            return json.load(db)
    except Exception:
        return {}


def save_decision_matrix(matrix):
    with open(POLICY_DB + ".tmp", "w") as db:
        json.dump(matrix, db, indent=4, sort_keys=True)
    os.chmod(POLICY_DB + ".tmp", 0o664)
    os.rename(POLICY_DB + ".tmp", POLICY_DB)


def apply_policy_changes(matrix):
    tpl = "/etc/qubes-rpc/policy/ruddo.ConnectToFolder+%s"
    existing_policy_files = glob.glob(tpl % "*")
    for fingerprint, decision in matrix.items():
        if tpl % fingerprint in existing_policy_files:
            existing_policy_files.remove(tpl % fingerprint)
        elif decision["response"] == RESPONSE_ALLOW_ONETIME:
            grant_for(decision["source"], decision["target"], fingerprint)
        if decision["response"] == RESPONSE_ALLOW_ALWAYS:
            grant_for(decision["source"], decision["target"], fingerprint)
        elif decision["response"] == RESPONSE_DENY_ONETIME:
            revoke_for(decision["source"], decision["target"], fingerprint)
        elif decision["response"] == RESPONSE_DENY_ALWAYS:
            revoke_for(decision["source"], decision["target"], fingerprint)
    for p in existing_policy_files:
        logger.info("Removing %s", p)
        os.unlink(p)


def lookup_decision_in_matrix(matrix, source, target, folder):
    """Look up a decision in the table for src->dst VMs, from most specific to least specific.

    If no decision is made, prospectively generate a fingerprint for this decision to use later.
    """
    matches = []
    for fingerprint, decision in matrix.items():
        if (
            source == decision["source"]
            and target == decision["target"]
            and contains(folder, decision["folder"])
        ):
            matches.append((fingerprint, decision))
    if matches:
        for fingerprint, match in reversed(
            sorted(matches, key=lambda m: len(m[1]["folder"]))
        ):
            if match["response"].startswith(RESPONSE_ALLOW_PREFIX):
                break
        return match, fingerprint
    fingerprint = fingerprint_decision(source, target, folder)
    return None, fingerprint


def lookup_decision_response(source, target, folder):
    matrix = load_decision_matrix()
    match, fingerprint = lookup_decision_in_matrix(matrix, source, target, folder)
    return (match["response"], fingerprint) if match else (None, fingerprint)


def lookup_decision_folder(fingerprint, requested_folder):
    matrix = load_decision_matrix()
    match = matrix.get(fingerprint)
    if match and contains(requested_folder, match["folder"]):
        logger.info(
            "Requested folder %s is contained in folder %s", requested_folder, match
        )
        if match["response"] == RESPONSE_ALLOW_ONETIME:
            del matrix[fingerprint]
            logger.info("One-time decision expired, applying policy changes")
            apply_policy_changes(matrix)
            save_decision_matrix(matrix)
        logger.info("Returning containing folder")
        return match["folder"]
    logger.info("No approved requests for folder %s", requested_folder)


def process_decision_output(source, target, folder, response):
    if response == RESPONSE_BLOCK:
        # The user means to block ALL, so we transform this into
        # a complete block for the machine, by blocking the root
        # directory, which means to block absolutely everything.
        response = RESPONSE_DENY_ALWAYS
        folder = "/"
    matrix = load_decision_matrix()
    fingerprint = fingerprint_decision(source, target, folder)
    decision = {
        "source": source,
        "target": target,
        "folder": folder,
        "response": response,
    }
    matrix[fingerprint] = decision
    if response == RESPONSE_DENY_ONETIME:
        del matrix[fingerprint]
    save_decision_matrix(matrix)
    apply_policy_changes(matrix)
    return fingerprint


def ask_for_authorization(source, target, folder):
    cmd = [
        "/usr/libexec/qvm-authorize-folder-access",
        source,
        target,
        folder,
    ]
    env = dict((x, y) for x, y in os.environ.items())
    env["DISPLAY"] = ":0"
    return subprocess.check_output(cmd, env=env, universal_newlines=True).strip()


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
