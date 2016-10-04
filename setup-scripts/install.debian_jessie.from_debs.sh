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

apt_install --no-install-recommends pulseaudio pulseaudio-utils alsa-utils
apt_install paging-server python-systemd
apt_install python-setuptools # missing dep for older packages

if getent passwd paging &>/dev/null ; then
	[[ -e /home/paging ]] || {
		usermod -d /home/paging paging
		mkdir -p -m700 /home/paging
		chown -R paging: /home/paging
	}
else useradd -r -md /home/paging -s /bin/false -G audio paging
fi

[[ -e /etc/paging.conf ]]\
	|| install -o root -g paging -m640 -T /usr/share/doc/paging-server/paging.example.conf /etc/paging.conf


echo
echo --------------------
echo
echo "Installation process completed successfully."
echo
echo "Edit configuration file in: /etc/paging.conf"
echo "At least domain/user/pass MUST be specified there in the [sip] section."
echo
echo "Then configure pulseaudio and/or music player instances to start."
echo
echo "After that, start the service with: systemctl start paging"
echo "  check status: systemctl status paging"
echo "  check service log with: journalctl -ab -u paging"
echo "  continuously 'tail' log with: journalctl -af -u paging"
echo "  continuously tail all system logs with: journalctl -af"
echo
echo "If service has been started and is running successfully,"
echo " enable it to run on boot with: systemctl enable paging"
echo
echo --------------------

exit 0
