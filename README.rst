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

* Optional `python-systemd`_ module dependency is installed.

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
packaging tutorial`_ or documentation below for more detailed step-by-step
instructions for both python package and other requirements.


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

* (optional) `python-systemd`_ - only if ``--systemd`` option is used (e.g. with
  shipped .service file).

  Developed and shipped separately from main systemd package since v223
  (2015-07-29), likely comes installed with systemd prior to that.

  Would probably make sense to install that module from OS package, which should
  be available if systemd is used there as init by default.

* (optional) `raven python module`_ - for reporting any errors via sentry.


Step-by-step installation process
`````````````````````````````````

It's recommended to follow these in roughly same order, as next ones might rely
on stuff installed in the previous ones.

Each step can be skipped entirely if "Verify or check" commands for it work,
when packages in question were installed through some other means.
But be sure to run at least those commands to spot any potential issues.

Line prefixed by "%" are meant to be executed in the terminal with that prefix
removed.


* Install generic build tools and python dev packages.

  Debian / Ubuntu::

    % apt-get install python python-pip python-virtualenv

  Arch Linux::

    % pacman -S python2 python2-pip python2-virtualenv

  Verify or check if already installed::

    % pip --version
    pip 1.5.6 from /usr/lib/python2.7/dist-packages (python 2.7)

    % virtualenv --version
    1.11.6

  Note that on some systems, "pip" for python-2.7 might be installed as "pip2"
  or "pip-2.7", same might apply to "virtualenv", substitute these as necessary.


* Install JACK sound server.

  JACK is very mature and widely-used project, hence is packaged for all major
  linux distros, hence it's better to install it using distro's package manager.

  There are two different forks of JACK, both are in use and maintained -
  JACK1 (C) and JACK2 (C++).

  It is recommended to install JACK1 (or simply "jack", not e.g. "jack2")
  package, as this script is tested to work with that fork, but "jack2" should
  likely work just as well.

  * Debian/Ubuntu::

      apt-get install --no-install-recommends jackd1

    Note the ``--no-install-recommends`` flag, which should prevent Debian from
    installing "recommended" GUI packages and X11 server for these.
    None of them are needed or helpful, hence that option here.

    "Realtime process priority" option (which apt-get might ask) is irrelevant.

  * Arch Linux: ``pacman -S jack``

  * Other distros: install from distro repositories (recommended) or build it
    (JACK1) from sources available at http://jackaudio.org/downloads/

  Verify or check if already installed::

    % jackd --version
    jackd version 0.124.1 tmpdir /dev/shm protocol 25

  Here versions 0.X (such as in example above) will indicate that JACK1 is
  installed and versions 1.X for JACK2.


* Build/install PJSIP project and its python bindings.

  If PJSIP (can also be called: pj, pjsip, pjproject, pjsua) packaged for your
  distro (e.g. `pjproject packages for Debian Sid`_, or in AUR on Arch), it
  might be easier to install these and avoid building them from scratch
  entirely.

  See also all the great PJSIP build/installation instructions:

    | http://trac.pjsip.org/repos/wiki/Getting-Started
    | http://trac.pjsip.org/repos/wiki/Getting-Started/Download-Source
    | http://trac.pjsip.org/repos/wiki/Getting-Started/Build-Preparation
    | http://trac.pjsip.org/repos/wiki/Getting-Started/Autoconf

  Below in this step is just a shorter version of these.

  Some operations below, such as obvious package manager invocations, and where
  otherwise noted, should be run as "root", or can be prefixed with "sudo", if
  necessary.

  Install build-tools and python headers:

  * Debian: ``apt-get install build-essential python-dev``
  * Arch: ``pacman -S base-devel``

  On source-based distros like Gentoo, gcc, headers and such are always come
  pre-installed, so neither "build tools" nor "dev"-type extra packages are
  necessary.

  Verify or check if tools/headers are already installed::

    % cc --version
    cc (Debian 4.9.2-10) 4.9.2

    % make --version
    GNU Make 4.0

    % python2-config --includes
    -I/usr/include/python2.7 -I/usr/include/x86_64-linux-gnu/python2.7

  Get the latest release of PJSIP code from http://www.pjsip.org/download.htm
  with one of these commands (substituting newer release URL, if possible)::

    % wget http://www.pjsip.org/release/2.4.5/pjproject-2.4.5.tar.bz2 && tar xf pjproject-2.4.5.tar.bz2
    ### or
    % curl http://www.pjsip.org/release/2.4.5/pjproject-2.4.5.tar.bz2 | tar xj
    ### or (NOT RECOMMENDED, can be too buggy)
    % svn export http://svn.pjsip.org/repos/pjproject/trunk pjproject

  Build the code::

    % cd pjproject*

    % sed -i 's/\(AC_PA_USE_.*\)=1/\1=0/' third_party/build/portaudio/os-auto.mak
    % echo 'AC_PA_USE_JACK=1' >>third_party/build/portaudio/os-auto.mak
    % echo 'export CFLAGS += -DPA_USE_JACK=1' >>third_party/build/portaudio/os-auto.mak

    % ./configure --prefix=/usr --enable-shared --disable-v4l2 --disable-video
    % make dep
    % make

  Above alterations to ``third_party/build/portaudio/os-auto.mak`` file
  (sed and echo lines) are necessary to enable JACK support in the PortAudio
  version bundled with pjsip.

  Install pjsip/pjsua libs (should be done root or via sudo):

  * On Debian/Ubuntu (or similar distros)::

      % apt-get install checkinstall
      % sed -i 's/^\(\s\+\)cp -af /\1cp -r /' Makefile
      % checkinstall -y

      ...
      **********************************************************************
       Done. The new package has been installed and saved to
       /root/pjproject-2.4.5/pjproject_2.4.5-1_amd64.deb
       You can remove it from your system anytime using: dpkg -r pjproject
      **********************************************************************

      % dpkg -s pjproject

      ...
      Status: install ok installed
      ...

    This will create (via "checkinstall" tool) and cleanly install .deb package
    to the system, making it easy to remove/update it later.

    If "checkinstall" isn't your cup of tea, more generic way below should work
    as well.

  * On any random linux/unix distro::

      % make install

    Easy, but there's almost always a better way, that makes packaging system
    aware of (and hence capable of managing) the installed files.

  Install python pjsua bindings (should be done root or via sudo):

  * On Debian/Ubuntu (or similar distros)::

      % pushd pjsip-apps/src/python
      % checkinstall -y --pkgname=python-pjsua python2 setup.py install
      % popd

    Same as above, using "checkinstall" is highly recommended on these distros.

  * On any generic linux (or similar system)::

      % pushd pjsip-apps/src/python
      % python2 setup.py install
      % popd

    ``... install --user`` can be used to install package for current user only,
    or whole step can be performed with virtualenv active to install it there.

  Note that pjsua bindings are just a regular python package, and hence subject
  to any general python package installation/management guidelines,
  e.g. aforementioned `python packaging tutorial`_.

  Verify or check if pjsip/pjproject/pjsua are all installed and can be used
  from python::

    % python2 -c 'import pjsua; lib = pjsua.Lib(); lib.init(); lib.destroy()'

    04:43:41.097 os_core_unix.c !pjlib 2.4.5 for POSIX initialized
    04:43:41.097 sip_endpoint.c  .Creating endpoint instance...
    04:43:41.097          pjlib  .select() I/O Queue created (0x230f630)
    04:43:41.097 sip_endpoint.c  .Module "mod-msg-print" registered
    04:43:41.097 sip_transport.  .Transport manager created.
    04:43:41.098   pjsua_core.c  .PJSUA state changed: NULL --> CREATED

  Last command should not give anything like "ImportError" or segmentation
  faults, and should exit cleanly with output similar to one presented above.


* Prepare environment for PagingServer, install it and its python dependency
  modules.

  It'd be unwise to run this app as a "root" user, so special uid should be
  created for it (from a root user), along with home directory, where all app
  files will reside::

    % useradd -d /srv/paging -s /bin/bash paging
    % mkdir -p -m700 ~paging
    % chown -R paging: ~paging

  "User=paging" is also used in systemd unit (installed and explained below),
  so if other user name will be used here, it should be changed there as well.

  Same goes for directory used here.

  Then, for all the next commands in this step, shell should be switched to the
  created user, which can be done by running "su" with root privileges::

    % su - paging

    % id
    uid=1001(paging) gid=1001(paging) groups=1001(paging)

  This should likely also change the shell prompt, and "id" command should give
  non-root uid/gid (as shown above).

  **IMPORTANT:** DO NOT skip any errors from command above before running the
  next steps.

  Create python virtualenv for installing the app there::

    % virtualenv --clear --system-site-packages --python=python2.7 PagingServer
    % cd PagingServer
    % . bin/activate

    % python2 -c 'import sys; print sys.path[1]'
    /srv/paging/PagingServer/lib/python2.7

  Last command can be used to verify that ``sys.path[1]`` indeed points to a
  subdir in ~paging, and not something in /usr, which means that virtualenv was
  correctly activated for this shell session.

  Install the app and all its python module dependencies::

    % pip install PagingServer

    Downloading/unpacking PagingServer
    ...
    Downloading/unpacking JACK-Client (from PagingServer)
    ...
    Successfully installed PagingServer
    Cleaning up...

  Make sure app is installed and works with installed pjsua version::

    % paging --version
    paging version-unknown (see python package version)

    % paging --dump-pjsua-conf-ports
    Detected conference ports:
    ...

    % paging --dump-pjsua-devices
    Detected sound devices:
    ...

    % paging --dump-conf
    ;; Current configuration options
    ...

  As usual, there should be no error messages for these commands.

  To return back to root shell after running ``su - paging`` command above
  (should be still active), ``exit`` command can be used or a "Ctrl + d" key combo.

  To later get back to same "paging" user shell and installed python virtualenv,
  use the following commands (same as used above during virtualenv setup)::

    % su - paging
    % . PagingServer/bin/activate

  Any (at least non system-wide) python stuff for the app should be tweaked or
  installed only after running these (and until exiting the shell).


* (optional) Start JACK sound server.

  It is important to do this before running PagingServer, as the latter depends
  on jackd in general, though can start it by itself with "jack-autostart = yes"
  configuration option.

  Unless that option will be used (not recommended, as there might be other apps
  still needing JACK to be started explicitly - e.g. music players), JACK daemon
  (jackd) should be always started before PagingServer, using the same uid
  ("paging") as the app.

  Start jackd in one of the following ways (assuming initial root shell)::

    % sudo -u paging -- setsid jackd --nozombies -d dummy &
    % disown

    ### or

    % su - paging
    % setsid jackd --nozombies -d dummy &
    % disown

    ### or (if systemd is used in OS as init)

    % systemd-run --uid=paging -- jackd --nozombies -d dummy

  Here ``-d dummy`` output is used to avoid relying on any particular sound
  hardware available.

  Any ALSA_ (linux audio hardware stack) devices can be connected to this jackd
  server later via "alsa_in" / "alsa_out" commands, installed along with JACK1
  server.

  See JACK_ documentation (for particular fork that is used, as this process is
  different between JACK1 / JACK2) for more details on how to connect this sound
  server to the actual audio hardware.

  Started without any extra options (on top of what's shown above), this jackd
  will have "default" server name, and should be used by default by all
  jack-enabled apps (e.g. music players and such), including PagingServer itself.


* Configure PagingServer and install binary/configuration files for running it
  as a system service.

  Install symlink to a "paging" script into system-wide $PATH (as root)::

    % ln -s ~paging/PagingServer/bin/paging /usr/local/bin/

    % paging --version
    paging version-unknown (see python package version)

  Despite binary being available to all users after that, DO NOT run the actual
  service as a "root" user, at least outside of very exceptional cases
  (e.g. maybe checking if it works as root due to dev/file access permissions).

  Get annotated `paging.example.conf`_ from the github repository or pypi
  package (included there, but not actually installed)::

    % wget https://raw.githubusercontent.com/AccelerateNetworks/PagingServer/master/paging.example.conf
    ### or
    % curl -O https://raw.githubusercontent.com/AccelerateNetworks/PagingServer/master/paging.example.conf

  Edit file as necessary (see comments there and usage/configuration-related
  info in this README), and put it to ``/etc/paging.conf`` (requires root privileges)::

    % nano paging.example.conf
    % install -o root -g paging -m640 -T paging.example.conf /etc/paging.conf

  ``/etc/paging.conf`` is one of the default locations where app looks for
  configuration file (see ``paging --help`` output for a full list of such
  locations).

  Test-run the service as a proper "paging" user (created in previous step) in
  one of the following ways (assuming starting shell is root)::

    % sudo -u paging -- paging --debug

    ### or

    % su - paging
    % paging --debug

    ### or (if systemd is used in OS as init)

    % systemd-run --uid=paging -- paging --debug
    % journalctl -n30 -af  # to see output of the ad-hoc service there

  If correctly configured and working, there should be plenty of "DEBUG" output
  (due to ``--debug`` option in commands above), but no errors, especially fatal
  ones that cause the app to crash.


* Configure system to run PagingServer and jackd on boot and start these as
  system services.

  Most linux distros these days run systemd as an init (pid-1), so instructions
  below are more detailed for that scenario.

  * With systemd as os init.

    Install python-systemd for python 2.7:

    * Arch Linux: ``pacman -S python2-systemd``

    * Debian **Jessie**:

      At least as of now (2015-08-16), there's no prebuilt bindings package for
      python 2.7, which was dropped due to maintainer decision, given that
      nothing (yet) in debian depended on it.

      Rebuild "systemd" packages manually with python2 instead of python3::

        % apt-get install packaging-dev python-lxml
        % apt-get build-dep systemd

        % apt-get source systemd
        % cd systemd-215

        % mv debian/python{3,}-systemd.install
        % sed -i \
          -e 's/python3/python2/' \
          -e 's/--without-python/--with-python/' \
          debian/rules
        % sed -i \
          -e 's/python3-all-dev/python-dev/' \
          -e 's/python3-lxml/python-lxml/' \
          -e 's/python3-systemd/python-systemd/' \
          -e 's/python3:Depends/python:Depends/' \
          -e 's/Python 3/Python 2/' \
          debian/control
        ### last two "sed" commands above are both one-liners,
        ###  wrapped for readability

        % fakeroot debian/rules binary
        ### this might take a while...

        % apt-get markauto python-lxml \
          $( apt-cache showsrc systemd | sed -e \
            '/Build-Depends/!d;s/Build-Depends: \|,\|([^)]*),*\|\[[^]]*\]//g' )
        ### also all on one line

        % apt-get remove packaging-dev
        % apt-get autoremove

        % dpkg -i ../python-systemd_215-17+deb8u1_amd64.deb

      If that doesn't work for whatever reason, and the installed OS arch is
      x86_64 (amd64), then there's also an option to try the package I've built
      directly::

        % wget http://fraggod.net/static/mirror/packages/python-systemd_215-17%2bdeb8u1_amd64.deb

        % sha256sum python-systemd_215-17+deb8u1_amd64.deb
        02fbec7a120ab2597a784df44cfa85d31aacbdf725782bb3413436702babe955 ...
        ### ^^^ make sure sha256sum of the downloaded package matches that ^^^

        % dpkg -i python-systemd_215-17+deb8u1_amd64.deb

      Should likely work on any Debian Jessie, even with any of the later
      systemd patchsets (i.e. beyond 17).

      Otherwise it should be fine to just drop the ``--systemd`` option (and
      associated stuff) from the paging.service file.

      See "Running as a systemd service" in the "Usage" section for more details
      on how to do that.

    * For Debian Sid or any other distro, either:

      * Install from distro package repositories, if available (recommended).

      * Install into virtualenv (setup in one of the previous steps) from
        python-systemd_ repository directly::

          % su - paging
          % . PagingServer/bin/activate
          % pip install git+https://github.com/systemd/python-systemd
          % exit

        Separate python-systemd bindings are only available starting from
        systemd-223 (when they were split), so it might not work for earlier
        systemd versions.

    If systemd python bindings are going to be used, make sure that they can be
    imported from python2::

      % python2 -c 'import systemd.daemon; print systemd.daemon.__version__'
      215

    Get systemd unit files for paging.service and jack@.service from the github
    repository and install these to ``/etc/systemd/system`` directory::

      % cd /etc/systemd/system

      % wget https://raw.githubusercontent.com/AccelerateNetworks/PagingServer/master/paging.service
      % wget https://raw.githubusercontent.com/AccelerateNetworks/PagingServer/master/jack@.service

      ### or

      % curl -O https://raw.githubusercontent.com/AccelerateNetworks/PagingServer/master/paging.service
      % curl -O https://raw.githubusercontent.com/AccelerateNetworks/PagingServer/master/jack@.service

    Note that both .service files assume that app will be run with the user and
    paths (config, script symlink) from the steps above, and should be changed
    if other uid/paths should be used.

    See "Running as a systemd service" (under "Usage") for more details on
    contents and editing of these files.

    Make sure that jackd and/or PagingServer are not currently running
    (especially if were started in previous steps above)::

      % pkill -x jackd
      % pkill -f paging

    Start both services::

      % systemctl start jack@paging paging

    Verify that both were started and are running correctly::

      % systemctl status jack@paging paging

      ● jack@paging.service
         Loaded: loaded (/etc/systemd/system/jack@.service; disabled)
         Active: active (running) since Sun 2015-08-16 08:20:28 EDT; 3min 32s ago
      ...

      ● paging.service
         Loaded: loaded (/etc/systemd/system/paging.service; disabled)
         Active: active (running) since Sun 2015-08-16 08:20:30 EDT; 3min 30s ago
      ...

    If there were any errors logged, last 10 lines of these should be presented
    in the "status" command output above,

    ``journalctl -ab`` command can be used to see all combined logging produced
    by system services since boot, and ``journalctl -ab -u paging`` can further
    limit that to a single unit (to e.g. see error tracebacks there).

    ``journalctl -af`` can be used to continously follow what is being logged
    (like ``tail -f`` for all system logs), optionally with the same "-u" option.

    At any point these services can be stopped/started/restarted using
    "systemctl" command, as described in more detail in "Usage" section.

    Enable JACK and PagingServer to start on OS boot::

      % systemctl enable jack@paging paging

      Created symlink from ... to /etc/systemd/system/jack@.service.
      Created symlink from ... to /etc/systemd/system/paging.service.

    Note that "systemctl enable" won't start the services right away, "start"
    can be used to do that separately.

    Verify or check whether paging.service and jack@paging.service are enabled
    to start on boot::

      % systemctl is-enabled jack@paging paging
      enabled
      enabled

    There should be one "enabled" message for each.

  * With SysV init (``/etc/init.d/`` scripts) or any other init system.

    Both commands from ``ExecStart=...`` lines in paging.service and
    jack@.service in the github repository should be scheduled to run on boot as
    specific user (e.g. "paging") and "backgrounded".

    From any sh/bash script (running as root) it's fairly easy to do this by
    adding the following lines::

      sudo -u paging -- setsid paging &
      disown
      sudo -u paging -- setsid jackd --nozombies --no-realtime -d dummy &
      disown

    On many "classic" sysvinit/rc.d systems it can be done by adding these to
    /etc/rc.local, or creating a separate initscript for these in
    ``/etc/init.d`` or ``/etc/rc.d``.

    Other init systems like openrc, runit, upstart can have their own ways to
    achieve same results, which should be fairly trivial to configure by
    following their docs.

  With this step completed, PagingServer should be starting properly after
  reboot, which is a good idea to test by rebooting the machine, to avoid future
  surprises, if that is possible/acceptable for a particular server where it is
  installed.


If anything in the steps above is unclear, misleading or does not work, and can
be fixed, please `leave a comment on- or file a new github issue`_, describing
what's wrong and how it can be done better or corrected.

More info on how to file these in a most efficient, useful and productive way
can be found e.g. in this "`Filing Effective Bug Reports`_" article.



Audio configuration
```````````````````

Overview of the software stack related to audio flow:

* PJSUA picks-up the calls, decoding audio streams from SIP connections.

* PJSUA outputs call audio to via PortAudio_.

* PortAudio can use multiple backends on linux systems, including:

  * ALSA libs (and straight down to linux kernel)
  * OSS (/dev/dsp*, only supported through emulation layer in modern kernels)
  * JACK sound server
  * PulseAudio sound server
    (with a `somewhat unstable patch`_, see `comment on #3`_ for details)

  In this particular implementation, JACK backend is used, as it is necessary to
  later multiplex PJSUA output to multiple destinations and mix-in sounds from
  other sources there.

  So PortAudio sends sound stream to JACK.

* JACK serves as a "hub", receiving streams from music players (mpd instances),
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

Might help to avoid startup delays to conversion of these on each run.

If pjsua will be complaining about sample-rate difference between wav file and
output, ``-ar 44100`` option can be used (after ``-f wav``) to have any sampling
rate for the output file.


Running JACK on a system where PulseAudio is the main sound server
``````````````````````````````````````````````````````````````````

First of all, jackd has to be started manually there, and strictly before
pulseaudio server.

Then, /etc/pulse/default.pa should have something like this at the end
(after default sink init!)::

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



Old README.md things
--------------------

To be spliced here later, if still applicable::

  ## Benchmarking

  We've tested this script with thousands of calls, it is fairly reliable and light on resources. Total CPU use on a Pentium 4 @ 2.8ghz hovered around 0.5% with 4MB ram usage. identical figures were observed on a Celeron D @ 2.53Ghz, you could probably get away with whatever your operating system requires to run in terms of hardware.

  To benchmark, you'll need to set up callram.py.

  ### Setting up callram.py
  This setup assumes you have PJSUA installed, if not, go back to Installation earlier in this readme and install it.

  ### Put the files in the right places
  ```
  sudo cp callram.py /opt/bin/callram.py
  sudo cp callram.example.conf /etc/callram.conf
  ```
  ### Add your SIP account
  ```
  sudo nano /etc/callram.conf
  ```
  Change the top 3 values to your SIP server, username (usually ext. number) and password.

  Then fill in both SIP URI: fields (uri= and to=) with the SIP URI of the client you'd like to test. SIP URIs are usually formatted as `sip:<extension#>@<exampledomain.com>` in most cases. The Domain may sometimes be an IPv4 or IPv6 address depending on your setup.


  ## Running the Paging Server
  Run either of the commands below:
  ```
  Run in bash/terminal:
  /usr/bin/python /opt/bin/callram.py
  ```


.. _PJSUA: http://www.pjsip.org/
.. _JACK: http://jackaudio.org/
.. _ALSA: http://www.alsa-project.org/main/index.php/Main_Page
.. _ini format: https://en.wikipedia.org/wiki/INI_file
.. _paging.example.conf: paging.example.conf
.. _PortAudio: http://www.portaudio.com/
.. _somewhat unstable patch: https://build.opensuse.org/package/show/home:illuusio:portaudio/portaudio
.. _comment on #3: https://github.com/AccelerateNetworks/PagingServer/issues/3#issuecomment-128797116
.. _jack-client module documentation: https://jackclient-python.readthedocs.org/#jack.Client
.. _ffmpeg: http://ffmpeg.org/
.. _systemctl(1) manpage: http://www.freedesktop.org/software/systemd/man/systemctl.html

.. _pip: http://pip-installer.org/
.. _pip2014.com: http://pip2014.com/
.. _python packaging tutorial: https://packaging.python.org/en/latest/installing.html

.. _Python 2.7: http://python.org/
.. _JACK-Client python module: https://pypi.python.org/pypi/JACK-Client/
.. _raven python module: https://pypi.python.org/pypi/raven/5.5.0
.. _python-systemd: https://github.com/systemd/python-systemd

.. _pjproject packages for debian sid: https://packages.debian.org/source/sid/pjproject
.. _leave a comment on- or file a new github issue: https://github.com/AccelerateNetworks/PagingServer/issues
.. _Filing Effective Bug Reports: https://raymii.org/s/articles/Filing_Effective_Bug_Reports.html
