# Shared folders for Qubes OS

**Connect qube storage to another qube.**  Access and manage folders
saved in one qube (or a file server connected to it) from another
qube, transparently, as they were in the other qube.

We have some [to-do items](./TODO.md) which we'd love your help with!

## Principle

The programs in this project collaborate together to allow a qube
to *mount* a folder in another qube, using the Plan 9 file system
as a transport mechanism, with `qfsd` (a Rust-based Plan 9 userspace
server, built within this project) running on the server qube, and
the `v9fs` kernel file system module on the client qube.  These two
components communicate with each other via the Qubes RPC mechanism.

## Usage

The following instructions assume that the qube which contains the
files you want to share is named `server` and the qube where you
want to access the files is named `client`.  They also assume you
successfully finished the one-time installation instructions below.

### Connect to a folder in another qube

To mount `/home/user` from the `server` VM onto `/home/user/mnt`,
run the following on a terminal of `client`:

```
cd /home/user
mkdir mnt
qvm-mount-folder server /home/user mnt
```

At this point you will see an authorization message from dom0 asking
you if you really want to give `client` access to `server`'s files.

![Authorization dialog example](./doc/auth-dialog.png)

This access can be denied one-time or perpetually, and it can also
be granted one-time (for the duration of the mount) or permanently.
Note that the access granted is limited to the requested folder and
all subfolders (modulo file permissions on the shared folder) and,
once granted, access lasts until the `server` qube is shut off, or
the `client` qube unmounts the shared folder.

Authorize the access by confirming the name of the qube (`server`) on
the dialog and continuing.

**Presto.**  You should be able to use a file manager, a terminal, or
any of your favorite applications to use files in `/home/user/mnt`
-- these files are all stored in `server` on folder `/home/user`.

### Disconnect from the folder

To finish using it, run `sudo umount /home/user/mnt`.

### In case of error

If your `server` qube shuts off before you unmount the mounted share,
you'll see `I/O error`s on the `client` qube whenever you attempt
to access the mounted share.  You can always unmount the errored
folder to resolve the issue.

### Manage file shares

Your dom0 has a settings tool called *Folder share manager*
(`qvm-folder-share-manager`) that allows you to define or revoke
*permanent* grants or denials on particular file shares:

![Authorization dialog example](./doc/folder-share-manager.png)

Temporary one-time grants or denials are handled internally, not
persisted for long (they are ephemeral) and they cannot be modified
through this settings tool.

Note that grants and denial do not automatically translate into
qubes auto-mounting folders on boot -- they are merely permissions
— you need to figure out how to mount folders when your qube powers
on, using the XDG autostart facility.

## Comparison with other solutions

* File copy/move between VMs: serves a different use case, although
  admittedly it is more secure than this solution given the smaller
  attack surface.
* `rsync` via qrexec / `qubes.ConnectTCP`: large codebase to trust,
  plus extremely inconvenient compared to a simple mounted file share,
  as the user has to (1) configure low-level settings (2) manage the
  synchronization manually (3) take care to remember to sync up.
* Syncthing: in principle, it can work to synchronize across qubes,
  as well as other equipment.  However, it requires networking,
  it's a large codebase, and it results in duplication of files
  across all synced qubes.
* NFS / SAMBA shared over `qubes.ConnectTCP`: this solution is much
  simpler, because it requires zero configuration.  This solution
  should also, by some metrics, be less risky than NFS and SAMBA,
  which are both much larger codebases with many more features that
  you are simply *not going to need* in the context of sharing files
  between qubes.
* NFS / SAMBA mounted from a NAS: this solution is much simpler than
  that, and — unlike mounting a NAS share on the target VM — it
  requires neither other equipment nor a LAN to work properly.
  Furthermore, since NAS solutions obligate you to setup and manage
  authentication and authorization for specific folders, this ends
  up discouraging you from adopting "one share + one mount per qube",
  which reduces your overall security.  Plus, if a qube with access
  to the share is compromised, then the whole NAS may be attacked
  from the compromised qube.

For comparison:

* `qfsd` a few dozen lines, plus 1300 lines for the server portion
  of the Rust `rust-p9` library, plus 1600 lines for the protocol
  portion of the `rust-p9` library.
* `samba` raw C / C++ language line count: **over 2 million**
* NFS' and rsync's line counts are homework for the reader.

## Design

When authorized, the client qube initiates a Qubes RPC connection to
the server qube, asking it to share a specific folder (which must
exist).  If the RPC mechanism authorizes it (by prompting you), then
the server qube starts a `qfsd` instance, and the client uses the
established I/O channel to mount the shared folder onto a folder of
its file system tree.

The full design is documented [here](./doc/authorization-design.md).

## Security considerations

* A compromise of the client qube could be used to escalate into a
  compromise of the `qfsd` daemon running on the server qube -- in
  which case the server qube can be considered compromised.  The
  converse case is possible as well.  Admittedly, this is hard because
  the server is written in a memory-safe language.
* A compromise of the server qube (and therefore `qfsd` could be used
  to exploit the kernel of any client qubes.  In other words: the client
  qube trusts that `qfsd` (on the server) will not send malicious data
  back to the `v9fs` kernel module of the client.

These are inherent risks of running a client/server setup that uses a
low-level binary protocol and two sides (a client and a server), whether
it be Git, SSH, or any other protocol.

If these security considerations cannot be accommodated by your
security model, you are better off *not using this program*.

## Installation

### From packages

If you want to test using prebuilt packages, they are available
[here](https://repo.rudd-o.com) for the latest Fedora templates, and in
folder `q4.2` on dom0.*  Be aware that the packages are signed with a
private key and, as such, you must currently trust their authenticity.

If you use these packages to install `qubes-network-server` in your template
qube, and `qubes-shared-folders-dom0` in your dom0, you don't need to follow
the build and installation instructions below.

After installing the packages on your template and dom0, stop the
template, and shut down all qubes you plan to use this software on.

*Updated packages are no longer available for Qubes OS 4.1.*

### Build and install the software

*Pro tip: if you want to skip the build, just install the following
packages on your template qube from https://repo.rudd-o.com/ .

For this, you'll have to build the packages twice.  Once for your qubes'
*template*, and once for the right Fedora version of your dom0 (Qubes OS
4.2 uses Fedora 37 in dom0, while Qubes OS 4.1 uses Fedora 32).

### Build and install the template side of this software

To build the packages for your template, start a disposable qube based on
that template.

In the disposable qube, run

```
git clone https://github.com/Rudd-O/qubes-shared-folders
cd qubes-shared-folders
make rpm
```

You may be missing some dependencies.  Make sure to install them within
the disposable qube.

An RPM package will be deposited in the `qubes-shared-folders` directory,
named `qubes-shared-folders-<version>-<release>.noarch.rpm`.

Copy the RPM package to your template, and install it there.

Keep the disposable qube around.

#### But what if I have a Debian template qube or Windows VM?

*On Windows:* The 9P file system client is in principle available as a driver
for Windows, but the Qubes-specific authorization mechanisms are not
implemented, so you won't be able to make that work there.

*On Debian and derivatives*: the client/server package will work in a Debian
VM correctly, provided everything is properly installed.  From a copy of the
source in a disposable VM, run
`make install-client install-server DESTDIR=/tmp` to deploy everything to
`/tmp` (causing the necessary binaries to be built), then copy *the source
tree* to a folder in your template (preserving timestamps), and then run
`make install-client install-server DESTDIR=/usr` within that folder of
your template.  Note that this will modify your template's root file system.

Pull requests are gladly welcome to enable packaging the client for Debian.

### Build and install the dom0 side of this software

Of the two following subheadings, follow the instructions of only the
one applicable to you.

#### If you are running Qubes OS 4.2

To build the packages for your dom0, first install Fedora Toolbox
(`toolbox`) in the disposable qube you were were building the prior package
in.  `dnf install -y toolbox` does the trick.

Once you have `toolbox` available, change into the `qubes-shared-folders`
folder again, then instantiate a toolbox with the right Fedora version.
This terminal transcript will be useful:

```
[user@disp9999 qubes-shared-folders]$ toolbox create -r 37  # creates the container
Creating container fedora-toolbox-37: | Created container: fedora-toolbox-37
Enter with: toolbox enter --release 37
[user@disp9999 qubes-shared-folders]$ toolbox enter --release 37 # enters the container
# now we are going to install needed build dependencies inside the container
⬢[user@toolbox qubes-shared-folders]$ sudo dnf install -y make rpm-build desktop-file-utils python3-mock python3-mypy
[... DNF output omitted for brevity ...]
⬢[user@toolbox qubes-shared-folders]$ make rpm  # builds the RPM
[... make output omitted for brevity...]
⬢[user@toolbox qubes-shared-folders]$ # you are now done
```

If you are missing dependencies, again, install them *within the toolbox*
and retry the build.

An RPM package will be deposited in the `qubes-shared-folders` directory,
named `qubes-shared-folders-dom0-<version>-<release>.noarch.rpm`.  This
package contains service security policies (default `deny` for the file
sharing service) and authorization services for inter-VM file system sharing.
Copy it to dom0, and install it using `sudo rpm -ivh`.

You can now shut down the disposable qube.

#### If you are running Qubes OS 4.1

The instructions above work but you must use toolbox images for Fedora
32 instead of Fedora 37.

#### Qubes 4.0 users

*This is no longer supported.*

### Shut down all involved qubes

Now shut down all involved qubes, to ensure the installation takes
effect.  You don't need to shut down your computer or dom0.
