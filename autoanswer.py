#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys
import pjsua as pj
import ConfigParser
import time
import functools


class Defaults(object):

    conf_paths = 'paging.conf', '/etc/paging.conf', 'callpipe.conf', '/etc/callpipe.conf'
    raven_dsn = ( 'https://0b915e29784f479f93db6ae2870515b6'
        ':b2fb7becafdc4c259b813a8f84f5b855@sentry.finn.io/2' )


log = raven_client = None

def err_report_wrapper(func):
    @functools.wraps(func)
    def _wrapper(*args, **kws):
        try: return func(*args, **kws)
        except Exception as e:
            if raven_client: raven_client.captureException()
            if func.func_name == '__init__': raise
            if log: log.exception('ERROR (%s): %s', func.func_name, e)
    return _wrapper


class AccountCallback(pj.AccountCallback):

    @err_report_wrapper
    def __init__(self, account=None):
        pj.AccountCallback.__init__(self, account)
        self.totalcalls = 0

    @err_report_wrapper
    def on_incoming_call(self, call):
        self.totalcalls += 1
        print('At call #%0.d' % self.totalcalls)
        call.set_callback(CallCallback())
        if config.has_section('pa'):
            wav_player_id = pj.Lib.instance().create_player(config.get('pa', 'file'), loop=False)
            wav_slot = pj.Lib.instance().player_get_slot(wav_player_id)
            pj.Lib.instance().conf_connect(wav_slot, 0)
            time.sleep(config.getint('pa', 'filetime'))
            pj.Lib.instance().player_destroy(wav_player_id)
        call.answer(200)


class CallCallback(pj.CallCallback):

    call = None

    @err_report_wrapper
    def __init__(self, call=None, number=0):
        self.call = call
        self.number = number
        pj.CallCallback.__init__(self, call)

    @err_report_wrapper
    def on_state(self):
        log.debug(
            'Call with %s is %s (last code=%s: %s)',
            self.call.info().remote_uri,
            self.call.info().state_text,
            self.call.info().last_code,
            self.call.info().last_reason )
        if self.call.info().state_text == 'DISCONNCTD' and self.number > 30:
            sys.exit(0) # XXX

    @err_report_wrapper
    def on_media_state(self):
        '''Notification when call's media state has changed.'''
        if self.call.info().media_state == pj.MediaState.ACTIVE:
            # Connect the call to sound device
            call_slot = self.call.info().conf_slot
            pj.Lib.instance().conf_connect(call_slot, 0)
            pj.Lib.instance().conf_connect(0, call_slot)
            log.debug('Media is now active')
        else:
            log.debug('Media is inactive')


@err_report_wrapper
def handle_calls_loop(lib, config):
    acc = lib.create_account(pj.AccountConfig(
        config.get('sip', 'domain'),
        config.get('sip', 'user'),
        config.get('sip', 'pass')
    ), cb=AccountCallback())
    while True:
        try: time.sleep(3600)
        except KeyboardInterrupt: break


def main(args=None, defaults=None):
    defaults = defaults or Defaults()

    import argparse
    parser = argparse.ArgumentParser(
        description='Script to auto-answer SIP calls after playing some announcement?')

    parser.add_argument('conf', nargs='*',
        help='Extra config files to load on top of default ones.'
            ' Values in latter ones override those in the former.'
            ' Initial files (always loaded, if exist): {}'.format(' '.join(Defaults.conf_paths)))

    parser.add_argument('--sentry-dsn', metavar='dsn',
        default=Defaults.raven_dsn,
        help='Use specified sentry DSN to capture errors/logging using'
            ' "raven" module. Enabled by default, empty - do not use. Default: %(default)s')
    parser.add_argument('-d', '--debug', action='store_true', help='Verbose operation mode.')
    opts = parser.parse_args(sys.argv[1:] if args is None else args)

    global log
    import logging
    logging.basicConfig(
        datefmt='%Y-%m-%d %H:%M:%S',
        format='%(asctime)s :: %(levelname)s :: %(message)s',
        level=logging.DEBUG if opts.debug else logging.WARNING )
    log = logging.getLogger()

    if opts.sentry_dsn.strip():
        global raven_client
        import raven
        raven_client = raven.Client(opts.sentry_dsn)
        # XXX: can be hooked-up into logging and/or sys.excepthook

    config = ConfigParser.SafeConfigParser()
    config.read(
        map(os.path.expanduser, list(Defaults.conf_paths) + list(opts.conf or list()))
        + list(sys.argv[1:] if args is None else args) )

    try:
        log.debug('Initializing pjsua')
        lib = pj.Lib()
        ua = pj.UAConfig()
        ua.max_calls = 10
        ua.user_agent = 'PagingServer/git (+https://github.com/AccelerateNetworks/PagingServer)'
        lib.init(ua)
        transport = lib.create_transport(pj.TransportType.UDP)
        lib.start()

        log.debug('Entering handle_calls_loop')
        handle_calls_loop(lib, config)
    finally: lib.destroy()

    log.debug('Finished')

if __name__ == '__main__': sys.exit(main())
