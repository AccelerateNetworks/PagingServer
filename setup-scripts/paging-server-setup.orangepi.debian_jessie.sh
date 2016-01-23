#!/bin/bash

usage() {
	bin=$(basename $0)
	echo >&2 "Usage: $bin"
	echo >&2 "Usage: $bin -x"
	echo >&2
	echo >&2 "Setup OrangePi with Debian Jessie to run PagingServer as the main app."
	echo >&2 "-x option disables check for platform type in /proc/cpuinfo."
	exit ${1:-0}
}
[[ $# -gt 1 || "$1" = -h || "$1" = --help ]] && usage
[[ $# -eq 1 && "$1" != -x ]] && usage 1

[[ "$UID" == 0 ]] || {
	echo >&2 "This script should be run as root."
	exit 1
}

[[ "$1" == -x ]] || {
	grep -q '^Hardware[[:space:]]*:[[:space:]]*sun8i$' /proc/cpuinfo\
			&& grep -q '^Debian GNU/Linux 8 ' /etc/issue || {
		echo >&2 "Failed to match Hardware=sun8i in /proc/cpuinfo"
		echo >&2 " or 'Debian GNU/Linux 8' in /etc/issue."
		echo >&2 "This script specifically written for Debian Jessie on"
		echo >&2 " OrangePi boards and should not work on any other platforms."
		echo >&2 "Use -x option to disable this check and run it here anyway."
		exit 1
	}
}


set -e -o pipefail

run_apt_get() {
	env\
		DEBIAN_FRONTEND=noninteractive\
		DEBIAN_PRIORITY=critical\
		apt-get\
			-o Dpkg::Options::="--force-confdef"\
			-o Dpkg::Options::="--force-confold"\
			--force-yes -y "$@"
}

get_repo_file() {
	wget -q -O- https://raw.githubusercontent.com/AccelerateNetworks/PagingServer/master/"$1"
}



echo
echo '-----===== Step: install.debian_jessie.from_debs.sh'
echo

get_repo_file setup-scripts/install.debian_jessie.from_debs.sh | bash


echo
echo '-----===== Step: networking setup (replace NM with dhcpcd)'
echo

run_apt_get install --no-install-recommends dhcpcd5

cat >/etc/dhcpcd.conf <<EOF
duid
persistent
option classless_static_routes
require dhcp_server_identifier
nohook resolv.conf, lookup-hostname, hostname, wpa_supplicant, timezone, test, dump
noipv4ll
slaac private

waitip 4
timeout 10
EOF

cat >/etc/systemd/system/dhcpcd.service <<EOF
[Unit]
Wants=network.target
Before=network.target

[Service]
Type=forking
PIDFile=/run/dhcpcd.pid
ExecStart=/sbin/dhcpcd -q
ExecStop=/sbin/dhcpcd -x

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable dhcpcd
systemctl disable resolvconf

rm -f /etc/resolv.conf
echo 'nameserver 8.8.8.8' >/etc/resolv.conf
echo 'nameserver 8.8.4.4' >>/etc/resolv.conf

systemctl disable NetworkManager ModemManager pppd-dns
run_apt_get remove network-manager modemmanager ppp
run_apt_get autoremove


echo
echo '-----===== Step: system.conf watchdog setup, journald.conf logging setup'
echo

grep -q '^RuntimeWatchdogSec=' /etc/systemd/system.conf\
	|| sed -i '/^\[Manager\]$/a\\nRuntimeWatchdogSec=14\nShutdownWatchdogSec=14\n' /etc/systemd/system.conf
grep -q '^Storage=' /etc/systemd/journald.conf\
	|| sed -i '/^\[Journal\]$/a\\nStorage=volatile\nRuntimeMaxUse=10\nRuntimeMaxFileSize=2M\n' /etc/systemd/journald.conf


echo
echo '-----===== Step: alsa config/levels/mute setup'
echo

amixer sset 'Lineout volume control' 31
amixer sset 'Audio lineout' on
alsactl store

## PulseAudio should be doing all softvol stuff here
# cat >/etc/asound.conf <<EOF
# pcm.!default {
#   # See http://www.alsa-project.org/alsa-doc/alsa-lib/pcm_plugins.html#pcm_plugins_softvol
#   type softvol
#   slave.pcm "sysdefault:CARD=audiocodec"
#   control.name "Soft-amp PCM"
#   hint.description "Sound thru alsa-softvol amp thing"
#   max_dB 32.0 # default is 0
#   # min_dB -51.0 # default is -51.0
# }
# EOF


echo
echo '-----===== Step: enable watchdog actions (reboot-on-fail) for PagingServer-related systemd units'
echo

for s in paging ; do
	mkdir -p /etc/systemd/system/"$s".service.d
	s=/etc/systemd/system/"$s".service.d/paging-reboot-on-fail.conf
	echo '[Service]' >"$s"
	echo 'StartLimitAction=reboot' >>"$s"
done


echo
echo '-----===== Step: starting/enabling PagingServer-related stuff'
echo

run_apt_get install --no-install-recommends mpd mpc
systemctl disable mpd
systemctl stop mpd

get_repo_file setup-configs/paging.pa |
	sed 's|\( module-alsa-sink device=sysdefault\) |\1:CARD=audiocodec |' |
	cat >/etc/pulse/paging.pa

get_repo_file setup-configs/mpd.instance.conf |
	sed 's|instance|speakers|' >/etc/mpd.speakers.conf

get_repo_file setup-configs/mpd@.service >/etc/systemd/system/mpd@.service
get_repo_file setup-configs/pulse.service >/etc/systemd/system/pulse.service

systemctl daemon-reload
systemctl enable mpd@speakers

if awk 'p&&/^\[/ {p=0} /^\[sip\]$/ {p=1} p&&/^ *(domain|user|pass) *= *<(sip server|username|password)>$/ {exit 1}' /etc/paging.conf
then
	systemctl start paging
	systemctl enable paging
	echo
	echo --------------------
	echo
	echo "System setup process completed successfully."
	echo
	echo "PagingServer has been started (should be running right now) and was enabled to start on boot."
	echo "If it will keep failing (with some restart-limit threshold),"
	echo " or its sound outputs will be crashing repeatedly, whole system will reboot."
	echo "So make sure that either configuration always stays correct,"
	echo " or run:  rm /etc/systemd/system/*.service.d/paging-reboot-on-fail.conf"
	echo
	echo "To auto-start radio playback on boot, create either"
	echo " /etc/mpd.speakers.url with e.g. 'https://live.uwave.fm:8443/listen-128.mp3.m3u' inside,"
	echo " or /etc/mpd.speakers.m3u with list of tracks or urls to play."
	echo "*.url file will be re-downloaded every time mpd starts."
	echo
	echo "mpd music player will be started on boot, or you can"
	echo "  create url/m3u file and (re)start it manually, using command:"
	echo " systemctl restart mpd@speakers"
	echo
	echo "Have a nice day."
	echo
	echo --------------------
	exit 0
else
	echo "ATTENTION:"
	echo "ATTENTION: Detected default or missing sip auth/connection credentials in /etc/paging.conf file."
	echo "ATTENTION:"
	echo "ATTENTION: These MUST be changed (under [sip] secion) to something that works"
	echo "ATTENTION:  (i.e. real account data) before starting/enabling the daemon."
	echo "ATTENTION: See README.rst and comments there for more information on these options."
	echo "ATTENTION:"
	echo "ATTENTION: Edit that file right now and run this script again to enable the service."
	echo "ATTENTION: It's perfectly safe to re-run this script any number of times."
	echo "ATTENTION:"
	echo "ATTENTION: EXITING without enabling paging.service."
	echo "ATTENTION:"
	exit 1
fi
