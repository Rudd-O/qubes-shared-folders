#!/usr/bin/python3

import base64
import errno
import getpass
import logging
import os
import subprocess
import sys

from sharedfolders import (
    RESPONSE_DENY_PREFIX,
    lookup_decision_response,
    ask_for_authorization,
    process_decision_output,
    base_to_str,
    deny,
    reject,
    fatal,
    validate_target_vm,
    validate_path,
    PATH_MAX,
    VM_NAME_MAX,
    check_target_is_dom0,
    setup_logging,
    lookup_decision_folder,
)


DENIED = 126


def AuthorizeFolderAccess():
    """AuthorizeFolderAccess runs in dom0 and is used by client
    qubes to request permission to mount other qubes' folders."""
    logger = logging.getLogger("AuthorizeFolderAccess")
    setup_logging()

    check_target_is_dom0() or fatal(
        "fatal: unexpected targetfor this RPC (target type %s, target %s, target keyword %s)"
        % (
            os.getenv("QREXEC_REQUESTED_TARGET_TYPE"),
            os.getenv("QREXEC_REQUESTED_TARGET"),
            os.getenv("QREXEC_REQUESTED_TARGET_KEYWORD"),
        ),
        errno.EINVAL,
    )

    source = os.getenv("QREXEC_REMOTE_DOMAIN")
    if not source:
        reject("no source VM")

    arguments = sys.stdin.buffer.read(int(PATH_MAX * 130 / 100 + VM_NAME_MAX))
    sys.stdin.close()
    try:
        base64_target, base64_folder = arguments.split(b"\n")[0:2]
    except (ValueError, IndexError):
        reject("the arguments were malformed")

    try:
        target = base_to_str(base64_target)
        validate_target_vm(target)
    except Exception:
        reject("the target VM is malformed or has invalid characters")
    if source == target:
        reject("cannot request file share to and from the same VM")

    try:
        folder = base_to_str(base64_folder)
        validate_path(folder)
    except Exception:
        reject(
            "the requested folder is malformed, is not a proper absolute path, or has invalid characters"
        )

    response, fingerprint = lookup_decision_response(source, target, folder)
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
        fingerprint = process_decision_output(source, target, folder, response)
        logger.info("Response: %s; fingerprint: %s", response, fingerprint)
    if response.startswith(RESPONSE_DENY_PREFIX):
        deny()

    sys.stdout.write(fingerprint)
    sys.stdout.close()


def QueryFolderForAuthorization():
    """QueryFolderForAuthorization runs in dom0 and is called by server
    qubes to verify that a client qube has been authorized to get access
    to a folder."""
    logger = logging.getLogger("QueryFolderForAuthorization")
    setup_logging()

    check_target_is_dom0() or fatal(
        "fatal: unexpected targetfor this RPC (target type %s, target %s, target keyword %s)"
        % (
            os.getenv("QREXEC_REQUESTED_TARGET_TYPE"),
            os.getenv("QREXEC_REQUESTED_TARGET"),
            os.getenv("QREXEC_REQUESTED_TARGET_KEYWORD"),
        ),
        errno.EINVAL,
    )

    fingerprint = os.getenv("QREXEC_SERVICE_ARGUMENT")
    if not fingerprint:
        reject("this RPC call requires an argument")

    # Read the requested folder from the caller.  The caller is NOT
    # the VM which wants to mount the folder -- it is rather the
    # server VM that has the desired folder to be mounted.
    requested_folder_encoded = sys.stdin.buffer.read()
    try:
        requested_folder = base_to_str(requested_folder_encoded)
        validate_path(requested_folder)
    except Exception:
        reject(
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
    folder = lookup_decision_folder(fingerprint, requested_folder)
    if not folder:
        deny()

    # Send the requested folder back to the client.
    print(requested_folder)


def QvmMountFolder():
    """QvmMountFolder runs in the qube that wants to mount a folder from
    another qube."""
    logger = logging.getLogger("QvmMountFolder")
    setup_logging()

    def usage(fatal=""):
        if fatal:
            print("fatal:", fatal, file=sys.stderr)
        print(
            """usage:
    
    qvm-mount-folder <VM> <folder from VM> <mountpoint>""",
            file=sys.stderr if fatal else sys.stdout,
        )
        sys.exit(os.EX_USAGE)

    try:
        vm, source, target = sys.argv[1:4]
    except (IndexError, ValueError):
        usage("invalid arguments")

    if not os.path.isdir(target):
        fatal("%s does not exist or is not a directory" % target, errno.ENOENT)

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
            print("Unknown fatal", file=sys.stderr)
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
            fatal("directory %s does not exist in qube %s" % (source, vm), errno.ENOENT)
        elif ex == errno.EACCES:
            fatal(
                "qube %s has denied the mount request for directory %s" % (vm, source),
                errno.EACCES,
            )
        elif ex == 126:
            fatal(
                "qrexec policy has denied the mount request to %s for directory %s"
                % (vm, source),
                126,
            )
        else:
            fatal("unknown exit status %s" % ex, ex)
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

    sys.exit(p2.wait())
