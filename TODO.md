Things I would love to get addressed (of course, other suggestions and improvements welcome):

* Permission system to allow certain folders to certain qubes (the argument in qrexec is sanitized, rendering it useless for that)
* Persistent notification on tray that indicates a specific folder is currently exported to a certain qube
* Performance improvements (it can be slow to browse large folders from a client qube)
* [Security hardening of diod](https://github.com/Rudd-O/diod) (make check was disabled in the specfile because there are some issues I don't know how to fix, sadly, but I did fix a `snprintf` buffer overflow in my [fork of diod](https://github.com/Rudd-O/diod))
* UI for mount clients to configure certain mounts to be mounted upon start / list existing configured mountpoints and statuses and open file managers to these mountpoints
* Ensure that the `diod` daemon dies on the server (and the client `qrexec` on the client dies too) when the file system is unmounted on the client (this might require changes to `diod`)
