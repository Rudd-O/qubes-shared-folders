%define debug_package %{nil}

%define mybuildnumber %{?build_number}%{?!build_number:1}

Name:           qubes-shared-folders
Version:        0.0.2
Release:        %{mybuildnumber}%{?dist}
Summary:        Inter-VM folder sharing via Plan 9 filesystem
BuildArch:      noarch

License:        GPLv2+
URL:            https://github.com/Rudd-O/%{name}
Source0:        https://github.com/Rudd-O/%{name}/archive/{%version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  make
Requires:       bash
Requires:       python3
Requires:       qubes-core-agent-qrexec
Requires:       diod

%package dom0
Summary:        Policy package for Qubes OS dom0s that arbitrates %{name}

Requires:       qubes-core-dom0-linux

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
make DESTDIR=$RPM_BUILD_ROOT BINDIR=%{_bindir} SYSCONFDIR=%{_sysconfdir} LIBEXECDIR=%{_libexecdir}

%install
rm -rf $RPM_BUILD_ROOT
# variables must be kept in sync with build
for target in install-client install-dom0; do
    make $target DESTDIR=$RPM_BUILD_ROOT BINDIR=%{_bindir} SYSCONFDIR=%{_sysconfdir} LIBEXECDIR=%{_libexecdir}
done

%check
if grep -r '@.*@' $RPM_BUILD_ROOT ; then
    echo "Check failed: files with AT identifiers appeared" >&2
    exit 1
fi

%files
%attr(0755, root, root) %{_bindir}/qvm-mount-folder
%attr(0755, root, root) %{_libexecdir}/qvm-share-folder
%attr(0755, root, root) %{_sysconfdir}/qubes-rpc/ruddo.ShareFolder
%doc README.md

%files dom0
%config(noreplace) %attr(0664, root, qubes) %{_sysconfdir}/qubes-rpc/policy/ruddo.ShareFolder

%changelog
* Sat Dec 11 2021 Manuel Amador (Rudd-O) <rudd-o@rudd-o.com>
- Initial release.
