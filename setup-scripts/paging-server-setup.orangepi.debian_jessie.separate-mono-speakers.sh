#!/bin/bash

usage() {
	bin=$(basename $0)
	echo >&2 "Usage: $bin"
	echo >&2 "Usage: $bin -x"
	echo >&2
	echo >&2 "Setup OrangePi with Debian Jessie to run PagingServer as the main app."
	echo >&2 "This script sets up two mono outputs, with separate mpd running for each."
	echo >&2 "-x option disables check for platform type in /proc/cpuinfo."
	exit ${1:-0}
}
[[ $# -gt 1 || "$1" = -h || "$1" = --help ]] && usage
[[ $# -eq 1 && "$1" != -x ]] && usage 1

[[ "$UID" == 0 ]] || {
	echo >&2 "This script should be run as root."
	exit 1
}


set -e -o pipefail

get_repo_file() {
	wget -q -O- https://raw.githubusercontent.com/AccelerateNetworks/PagingServer/master/"$1"
}


setup_tmp=$(mktemp /tmp/paging-server-setup.XXXXX.sh)
trap "rm -f '$setup_tmp'" EXIT
get_repo_file setup-scripts/paging-server-setup.orangepi.debian_jessie.sh >"$setup_tmp"
bash "$setup_tmp" $1


echo
echo '-----===== Extra step: changing output to be two separate mono speakers'
echo

sed -i 's/^# \(load-module module-remap-sink \)/\1/' /etc/pulse/paging.pa

get_repo_file setup-configs/mpd.instance.conf | sed 's|instance|left|' >/etc/mpd.left.conf
get_repo_file setup-configs/mpd.instance.conf | sed 's|instance|right|' >/etc/mpd.right.conf

systemctl stop mpd@speakers
systemctl disable mpd@speakers

systemctl daemon-reload
systemctl enable mpd@left mpd@right

echo
echo --------------------
echo
echo "System setup process completed successfully."
echo
echo "This particular setup starts separate mpd@left and mpd@right music players."
echo "Use following files to init their playlists:"
echo "  /etc/mpd.left.url or /etc/mpd.left.m3u - for 'left channel' mpd player."
echo "  /etc/mpd.right.url or /etc/mpd.right.m3u - for 'right channel' mpd player."
echo
echo "mpd instances will be started on boot, or you can"
echo "  create url/m3u files and (re)start these manually, using command:"
echo " systemctl restart mpd@left mpd@right"
echo
echo "Have a nice day."
echo
echo --------------------
