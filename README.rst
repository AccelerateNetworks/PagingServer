PagingServer
============

SIP-based Announcement / PA / Paging / Public Address Server system.

Main component of this project is a script to run PJSUA_ SIP client connected to
a JACK_ sound server routing audio to whatever sound cards and speaker sets.

It picks up calls, plays klaxon on speakers, followed by the announcement made
in that call. Music plays in-between announcements.

Script controls PJSUA and JACK to make them work to that effect.


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

Provided `paging.example.conf`_ file has all the available
configuration options and their descriptions.

To see default configuration options, use ``paging --dump-conf-defaults``, and
run ``paging --dump-conf ...`` to see the actual options being picked-up and
used at any time.

There are two general (supported) ways to start and run the script:

* In the foreground (non-forking).
* As a systemd service.

Both are described in more detail below.


Start/run in the foreground
```````````````````````````

Aka simple non-forking start.

Just run the thing as::

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

* Enable service to start on OS boot: ``systemctl enable paging``

* See if service is running, show last log entries: ``systemctl status paging``
* Show all logging for service since last OS boot: ``journalctl -ab -u paging``

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
packages/repo) on specific systems, or a more detailed step-by-step instructions
for both python package and other requirements in "README.install.rst" file.


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

* JACK_ - both JACK1 (C) and JACK2 (C++) forks should work.

  Only tested with JACK1 fork, but as both have same ABI and only interacted
  with via libjack, there should be no difference wrt which one is actually
  running.

* `JACK-Client python module`_

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

TODO: packages/repo


Other systems
`````````````

TODO: build script

See also "README.install.rst" file for more information on the
manual installation process.



Audio configuration
```````````````````

Overview of the software stack related to audio flow:

* PJSUA picks-up the calls, decoding audio streams from SIP connections.

* PJSUA outputs call audio to via PortAudio_.

* PortAudio can use multiple backends on linux systems, including:

  * ALSA_ libs (and straight down to linux kernel)
  * OSS (/dev/dsp*, only supported through emulation layer in modern kernels)
  * JACK sound server
  * PulseAudio sound server
    (with a `somewhat unstable patch`_, see `comment on #3`_ for details)

  In this particular implementation, JACK backend is used, as it is necessary to
  later multiplex PJSUA output to multiple destinations and mix-in sounds from
  other sources there.

  So PortAudio sends sound stream to JACK.

* JACK serves as a "hub", receiving streams from music players (mpd_ instances),
  klaxon sounds, calls picked-up by PJSUA.

  JACK mixes these streams together, muting and connecting/disconnecting some as
  necessary, controlled by the server script ("paging").

  End result is N stream(s) corresponding to (N) configured hardware output(s).

* JACK outputs resulting sound stream(s) through ALSA libs (and linux from
  there) to the sound hardware.


Hence audio configuration can be roughly divided into these sections (at the moment):


* Sound output settings for PJSUA.

  Related configuration options:

  * pjsua-device
  * pjsua-conf-port

  As PortAudio (used by pjsua) can use one (and only one) of multiple backends
  at a time, and each of these backend can have multiple "ports" in turn,
  ``pjsua-device`` should be configured to use JACK backend "device".

  To see all devices that PJSUA and PortAudio detects, run::

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
      [15] system
      [16] PulseAudio JACK Source

  (output is truncated, as it also includes misc info for each of these
  devices/ports that PortAudio/PJSUA provides)

  This should print a potentially-long list of "playback devices" (PJSUA
  terminology) that can be used for output there, as shown above.

  JACK default output (as created by e.g. ``-d dummy`` option to jackd) in the
  example list above is called "system" - same as in JACK, and should be matched
  by default.

  If any other JACK-input/PortAudio-output should be used, it can be specified
  either as numeric id (number in square brackets on the left) or regexp (python
  style) to match against name in the list.

  To avoid having any confusing non-JACK ports there, PortAudio can be compiled
  with only JACK as a backend.

  ``pjsua-conf-port`` option can be used to match one of the "conference ports"
  from ``paging --dump-pjsua-conf-ports`` command output in the same fashion, if
  there will ever be more than one (due to more complex pjsua configuration, for
  example), otherwise it'll work fine with empty default.


* JACK daemon startup and control client connection configuration.

  Related configuration options:

  * jack-autostart
  * jack-server-name
  * jack-client-name

  All of these are common JACK client settings, described in jackd(1),
  jackstart(1) manpages, libjack or `jack-client module documentation`_.

  With exception for self-explanatory ``jack-autostart`` (enabled by default),
  these options should be irrelevant, unless this script is used with multiple
  JACK instances or clients.


* Configuration for any non-call inputs (music, klaxons, etc) for JACK.

  Related configuration options:

  * klaxon
  * jack-music-client-name
  * jack-music-links

  "klaxon" can be a path to any file that has sound in it (that ffmpeg would
  understand), and will be played before each announcement call on all
  "jack-output-ports" (see below), and before that call gets answered.

  "jack-music-client-name" should be a regexp to match outputs of music clients,
  that should play stuff in-between announcements, and "jack-music-links" allows
  to control which set(s) of speakers they'll be connected to.

  For example, if mpd.conf has something like this::

    audio_output {
      type "jack"
      name "jack"
      client_name "mpd.paging:test"
    }

  Then configuration like this (these are actually defaults)::

    jack-music-client-name = ^mpd\.paging:(.*)$
    jack-music-links = left---left right---right

  Will connect output from that player to all speakers matched by
  "jack-output-ports" (all available to JACK by default).

  Script can be run with ``--dump-jack-ports`` option to show all JACK ports
  that are currently available - all connected players, speakers, cards and such.

  See more detailed description of these options and how they're interpreted in
  `paging.example.conf`_.


* List of hardware outputs (ALSA PCMs) to use as JACK final outputs/sinks.

  Related configuration options:

  * jack-output-ports

  Same as with PJSUA outputs/ports above, ``jack-output-ports`` can be
  enumerated via ``paging --dump-jack-ports`` command, and filtered by direct id
  or name regexp, if necessary.

  Default is to route PJSUA call to all outputs available in JACK.


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


Running JACK on a system where PulseAudio is the main sound server
``````````````````````````````````````````````````````````````````

First of all, jackd has to be started manually there, and strictly before
pulseaudio server.

``/etc/pulse/default.pa`` should have something like this at the end
(after default sink - probably alsa - init!)::

  load-module module-jack-source source_name=jack_in
  load-module module-loopback source=jack_in

That will create an output from JACK to PulseAudio and from there to whatever
actually makes sound on the particular system, provided that the loopback stream
and source in question are not muted and have some non-zero volume set in pulse.

"module-jack-source" has options for picking which jackd to connect to, if isn't
not "default", "module-loopback" after it creates a stream from that jack source
to a default sink (which is probably an ALSA sink).

On the JACK side, "PulseAudio JACK Source" port (sink) gets created, and
anything connected there will make its way to pulseaudio.


Running mpd player connected to JACK
````````````````````````````````````

Music Player Daemon (mpd_) is a nice player, well-suited for purposes of
hands-off playing music all day long in-between any kind of announcements.

It also has `a vast number of clients`_, including evertyhing from IR remote
listeners (via lirc), bluetooth phones, car stereos, to more conventional
desktop apps and WebUIs.

Example configuration for mpd with JACK output and "client_name" recognized by
default PagingServer configuration and suitable for playing pretty much
anything::

  log_file "/dev/stdout"
  music_directory "/mnt/music"

  # password "super-secret-admin-password@read,add,control,admin"
  # password "password-for-teh-peeple@read,add,control"

  input {
    plugin "curl"
  }

  audio_output {
    type "jack"
    name "jack"
    client_name "mpd.paging:test"
    autostart "no"
  }

Note that "password" lines are commented-out, which will allow any client to
connect without any kind of authorization, so it might be a good idea to change
these if control port is to be exposed to any kind of non-localhost network.


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

If you followed manual installation instructions from README.install.rst, then
it should be installed into the same virtualenv as the PagingServer itself,
i.e. from a root shell run::

  % su - paging
  % . PagingServer/bin/activate
  % pip install raven
  % exit

Otherwise that module can be installed from an OS package, if available
(recommended), or via standard python packaging tools (see `python packaging
tutorial`_).

Then uncomment and/or set "sentry_dsn" option under the ``[server]`` section of
the configuration file.

It can also be set via ``--sentry-dsn`` command-line option, e.g. in systemd
unit distributed with the package, to apply on all setups where package is deployed.



Copyright and License
---------------------

| Code and documentation copyright 2015 Accelerate Networks.
| Code released under the GNU General Public License v2.0.
| See LICENSE file in the repository for more details.
| Docs released under Creative Commons.
| Please don't be a dick about it.



.. _PJSUA: http://www.pjsip.org/
.. _JACK: http://jackaudio.org/
.. _ALSA: http://www.alsa-project.org/main/index.php/Main_Page
.. _ini format: https://en.wikipedia.org/wiki/INI_file
.. _paging.example.conf: https://github.com/AccelerateNetworks/PagingServer/blob/master/paging.example.conf
.. _PortAudio: http://www.portaudio.com/
.. _somewhat unstable patch: https://build.opensuse.org/package/show/home:illuusio:portaudio/portaudio
.. _comment on #3: https://github.com/AccelerateNetworks/PagingServer/issues/3#issuecomment-128797116
.. _jack-client module documentation: https://jackclient-python.readthedocs.org/#jack.Client
.. _ffmpeg: http://ffmpeg.org/
.. _systemctl(1) manpage: http://www.freedesktop.org/software/systemd/man/systemctl.html
.. _mpd: http://musicpd.org/
.. _a vast number of clients: http://mpd.wikia.com/wiki/Clients
.. _Sentry: https://getsentry.com/
.. _pip: http://pip-installer.org/
.. _pip2014.com: http://pip2014.com/
.. _python packaging tutorial: https://packaging.python.org/en/latest/installing.html
.. _Python 2.7: http://python.org/
.. _JACK-Client python module: https://pypi.python.org/pypi/JACK-Client/
.. _raven: https://pypi.python.org/pypi/raven/5.5.0
.. _python-systemd: https://github.com/systemd/python-systemd
