# Paging Server
Announcement/PA/Paging/Public Address Server stuff to do the needful.

## Installation
These instructions are for Debian-based Linux distributions. They should point you in the right direction to set this up on other distributions - just don't expect them to work verbatim.
### Install the Dependencies
```
sudo apt-get install build-essential python2.7-dev nano subversion git
sudo pip install raven
```
### Download PJSIP
```
svn co http://svn.pjsip.org/repos/pjproject/trunk pjsip
```
### Compile PJSIP
```
cd pjsip
./configure && make dep && make
```
### Install PJSUA
```
cd pjsip-apps/src/python
sudo python ./setup.py install
cd
```
### Get our Git repo
```
git clone https://github.com/AccelerateNetworks/PagingServer
cd PagingServer
```
### Put the files in the right places
```
sudo cp autoanswer.py /opt/autoanswer.py
sudo cp config.conf /etc/config.conf
sudo cp paging.service /etc/systemd/system/paging.service
```
### Enable systemd service
```
systemctl enable paging.service
```
### Add your SIP account
```
sudo nano /etc/config.conf
```
Change the top 3 values to your SIP server, username (usually ext. number) and password. Get rid of the PA section from [PA] down unless you want a .wav to be played prior to each call.

To configure the PA section set the path to the .wav file you want played in `file =` and set how many seconds it should play in `filetime =`.

## Running the Paging Server
Run either of the commands below:
```
Run in bash/terminal:
/usr/bin/python /opt/autoanswer.py

or

Start the systemd service (nonfunctional!!!)
sudo service paging start
```

## Benchmarks

We've tested this script with thousands of calls, it is fairly reliable and light on resources. Total CPU use on a Pentium 4 @ 2.8ghz hovered around 0.5% with 4MB ram usage. identical figures were observed on a Celeron D @ 2.53Ghz, you could probably get away with whatever your operating system requires to run in terms of hardware.
