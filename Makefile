BINDIR=/usr/bin
LIBEXECDIR=/usr/libexec
SYSCONFDIR=/etc
DESTDIR=
PROGNAME=qubes-shared-folders

clean:
	find -name '*~' -print0 | xargs -0 rm -fv
	rm -fv *.tar.gz *.rpm

dist: clean
	excludefrom= ; test -f .gitignore && excludefrom=--exclude-from=.gitignore ; DIR=$(PROGNAME)-`awk '/^Version:/ {print $$2}' $(PROGNAME).spec` && FILENAME=$$DIR.tar.gz && tar cvzf "$$FILENAME" --exclude="$$FILENAME" --exclude=.git --exclude=.gitignore $$excludefrom --transform="s|^|$$DIR/|" --show-transformed *

rpm: dist
	T=`mktemp -d` && rpmbuild --define "_topdir $$T" -ta $(PROGNAME)-`awk '/^Version:/ {print $$2}' $(PROGNAME).spec`.tar.gz || { rm -rf "$$T"; exit 1; } && mv "$$T"/RPMS/*/* "$$T"/SRPMS/* . || { rm -rf "$$T"; exit 1; } && rm -rf "$$T"

srpm: dist
	T=`mktemp -d` && rpmbuild --define "_topdir $$T" -ts $(PROGNAME)-`awk '/^Version:/ {print $$2}' $(PROGNAME).spec`.tar.gz || { rm -rf "$$T"; exit 1; } && mv "$$T"/SRPMS/* . || { rm -rf "$$T"; exit 1; } && rm -rf "$$T"

install-client:
	install -Dm 755 libexec/qvm-share-folder -t $(DESTDIR)/$(LIBEXECDIR)/
	install -Dm 755 bin/qvm-mount-folder -t $(DESTDIR)/$(BINDIR)/
	install -Dm 755 etc/qubes-rpc/ruddo.ShareFolder -t $(DESTDIR)/$(SYSCONFDIR)/qubes-rpc/

install-dom0:
	install -Dm 664 etc/qubes-rpc/policy/ruddo.ShareFolder -t $(DESTDIR)/$(SYSCONFDIR)/qubes-rpc/policy/
	getent group qubes && chgrp qubes $(DESTDIR)/$(SYSCONFDIR)/qubes-rpc/policy/ruddo.ShareFolder || true
