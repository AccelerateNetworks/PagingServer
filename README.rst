PagingServer
============

**WARNING: project is in early stages of development and not suitable for
any kind of general usage yet**

SIP-based Announcement / PA / Paging / Public Address Server system.

Main component of this project is a script to run PJSUA_ SIP client connected to
a JACK_ sound server routing audio to whatever sound cards and speaker sets.

It picks up calls, plays klaxon on speakers, followed by the announcement made
in that call.

Script controls both PJSUA and JACK to make them work to that effect.

.. _PJSUA: http://www.pjsip.org/
.. _JACK: http://jackaudio.org/


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

Provided `paging.example.conf <paging.example.conf>`_ file has all the available
configuration options and their descriptions.

To see default configuration options, use ``paging --dump-conf-defaults``, and
run ``paging --dump-conf ...`` to see the actual options being picked-up and
used at any time.

There are two general (supported) ways to start and run the script:

* In the foreground (non-forking).
* As a systemd service.

Both are described in more detail below.

.. _ini format: https://en.wikipedia.org/wiki/INI_file


Start/run in the foreground
```````````````````````````

Aka simple non-forking start.

Just run the thing as::

  paging

Can be used directly from terminal, or with any init system or daemon manager,
including systemd, upstart, openrc, runit, daemontools, debian's
"start-stop-daemon", simple bash scripts, etc.

For systemd in particular, see the "Running as a systemd service" section below.

Running from terminal to understand what's going on, these options might be also
useful::

  paging --debug
  paging --debug --pjsua-log-level 10
  paging --dump-conf

See also "Installation" and "Audio configuration" sections below.


Running as a systemd service
````````````````````````````

TODO





Installation
------------

TODO


Audio configuration
```````````````````

TODO: portaudio/jack/alsa concepts
 knobs for these, --test option, ffmpeg line to get wav ;)


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

* (optional) `python-systemd`_ - only if ``--systemd`` option is used (e.g. with
  shipped .service file).

  Developed and shipped separately from main systemd package since v223
  (2015-07-29), likely come installed with systemd prior to that.

  Would probably make sense to install these from OS package, which should be
  available if systemd is used there as init by default.

* (optional) `raven python module`_ - for reporting any errors via sentry.

.. _Python 2.7: http://python.org/
.. _JACK-Client python module: https://pypi.python.org/pypi/JACK-Client/
.. _raven python module: https://pypi.python.org/pypi/raven/5.5.0
.. _python-systemd: https://github.com/systemd/python-systemd



Other stuff
-----------

TODO


Old md
------

To be spliced here later::

  ## Installation
  These instructions are for Debian-based Linux distributions. They should point you in the right direction to set this up on other distributions - just don't expect them to work verbatim.
  ### Install the Dependencies
  ```
  sudo apt-get install build-essential python2.7-dev python-pip libasound2-dev nano subversion git
  sudo pip install raven
  ```
  ### Download PJSIP
  ```
  svn co http://svn.pjsip.org/repos/pjproject/trunk pjsip
  ```
  ### Compile PJSIP
  ```
  cd pjsip
  export CFLAGS="$CFLAGS -fPIC" && ./configure && make dep && make
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
  sudo cp paging.py /opt/bin/paging.py
  sudo cp paging.example.conf /etc/paging.conf
  sudo cp paging.service /etc/systemd/system/paging.service
  ```
  ### Enable systemd service
  ```
  systemctl enable paging.service
  ```
  ### Add your SIP account
  ```
  sudo nano /etc/paging.conf
  ```
  Change the top 3 values to your SIP server, username (usually ext. number) and password. Get rid of the PA section from [PA] down unless you want a .wav to be played prior to each call.

  To configure the PA section set the path to the .wav file you want played in `file =` and set how many seconds it should play in `filetime =`.

  ## Running the Paging Server
  Run either of the commands below:
  ```
  Run in bash/terminal:
  /usr/bin/python /opt/bin/paging.py
  ```
  or
  ```
  Start as systemd service:
  sudo cp paging.service /etc/systemd/system
  sudo systemctl start paging
  ```

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
