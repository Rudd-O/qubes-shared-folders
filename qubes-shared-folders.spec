%define debug_package %{nil}

%define mybuildnumber %{?build_number}%{?!build_number:1}

Name:           qubes-shared-folders
Version:        0.3.1
Release:        %{mybuildnumber}%{?dist}
Summary:        Inter-VM folder sharing via Plan 9 filesystem

License:        GPLv2+
URL:            https://github.com/Rudd-O/%{name}
Source0:        https://github.com/Rudd-O/%{name}/archive/{%version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  make
BuildRequires:  python3
BuildRequires:  python3-pytest
BuildRequires:  python3-mock
BuildRequires:  python3-mypy
BuildRequires:  desktop-file-utils
BuildRequires:  cargo-rpm-macros >= 24
BuildRequires:  python3-rpm-macros
Requires:       bash
Requires:       python3
Requires:       qubes-core-agent-qrexec

%package dom0
Summary:        Policy package for Qubes OS dom0s that arbitrates access to shared folders

Requires:       qubes-core-dom0-linux >= 4.1
Requires:       python3
Requires:       gobject-introspection
Requires:       gtk3
BuildArch:      noarch

%description
This package offers a collection of programs that allow users to
securely mount folders from one qube into another qube.

%description dom0
This package contains the Qubes OS execution policy for the %{name} package.
You are meant to install this package on the dom0, if you installed the
%{name} package installed on any of your qubes.

%prep
%autosetup -n %{name}-%{version}
%cargo_prep -v vendor

%generate_buildrequires

%build
%cargo_build

%install
rm -rf "$RPM_BUILD_ROOT"
for target in install-client install-server install-dom0; do
    make $target DESTDIR="$RPM_BUILD_ROOT" BINDIR=%{_bindir} SYSCONFDIR=%{_sysconfdir} LIBEXECDIR=%{_libexecdir} DATADIR=%{_datadir} || exit $?
done
touch "$RPM_BUILD_ROOT"/%{_sysconfdir}/qubes/shared-folders/policy.db

%check
desktop-file-validate desktop/*.desktop
make test || exit $?

%files
%attr(0755, root, root) %{_bindir}/qvm-mount-folder
%attr(0755, root, root) %{_bindir}/qfsd
%attr(0755, root, root) %{_sysconfdir}/qubes-rpc/ruddo.ConnectToFolder
%attr(0644, root, root) %{python3_sitearch}/sharedfolders/*
%doc README.md TODO.md doc

%files dom0
%attr(0644, root, root) %{_datadir}/%{name}/ui/*.ui
%attr(0644, root, root) %{_datadir}/applications/*.desktop
%config(noreplace) %attr(0664, root, qubes) %{_sysconfdir}/qubes/policy.d/*-qubes-shared-folders.policy
%dir %attr(2775, root, qubes) %{_sysconfdir}/qubes/shared-folders
%ghost %config(noreplace) %attr(0664, root, qubes) %{_sysconfdir}/qubes/shared-folders/policy.db
%attr(0755, root, root) %{_sysconfdir}/qubes-rpc/ruddo.AuthorizeFolderAccess
%attr(0755, root, root) %{_sysconfdir}/qubes-rpc/ruddo.QueryFolderAuthorization
%attr(0755, root, root) %{_libexecdir}/qvm-authorize-folder-access
%attr(0644, root, root) %{python3_sitearch}/sharedfolders/*
%attr(0755, root, root) %{_bindir}/qvm-folder-share-manager
%doc README.md TODO.md doc src/test-qfsd-mount.py

%changelog
* Sat Dec 11 2021 Manuel Amador (Rudd-O) <rudd-o@rudd-o.com>
- Initial release.
