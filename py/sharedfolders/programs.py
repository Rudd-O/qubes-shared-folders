#!/usr/bin/python3

import base64
import errno
import getpass
import logging
import os
import re
import subprocess
import sys

from sharedfolders import (
    DecisionMatrix,
    Response,
)


PATH_MAX = 4096
VM_NAME_MAX = 64
# from qubes.vm package in dom0
VM_REGEX = "^[a-zA-Z][a-zA-Z0-9_-]*$"


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO if os.getenv("DEBUG") else logging.WARNING)


def error(message: str, exitstatus: int = 4) -> int:
    print("error:", message, file=sys.stderr)
    return exitstatus


def reject(message: str) -> int:
    return error(message, errno.EINVAL)


def deny() -> int:
    print("Request refused", file=sys.stderr)
    return errno.EACCES


def valid_vm_name(target: str) -> bool:
    if not target:
        raise ValueError(target)
    if re.match(VM_REGEX, target) is None:
        raise ValueError(target)
    vm_list = subprocess.check_output(
        ["qvm-ls", "--raw-list"], universal_newlines=True
    ).splitlines()
    if "dom0" in vm_list:
        vm_list.remove("dom0")
    return target in vm_list


def check_target_is_dom0() -> bool:
    return (
        os.getenv("QREXEC_REQUESTED_TARGET_TYPE") == "name"
        and os.getenv("QREXEC_REQUESTED_TARGET") == "dom0"
    ) or (
        os.getenv("QREXEC_REQUESTED_TARGET_TYPE") == "keyword"
        and os.getenv("QREXEC_REQUESTED_TARGET_KEYWORD") == "adminvm"
    )


def valid_path(folder: str) -> bool:
    return len(folder) < PATH_MAX and os.path.abspath(folder) == folder


def base_to_str(binarydata: bytes) -> str:
    data = base64.b64decode(binarydata)
    return data.decode("utf-8")


def ask_for_authorization(source: str, target: str, folder: str) -> Response:
    cmd = [
        "/usr/libexec/qvm-authorize-folder-access",
        source,
        target,
        folder,
    ]
    env = dict((x, y) for x, y in os.environ.items())
    if not env.get("DISPLAY"):
        env["DISPLAY"] = ":0"
    return Response.from_string(
        subprocess.check_output(cmd, env=env, universal_newlines=True).strip()
    )


def AuthorizeFolderAccess() -> int:
    """AuthorizeFolderAccess runs in dom0 and is used by client
    qubes to request permission to mount other qubes' folders."""
    logger = logging.getLogger("AuthorizeFolderAccess")
    setup_logging()

    if not check_target_is_dom0():
        return error(
            "unexpected targetfor this RPC (target type %s, target %s, target keyword %s)"
            % (
                os.getenv("QREXEC_REQUESTED_TARGET_TYPE"),
                os.getenv("QREXEC_REQUESTED_TARGET"),
                os.getenv("QREXEC_REQUESTED_TARGET_KEYWORD"),
            ),
            errno.EINVAL,
        )

    source = os.getenv("QREXEC_REMOTE_DOMAIN")
    if not source:
        return reject("no source VM")

    arguments = sys.stdin.buffer.read(int(PATH_MAX * 130 / 100 + VM_NAME_MAX))
    sys.stdin.close()
    try:
        base64_target, base64_folder = arguments.split(b"\n")[0:2]
    except (ValueError, IndexError):
        return reject("the arguments were malformed")

    try:
        target = base_to_str(base64_target)
        if not valid_vm_name(target):
            return deny()
    except Exception:
        return reject("the target VM is malformed or has invalid characters")
    if source == target:
        return reject("cannot request file share to and from the same VM")

    try:
        folder = base_to_str(base64_folder)
        if not valid_path(folder):
            raise ValueError(folder)
    except Exception:
        return reject(
            "the requested folder is malformed, is not a proper absolute path, or has invalid characters"
        )

    response, fingerprint = DecisionMatrix.load().lookup_prior_authorization(
        source, target, folder
    )
    if response:
        logger.info(
            "VM %s has a response already registered for %s:%s: %s (fingerprint: %s)",
            source,
            target,
            folder,
            response,
            fingerprint,
        )
    else:
        logger.info(
            "VM %s has yet to receive a response for %s:%s", source, target, folder
        )
        # User has never been asked.
        response = ask_for_authorization(source, target, folder)
        fingerprint = DecisionMatrix.load().process_authorization_request(
            source, target, folder, response
        )
        logger.info("Response: %s; fingerprint: %s", response, fingerprint)

    if not response or not response.is_allow():
        return deny()

    sys.stdout.write(fingerprint)
    sys.stdout.close()
    return 0


def QueryFolderForAuthorization() -> int:
    """QueryFolderForAuthorization runs in dom0 and is called by server
    qubes to verify that a client qube has been authorized to get access
    to a folder."""
    logger = logging.getLogger("QueryFolderForAuthorization")
    setup_logging()

    if not check_target_is_dom0():
        return error(
            "unexpected targetfor this RPC (target type %s, target %s, target keyword %s)"
            % (
                os.getenv("QREXEC_REQUESTED_TARGET_TYPE"),
                os.getenv("QREXEC_REQUESTED_TARGET"),
                os.getenv("QREXEC_REQUESTED_TARGET_KEYWORD"),
            ),
            errno.EINVAL,
        )

    fingerprint = os.getenv("QREXEC_SERVICE_ARGUMENT")
    if not fingerprint:
        return reject("this RPC call requires an argument")

    # Read the requested folder from the caller.  The caller is NOT
    # the VM which wants to mount the folder -- it is rather the
    # server VM that has the desired folder to be mounted.
    requested_folder_encoded = sys.stdin.buffer.read()
    try:
        requested_folder = base_to_str(requested_folder_encoded)
        if not valid_path(requested_folder):
            raise ValueError(requested_folder)
    except Exception:
        return reject(
            "the requested folder is malformed, is not a proper absolute path, or has invalid characters"
        )

    # Look up the folder in the authorization database.  If the
    # requested folder is exactly or is a subfolder of any of the
    # authorized folders, we will succeed in this call.
    logger.info(
        "Looking up fingerprint %s for requested folder %s",
        fingerprint,
        requested_folder,
    )
    folder = DecisionMatrix.load().lookup_decision_folder(fingerprint, requested_folder)
    if not folder:
        return deny()

    # Send the requested folder back to the client.
    print(requested_folder)
    return 0


def QvmMountFolder() -> int:
    """QvmMountFolder runs in the qube that wants to mount a folder from
    another qube."""
    logger = logging.getLogger("QvmMountFolder")
    setup_logging()

    def usage(error: str = "") -> int:
        if error:
            print("error:", error, file=sys.stderr)
        print(
            """usage:

"qvm-mount-folder" <VM> <folder from VM> <mountpoint>""",
            file=sys.stderr if error else sys.stdout,
        )
        return os.EX_USAGE

    try:
        vm, source, target = sys.argv[1:4]
    except (IndexError, ValueError):
        return usage("invalid arguments")

    if not os.path.isdir(target):
        error("%s does not exist or is not a directory" % target, errno.ENOENT)

    vm_encoded = base64.standard_b64encode(vm.encode("utf-8"))
    folder_encoded = base64.standard_b64encode(source.encode("utf-8"))

    # Request authorization for a specific folder (and its subfolders)
    # on a particular VM.  If the authorization is successful, a
    # ticket called a "fingerprint" is returned, which entitles this
    # program to access the folder (either one-time or permanently,
    # as the user has decided).
    logger.info("Requesting authorization for qvm://%s%s", vm, source)
    p = subprocess.Popen(
        ["qrexec-client-vm", "dom0", "ruddo.AuthorizeFolderAccess"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        bufsize=0,
        close_fds=True,
    )
    assert p.stdin
    assert p.stdout
    p.stdin.write(vm_encoded + b"\n")
    p.stdin.write(folder_encoded + b"\n")
    p.stdin.close()
    fingerprint = p.stdout.read().decode("utf-8")
    p.stdout.close()
    ret = p.wait()

    if ret != 0:
        if ret == errno.EACCES:
            print("Request denied", file=sys.stderr)
        elif ret == errno.EINVAL:
            print("Invalid parameters", file=sys.stderr)
        else:
            print("Unknown error", file=sys.stderr)
        sys.exit(ret)

    f1_read, f1_write = os.pipe2(0)
    f2_read, f2_write = os.pipe2(0)

    stdin_for_read = os.fdopen(f1_read, "rb", buffering=0)
    stdout_for_write = os.fdopen(f2_write, "wb", buffering=0)
    stdin_for_write = os.fdopen(f1_write, "wb", buffering=0)
    stdout_for_read = os.fdopen(f2_read, "rb", buffering=0)

    # With the fingerprint, use it to invoke the RPC service that was
    # just authorized for this script.
    logger.info(
        "Connecting to qvm://%s%s using fingerprint %s", vm, source, fingerprint
    )
    p = subprocess.Popen(
        [
            "qrexec-client-vm",
            vm,
            "ruddo.ConnectToFolder+%s" % fingerprint,
        ],
        stdin=stdin_for_read,
        stdout=stdout_for_write,
        bufsize=0,
        close_fds=True,
    )
    stdin_for_read.close()
    stdout_for_write.close()

    # Now send the folder we intend to mount, which may be
    # a subfolder of the requested folder.  This is thought
    # so that e.g. permanent authorization for /home/user works to
    # grant authorization for a mount request of /home/user/subfolder.
    # The receiver will check if this script is not "cheating",
    # id est, if the folder I am passing here is the same folder
    # used to obtain the fingerprint above, or at least a subfolder
    # of it.
    stdin_for_write.write(folder_encoded + b"\n")
    response = stdout_for_read.read(3).decode("utf-8").rstrip()
    if response == "ok":
        # Proceed.  We have received authorization and diod has
        # already started on the other side.
        pass
    elif response == "":
        # folder does not exist
        ex = p.wait()
        if ex == errno.ENOENT:
            return error(
                "directory %s does not exist in qube %s" % (source, vm), errno.ENOENT
            )
        elif ex == errno.EACCES:
            return error(
                "qube %s has denied the mount request for directory %s" % (vm, source),
                errno.EACCES,
            )
        elif ex == 126:
            return error(
                "qrexec policy has denied the mount request to %s for directory %s"
                % (vm, source),
                126,
            )
        else:
            return error("unknown exit status %s" % ex, ex)
    else:
        p.kill()
        assert 0, "not reached: %r" % response

    uid = os.getuid()
    gid = os.getgid()
    username = getpass.getuser()
    cmdline = [
        "/usr/bin/sudo",
        "/usr/bin/mount",
        "-t",
        "9p",
        "-o",
        "trans=fd,rfdno=%s,wfdno=%s,version=9p2000.L,dfltuid=%s,dfltgid=%s,uname=%s,aname=%s"
        % (0, 1, uid, gid, username, source),
        "qvm://%s%s" % (vm, source),
        target,
    ]

    logger.info("Mounting qvm://%s%s", vm, source)
    p2 = subprocess.Popen(
        cmdline, stdin=stdout_for_read, stdout=stdin_for_write, close_fds=True
    )
    stdout_for_read.close()
    stdin_for_write.close()

    return p2.wait()
