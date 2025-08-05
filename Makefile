BINDIR=/usr/bin
LIBEXECDIR=/usr/libexec
SYSCONFDIR=/etc
DATADIR=/usr/share
DESTDIR=
PROGNAME=qubes-shared-folders
PYTHON=/usr/bin/python3
SITEPACKAGES=$(shell python3 -Ic "import sysconfig; print(sysconfig.get_path('platstdlib', vars={'platbase': '/usr', 'base': '/usr'}))")

.PHONY: clean install-client install-dom0 install-py black test mypy unit

clean:
	find -name '*~' -print0 | xargs -0 rm -f
	find -name '__pycache__' -print0 | xargs -0 rm -rf
	find -name .mypy_cache -print0 | xargs -0 rm -rf
	rm -fr *.tar.gz *.rpm target

dist: clean
	excludefrom= ; test -f .gitignore && excludefrom=--exclude-from=.gitignore ; DIR=$(PROGNAME)-`awk '/^Version:/ {print $$2}' $(PROGNAME).spec` && FILENAME=$$DIR.tar.gz && tar cvzf "$$FILENAME" --exclude="$$FILENAME" --exclude=.git --exclude=.gitignore $$excludefrom --transform="s|^|$$DIR/|" --show-transformed *

rpm: dist
	T=`mktemp -d` && rpmbuild --define "_topdir $$T" -ta $(PROGNAME)-`awk '/^Version:/ {print $$2}' $(PROGNAME).spec`.tar.gz || { rm -rf "$$T"; exit 1; } && set -o pipefail && find "$$T" -type f -print0 | xargs -0 -I{} mv {} . || { rm -rf "$$T"; exit 1; } && rm -rf "$$T"

srpm: dist
	T=`mktemp -d` && rpmbuild --define "_topdir $$T" -ts $(PROGNAME)-`awk '/^Version:/ {print $$2}' $(PROGNAME).spec`.tar.gz || { rm -rf "$$T"; exit 1; } && mv "$$T"/SRPMS/* . || { rm -rf "$$T"; exit 1; } && rm -rf "$$T"

install-py:
	install -Dm 644 py/sharedfolders/*.py -t $(DESTDIR)/$(SITEPACKAGES)/sharedfolders/
	$(PYTHON) -m compileall $(DESTDIR)/$(SITEPACKAGES)/sharedfolders/

install-client: install-py
	install -Dm 755 bin/qvm-mount-folder -t $(DESTDIR)/$(BINDIR)/
	install -Dm 755 etc/qubes-rpc/ruddo.ConnectToFolder -t $(DESTDIR)/$(SYSCONFDIR)/qubes-rpc/

target/release/qfsd: src/main.rs $(wildcard p9/src/*.rs) $(wildcard p9/src/protocol/*.rs) $(wildcard p9/src/server/*.rs)
	cargo build --release

install-server: target/release/qfsd
	install -Dm 755 target/release/qfsd -t $(DESTDIR)/$(BINDIR)/

install-dom0: install-py
	install -Dm 664 etc/qubes/policy.d/80-*.policy -t $(DESTDIR)/$(SYSCONFDIR)/qubes/policy.d/
	test -f $(DESTDIR)/$(SYSCONFDIR)/qubes/policy.d/79-*.policy || install -Dm 664 etc/qubes/policy.d/79-*.policy -t $(DESTDIR)/$(SYSCONFDIR)/qubes/policy.d/
	getent group qubes >/dev/null 2>&1 || exit 0 ; [ "$UID" = "0" ] || { echo "Not chgrping, not running as root" >&2 ; exit 0 ; } ; chgrp qubes $(DESTDIR)/$(SYSCONFDIR)/qubes/policy.d/*.policy
	install -Dm 755 etc/qubes-rpc/ruddo.AuthorizeFolderAccess -t $(DESTDIR)/$(SYSCONFDIR)/qubes-rpc/
	install -Dm 755 etc/qubes-rpc/ruddo.QueryFolderAuthorization -t $(DESTDIR)/$(SYSCONFDIR)/qubes-rpc/
	install -Dm 755 libexec/qvm-authorize-folder-access -t $(DESTDIR)/$(LIBEXECDIR)/
	install -Dm 755 bin/qvm-folder-share-manager -t $(DESTDIR)/$(BINDIR)/
	install -Dm 644 ui/*.ui -t $(DESTDIR)/$(DATADIR)/$(PROGNAME)/ui/
	install -Dm 644 desktop/*.desktop -t $(DESTDIR)/$(DATADIR)/applications/
	mkdir -p $(DESTDIR)/$(SYSCONFDIR)/qubes/shared-folders
	chmod 2775 $(DESTDIR)/$(SYSCONFDIR)/qubes/shared-folders
	getent group qubes >/dev/null 2>&1 || exit 0 ; [ "$UID" = "0" ] || { echo "Not chgrping, not running as root" >&2 ; exit 0 ; } ; chgrp qubes $(DESTDIR)/$(SYSCONFDIR)/qubes/shared-folders

black:
	grep "^#!/usr/bin/python3" -r . | cut -d : -f 1 | sort | uniq | xargs -n1 black

unit:
	PYTHONPATH="$$PWD"/py $(PYTHON) -m pytest -v

mypy:
	PYTHONPATH="$$PWD"/py MYPYPATH="$$PWD"/py mypy --python-version 3.10 --strict -p sharedfolders

test: unit mypy
