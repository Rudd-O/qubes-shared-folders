%define debug_package %{nil}

%define mybuildnumber %{?build_number}%{?!build_number:1}

%{!?python3_sitearch: %define python3_sitearch  %(python3 -c 'from distutils.sysconfig import get_python_lib; print(get_python_lib(1))')}

Name:           qubes-shared-folders
Version:        0.2.1
Release:        %{mybuildnumber}%{?dist}
Summary:        Inter-VM folder sharing via Plan 9 filesystem
BuildArch:      noarch

License:        GPLv2+
URL:            https://github.com/Rudd-O/%{name}
Source0:        https://github.com/Rudd-O/%{name}/archive/{%version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  make
BuildRequires:  python3
BuildRequires:  python3-mock
BuildRequires:  python3-mypy
BuildRequires:  desktop-file-utils
Requires:       bash
Requires:       python3
Requires:       qubes-core-agent-qrexec
Requires:       diod

%package dom0
Summary:        Policy package for Qubes OS dom0s that arbitrates access to shared folders

Requires:       qubes-core-dom0-linux >= 4.1
Requires:       python3
Requires:       gobject-introspection
Requires:       gtk3

%description
This package offers a collection of programs that allow users to
securely mount folders from one qube into another qube.

%description dom0
This package contains the Qubes OS execution policy for the %{name} package.
You are meant to install this package on the dom0, if you installed the
%{name} package installed on any of your qubes.

%prep
%setup -q

%build
# variables must be kept in sync with install
make DESTDIR=$RPM_BUILD_ROOT BINDIR=%{_bindir} SYSCONFDIR=%{_sysconfdir} LIBEXECDIR=%{_libexecdir} DATADIR=%{_datadir}

%install
rm -rf $RPM_BUILD_ROOT
# variables must be kept in sync with build
for target in install-client install-dom0; do
    make $target DESTDIR=$RPM_BUILD_ROOT BINDIR=%{_bindir} SYSCONFDIR=%{_sysconfdir} LIBEXECDIR=%{_libexecdir} DATADIR=%{_datadir}
done
touch $RPM_BUILD_ROOT/%{_sysconfdir}/qubes/shared-folders/policy.db

%check
desktop-file-validate desktop/*.desktop
python3 -c 'import sys
if sys.version_info.major == 3 and sys.version_info.minor < 6:
    sys.exit(1)
' && {
    make test || exit $?
} || {
    make unit || exit $?
}
if grep -r --exclude-dir=__pycache__ '@.*@' $RPM_BUILD_ROOT ; then
    echo "Check failed: files with AT identifiers appeared" >&2
    exit 1
fi

%files
%attr(0755, root, root) %{_bindir}/qvm-mount-folder
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
%doc README.md TODO.md doc

%changelog
* Sat Dec 11 2021 Manuel Amador (Rudd-O) <rudd-o@rudd-o.com>
- Initial release.
