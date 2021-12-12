# Inter-VM shared folders for Qubes OS

This package aims to solve the problem of inter-VM file sharing
(rather than manual copying) by allowing a VM to mount folders
from any other VM's file system (or mounted network shares).

This package contains:

* a Qubes OS `qrexec` service to serve folders from a qube
* a program to mount folders in a qube served from other qubes
* policy (for dom0) to permit or deny the process

There's a number of [to-do items](./TODO.md) for which we'd love your help!

## Usage

The following instructions assume that the qube which contains the
files you want to share is named `server` and the qube where you
want to access the files is named `client`.  They also assume you
successfully finished the one-time installation instructions below.

To mount `/home/user` from the `server` VM onto `/home/user/mnt`,
run the following on a terminal of `client`:

```
cd /home/user
mkdir mnt
qvm-mount-folder server /home/user mnt
```

At this point you will see an authorization message from dom0 asking
you if you really want to give `client` access to `server`'s files.
Note that the access is blanket read/write, and once given.

Authorize the access by confirming the name of the qube (`server` on
the dialog and continuing.

**Presto.**  You should be able to use a file manager, a terminal, or
any of your favorite applications to use files in `/home/user/mnt`
-- these files are all stored in `server` on folder `/home/user`.

To finish using it, run `sudo umount /home/user/mnt`.  Note that
currently, the connection remains open between `client` and `server`
even after unmounting, so the only way to sever the connection is
to power off one of the two qubes.


## Security considerations

* There is currently no way to control *which* folders of the server
  qube can be requested by client qubes.  In principle this should
  be doable because `diod` can export only a subtree of any file
  system hierarchy, but the next point needs to be addressed first.
* The connection remains open after unmounting.  This means that the
  client VM can in principle continue to access resources from the
  file system exported by `diod` before the unmount happened.
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

First, build a [`diod`](https://github.com/Rudd-O/diod) RPM package:

```
git clone https://github.com/Rudd-O/diod
cd diod
./autogen.sh && ./configure --prefix=/usr && make dist && rpmbuild -ts *tar.gz
```

Then, install this package on the template of the qube you plan to
*share your files from*.

Now build RPM packages for this software:

```
git clone https://github.com/Rudd-O/qubes-shared-folders
cd qubes-shared-folders
make rpm
```

Two RPMs will result:

1. `qubes-shared-folders-...noarch.rpm`
2. `qubes-shared-folders-dom0-...noarch.rpm`

Install the first one in the template of the qube you plan to
*share your files from*, as well as the template of the qube
you plan to *access your files in*.

Install the second one in dom0.  This package contains policy
(default `ask`) for the service.

Now shut down all involved qubes, to ensure the installation takes.
You don't need to shut down your computer or dom0.
