#!/bin/bash

usage() {
	bin=$(basename $0)
	echo >&2 "Usage: $bin [-x]"
	echo >&2
	echo >&2 "Install PagingServer and all necessary"
	echo >&2 " dependencies to preset paths on a Debian Jessie system."
	echo >&2 "See also README.install.rst file."
	exit ${1:-0}
}
[[ $# -gt 1 || "$1" = -h || "$1" = --help ]] && usage

set -e -o pipefail


[[ "$1" = -x ]] || {
	echo >&2 "This script is intended to run ONLY on Debian Jessie system."
	echo >&2 "It will install packages via apt-get and create some preset paths (e.g. /srv/paging) on the system."
	echo >&2 "If you are OK with that, run script with -x option, like this: $(basename "$0") -x"
	echo >&2 "See README.install.rst file for descriptions of all the actions here."
	exit 1
}

[[ $(id -u) -eq 0 ]] || {
	echo >&2 "This script should be run as root."
	exit 1
}


pkg_cache=/var/tmp/PagingServer.debs
pkg_list="$pkg_cache"/apt-get-installed.list

tmp_dir=$(mktemp -d "${HOME}"/PagingServer.install.XXXXXX)
[[ -n "$NOCLEANUP" ]] || trap "rm -rf '$tmp_dir'" EXIT
cd "$tmp_dir"

echo --------------------
echo
echo "Using temporary directory (will be removed on exit): $tmp_dir"
echo
echo "Names of all NEW packages installed *via apt-get* will be logged to: $pkg_list"
echo "Some of these (e.g. build tools) can be manually removed afterwards."
echo
echo "All created debian packages will be stored in: $pkg_cache"
echo
echo --------------------
echo


die() { echo >&2 "$@"; exit 1; }
die_check() { echo >&2 "Check failed: $@"; exit 1; }
force_empty_line_end() { { rm "$1"; awk '{chk=!$0; print} END {if (!chk) print ""}' >"$1"; } <"$1"; }

export DEBIAN_FRONTEND=noninteractive DEBIAN_PRIORITY=critical

dpkg_check() {
	for p in "$@"; do
		dpkg-query -W -f='${Status}\n' "$p" | grep -q '^install ok installed$' || return 1
	done
}

apt_install() {
	local args=() args_pkg=()
	for arg in "$@"; do
		[[ "${arg#-}" = "$arg" ]] &&
			{ dpkg_check "$arg" || { args_pkg+=( "$arg" ); false; } }\
			|| args+=( "$arg" )
	done
	[[ ${#args_pkg[@]} -ne 0 ]] || return 0

	for arg in "${args_pkg[@]}"; do echo "$arg" >>"$pkg_list"; done
	LC_ALL=C sort -u "$pkg_list" >"$pkg_list".clean
	mv "$pkg_list"{.clean,}

	apt-get\
		-o Dpkg::Options::="--force-confdef"\
		-o Dpkg::Options::="--force-confold"\
		--force-yes -y install "${args[@]}"
}

mkdir -p "$pkg_cache"


apt_install --no-install-recommends jackd1

jackd --version | grep '^jackd version 0\.'\
	|| die "Failed to match valid jackd1 version from 'jackd --version'"


apt_install curl build-essential checkinstall libjack-dev python python-dev python-setuptools

cc --version
make --version
python2-config --includes

dpkg_check pjproject python-pjsua >/dev/null || {
	pj_ver=2.4.5
	pj_dir="pjproject-${pj_ver}"
	pj_tar=/tmp/"${pj_dir}.tar.bz2"
	pj_url=http://www.pjsip.org/release/"${pj_ver}/${pj_dir}.tar.bz2"

	[[ ! -e "${pj_dir}" ]] || rm -rf "${pj_dir}"
	[[ -e "${pj_tar}" ]] || {
		echo "Using temporary pjproject tar-path: $pj_tar"
		curl -L -o "$pj_tar" "${pj_url}"
	}
	tar -xf "${pj_tar}"

	pushd "${pj_dir}"

	./configure --prefix=/usr --enable-shared --disable-v4l2 --disable-video
	sed -i 's/\(AC_PA_USE_.*\)=1/\1=0/' third_party/build/portaudio/os-auto.mak
	echo 'AC_PA_USE_JACK=1' >>third_party/build/portaudio/os-auto.mak
	echo 'export CFLAGS += -DPA_USE_JACK=1' >>third_party/build/portaudio/os-auto.mak
	echo 'PORTAUDIO_OBJS += pa_jack.o pa_ringbuffer.o' >>third_party/build/portaudio/os-auto.mak
	echo '#include "../../../portaudio/src/hostapi/jack/pa_jack.c"' > third_party/build/portaudio/src/pa_jack.c
	echo '#include "../../../portaudio/include/pa_jack.h"' > third_party/build/portaudio/src/pa_jack.h
	sed -i 's/-lportaudio/-ljack \0/' build.mak
	make dep
	make
	sed -i 's/^\(\s\+\)cp -af /\1cp -r /' Makefile

	checkinstall -y\
		--pkgname=pjproject --pkgversion="${pj_ver}"

	dpkg_check pjproject
	cp *.deb "$pkg_cache"/

	pushd pjsip-apps/src/python

	checkinstall -y\
		--pkgname=python-pjsua --pkgversion="${pj_ver}"\
		--exclude /usr/local/lib/python2.7/dist-packages/easy-install.pth\
		-- python2 setup.py install

	dpkg_check python-pjsua
	cp *.deb "$pkg_cache"/

	popd

	python2 -c 'import pjsua; lib = pjsua.Lib(); lib.init(); lib.destroy()' 2>&1 |
		grep 'Transport manager created'

	popd

	rm "${pj_tar}"
}


apt_install python-cffi

dpkg_check python-jack || {
	curl -L https://github.com/spatialaudio/jackclient-python//archive/master.tar.gz | tar xz
	pushd jackclient-python-master

	checkinstall -y\
		--pkgname=python-jack\
		--pkgversion=$(grep '^__version__' jack.py | grep -o '[0-9.]\+')\
		--exclude /usr/local/lib/python2.7/dist-packages/easy-install.pth\
		-- python2 setup.py install

	dpkg_check python-jack
	cp *.deb "$pkg_cache"/

	popd
}
python2 -c 'import jack'

dpkg_check python-systemd || {
	apt_install libsystemd-dev libsystemd-journal-dev

	curl -L https://github.com/systemd/python-systemd/archive/v230.tar.gz | tar xz
	pushd python-systemd-230

	make
	checkinstall -y\
		--pkgname=python-systemd\
		--pkgversion=$(grep 'version *=' setup.py | grep -o '[0-9.]\+')\
		--exclude /usr/local/lib/python2.7/dist-packages/easy-install.pth\
		-- python2 setup.py install

	dpkg_check python-systemd
	cp *.deb "$pkg_cache"/

	popd
}
python2 -c 'import systemd.daemon; print systemd.daemon.__version__'

dpkg_check paging-server || {
	curl -L https://github.com/AccelerateNetworks/PagingServer/archive/master.tar.gz | tar xz
	pushd PagingServer-master

	cat >extras.list <<EOF
usr/lib/systemd/system/paging.service
usr/lib/systemd/system/jack@.service
usr/share/doc/PagingServer/paging.example.conf
EOF
	install -D -m0644 -t usr/lib/systemd/system/ paging.service jack@.service
	install -D -m0644 -t usr/share/doc/PagingServer/ paging.example.conf

	checkinstall -y\
		--pkgname=paging-server\
		--pkgversion=$(grep 'version *=' setup.py | grep -o '[0-9.]\+')\
		--exclude /usr/local/lib/python2.7/dist-packages/easy-install.pth\
		--include extras.list\
		-- python2 setup.py install

	dpkg_check paging-server
	cp *.deb "$pkg_cache"/

	popd
}
paging --version


id paging || useradd -r -d /var/empty -s /bin/false paging

[[ -e /etc/paging.conf ]]\
	|| install -o root -g paging -m640 -T /usr/share/doc/PagingServer/paging.example.conf /etc/paging.conf

[[ -n "$(systemctl cat paging)" ]] || die "Failed to load paging.service"
[[ -n "$(systemctl cat jack@paging)" ]] || die "Failed to load jack@paging.service"


echo
echo --------------------
echo
echo "Installation process completed successfully."
echo
echo "Edit configuration file in: /etc/paging.conf"
echo "At least domain/user/pass MUST be specified there in the [sip] section."
echo
echo "After that, start the service with: systemctl start jack@paging paging"
echo "  check status: systemctl status jack@paging paging"
echo "  check service log with: journalctl -ab -u paging"
echo "  continuously 'tail' log with: journalctl -ab -u paging"
echo
echo "If service has been started and is running successfully,"
echo " enable it to run on boot with: systemctl enable jack@paging paging"
echo
echo --------------------
