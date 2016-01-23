PagingServer
============

SIP-based Announcement / PA / Paging / Public Address Server system.

Main component of this project is a script to run PJSUA_ SIP client connected to
a PulseAudio_ sound server routing audio to whatever sound cards and speaker
sets.

It picks up calls, plays klaxon on speakers, followed by the announcement made
in that call. Music plays in-between announcements.

Script controls PJSUA and PulseAudio (muting/unmuting streams there) to make
them work to that effect.

|

.. contents::
  :backlinks: none



Usage
-----

After installation (see below), the script should be configured, providing it
with at least the SIP account data for the general usage.

Configuration file (`ini format`_) locations:

* paging.conf
* /etc/paging.conf
* callpipe.conf
* /etc/callpipe.conf
* Paths specified on the command line.

All files will be looked up and parsed in that order, values in next ones
overriding corresponding ones in the previous and defaults.

See output of ``paging --help`` for info on how to specify additional
configuration, more up-to-date list of default paths, as well as general
information for all the other options available.

Provided `paging.example.conf`_ file has all the available configuration options
and their descriptions.

To see default configuration options, use ``paging --dump-conf-defaults``, and
run ``paging --dump-conf ...`` to see the actual options being picked-up and
used at any time.

There are two general (supported) ways to start and run the script:

* In the foreground (non-forking).
* As a systemd service.

Both are described in more detail below.


Start/run in the foreground
```````````````````````````

First - make sure PulseAudio_ and its ALSA_ backend are configured (and unmuted,
in case of ALSA) as they should be and pulse server can run/runs for same user
that this script will be running as.

How to do that is out of scope for this README.

Then just run the thing as::

  % paging

Can be used directly from terminal, or with any init system or daemon manager,
including systemd, upstart, openrc, runit, daemontools, debian's
"start-stop-daemon", simple bash scripts, etc.

For systemd in particular, see the "Running as a systemd service" section below.

Running from terminal to understand what's going on, these options might be also
useful::

  % paging --debug
  % paging --debug --pjsua-log-level 10
  % paging --dump-conf

See also "Installation" and "Audio configuration" sections below.


Running as a systemd service
````````````````````````````

This method should be preferred, as it correctly notifies init when service is
actually ready (i.e. pjsua inputs/outputs initialized), so that others can be
scheduled around that, and primes watchdog timer, detecting if/when app might
hang due to some bug.

Provided ``paging.service`` file (in the repository, just an ini file) should be
installed to ``/etc/systemd/system``, and assumes following things:

* PagingServer app should be run as a "paging" user, which exists on the system
  (e.g. in ``/etc/passwd``).

* "paging.py" script, its "entry point" or symlink to it is installed at
  ``/usr/local/bin/paging``.

* Configuration file can be read from one of default paths
  (see above for a list of these).

* Optional python-systemd_ module dependency is installed.

With all these correct, service can then be used like this:

* Start/stop/restart service::

    % systemctl start paging
    % systemctl stop paging
    % systemctl restart paging

* Enable service(s) to start on OS boot::

    systemctl enable paging

* See if service is running, show last log entries: ``systemctl status paging``
* Show all logs for service since last OS boot: ``journalctl -ab -u paging``

* Continously show ("tail") all logs in the system: ``journalctl -af``

* Brutally kill service if it hangs on stop/restart:
  ``systemctl kill -s KILL paging``
  (will be done after ~60s by systemd automatically).

See `systemctl(1) manpage`_ for more info on such commands.

If either app itself is installed to another location (not
``/usr/local/bin/paging``) or extra command-line parameters for it are required,
``ExecStart=`` line can be altered either in installed systemd unit file
directly, or via ``systemctl edit paging``.

``systemctl daemon-reload`` should be run for any modifications to
``/etc/systemd/system/paging.service`` to take effect.

Similarly, ``User=paging`` line can be altered or overidden to change system uid
to use for the app.

If python-systemd module is unavailable, following lines should be dropped from
the ``paging.service``::

  Type=notify
  WatchdogSec=...

And ``--systemd`` option removed from ``ExecStart=`` line, so that app would be
started as a simple non-forking process, which will then be treated correctly by
systemd without two options above.



Installation
------------

This is a regular package for Python 2.7 (not 3.X), but with some extra
run-time requirements (see below), which can't be installed from PyPI.

Package itself can be installed at any time using pip_, e.g. via ``pip install
PagingServer`` (this will try to install stuff to /usr!!!).

Unless you know python packaging though, please look at `pip2014.com`_, `python
packaging tutorial`_, documentation below for easy installation (from
packages/repo) on specific systems.


Requirements
````````````

* `Python 2.7`_ (NOT 3.X).

* PJSUA_ (PJSIP User Agent) and its python bindings.

  Can be packaged as "pjsip", "pjsua" or "pjproject" in linux distros.

  Python bindings (from the same tarball) can also be packaged separately as
  "python-pjproject" or something like that.

  If either of those isn't available, be sure to build and install pjsua AND its
  python bindings manually from the same sources, and NOT e.g. install pjsua
  from package and then build bindings separately.

* PulseAudio_

* `pulsectl python module`_

* (optional) ffmpeg_ binary - if audio samples are not wav files (will be
  converted on every startup, if needed).

* (optional) python-systemd_ - only if ``--systemd`` option is used (e.g. with
  shipped .service file).

  Developed and shipped separately from main systemd package since v223
  (2015-07-29), likely comes installed with systemd prior to that.

  Would probably make sense to install that module from OS package, which should
  be available if systemd is used there as init by default.

* (optional) raven_ python module - for reporting any errors via sentry.


Debian Jessie
`````````````

* Installing everything via debian packages from third-party repository.

  Running this one-liner should be the easiest way by far::

    wget -O- https://raw.githubusercontent.com/AccelerateNetworks/PagingServer/master/setup-scripts/install.debian_jessie.from_debs.sh | bash

  Or, if ``wget ... | bash`` sounds too scary, same exact steps as in that
  script are::

    # apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 3D021F1F4C670809
    # echo 'deb http://paging-server.ddns.net/ jessie main' >/etc/apt/sources.list.d/paging-server.list
    # apt-get update

    # apt-get install --no-install-recommends pulseaudio pulseaudio-utils alsa-utils
    # apt-get install paging-server python-systemd

    # useradd -r -d /var/empty -s /bin/false -G audio paging
    # install -o root -g paging -m640 -T /usr/share/doc/paging-server/paging.example.conf /etc/paging.conf

  Configure, set-levels and unmute alsa/pulse, if necessary (depends heavily on
  the specific setup)::

    # alsamixer
    # nano /etc/pulse/default.pa

  Then edit config in ``/etc/paging.conf`` and start/enable the daemon::

    # nano /etc/paging.conf
    # systemctl start paging
    # systemctl enable paging

  See "Usage" section for more details on how to run the thing.

  Packages here are built with `install.debian_jessie.sh`_ script described in
  the next section.

* Building/installing everything on-site with one script.

  It's possible to install all required packages, building missing ones where
  necessary by running `install.debian_jessie.sh`_ script from the repository as
  a root user (as it runs apt-get and such)::

    # wget https://raw.githubusercontent.com/AccelerateNetworks/PagingServer/master/setup-scripts/install.debian_jessie.sh
    # bash install.debian_jessie.sh -x

  (running without -x flag will issue a warning message and exit)

  It's safe to run the script several times or on a machine where some of the
  requirements (see the list above) are installed already - should skip steps
  that are already done or unnecessary.

  Script builds everything into deb packages, stores each in
  ``/var/tmp/PagingServer.debs``, and installs them.

  Also creates ``apt-get-installed.list`` file in the same directory, where
  every package name it has passed to apt-get (i.e. packages that it has
  installed via apt-get) is recorded, in case there might be a need to clean
  these up later.

  After successful installation, enable/run the service as described in "Usage" section.

* Manual installation.

  Follow roughly same steps as what `install.debian_jessie.sh`_ script does.



Other systems
`````````````

Just build/install all the requirements above from OS packages or however.



Audio configuration
-------------------

Overview of the software stack related to audio flow:

* PJSUA picks-up the calls, decoding audio streams from SIP connections.

* PJSUA outputs call audio to via PortAudio_.

* PortAudio can use multiple backends on linux systems, including:

  * ALSA_ libs (and straight down to linux kernel)
  * OSS (/dev/dsp*, only supported through emulation layer in modern kernels)
  * JACK sound server
  * PulseAudio_ sound server (through ALSA compatibility layer)

  In this particular implementation, PulseAudio backend is assumed.

* PulseAudio serves as a "hub", receiving streams from music players (mpd_
  instances), klaxon sounds, calls picked-up by PJSUA.

  Depending on PulseAudio and music players' configuration, these outputs can be
  then mixed together and mapped to audio cards (or specific channels of these)
  as necessary.

* PulseAudio outputs sound through ALSA libs and that goes to kernel driver and
  hardware, eventually.

  Here make sure that ALSA is also configured properly - sound hardware unmuted,
  volume level is set correctly and any other necessary mixer controls are set.

  This all is usually easy to do with "alsamixer" tool.

Whole stack can always be tested with command like this::

  % paging --test-audio-file my-sound.wav

That option makes script just play the specified file through pjsua (as it would
output the sound of the incoming call or a klaxon sound) and exit.

If that works correctly, all that sound output pipeline from pjsua to alsa
should be fine.


PagingServer audio configuration
````````````````````````````````

Configuration here can be roughly divided into these sections (at the moment):


* Sound output settings for PJSUA.

  Related configuration options:

  * pjsua-device
  * pjsua-conf-port

  As PortAudio (used by pjsua) can use one (and only one) of multiple backends
  at a time, and each of these backend can have multiple "ports" in turn,
  ``pjsua-device`` should be configured to use Pulse/ALSA backend "device".

  Usually when pulse is installed, "pulse" ALSA output gets configured, and that
  is what script uses by default, so no addition configuration should be
  necessary in that case.

  Otherwise, to see all devices that PJSUA and PortAudio detects, run::

    % paging --dump-pjsua-devices

    Detected sound devices:
      [0] HDA ATI SB: ID 440 Analog (hw:0,0)
      [1] HDA ATI SB: ID 440 Digital (hw:0,3)
      [2] HDA ATI HDMI: 0 (hw:1,3)
      [3] sysdefault
      [4] front
      [5] surround21
      [6] surround40
      ...
      [13] dmix
      [14] default
      [15] pulse
      [15] system
      [16] PulseAudio JACK Source

  (output is truncated, as it also includes misc info for each of these
  devices/ports that PortAudio/PJSUA provides)

  This should print a potentially-long list of "playback devices" (PJSUA
  terminology) that can be used for output there, as shown above.

  "aplay -L" command can also be used to match that with ALSA outputs.

  PortAudio-output should be specified either as numeric id (number in square
  brackets on the left) or regexp (python style) to match against name in the
  list via ``pjsua-device`` option.

  To avoid having any confusing non-ALSA (incl. pulse-alsa emulation) ports
  there, PortAudio can be compiled with only ALSA as a backend.

  ``pjsua-conf-port`` option can be used to match one of the "conference ports"
  from ``paging --dump-pjsua-conf-ports`` command output in the same fashion, if
  there will ever be more than one (due to more complex pjsua configuration, for
  example), otherwise it'll work fine with empty default.


* Configuration for any non-call inputs (music, klaxons, etc) for pulse.

  Related configuration options:

  * klaxon
  * pulse-mute

  "klaxon" can be a path to any file that has sound in it (that ffmpeg would
  understand), and will be played before each announcement call gets picked-up.

  "pulse-mute" should be a regexp to match any sufficiently unique property of
  music streams, that would play in-between announcements.

  For example, if mpd_ player is used for music output, ``pulse-mute =
  ^application\.name=mpd$`` setting should match and mute all running player
  instances as necessary.

  Script can be run with ``--debug --dump-pulse-props`` option to show
  properties of each PulseAudio stream, and info on when/whether they match
  ``pulse-mute`` option.

  See `paging.example.conf`_ for more detailed info on these options.


All settings mentioned here are located in the ``[audio]`` section of the
configuration file.

See `paging.example.conf`_ for more detailed descriptons.



Misc tips and tricks
--------------------

Collection of various things related to this project.


Pre-convert klaxon sound(s) to wav from any format
``````````````````````````````````````````````````

Can be done via ffmpeg_ with::

  ffmpeg -y -v 0 -i sample.mp3 -f wav sample.wav

Where it doesn't actually matter which format source "sample.mp3" is in - can be
mp3, ogg, aac, mpc, mp4 or whatever else ffmpeg supports.

Might help to avoid startup delays due to conversion of these on each run.

If pjsua will be complaining about sample-rate difference between wav file and
output, e.g. ``-ar 44100`` option can be used (after ``-f wav``) to have any
sampling rate for the output file.


Benchmark script (callram.py)
`````````````````````````````

Description below is from old README.md file pretty much verbatim.

We've tested this script with thousands of calls, it is fairly reliable and
light on resources. Total CPU use on a Pentium 4 @ 2.8ghz hovered around 0.5%
with 4MB ram usage. identical figures were observed on a Celeron D @ 2.53Ghz,
you could probably get away with whatever your operating system requires to run
in terms of hardware.

To benchmark, you'll need to set up callram.py.

* Setting up callram.py

  This setup assumes you have PJSUA installed, if not, go back to Installation
  earlier in this readme and install it.

* Put the files in the right places::

    sudo cp callram.py /opt/bin/callram.py
    sudo cp callram.example.conf /etc/callram.conf

* Add your SIP account::

    sudo nano /etc/callram.conf

  Change the top 3 values to your SIP server, username (usually ext. number) and
  password.

  Then fill in both SIP URI: fields (uri= and to=) with the SIP URI of the
  client you'd like to test.

  SIP URIs are usually formatted as ``sip:<extension#>@<exampledomain.com>`` in
  most cases.

  The Domain may sometimes be an IPv4 or IPv6 address depending on your setup.

* Run::

    /usr/bin/python /opt/bin/callram.py


Sending error reports to Sentry
```````````````````````````````

Sentry_ is a "modern error logging and aggregation platform".

Python raven_ module has to be installed in order for this to work.

Uncomment and/or set "sentry_dsn" option under the ``[server]`` section of the
configuration file.

It can also be set via ``--sentry-dsn`` command-line option, e.g. in systemd
unit distributed with the package, to apply on all setups where package is deployed.



Copyright and License
---------------------

| Code and documentation copyright 2015 Accelerate Networks.
| Code released under the GNU General Public License v2.0.
| See LICENSE file in the repository for more details.
| Docs released under Creative Commons.



.. _PJSUA: http://www.pjsip.org/
.. _PulseAudio: https://wiki.freedesktop.org/www/Software/PulseAudio/
.. _ALSA: http://www.alsa-project.org/main/index.php/Main_Page
.. _ini format: https://en.wikipedia.org/wiki/INI_file
.. _paging.example.conf: https://github.com/AccelerateNetworks/PagingServer/blob/master/paging.example.conf
.. _PortAudio: http://www.portaudio.com/
.. _ffmpeg: http://ffmpeg.org/
.. _systemctl(1) manpage: http://www.freedesktop.org/software/systemd/man/systemctl.html
.. _mpd: http://musicpd.org/
.. _Sentry: https://getsentry.com/
.. _pip: http://pip-installer.org/
.. _pip2014.com: http://pip2014.com/
.. _python packaging tutorial: https://packaging.python.org/en/latest/installing.html
.. _Python 2.7: http://python.org/
.. _pulsectl python module: https://github.com/mk-fg/python-pulse-control
.. _raven: https://pypi.python.org/pypi/raven/5.5.0
.. _python-systemd: https://github.com/systemd/python-systemd
.. _install.debian_jessie.sh: https://github.com/AccelerateNetworks/PagingServer/blob/master/setup-scripts/install.debian_jessie.sh
