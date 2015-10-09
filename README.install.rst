PagingServer Manual Installation
================================

This file describes manual steps to install PagingServer and its dependencies on
a modern linux distribution.

Idea behind this document is to allow experienced sysadmin to:

* Retrace any step of the process easily, being able to tweak it in any way or
  adjust it for different system.

* Include related software versions that are known to work, known quirks and
  pitfalls.

* Have tests for every step, to be able to identify exactly when things went
  wrong and how.

* Provide rationale for doing things in that particular way.

Instructions for Debian Jessie (current stable as of 2015-09-04) are probably
the most detailed, as that is the initial target platform.


.. contents::
  :backlinks: none



Installation steps
------------------

It's recommended to follow these in roughly same order, as next ones might rely
on stuff installed in the previous ones.

Each step can be skipped entirely if "Verify or check" commands for it work,
when packages in question were installed through some other means.
But be sure to run at least those commands to spot any potential issues.

Line prefixed by "%" are meant to be executed in the terminal with that prefix
removed.

See also main README.rst file for short list of requrements and other
somewhat-related information.


Install generic build tools and python dev packages
```````````````````````````````````````````````````

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


Install JACK sound server
`````````````````````````

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


Build/install PJSIP project and its python bindings
```````````````````````````````````````````````````

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

* Debian: ``apt-get install build-essential python-dev libjack-dev``
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
  % ./configure --prefix=/usr --enable-shared --disable-v4l2 --disable-video

  % sed -i 's/\(AC_PA_USE_.*\)=1/\1=0/' third_party/build/portaudio/os-auto.mak
  % echo 'AC_PA_USE_JACK=1' >>third_party/build/portaudio/os-auto.mak
  % echo 'export CFLAGS += -DPA_USE_JACK=1' >>third_party/build/portaudio/os-auto.mak
  % echo 'PORTAUDIO_OBJS += pa_jack.o pa_ringbuffer.o' >>third_party/build/portaudio/os-auto.mak
  % echo '#include "../../../portaudio/src/hostapi/jack/pa_jack.c"' > third_party/build/portaudio/src/pa_jack.c
  % echo '#include "../../../portaudio/include/pa_jack.h"' > third_party/build/portaudio/src/pa_jack.h
  % sed -i 's/-lportaudio/-ljack \0/' build.mak

  % make dep
  % make

Above alterations (sed and echo lines) are necessary to enable JACK support in
PortAudio_ version bundled with pjsip.

Instead of that patching (e.g. if it fails for some future pjsip versions), it
is possible to install portaudio with JACK support from OS repositories and
add ``--with-external-pa`` option to ``./configure ...`` line, but is not
recommended here.

Install pjsip/pjsua libs (should be done as root or via sudo):

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

Install python pjsua bindings (should be done as root or via sudo):

* On Debian/Ubuntu (or similar distros)::

    % pushd pjsip-apps/src/python
    % checkinstall -y --pkgname=python-pjsua --\
        python2 setup.py install --prefix=/usr --install-layout=deb --old-and-unmanageable
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


Build environment for PagingServer, install it there
````````````````````````````````````````````````````

It'd be unwise to run this app as a "root" user, so special uid should be
created for it (from a root user), along with home directory, where all app
files will reside::

  % useradd -d /srv/paging -s /bin/bash -G audio paging
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

**IMPORTANT:** DO NOT skip any errors from ``su - paging`` command above
before running the next steps.

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


(optional) Start JACK sound server
``````````````````````````````````

It is important to do this before running PagingServer, as the latter depends
on jackd in general, though can start it by itself with "jack-autostart = yes"
configuration option.

Unless that option will be used (not recommended, as there might be other apps
still needing JACK to be started explicitly - e.g. music players), JACK daemon
(jackd) should be always started before PagingServer, using the same uid
("paging") as the app.

Start jackd in one of the following ways (assuming initial root shell)::

  % setsid sudo -u paging -- jackd --nozombies --no-realtime -d dummy &
  % disown

  ### or

  % su - paging
  % setsid jackd --nozombies --no-realtime -d dummy &
  % disown

  ### or (if systemd is used in OS as init)

  % systemd-run --uid=paging -- jackd --nozombies --no-realtime -d dummy

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


Install PagingServer binary/configuration files system-wide and test it
```````````````````````````````````````````````````````````````````````

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


Configure system to run PagingServer and jackd on boot and start these
``````````````````````````````````````````````````````````````````````

Most linux distros these days run systemd as an init (pid-1), so instructions
below are more detailed for that scenario.

* With systemd as os init.

  Install python-systemd_ for python 2.7:

  * Arch Linux: ``pacman -S python2-systemd``

  * Debian or any other distro where there is no packaged version.

    For Debian - Install headers for systemd shared libraries::

      % apt-get install libsystemd-dev libsystemd-journal-dev

    Build and install python module in virtualenv (created in "Build environment
    for PagingServer" step above)::

      % su - paging
      % . PagingServer/bin/activate

      % wget https://github.com/systemd/python-systemd/archive/v230.tar.gz
      % tar xf v230.tar.gz
      % cd python-systemd-230

      % make
      % pip install .

      % cd ..
      % rm -rf v230.tar.gz python-systemd-230

      % exit

    This module is not strictly required for app to work, only adds better
    integration with the init system.

    If it won't be installed, be sure to drop ``--systemd`` option (and
    associated stuff) from the paging.service file.
    See "Running as a systemd service" in the "Usage" section of the README for
    more details on how to do that.

  If systemd python bindings are going to be used, make sure that they can be
  imported from python2 in virtualenv::

    % su - paging
    % . PagingServer/bin/activate

    % python2 -c 'import systemd.daemon; print systemd.daemon.__version__'
    215

    % exit

  Get systemd unit files from the github repository and install these to
  ``/etc/systemd/system`` directory::

    % cd /etc/systemd/system

    % wget https://raw.githubusercontent.com/AccelerateNetworks/PagingServer/master/paging.service
    % wget https://raw.githubusercontent.com/AccelerateNetworks/PagingServer/master/jack@.service
    % wget https://raw.githubusercontent.com/AccelerateNetworks/PagingServer/master/paging-jack-out@.service
    % wget https://raw.githubusercontent.com/AccelerateNetworks/PagingServer/master/paging-jack-out-all.service

    ### or same URLs with "curl -O" instead of "wget"

  Note that all paging*.service files assume that app will be run with the user
  and paths (config, script symlink) from the steps above, and should be changed
  if other uid/paths should be used.

  See "Running as a systemd service" (under "Usage") for more details on
  contents and editing of these files.

  Make sure that jackd and/or PagingServer are not currently running
  (especially if were started in previous steps above)::

    % pkill -x jackd
    % pkill -f paging

  Start both services::

    % systemctl start paging-jack-out-all paging

  Verify that both were started and are running correctly::

    % systemctl status paging-jack-out-all paging

    ● paging-jack-out-all.service
       Loaded: loaded (/etc/systemd/system/paging-jack-out-all.service; disabled)
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

    % systemctl enable paging-jack-out-all paging

    Created symlink from ... to /etc/systemd/system/paging-jack-out-all.service.
    Created symlink from ... to /etc/systemd/system/paging.service.

  Note that "systemctl enable" won't start the services right away, "start"
  can be used to do that separately.

  See "JACK output configuration" section in the main README file for more
  detailed description of what "paging-jack-out-all.service" does and what it
  can be replaced with for non-trivial audio setups.

  Verify or check whether paging.service and paging-jack-out-all.service are
  enabled to start on boot::

    % systemctl is-enabled paging-jack-out-all paging
    enabled
    enabled

  There should be one "enabled" message for each.

* With SysV init (``/etc/init.d/`` scripts) or any other init system.

  Commands from ``ExecStart=...`` lines in paging.service, jack@.service and
  paging-jack-out-all.service in the github repository should be scheduled to
  run on boot as specific user (e.g. "paging") and "backgrounded".

  From any sh/bash script (running as root) it's fairly easy to do this by
  adding the following lines::

    sudo -u paging -- setsid paging &
    disown
    sudo -u paging -- setsid jackd --nozombies --no-realtime -d dummy &
    disown
    sudo -u paging -- bash -c\
      'for c in $(aplay -L | grep ^default:CARD= | cut -d: -f2);\
        do alsa_out -d hw:$c &>/dev/null & disown; done'

  On many "classic" sysvinit/rc.d systems it can be done by adding these to
  /etc/rc.local, or creating a separate initscript for these in
  ``/etc/init.d`` or ``/etc/rc.d``.

  See "JACK output configuration" section in the main README file for more info
  on what the last (kinda-complicated) command does.

  Other init systems like openrc, runit, upstart can have their own ways to
  achieve same results, which should be fairly trivial to configure by
  following their docs.

With this step completed, PagingServer should be starting properly after
reboot, which is a good idea to test by rebooting the machine, to avoid future
surprises, if that is possible/acceptable for a particular server where it is
installed.



More information and feedback
-----------------------------

If anything in the steps above is unclear, misleading or does not work, and can
be fixed, please `leave a comment on- or file a new github issue`_, describing
what's wrong and how it can be done better or corrected.

More info on how to file these in a most efficient, useful and productive way
can be found e.g. in this "`Filing Effective Bug Reports`_" article.



.. _JACK: http://jackaudio.org/
.. _ALSA: http://www.alsa-project.org/main/index.php/Main_Page
.. _paging.example.conf: https://github.com/AccelerateNetworks/PagingServer/blob/master/paging.example.conf
.. _PortAudio: http://www.portaudio.com/
.. _pjproject packages for debian sid: https://packages.debian.org/source/sid/pjproject
.. _leave a comment on- or file a new github issue: https://github.com/AccelerateNetworks/PagingServer/issues
.. _Filing Effective Bug Reports: https://raymii.org/s/articles/Filing_Effective_Bug_Reports.html
.. _python packaging tutorial: https://packaging.python.org/en/latest/installing.html
.. _python-systemd: https://github.com/systemd/python-systemd
