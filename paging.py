#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function

import itertools as it, operator as op, functools as ft
from contextlib import contextmanager, closing
import ConfigParser as configparser
from os.path import join, exists, isfile, expanduser
import os, sys, types, time, signal, logging, inspect

import pjsua as pj


class Conf(object):

    sip_domain = ''
    sip_user = ''
    sip_pass = ''

    samples_klaxon = ''

    server_debug = False
    server_pjsua_log_level = 0
    server_sentry_dsn = ''

    _conf_paths = ( 'paging.conf',
        '/etc/paging.conf', 'callpipe.conf', '/etc/callpipe.conf' )
    _conf_sections = 'sip', 'samples', 'server'

    def __repr__(self): return repr(vars(self))
    def get(self, *k): return getattr(self, '_'.join(k))

    @staticmethod
    def parse_bool(val, _states={
            '1': True, 'yes': True, 'true': True, 'on': True,
            '0': False, 'no': False, 'false': False, 'off': False }):
        try: return _states[val.lower()]
        except KeyError: raise ValueError(val)



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
            stream_base = getattr(sys, '__{}__'.format(k))
            if stream_base is not stream: stream_base.flush()
            os.dup2(fd_bak, fd)
            setattr(sys, k, stream)

def force_bytes(bytes_or_unicode, encoding='utf-8', errors='backslashreplace'):
    if isinstance(bytes_or_unicode, bytes): return bytes_or_unicode
    return bytes_or_unicode.encode(encoding, errors)

def force_unicode(bytes_or_unicode, encoding='utf-8', errors='replace'):
    if isinstance(bytes_or_unicode, unicode): return bytes_or_unicode
    return bytes_or_unicode.decode(encoding, errors)

def force_str_type(bytes_or_unicode, val_or_type, **conv_kws):
    if val_or_type is bytes or isinstance(val_or_type, bytes): f = force_bytes
    elif val_or_type is unicode or isinstance(val_or_type, unicode): f = force_unicode
    else: raise TypeError(val_or_type)
    return f(bytes_or_unicode, **conv_kws)

def update_conf_from_file(conf, path_or_file, section='default', prefix=None):
    if isinstance(path_or_file, types.StringTypes): path_or_file = open(path_or_file)
    if isinstance(path_or_file, configparser.RawConfigParser): config = path_or_file
    else:
        with path_or_file as src:
            config = configparser.RawConfigParser(allow_no_value=True)
            config.readfp(src)
    for k in dir(conf):
        if prefix:
            if not k.startswith(prefix): continue
            conf_k, k = k, k[len(prefix):]
        elif k.startswith('_'): continue
        else: conf_k = k
        v = getattr(conf, conf_k)
        if isinstance(v, types.StringTypes):
            get_val = lambda *a: force_str_type(config.get(*a), v)
        elif isinstance(v, bool): get_val = config.getboolean
        elif isinstance(v, (int, long)): get_val = config.getint
        elif isinstance(v, float): get_val = lambda *a: float(config.get(*a))
        else: continue # values with other types cannot be specified in config
        for k_conf in k, k.replace('_', '-'):
            try: setattr(conf, conf_k, get_val(section, k_conf))
            except configparser.Error: pass

def dict_with(d, **kws):
    d.update(kws)
    return d

def dict_for_ctype(obj):
    return dict((k, getattr(obj, k)) for k in dir(obj) if not k.startswith('_'))


### PJSUA handlers

# XXX: both are BROKEN, need to figure out hw audio output first

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

class PagingServerError(Exception): pass

class PagingServer(object):

    lib = None

    @err_report_wrapper
    def __init__(self, conf, sd_cycle=None):
        self.conf, self.sd_cycle = conf, sd_cycle
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
        conf_log = pj.LogConfig(level=self.conf.server_pjsua_log_level, callback=conf_log)

        lib.init(conf_ua, conf_log) # XXX: media config

        transport = lib.create_transport(pj.TransportType.UDP)
        lib.start(with_thread=False)
        lib.c = pj._pjsua

        ports = lib.c.enum_conf_ports()
        if len(ports) != 1:
            raise PagingServerError(
                'Failed to pick sound card output conference'
                    ' port after pjsua init (ports found: {}).'.format(len(ports)) )
        self.out_port_id, = ports

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
            *map(ft.partial(self.conf.get, 'sip'), ['domain', 'user', 'pass']) )
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


    def list_conf_ports(self):
        return list(
            dict_with(dict_for_ctype(self.lib.c.conf_get_port_info(port_id)), id=n)
            for n, port_id in enumerate(self.lib.c.enum_conf_ports()) )

    def list_sound_devices(self):
        return list( dict_with(vars(dev), id=n)
            for n, dev in enumerate(self.lib.enum_snd_dev()) )


    @contextmanager
    def wav_play(self, path, loop=False, connect_to_out=True):
        # Currently there (still!) doesn't seem to be any callback for player EOF:
        # http://lists.pjsip.org/pipermail/pjsip_lists.pjsip.org/2010-June/011112.html
        player_id = self.lib.create_player(path, loop=loop)
        try:
            player_port = self.lib.player_get_slot(player_id)
            if connect_to_out: self.lib.conf_connect(player_port, self.out_port_id)
            yield player_port
        finally: self.lib.player_destroy(player_id)

    def wav_length(self, path, force_file=True):
        # Only useful to stop playback in a hacky ad-hoc way,
        #  because pjsua python lib doesn't export proper callback,
        #  and ctypes wrapper would be even uglier
        import wave
        if force_file and not isfile(path): # missing, fifo, etc
            raise PagingServerError(path)
        with closing(wave.open(path, 'r')) as src:
            return src.getnframes() / float(src.getframerate())

    def wav_play_sync(self, path, ts_diff_pad=1.0):
        ts_diff = self.wav_length(path)
        with self.wav_play(path) as player_port:
            self.log.debug('Started blocking playback of wav with length: %s', ts_diff)
            time.sleep(ts_diff + ts_diff_pad)


def pprint_infos(infos, title=None):
    if title: print('{}:'.format(title))
    for info in infos:
        print('[{0[id]}] {0[name]}'.format(info))
        for k, v in sorted(info.viewitems()):
            if k in ['id', 'name']: continue
            print('  {}: {}'.format(k, v))

def main(args=None, defaults=None):
    defaults = defaults or Conf()

    import argparse
    parser = argparse.ArgumentParser(
        description='Script to auto-answer SIP calls after playing some announcement?')

    parser.add_argument('conf', nargs='*',
        help='Extra config files to load on top of default ones.'
            ' Values in latter ones override those in the former, cli values override all.'
            ' Initial files (always loaded, if exist): {}'.format(' '.join(defaults._conf_paths)))

    parser.add_argument('--systemd', action='store_true',
        help='Use systemd service'
            ' notification/watchdog mechanisms in daemon modes, if available.')

    parser.add_argument('-d', '--debug',
        action='store_true', help='Verbose operation mode.')
    parser.add_argument('--pjsua-log-level',
        metavar='0-10', type=int,
        help='pjsua lib logging level. Only used when --debug is enabled.'
            ' Zero is only for fatal errors, higher levels are more noisy.'
            ' Default: {}'.format(defaults.server_pjsua_log_level))
    parser.add_argument('--sentry-dsn', metavar='dsn',
        help='Use Sentry to capture errors/logging using "raven" module.'
            ' Default: {}'.format(defaults.server_sentry_dsn))

    parser.add_argument('--dump-sound-devices', action='store_true',
        help='Dump the list of sound devices that pjsua/portaudio detects and exit.')
    parser.add_argument('--dump-conf-ports', action='store_true',
        help='Dump the list of conference ports that pjsua creates after init and exit.')
    parser.add_argument('--test-audio-file', metavar='path',
        help='Play specified wav file and exit.')

    opts = parser.parse_args(sys.argv[1:] if args is None else args)

    global log
    log = '%(name)s %(levelname)s :: %(message)s'
    if not opts.systemd: log = '%(asctime)s :: {}'.format(log)
    logging.basicConfig(
        format=log, datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.DEBUG if opts.debug else logging.WARNING )
    log = logging.getLogger('main')
    if opts.debug:
        for k in 'stdout', 'stderr':
            setattr(sys, k, os.fdopen(getattr(sys, k).fileno(), 'wb', 0))

    conf_file = configparser.SafeConfigParser(allow_no_value=True)
    conf_user_paths = map(expanduser, opts.conf or list())
    for p in conf_user_paths:
        if not os.access(p, os.O_RDONLY):
            parser.error('Specified config file does not exists: {}'.format(p))
    conf_file.read(list(defaults._conf_paths) + conf_user_paths)

    conf = Conf()
    for k in conf._conf_sections:
        update_conf_from_file(conf, conf_file, section=k, prefix='{}_'.format(k))
    for k in 'debug', 'pjsua_log_level', 'sentry_dsn':
        v = getattr(opts, k)
        if v is not None: setattr(conf, 'server_{}'.format(k), v)

    if conf.server_sentry_dsn:
        global raven_client
        import raven
        dsn = conf.server_sentry_dsn
        raven_client = raven.Client(conf.server_sentry_dsn)
        # XXX: can be hooked-up into logging and/or sys.excepthook

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

    server_ctx = PagingServer(conf, sd_cycle)

    if opts.dump_sound_devices:
        with server_ctx as server:
            devs = server.list_sound_devices()
            pprint_infos(devs, 'Detected sound devices')
        return

    if opts.dump_conf_ports:
        with server_ctx as server:
            ports = server.list_conf_ports()
            pprint_infos(ports, 'Detected conference ports')
        return

    if opts.test_audio_file:
        with server_ctx as server:
            server.wav_play_sync(opts.test_audio_file)
        return

    log.info('Starting PagingServer...')
    with server_ctx as server:
        for sig in signal.SIGINT, signal.SIGTERM:
            signal.signal(sig, lambda sig,frm: server.destroy())
        server.run()
    log.info('Finished')

if __name__ == '__main__': sys.exit(main())
