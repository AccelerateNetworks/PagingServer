.. contents:: :depth: 5

-----------------------



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



Usage
-----

After _`Installation`, the script should be configured, providing it with at least
the SIP account data for the general usage.

Default configuration file locations it will try to read from:

* paging.conf
* /etc/paging.conf
* callpipe.conf
* /etc/callpipe.conf
* Config paths specified on the command line.

See output of ``paging --help`` for info on how to specify additional
configuration, more up-to-date list of default paths, as well as general
information for all the other options available.

Provided `paging.example.conf <paging.example.conf>`_ file has all the available
configuration options and their descriptions.

To see default configuration options, use ``paging --dump-conf-defaults``, and
run ``paging --dump-conf ...`` to see the actual options being picked-up and
used at any time.


There are two general ways to start and run the script:


Simple non-forking startup
``````````````````````````

Just run the thing as::

  paging

Can be used directly from terminal, or with any init system or daemon manager,
including systemd, upstart, openrc, runit, daemontools, debian's
"start-stop-daemon", simple bash scripts, etc.

For systemd in particular, see the _`Running as systemd service` section below.

Running from terminal to understand what's going on, these options might be also
useful::

  paging --debug
  paging --debug --pjsua-log-level 10
  paging --dump-conf


Running as a systemd service
````````````````````````````

TODO



Installation
------------

TODO

Requirements
````````````

TODO


Other stuff
-----------

TODO
