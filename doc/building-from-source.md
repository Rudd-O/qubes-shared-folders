# How to build and install Qubes shared folders from source

You'll need a working Qubes OS 4.2 system and familiarity with Qubes OS,
the terminal, and disposable qubes.  The instructions are complex, so to
facilitate the process, these are executable instructions you can run from
the safety of a disposable qube, or (if you know how) replicate by hand.

Start a terminal on a disposable qube based on the Fedora template backing
your regular qubes you intend to share files between.  When selecting the
terminal program to launch, choose the `gnome-terminal` Terminal application
rather than `xterm`, since `xterm` is hard to operate.

Now enlarge the *Private storage max size* option of the disposable qube.
Do this from the *Settings* dialog of the qube.  Make it at least 10 GB.

Run the following command on that terminal:

```
curl https://raw.githubusercontent.com/Rudd-O/qubes-shared-folders/master/doc/building-from-source.md | tail -n +25 | bash
```

That command will run the following commands on your disposable qube:

```bash
set -ex
sudo dnf install -y git /usr/bin/toolbox rpm-build gawk tar wget mock

if ! test -d srpms
then
    mkdir -p src

    for dep in p9_wire_format_derive-fedora-packaging p9-fedora-packaging
    do
        rm -rf src/"$dep"
        git clone https://github.com/Rudd-O/"$dep" src/"$dep"
        cd src/"$dep"
        url=$(rpmspec -P *.spec | grep ^Source: | awk ' { print $2 } ')
        fn=$(basename "$url")
        wget -O "$fn" "$url"
        rpmbuild --define "_srcrpmdir ./" --define "_sourcedir ./" -bs *.spec
        cd ../..
    done

    rm -rf src/qubes-shared-folders
    git clone https://github.com/Rudd-O/qubes-shared-folders src/qubes-shared-folders
    cd src/qubes-shared-folders
    git checkout origin/qfsd # FIXME
    make srpm
    cd ../..

    mkdir -p srpms
    mv -f src/*/*.src.rpm srpms
fi

if ! test -d rpms/fedora
then
    mkdir -p rpms/fedora
    {
        set -e
        sudo mock -nN --resultdir "$PWD/rpms/fedora" --postinstall --rebuild srpms/rust-p9_*.src.rpm
        sudo mock -nN --resultdir "$PWD/rpms/fedora" --postinstall --rebuild srpms/rust-p9-*.src.rpm
        sudo mock -nN --resultdir "$PWD/rpms/fedora" --rebuild srpms/qubes-shared-folders-*.src.rpm
    } || {
        rm -rf rpms/fedora
        exit 1
    }
fi

if ! test -d rpms/dom0
then
    mkdir -p rpms/dom0
    {
        set -e
        toolbox -r 37 run sudo dnf install -y mock || {
            toolbox -r 37 create -y
            toolbox -r 37 run sudo dnf install -y mock
        }
        toolbox -r 37 run mock --no-bootstrap-chroot -nN --resultdir "$PWD/rpms/dom0" --postinstall --rebuild srpms/rust-p9_*.src.rpm
        toolbox -r 37 run mock --no-bootstrap-chroot -nN --resultdir "$PWD/rpms/dom0" --postinstall --rebuild srpms/rust-p9-*.src.rpm
        toolbox -r 37 run mock --no-bootstrap-chroot -nN --resultdir "$PWD/rpms/dom0" --rebuild srpms/qubes-shared-folders-*.src.rpm
    } || {
        rm -rf rpms/dom0
        exit 1
    }
fi

exit
```

Once that command finishes, there will be a folder named `rpms` in the home
directory of your disposable qube.  Copy that folder to your template qube and
install onto the template all packages within the subfolder `fedora` that match
the expression `qubes-shared-folders-*.x86_64.rpm`.

Then move the packages within the subfolder `dom0` to your dom0, and install
in dom0 all packages from that folder that match the expression
`qubes-shared-folders-dom0-*.noarch.rpm`.

That completes the installation.  Shut down your template qube, and restart
any qubes you plan to use this software in.

## Building and installing for other platforms

### On Windows

The 9P file system client is in principle available as a driver
for Windows, but the Qubes-specific authorization mechanisms are not
implemented, so you won't be able to make that work there.

### On Debian and derivatives

The client/server package will work in a Debian qube correctly, provided
everything is properly installed.  From a copy of the source in a Debian
disposable qube, run `make install-client install-server DESTDIR=/tmp`
to deploy everything to `/tmp` (causing the necessary binaries to be
built).  These commands will require a few dependencies on the system you
build on, including `cargo` from the Rust collection.

Then copy *the source tree* to a folder in your template (preserving
timestamps), and then run `make install-client install-server DESTDIR=/usr`
within that folder of your template.  Note that this will modify your
template's root file system permanently.

You will still need to build and install the dom0 package for your dom0.
Follow the Fedora instructions above to do so.

Pull requests are gladly welcome to enable packaging the client for Debian.

### Qubes OS 4.1?

It is not currently known if the instructions above will work to build
(using toolbox images for Fedora 32 instead of Fedora 37) since the Rust
packaging ecosystem for Fedora was very different back in the Fedora 32
times.  You may as well give it a shot.

### Qubes 4.0 users

This is no longer supported.  Sorry.
