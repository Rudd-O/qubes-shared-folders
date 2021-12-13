Things I would love to get addressed (of course, other suggestions and improvements welcome):

* Prevent shared access from one VM to the same VM
* No persistent authorization for disposable VMs, either as source or as target
* Add throttling for authorization dialog so VMs can't pop a thousand of them
* Add serialized locking to reads and modifications of the policy database
* Add a manager UI to control shared folder authorizations (folder share manager)
* Persistent notification on tray that indicates a specific folder is currently exported to a certain qube
* Performance improvements (it can be slow to browse large folders from a client qube)
* [Security hardening of diod](https://github.com/Rudd-O/diod) (make check was disabled in the specfile because there are some issues I don't know how to fix, sadly, but I did fix a `snprintf` buffer overflow in my [fork of diod](https://github.com/Rudd-O/diod))
* UI for mount clients to configure certain mounts to be mounted upon start / list existing configured mountpoints and statuses and open file managers to these mountpoints
