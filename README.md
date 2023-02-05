# Shared folders for Qubes OS

**Connect qube storage to another qube.**  Access and manage folders
saved in one qube (or a file server connected to it) from another
qube, transparently, as they were in the other qube.

We have some [to-do items](./TODO.md) which we'd love your help with!

## Principle

The programs in this project collaborate together to allow a qube
to *mount* a folder in another qube, using the Plan 9 file system
as a transport mechanism, with `diod` (a Plan 9 userspace server)
running on the server qube, and the `v9fs` kernel file system module
on the client qube.  These two components talk over the Qubes RPC
mechanism.

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

* `diod` raw C language line count: *40 thousand*
* `samba` raw C / C++ language line count: **over 2 million**
* NFS' and rsync's line counts are homework for the reader.

## Design

When authorized, the client qube initiates a Qubes RPC connection to
the server qube, asking it to share a specific folder (which must
exist).  If the RPC mechanism authorizes it (by prompting you), then
the server qube starts a `diod` instance, and the client uses the
established I/O channel to mount the shared folder onto a folder of
its file system tree.

The full design is documented [here](./doc/authorization-design.md).

## Security considerations

* There is currently no way to control *which* folders of the server
  qube can be requested by client qubes.  In principle this should
  be doable because `diod` is able to export only a subtree of any
  file system hierarchy.
* A compromise of the client qube could be used to escalate into a
  compromise of the `diod` daemon running on the server qube -- in
  which case the server qube can be considered compromised.  The
  converse case is possible as well.
  In other words: the client qube trusts that `diod` (on the server)
  will not send malicious data back, and the server qube trusts that the
  `v9fs` kernel module on the client qube will not send malicious data.
  This is an inherent risk of running a client/server setup that uses
  a low-level binary protocol and two sides (a client and a server),
  whether it be Git, SSH, or any other protocol.

If these security considerations cannot be accommodated by your
security model, you are better off *not using this program*.

## Installation

*Note: the following instructions show how to build the packages from
scratch.  If you want to test using prebuilt packages (for the latest
Fedora templates, and Fedora 25 / 32 on dom0), they are available
[here](https://repo.rudd-o.com).*

*Note: these assume a Fedora template and dom0.  If your template is
Debian, see below.*

### Build and install `diod`

First, build a [`diod`](https://github.com/Rudd-O/diod) RPM package.

Before building, install the following dependencies using `dnf`:

* `munge-devel`
* `ncurses-devel`
* `autoconf`
* `automake`
* `lua-devel`
* `rpm-build`
* `libattr-devel`
* `libcap-devel`

Here is how you build it:

```
git clone https://github.com/Rudd-O/diod
cd diod
./autogen.sh && ./configure --prefix=/usr && make dist && rpmbuild -ts *tar.gz
# This will produce a source RPM you have to build now.
# The source RPM will be stored in $HOME/rpmbuild .
rpmbuild --rebuild $HOME/rpmbuild/SRPMS/diod*src.rpm
```

The result will produce a diod binary RPM in `$HOME/rpmbuild/RPMS/x86_64`.
copy and install this package on the *template* of the qube you plan to
*share your files from*.

*Note: if you have an error* that looks like
`Illegal char '-' (0x2d) in: Version: 1.0.24.3-1-ga082a0a`,
please file a ticket on this repository immediately.  This usually means
I forgot to push the right annotated tag to the `diod` repository.

### Build and install the qube side of this software

For this, you'll have to build the packages twice.  Once for your qubes'
*template*, and once for the right Fedora version of your dom0 (Qubes OS
4.0 uses Fedora 25 in dom0, while Qubes OS 4.1 uses Fedora 32).

Before building, install the following dependencies using `dnf`:
* `python3-mock`
* `python3-mypy`

To build the packages for your template, run the following in your qube
based on said template (or on a disposable qube):

```
git clone https://github.com/Rudd-O/qubes-shared-folders
cd qubes-shared-folders
make rpm
```

An RPM package will be deposited in the `qubes-shared-folders` directory,
named `qubes-shared-folders-<version>-<release>.noarch.rpm`.  Copy and
install it in the template of the qube you plan to *share your files from*,
as well as the template of the qube you plan to *access your files in*
(most likely they are the one and same qube template).

#### But what if I have a Debian template qube or Windows VM?

*On Windows:* The 9P file system client is not implemented for Windows,
so you won't be able to make that work there.

*On Debian and derivatives*: the client package will work in a Debian VM
(run `make install-client`) so long as you have the following Debian
packages installed:

* [desktop-file-utils](https://packages.debian.org/search?suite=default&section=all&arch=any&searchon=names&keywords=desktop-file-utils)
* Python 3
* [diod](https://packages.debian.org/search?searchon=sourcenames&keywords=diod)

Pull requests are gladly welcome if you want to package the client
for Debian.

### Build and install the dom0 side of this software

Of the two following subheadings, follow the instructions of only the
one applicable to you.

#### If you are running Qubes OS 4.1

To build the packages for your dom0, first install Fedora Toolbox
(`toolbox`) in the template of the qube where you were building the
prior package.

Once you have `toolbox` available in the qube where you were building,
you can change into the directory `qubes-shared-folders` again, then
instantiate a toolbox with the right Fedora version.  This terminal
transcript will be useful:

```
[user@projects qubes-shared-folders]$ toolbox create -r 32  # creates the container
Creating container fedora-toolbox-32: | Created container: fedora-toolbox-32
Enter with: toolbox enter --release 32
[user@projects qubes-shared-folders]$ toolbox enter --release 32 # enters the container
# now we are going to install needed build dependencies inside the container
⬢[user@toolbox qubes-shared-folders]$ sudo dnf install -y make rpm-build desktop-file-utils python3-mock python3-mypy
[... DNF output omitted for brevity ...]
⬢[user@toolbox qubes-shared-folders]$ make rpm  # builds the RPM
[... make output omitted for brevity...]
⬢[user@toolbox qubes-shared-folders]$ # you are now done
```

An RPM package will be deposited in the `qubes-shared-folders` directory,
named `qubes-shared-folders-dom0-<version>-<release>.noarch.rpm`.  Copy
it to dom0, and install it using `sudo rpm -ivh`.  This package contains
service security policies (default `deny` for the file sharing service).

You can now shut down the `toolbox` instance with command
`toolbox rm --force fedora-toolbox-32`.

#### If you are running Qubes OS 4.0

There are no Fedora Toolbox images for Fedora 25, unfortunately, but you
can deploy a `mock` jail on a disposable qube using `dnf` itself, with
instructions similar to the following:

```
[user@disp9524 ~]$ git clone https://github.com/Rudd-O/qubes-shared-folders
[... git output omitted for brevity ...]
# Set up the jail.
[user@disp9524 ~]$ sudo dnf install -y mock
[... DNF output omitted for brevity ...]
[user@disp9524 ~]$ sudo cp /etc/mock/fedora-33-x86_64.cfg /etc/mock/fedora-25-x86_64.cfg
[user@disp9524 ~]$ sudo sed -i 's/33/25/' /etc/mock/fedora-25-x86_64.cfg
[user@disp9524 ~]$ mock -r /etc/mock/fedora-25-x86_64.cfg install desktop-file-utils rpm-build python3-mock python3-mypy
[... mock output omitted for brevity...]
# Copy the source to the jail.
[user@disp9524 ~]$ mock -r /etc/mock/fedora-25-x86_64.cfg --chroot "bash -c 'rm -rf /builddir'"
[... mock output omitted for brevity...]
[user@disp9524 ~]$ mock -r /etc/mock/fedora-25-x86_64.cfg --copyin qubes-shared-folders /builddir/qubes-shared-folders
[... mock output omitted for brevity...]
# Build
[user@disp9524 ~]$ mock -r /etc/mock/fedora-25-x86_64.cfg --chroot "bash -c 'cd /builddir/qubes-shared-folders && make rpm'"
[... make output omitted for brevity...]
# Copy the results out.
[user@disp9524 ~]$ rm -rf qubes-shared-folders
[user@disp9524 ~]$ mock -r /etc/mock/fedora-25-x86_64.cfg --copyout /builddir/qubes-shared-folders qubes-shared-folders
[... mock output omitted for brevity...]
```

An RPM package will be deposited in the `qubes-shared-folders` directory,
named `qubes-shared-folders-dom0-<version>-<release>.noarch.rpm`.  Copy
it to dom0, and install it using `sudo rpm -ivh`.  This package contains
service security policies (default `deny` for the file sharing service).

You can now power the disposable qube off.

### Shut down all involved qubes

Now shut down all involved qubes, to ensure the installation takes
effect.  You don't need to shut down your computer or dom0.
