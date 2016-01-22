#!/usr/bin/env python2

from setuptools import setup, find_packages
import os

# Error-handling here is to allow package to be built w/o README included
pkg_root = os.path.dirname(__file__)
try: readme = open(os.path.join(pkg_root, 'README.rst')).read()
except IOError: readme = ''

setup(

    name = 'PagingServer',
    version = '16.1.11',
    author = 'Dan Ryan, Mike Kazantsev',
    author_email = 'dan@seattlemesh.net, mk.fraggod@gmail.com',
    license = 'GPL-2',
    keywords = [
        'sip', 'telephony', 'phone', 'paging', 'announcement',
        'autoanswer', 'callpipe', 'klaxon',
        'pj', 'pjproject', 'pjsip', 'pjsua', 'jack' ],
    url = 'https://github.com/AccelerateNetworks/PagingServer',

    description = 'SIP-based Announcement / PA / Paging / Public Address Server system',
    long_description = readme,

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
        'Topic :: Communications :: Telephony',
        'Topic :: Multimedia :: Sound/Audio',
        'Topic :: Multimedia :: Sound/Audio :: Mixers',
        'Topic :: Multimedia :: Sound/Audio :: Speech' ],

    install_requires = ['JACK-Client'],
    extras_require = {'sentry': ['raven']},

    py_modules=['paging'],

    entry_points = {
        'console_scripts': ['paging = paging:main'] })
