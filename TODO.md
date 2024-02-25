Things I would love to get addressed (of course, other suggestions and improvements welcome):

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
* Propose inclusion in default Qubes / in Qubes extra gear
