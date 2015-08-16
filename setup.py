#!/usr/bin/env python2

from setuptools import setup, find_packages


readme_gist = '''
Script to run PJSUA SIP client connected to a JACK sound server routing audio to
whatever sound cards and speaker sets.

It picks up calls, plays klaxon on speakers, followed by the announcement made
in that call. Music plays in-between announcements.

Script controls PJSUA and JACK to make them work to that effect.
'''.strip()


setup(

    name = 'PagingServer',
    version = '15.8.54',
    author = 'Dan Ryan, Mike Kazantsev',
    author_email = 'dan@seattlemesh.net, mk.fraggod@gmail.com',
    license = 'GPL-2',
    keywords = [
        'sip', 'telephony', 'phone', 'paging', 'announcement',
        'autoanswer', 'callpipe', 'klaxon',
        'pj', 'pjproject', 'pjsip', 'pjsua', 'jack' ],
    url = 'https://github.com/AccelerateNetworks/PagingServer',

    description = 'SIP-based Announcement / PA / Paging / Public Address Server system',
    long_description = readme_gist,

    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: No Input/Output (Daemon)',
        'Environment :: Other Environment',
        'Intended Audience :: Customer Service',
        'Intended Audience :: Telecommunications Industry',
        'License :: OSI Approved',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 2 :: Only',
        'Topic :: Communications :: Telephony'
        'Topic :: Multimedia :: Sound/Audio' ],

    install_requires = ['JACK-Client'],
    extras_require = {'sentry': ['raven']},

    packages = find_packages(),
    include_package_data = True,

    entry_points = {
        'console_scripts': ['paging = paging:main'] })
