#!/bin/bash

usage() {
	bin=$(basename $0)
	echo >&2 "Usage: $bin"
	echo >&2
	echo >&2 "Install PagingServer and all necessary"
	echo >&2 " dependencies from the deb repo on a Debian Jessie system."
	echo >&2 "See also README.install.rst file."
	exit ${1:-0}
}
[[ $# -gt 0 || "$1" = -h || "$1" = --help ]] && usage


set -e -o pipefail

apt_install() {
	env\
		DEBIAN_FRONTEND=noninteractive\
		DEBIAN_PRIORITY=critical\
		apt-get\
			-o Dpkg::Options::="--force-confdef"\
			-o Dpkg::Options::="--force-confold"\
			--force-yes -y install "$@"
}

apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 3D021F1F4C670809
echo 'deb http://paging-server.ddns.net/ jessie main' >/etc/apt/sources.list.d/paging-server.list
apt-get update

apt_install --no-install-recommends jackd1 alsa-utils
apt_install paging-server python-systemd

getent passwd paging &>/dev/null\
	|| useradd -r -d /var/empty -s /bin/false -G audio paging
install -o root -g paging -m640 -T /usr/share/doc/paging-server/paging.example.conf /etc/paging.conf


echo
echo --------------------
echo
echo "Installation process completed successfully."
echo
echo "Edit configuration file in: /etc/paging.conf"
echo "At least domain/user/pass MUST be specified there in the [sip] section."
echo
echo "After that, start the service with: systemctl start paging-jack-out-all paging"
echo "  check status: systemctl status jack@paging paging"
echo "  check service log with: journalctl -ab -u paging"
echo "  continuously 'tail' log with: journalctl -af -u paging"
echo "  continuously tail all system logs with: journalctl -af"
echo
echo "If service has been started and is running successfully,"
echo " enable it to run on boot with: systemctl enable paging-jack-out-all paging"
echo
echo "OrangePi PC Notes: Unmute Audio lineo in alsamixer by scrolling right and pressing m"
echo "Start service with:  systemctl start paging-jack-out@hw:0 paging"
echo "Enable service with: systemctl enable paging-jack-out@hw:0 paging"
echo
echo --------------------
