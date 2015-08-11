#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function

import itertools as it, operator as op, functools as ft
from contextlib import contextmanager
from ConfigParser import SafeConfigParser
from os.path import join, exists, expanduser
import os, sys, types, time, signal, logging, inspect

import pjsua as pj


class Defaults(object):

    conf_paths = 'paging.conf', '/etc/paging.conf', 'callpipe.conf', '/etc/callpipe.conf'
    sentry_dsn = ( 'https://0b915e29784f479f93db6ae2870515b6'
        ':b2fb7becafdc4c259b813a8f84f5b855@sentry.finn.io/2' )


### Utility boilerplates

log = raven_client = None

def err_report_wrapper(func=None, fatal=None):
    def _err_report_wrapper(func):
        @ft.wraps(func)
        def _wrapper(*args, **kws):
            try: return func(*args, **kws)
            except Exception as err:
                if raven_client: raven_client.captureException()
                if fatal is None and func.func_name == '__init__': raise # implicit
                elif fatal: raise
                if log: log.exception('ERROR (%s): %s', func.func_name, err)
        return _wrapper
    return _err_report_wrapper if func is None else _err_report_wrapper(func)

err_report = err_report_wrapper
err_report_only = err_report_wrapper(fatal=False)
err_report_fatal = err_report_wrapper(fatal=True)

def get_logger(logger=None, root=['__main__', 'paging']):
    'Returns logger for calling class or function name and module path.'
    if logger is None:
        frame = inspect.stack()[1][0]
        name = inspect.getargvalues(frame).locals.get('self')
        if isinstance(root, types.StringTypes): root = [root]
        if name:
            name = '{}.{}'.format(name.__module__, name.__class__.__name__).split('.')
            for k in root:
                if k in name: break
            else:
                raise ValueError( 'Unable to find logger name'
                    ' root(s) ({!r}) in module path: {!r}'.format(root, name) )
            name = name[name.index(k):]
            if k == '__main__': name[0] = root[-1]
        else: name = root[-1:]
        name_ext = frame.f_code.co_name
        if name_ext not in ['__init__', '__new__']:
            name.append(name_ext)
            if name_ext[0].isupper(): name.append('core')
        logger = '.'.join(name)
    if isinstance(logger, types.StringTypes):
        logger = logging.getLogger(logger)
    return logger

@contextmanager
def suppress_streams(*streams):
    with open(os.devnull, 'wb') as stream_null:
        fd_null, replaced = stream_null.fileno(), dict()
        for k in streams or ['stdout', 'stderr']:
            stream = getattr(sys, k)
            fd = stream.fileno()
            replaced[k] = fd, os.dup(fd), stream
            os.dup2(fd_null, fd)
            setattr(sys, k, stream_null)
        yield
        for k, (fd, fd_bak, stream) in replaced.viewitems():
            stream.flush()
            os.dup2(fd_bak, fd)
            setattr(sys, k, stream)

def dict_with(d, **kws):
    d.update(kws)
    return d


### PJSUA handlers

class AccountCallback(pj.AccountCallback):

    @err_report_wrapper
    def __init__(self, account=None):
        pj.AccountCallback.__init__(self, account)
        self.totalcalls = 0
        self.log = get_logger()

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

    @err_report_wrapper
    def __init__(self, call=None, number=0):
        pj.CallCallback.__init__(self, call)
        self.call, self.number = call, number
        self.log = get_logger()

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



### Server

class PJSUAOpts(object):

    log_level = 0

    def __init__(self, **opts):
        for k, v in opts.viewitems():
            if not hasattr(self, k): raise KeyError(k)
            setattr(self, k, v)

class PagingServer(object):

    lib = None

    @err_report_wrapper
    def __init__(self, config, pjsua_opts=None, sd_cycle=None):
        self.config, self.sd_cycle = config, sd_cycle
        self.pjsua_opts = pjsua_opts or PJSUAOpts()
        self.log = get_logger()

    @err_report_fatal
    def init(self):
        self.log.debug('pjsua init')

        # Before logging is configured, pjsua prints some init info to plain stderr fd
        # Unless there's a good reason to see this, like debugging early crashes,
        #  there should be no need to have this exception, hence the "suppress" hack
        with suppress_streams('stdout'): self.lib = lib = pj.Lib()

        conf_ua = pj.UAConfig()
        conf_ua.max_calls = 10
        conf_ua.user_agent = ( 'PagingServer/git'
            ' (+https://github.com/AccelerateNetworks/PagingServer)' )

        conf_log = lambda level,msg,n,\
            log=get_logger('pjsua'): log.debug(msg.strip().split(None,1)[-1])
        conf_log = pj.LogConfig(level=self.pjsua_opts.log_level, callback=conf_log)

        lib.init(conf_ua, conf_log) # XXX: media config

        transport = lib.create_transport(pj.TransportType.UDP)
        lib.start(with_thread=False)

    @err_report_fatal
    def destroy(self):
        if not self.lib: return
        self.log.debug('pjsua cleanup')
        self.lib.destroy()
        self.lib = None

    def __enter__(self):
        self.init()
        return self
    def __exit__(self, *err): self.destroy()
    def __del__(self): self.destroy()

    @err_report_fatal
    def run(self):
        assert self.lib, 'Must be initialized before run()'

        acc_config = pj.AccountConfig(
            *map(ft.partial(self.config.get, 'sip'), ['domain', 'user', 'pass']) )
        acc = self.lib.create_account(acc_config, cb=AccountCallback())

        log.debug('pjsua event loop started')
        while True:
            if not self.sd_cycle or not self.sd_cycle.ts_next: max_poll_delay = 600
            else:
                ts = time.time()
                max_poll_delay = self.sd_cycle.ts_next - ts
                if max_poll_delay <= 0:
                    self.sd_cycle(ts)
                    continue
            if not self.lib: break
            self.lib.handle_events(int(max_poll_delay * 1000)) # timeout in ms!
        log.debug('pjsua event loop has been stopped')

    def list_sound_devices(self):
        return list( dict_with(vars(dev), id=n)
            for n, dev in enumerate(self.lib.enum_snd_dev()) )



def main(args=None, defaults=None):
    defaults = defaults or Defaults()

    import argparse
    parser = argparse.ArgumentParser(
        description='Script to auto-answer SIP calls after playing some announcement?')

    parser.add_argument('conf', nargs='*',
        help='Extra config files to load on top of default ones.'
            ' Values in latter ones override those in the former.'
            ' Initial files (always loaded, if exist): {}'.format(' '.join(defaults.conf_paths)))

    parser.add_argument('--systemd', action='store_true',
        help='Use systemd service'
            ' notification/watchdog mechanisms in daemon modes, if available.')

    parser.add_argument('--sentry-dsn', nargs='?', metavar='dsn', const=True,
        help='Use Sentry to capture errors/logging using "raven" module.'
            ' If DSN is not specified, default one will be used: {}'.format(defaults.sentry_dsn))

    parser.add_argument('-d', '--debug', action='store_true', help='Verbose operation mode.')
    parser.add_argument('--pjsua-log-level',
        metavar='0-10', type=int, default=0,
        help='pjsua lib logging level. Only used when --debug is enabled.'
            ' Zero is only for fatal errors, higher levels are more noisy. Default: %(default)s')
    parser.add_argument('--dump-sound-devices', action='store_true',
        help='Dump the list of sound devices that pjsua/portaudio detects and exit.')

    opts = parser.parse_args(sys.argv[1:] if args is None else args)

    global log
    log = '%(name)s %(levelname)s :: %(message)s'
    if not opts.systemd: log = '%(asctime)s :: {}'.format(log)
    logging.basicConfig(
        format=log, datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.DEBUG if opts.debug else logging.WARNING )
    log = logging.getLogger('main')

    if opts.sentry_dsn:
        global raven_client
        import raven
        dsn = opts.sentry_dsn
        if dsn is True: dsn = defaults.sentry_dsn
        raven_client = raven.Client(opts.sentry_dsn)
        # XXX: can be hooked-up into logging and/or sys.excepthook

    config = SafeConfigParser()
    conf_user_paths = map(expanduser, opts.conf or list())
    for p in conf_user_paths:
        if not os.access(p, os.O_RDONLY):
            parser.error('Specified config file does not exists: {}'.format(p))
    config.read(list(defaults.conf_paths) + conf_user_paths)
    pjsua_opts = PJSUAOpts(log_level=opts.pjsua_log_level)

    if opts.systemd:
        from systemd import daemon
        def sd_cycle(ts=None):
            if not sd_cycle.ready:
                daemon.notify('READY=1')
                daemon.notify('STATUS=Running...')
                sd_cycle.ready = True
            if sd_cycle.delay:
                if ts is None: ts = time.time()
                delay = ts - sd_cycle.ts_next
                if delay > 0: time.sleep(delay)
                sd_cycle.ts_next += sd_cycle.delay
            else: sd_cycle.ts_next = None
            if sd_cycle.wdt: daemon.notify('WATCHDOG=1')
        sd_cycle.ts_next = time.time()
        wd_pid, wd_usec = (os.environ.get(k) for k in ['WATCHDOG_PID', 'WATCHDOG_USEC'])
        if wd_pid and wd_pid.isdigit() and int(wd_pid) == os.getpid():
            wd_interval = float(wd_usec) / 2e6 # half of interval in seconds
            assert wd_interval > 0, wd_interval
        else: wd_interval = None
        if wd_interval:
            log.debug('Initializing systemd watchdog pinger with interval: %ss', wd_interval)
            sd_cycle.wdt, sd_cycle.delay = True, wd_interval
        else: sd_cycle.wdt, sd_cycle.delay = False, None
        sd_cycle.ready = False
    else: sd_cycle = None

    if opts.dump_sound_devices:
        with PagingServer(config, pjsua_opts, sd_cycle) as server:
            devs = server.list_sound_devices()
            print('Detected sound devices:')
            for dev in devs:
                print('[{0[id]}] {0[name]}'.format(dev))
                for k, v in sorted(dev.viewitems()):
                    if k in ['id', 'name']: continue
                    print('  {}: {}'.format(k, v))
        return

    log.info('Starting PagingServer...')
    with PagingServer(config, pjsua_opts, sd_cycle) as server:
        for sig in signal.SIGINT, signal.SIGTERM:
            signal.signal(sig, lambda sig,frm: server.destroy())
        server.run()
    log.info('Finished')
    os._exit(0) # XXX: to prevent weird pjsua re-init (on gc?)

if __name__ == '__main__': sys.exit(main())
