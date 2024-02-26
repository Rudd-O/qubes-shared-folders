Things I would love to get addressed (of course, other suggestions and improvements welcome):

* End-to-end conformance tests of `qfsd` using a well-known file system tester or testing framework.
* Small CLI interface to allow / deny things permanently, then perform the necessary policy changes
* Small Salt module to permit the same as above
* Revise argument passing using 4.1 style instead of base64 encoding over pipes
* Add timeout for access requests so that one-time accesses don't turn into "request today, access in a year"; the timeout is to be verified at mount session establishment time (`lookup_folder`).
* Add support for GUI domains (marmarek says to look at https://github.com/QubesOS/qubes-core-qrexec/blob/master/qrexec/tools/qrexec_policy_exec.py#L64-L112 ) (he also says "Basically, factor out the prompt code into separate file, then call it via `qvm-run --service ...` instead of directly".)
Here is how qrexec policy prompt is doing it:
* Add support for Qubes 4.1 new-style policies
* Add icons on the folder share manager (code to retrieve them is here: https://github.com/QubesOS/qubes-core-qrexec/blob/master/qrexec/tools/qrexec_policy_exec.py#L64-L112 )
* Add throttling for authorization dialog so VMs can't pop a thousand of them
* Add locking between authorization dialog and folder share manager so that users cannot proceed with an open folder share request until the folder share manager is closed; alternatively, ensure that the folder share manager cannot save the changes done in the interim and forces the user to revert to what's stored on disk
* Add serialized locking to reads and modifications of the policy database
* Persistent notification on tray that indicates a specific folder is currently exported to a certain qube
* UI for mount clients to configure certain mounts to be mounted upon start / list existing configured mountpoints and statuses and open file managers to these mountpoints
* Add a `mount.qvm` command so that the `mount` command can be used normally (figure out how to make it work as non-root, although that should not be very difficult)
* Add a `qvm-mount` command, because the command `qvm-mount-folder` seems dumbly named in retrospect
* Performance improvements (it can be slow to browse large folders from a client qube)
  * Caching seems impossible to resolve because Plan 9 file system servers do not have a way to invalidate client caches, as
    1. the kernel has no way to inform the daemon that a cache is invalid
    2. the protocol itself has no way of informing the client that a cache is to be invalidated
  * This seems to be a general issue with client-server file protocols like SAMBA; it is not clear to me if or how smbd tells the client that a certain inode or a region from a file has been changed on the server, so the corresponding cached object on the client should be deemed invalid
* Propose inclusion in default Qubes / in Qubes extra gear
