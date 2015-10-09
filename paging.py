#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function

import itertools as it, operator as op, functools as ft
from os.path import join, exists, isfile, expanduser, dirname
from contextlib import contextmanager, closing
from collections import deque
import ConfigParser as configparser
import os, sys, io, re, types, ctypes
import time, signal, logging, inspect


class Conf(object):

    sip_domain = ''
    sip_user = ''
    sip_pass = ''

    audio_klaxon = ''
    audio_klaxon_tmpdir = ''
    audio_klaxon_max_length = 10.0
    audio_pjsua_device = '^system$' # name of a default jack port
    audio_pjsua_conf_port = '' # there should be only one

    audio_jack_autostart = True
    audio_jack_server_name = ''
    audio_jack_client_name = ''
    audio_jack_client_arg = '--jack-client-pid'

    audio_jack_output_ports = ''
    audio_jack_music_client_name = '^mpd\.paging:(.*)$'
    audio_jack_music_links = 'left---left right---right'

    server_debug = False
    server_pjsua_log_level = 0
    server_sentry_dsn = ''

    _conf_paths = ( 'paging.conf',
        '/etc/paging.conf', 'callpipe.conf', '/etc/callpipe.conf' )
    _conf_sections = 'sip', 'audio', 'server'

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


def mono_time():
    if not hasattr(mono_time, 'ts'):
        class timespec(ctypes.Structure):
            _fields_ = [('tv_sec', ctypes.c_long), ('tv_nsec', ctypes.c_long)]
        librt = ctypes.CDLL('librt.so.1', use_errno=True)
        mono_time.get = librt.clock_gettime
        mono_time.get.argtypes = [ctypes.c_int, ctypes.POINTER(timespec)]
        mono_time.ts = timespec
    ts = mono_time.ts()
    if mono_time.get(4, ctypes.pointer(ts)) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    return ts.tv_sec + ts.tv_nsec * 1e-9


def ffmpeg_towav(path=None, block=True, max_len=None, tmp_dir=None):
    import subprocess, hashlib, base64, tempfile, atexit

    self = ffmpeg_towav
    if not hasattr(self, 'init'):
        proc = subprocess.Popen(['/bin/which', 'ffmpeg'], stdout=subprocess.PIPE)
        ffmpeg_path = proc.stdout.read()
        if proc.wait() != 0 or not ffmpeg_path.strip():
            raise PagingServerError(( 'ffmpeg binary is required to'
                    ' convert specified file (path: {!r}) to wav format, and it was not found in PATH.'
                ' Either ffmpeg can be installed or file should be pre-converted to wav.' ).format(path))

        self.init, self.procs, self.log = True, dict(), get_logger()
        self.tmp_dir = tempfile.mkdtemp(prefix='ffmpeg_towav.{}.'.format(os.getpid()))
        def proc_gc(sig, frm):
            for p,proc in self.procs.items():
                if p and proc and proc.poll() is not None:
                    pid, err = proc.pid, proc.wait()
                    if err != 0:
                        self.log.warn( 'ffmpeg converter'
                            ' pid (%s) has exited with error: %s', pid, err )
                    self.procs[p] = None
        def files_cleanup():
            file_dirs, procs = set(), self.procs.items()
            self.log.debug(
                'ffmpeg cleanup (%s pid(s), %s tmp file(s))',
                len(filter(all, procs)), len(procs) )
            for p, proc in procs:
                if p and proc and proc.poll() is not None: proc.kill()
                try: os.unlink(p)
                except (OSError, IOError): pass
                file_dirs.add(dirname(p))
            for p in file_dirs:
                try: os.rmdir(p)
                except (OSError, IOError): pass
        chk = signal.signal(signal.SIGCHLD, proc_gc)
        assert chk in [None, signal.SIG_IGN, signal.SIG_DFL], chk
        atexit.register(files_cleanup)
    if not tmp_dir: tmp_dir = self.tmp_dir

    proc = dst_path = None
    if path:
        if path.endswith('.wav'): return path
        dst_path = join(tmp_dir, '{}.wav'.format(
            base64.urlsafe_b64encode(hashlib.sha256(path).digest())[:8] ))
        if exists(dst_path): self.procs[dst_path] = None
        else:
            cmd = ['ffmpeg', '-y', '-v', '0']
            if max_len: cmd += ['-t', bytes(max_len)]
            cmd += ['-i', path, '-f', 'wav', dst_path]
            self.log.debug('Starting ffmpeg conversion: %s', ' '.join(cmd))
            proc = self.procs[dst_path] = subprocess.Popen(cmd, close_fds=True)
    if block:
        self.log.debug(
            'Waiting for %s ffmpeg pid(s) to finish conversion',
            len(filter(None, self.procs.values())) )
        if proc: proc.wait()
        else:
            procs = self.procs.items()
            if isinstance(block, (set, frozenset, list, tuple)):
                procs = list((p,proc) for p,proc in procs if p in block)
            for p, proc in procs: proc.wait()
    return dst_path


def dict_with(d, **kws):
    d.update(kws)
    return d

def dict_for_ctype(obj):
    return dict((k, getattr(obj, k)) for k in dir(obj) if not k.startswith('_'))



### PJSUA event handlers

class PSCallbacks(object):

    ev_type = None

    def __getattribute__(self, k):
        event, cb_default = k[3:] if k.startswith('on_') else None, False
        sself = super(PSCallbacks, self)
        if not event:
            try: return sself.__getattribute__(k)
            except AttributeError: return getattr(self.cbs, k) # proxy
        try: v = sself.__getattribute__(k)
        except AttributeError: v, cb_default = getattr(self.cbs, k, AttributeError), True
        if event:
            self.log.debug( '%s event: %s%s',
                self.ev_type or self.__class__.__name__,
                event, ' [default callback]' if cb_default else '' )
        if v is AttributeError: raise v(k)
        return v


class PSAccountState(PSCallbacks):

    @err_report
    def __init__(self, server):
        self.server, self.cbs = server, server.pj.AccountCallback()
        self.call_queue, self.total_calls, self.call_active = deque(), 0, False
        self.log = get_logger()

    def call_init(self, cs):
        self.log.info('Handling call: %s', cs.caller)
        # XXX: SIP events, watchdog calls should be ran while this happens
        #  but shouldn't be a problem if klaxon is no more than a few seconds long
        self.call_active = cs
        self.server.set_music_mute(True)
        self.server.wav_play_sync(self.server.conf.audio_klaxon)
        cs.call.answer()

    def call_cleanup(self, cs):
        if not self.call_active: return
        self.call_active = False

    @err_report_fatal
    def on_reg_state(self):
        acc = self.account.info()
        self.log.debug(
            'acc registration state (active: %s): %s %s',
            acc.reg_active, acc.reg_status, acc.reg_reason )
        if acc.reg_status >= 400:
            raise PSAuthError( 'Account registration'
                ' failure: {} {}'.format(acc.reg_status, acc.reg_reason) )

    @err_report
    def on_incoming_call(self, call):
        self.total_calls += 1
        call.pj = self.server.pj
        cs = PSCallState(self, self.total_calls, call)
        if not self.call_active: self.call_init(cs)
        else:
            self.log.info( 'Queueing parallel call/announcement %s, because'
                ' another one is already in-progress: %s', cs.caller, self.call_active.caller )
            self.call_queue.append(cs)

    @err_report
    def on_cs_media_activated(self, cs, conf_slot):
        self.server.conf_port_connect(conf_slot)

    @err_report
    def on_cs_disconnected(self, cs):
        self.call_cleanup(cs)
        if self.call_queue: self.call_init(self.call_queue.popleft())
        else: self.server.set_music_mute(False)


class PSCallState(PSCallbacks):

    @err_report
    def __init__(self, acc, call_id, call):
        self.cbs = call.pj.CallCallback(call)
        self.acc, self.call_id, self.call = acc, call_id, call
        self.pj_media_states = dict(
            (v, k.lower()) for k,v in vars(call.pj.MediaState).viewitems() )
        self.log = get_logger()

        ci = self.call.info()
        self.call_state = ci.state_text.lower()
        self.media_state = self.pj_media_states[ci.media_state]
        self.caller = ci.remote_uri
        m = re.findall(r'<([^>]+)>', self.caller)
        if m: self.caller = ' / '.join(m)
        self.caller = '{} (#{})'.format(self.caller, self.call_id)
        self.log.debug( 'New incoming call [%s]'
            ' (remote contact: %s)', self.caller, ci.remote_contact )
        self.ev_type = 'call [{}]'.format(self.caller)

        call.set_callback(self)

    @err_report
    def on_state(self):
        ci = self.call.info()
        state_last, self.call_state = self.call_state, ci.state_text.lower()
        self.log.debug(
            'call [%s] state change: %r -> %r (SIP status: %s %s)',
            self.caller, state_last, self.call_state, ci.last_code, ci.last_reason )
        if self.call_state == 'disconnctd':
            self.acc.on_cs_disconnected(self)

    @err_report
    def on_media_state(self, _state_dict=dict()):
        ci = self.call.info()
        state_last, self.media_state = self.media_state, self.pj_media_states[ci.media_state]
        self.log.debug(
            'call [%s] media-state change: %r -> %r (call time: %s)',
            self.caller, state_last, self.media_state, ci.call_time )
        if self.media_state == 'active':
            self.acc.on_cs_media_activated(self, ci.conf_slot)



### JACK Client

# Runs in a subprocess because two libjack clients can't work from
#  the same pid, and libjack.so in the main pid is already used by pjsua.

class JackClient(object):

    child = self_exec_args = self_exec_env = None
    jack = pj_to_jack = pj_from_jack = jack_out_hw = mpds = None

    def __init__(self, self_exec_args=None, conf=None):
        import json
        if self_exec_args:
            args = self_exec_args
            if isinstance(args, types.StringTypes): args = [args]
            args = [__file__] + list(args)
            if not os.access(__file__, os.X_OK):
                args = [sys.executable or 'python'] + args
            env = os.environ.copy()
            env['jack_slave_conf'] = json.dumps(conf)
            self.self_exec_args, self.self_exec_env = args, env
        else:
            env = os.environ.get('jack_slave_conf')
            if env: conf = json.loads(env)
        assert isinstance(conf, dict), conf
        self.conf = type('Conf', (object,), conf)
        self.log = get_logger()

    @classmethod
    def run_master(cls, args, conf):
        self = cls(args, conf)
        self.slave_start()
        return self

    @classmethod
    def run_in_slave_pid(cls): return cls().run()

    def slave_start(self):
        import subprocess
        assert not self.child and self.self_exec_args and self.self_exec_env
        self.log.debug('Starting jack client pid: %s', ' '.join(self.self_exec_args))
        self.child = subprocess.Popen(
            self.self_exec_args,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            env=self.self_exec_env, close_fds=True )
        assert self.child.stdout.readline() == 'started\n'
        # XXX: restarting child pid on failures

    def slave_stop(self):
        if self.child and self.child.poll() is not None:
            try: self.child.kill()
            except OSError: pass
        self.child = None

    def set_music_mute(self, state):
        self.child.stdin.write('{}\n'.format('+-'[bool(state)]))
        self.child.stdin.flush()
        assert self.child.stdout.readline() == 'ack\n'

    def run(self):
        assert not (self.self_exec_args or self.self_exec_env)
        logging.basicConfig(
            format='%(asctime)s :: jack-client.%(name)s %(levelname)s :: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            level=logging.DEBUG if self.conf.debug else logging.WARNING )

        self.jack_out_hw, self.mpds = set(), dict()
        self.mpd_links, self.mpd_mute = list(), False
        for mpd_link in self.conf.mpd_links.split():
            try: p_mpd, p_out = mpd_link.split('---', 1)
            except ValueError:
                raise ValueError('Invalid music-link spec: {!r}'.format(mpd_link))
            self.mpd_links.append(tuple(map(re.compile, [p_mpd, p_out])))

        import jack
        client_name = self.conf.client_name
        if not client_name: client_name = 'paging.{}'.format(os.getpid())
        self.jack = jack.Client( client_name,
            servername=self.conf.server_name or None,
            no_start_server=not self.conf.autostart )
        self.jack.Error = jack.JackError
        self.jack.set_port_registration_callback(self.init_port)
        self.jack.activate()

        for port in self.jack.get_ports(): self.init_port(port)

        for k in 'stdout', 'stderr':
            setattr(sys, k, os.fdopen(getattr(sys, k).fileno(), 'wb', 0))
        sys.stdout.write('started\n')
        m2s, s2m = sys.stdin, sys.stdout

        self.log.debug('jack client loop started')
        self.running = True
        while self.running:
            try: cmd = m2s.readline().strip()
            except KeyboardInterrupt: continue # it's for parent pid anyway
            except (OSError, IOError): cmd = ''
            self.log.debug('jack command: %r', cmd)
            if not cmd or cmd == 'exit': self.running = False
            elif cmd in ['+', '-']:
                self.mpd_mute = bool('+-'.find(cmd))
                map(self.init_port, self.mpds)
            try: s2m.write('ack\n')
            except (OSError, IOError): break
        self.log.debug('jack client loop finished')

        self.jack.deactivate()
        self.jack.close()

    def init_port( self, port, port_new=None,
            _ev_names={True: 'added', False: 'removed', None: 'synthetic'} ):
        if isinstance(port, types.StringTypes):
            p, port = port, self.jack.get_ports(re.escape(port))
            if len(port) != 1: raise LookupError(p, port)
            port, = port
        if not port.is_audio: return
        assert port.is_input ^ port.is_output, port

        print = lambda *a,**k: self.log.debug('---: %s %s', a, k)
        p, p_remove, conns_check = bytes(port.name), port_new is False, set()
        self.log.debug('jack port registration event - %s: %s', _ev_names[port_new], p)

        def get_conn_tuples():
            ps = map(op.attrgetter('name'), self.jack.get_all_connections(p))
            if port.is_output: return it.product([p], ps)
            else: return it.product(ps, [p])
        def set_link(p1, p2, state):
            t = 'connect' if state else 'disconnect'
            self.log.debug('set_link %s %s %s', p1, p2, t)
            try: getattr(self.jack, t)(p1, p2)
            except self.jack.Error as err: pass # failures here seem to be lies, client sucks
                # err = bytes(err)
                # if not re.search(r'already exists$', err):
                # 	self.log.debug('Failed to %s jack ports %s -> %s: %s', t, p1, p2, err)

        if not p_remove:
            ## New PortAudio ports
            if re.search(r'^PortAudio:', p):
                if port.is_input: self.pj_from_jack = p
                else:
                    self.pj_to_jack = p
                    conns_check.update(it.product([p], self.jack_out_hw))
                conns_check.update(get_conn_tuples())
            ## New hw output ports (speakers/cards)
            if port.is_input and p != self.pj_from_jack\
                    and re.search(self.conf.out_ports, p):
                self.jack_out_hw.add(p)
                if self.pj_to_jack: conns_check.add((self.pj_to_jack, p))
                conns_check.update(it.product(self.mpds, self.jack_out_hw))
            ## New music input ports (players)
            if port.is_output:
                mpd = p
                m = re.search(self.conf.mpd_filter, mpd)
                if m:
                    if m.groups(): mpd = m.group(1)
                    conns_check.update(get_conn_tuples())
                    if p not in self.mpds: self.mpds[p] = set()
                    for re_mpd, re_out in self.mpd_links:
                        if not re_mpd.search(mpd): continue
                        self.mpds[p].add(re_out)
                        conns_check.update(it.product([p], self.jack_out_hw))

        else:
            self.mpds.pop(p, None)
            self.jack_out_hw.discard(p)

        for p1, p2 in conns_check:
            state = None
            if p2 == self.pj_from_jack: state = False
            elif p1 == self.pj_to_jack: state = p2 in self.jack_out_hw
            elif p1 in self.mpds:
                state = not self.mpd_mute\
                    and any(re_out.search(p2) for re_out in self.mpds[p1])
            if state is not None: set_link(p1, p2, state)



### Server

class PagingServerError(Exception): pass
class PSConfigurationError(PagingServerError): pass
class PSAuthError(PagingServerError): pass

class PagingServer(object):

    lib = pj_out_dev = pj_out_port = None

    @err_report
    def __init__(self, conf, sd_cycle=None):
        import pjsua as pj # should not be imported together with jack-client
        self.pj = pj
        self.conf, self.sd_cycle = conf, sd_cycle
        self.log = get_logger()


    def match_info(self, infos, spec, kind):
        if spec.isdigit():
            try: infos = [infos[int(spec)]]
            except KeyError:
                self.log.error( 'Failed to find %s with id=%s,'
                    ' available: %s', kind, spec, ', '.join(map(bytes, infos.keys())) )
                infos = list()
        else:
            info_re = re.compile(spec, re.I)
            infos_match, infos_left = list(), list()
            for info in infos.viewvalues():
                dst_list = infos_match if info_re.search(info['name']) else infos_left
                dst_list.append(info)
        if len(infos_match) != 1:
            buff = io.BytesIO()
            pprint_infos( infos_match, 'Specification {!r}'
                ' matched {} entries'.format(spec, len(infos_match)), buff=buff )
            pprint_infos( infos_left,
                'Unmatched entries'.format(spec, len(infos_left)), buff=buff )
            raise PSConfigurationError(
                ( 'Failed to pick matching {} after pjsua init.\n{}'
                    'Only one of these has to be specified in the configuration file.\n'
                    'See "Audio configuration" section in the README file for more details.' )
                .format(kind, buff.getvalue()) )
        return infos_match[0]

    def init_outputs(self):
        if self.pj_out_dev is None:
            m, spec = self.get_pj_out_devs(), self.conf.audio_pjsua_device
            m = self.match_info(m, spec, 'output device')
            self.pj_out_dev = m['id']
            self.log.debug('Using output device: %s [%s]', m['name'], self.pj_out_dev)
            self.lib.set_snd_dev(self.pj_out_dev, self.pj_out_dev)

        if self.pj_out_port is None:
            m, spec = self.get_pj_conf_ports(), self.conf.audio_pjsua_conf_port
            m = self.match_info(m, spec, 'conference output port')
            self.pj_out_port = m['id']
            self.log.debug('Using output port: %s [%s]', m['name'], self.pj_out_port)

        self.jack.slave_start()

    @err_report_fatal
    def init(self):
        assert not self.lib

        self.log.debug('jack init')

        jack_client_conf = dict(
            debug=self.conf.server_debug,
            autostart=self.conf.audio_jack_autostart,
            server_name=self.conf.audio_jack_server_name,
            client_name=self.conf.audio_jack_client_name,
            out_ports=self.conf.audio_jack_output_ports,
            mpd_filter=self.conf.audio_jack_music_client_name,
            mpd_links=self.conf.audio_jack_music_links )
        self.jack = JackClient(self.conf.audio_jack_client_arg, jack_client_conf)

        self.log.debug('pjsua init')

        # Before logging is configured, pjsua prints some init info to plain stderr fd
        # Unless there's a good reason to see this, like debugging early crashes,
        #  there should be no need to have this exception, hence the "suppress" hack
        with suppress_streams('stdout'): self.lib = lib = self.pj.Lib()

        conf_ua = self.pj.UAConfig()
        conf_ua.max_calls = 10
        conf_ua.user_agent = ( 'PagingServer/git'
            ' (+https://github.com/AccelerateNetworks/PagingServer)' )
        conf_media = self.pj.MediaConfig()

        conf_log = lambda level,msg,n,\
            log=get_logger('pjsua'): log.debug(msg.strip().split(None,1)[-1])
        conf_log = self.pj.LogConfig(level=self.conf.server_pjsua_log_level, callback=conf_log)

        lib.init(conf_ua, conf_log, conf_media)

        # lib.start(with_thread=False) doesn't work well with python code
        transport = lib.create_transport(self.pj.TransportType.UDP)
        lib.start(with_thread=True)
        lib.c = self.pj._pjsua

    @err_report_fatal
    def destroy(self):
        if not self.lib: return

        self.log.debug('pjsua cleanup')
        self.lib.destroy()
        self.lib = None

        self.log.debug('jack cleanup')
        self.jack.slave_stop()
        self.jack = None

    def __enter__(self):
        self.init()
        return self
    def __exit__(self, *err): self.destroy()
    def __del__(self): self.destroy()


    @err_report_fatal
    def run(self):
        assert self.lib, 'Must be initialized before run()'
        self.init_outputs()

        acc = self.lib.create_account(self.pj.AccountConfig(
            *map(ft.partial(self.conf.get, 'sip'), ['domain', 'user', 'pass']) ))
        acc.set_callback(PSAccountState(self))

        self.running = True
        self.log.debug('pjsua event loop started')
        while True:
            if not self.sd_cycle or not self.sd_cycle.ts_next: max_poll_delay = 600
            else:
                ts = mono_time()
                max_poll_delay = self.sd_cycle.ts_next - ts
                if max_poll_delay <= 0:
                    self.sd_cycle(ts)
                    continue
            if not (self.running and self.lib): break
            time.sleep(max_poll_delay)
            if self.conf.audio_klaxon_tmpdir: os.utime(self.conf.audio_klaxon_tmpdir, None)
        self.log.debug('pjsua event loop has been stopped')

    def stop(self): self.running = False


    def get_pj_conf_ports(self):
        return dict(
            (n, dict_with(dict_for_ctype(self.lib.c.conf_get_port_info(port_id)), id=n))
            for n, port_id in enumerate(self.lib.c.enum_conf_ports()) )

    def get_pj_out_devs(self):
        return dict( (n, dict_with(vars(dev), id=n))
            for n, dev in enumerate(self.lib.enum_snd_dev()) )

    def conf_port_connect(self, conf_port):
        self.lib.conf_connect(conf_port, self.pj_out_port)

    def set_music_mute(self, state):
        self.jack.set_music_mute(state)


    @contextmanager
    def wav_play(self, path, loop=False, connect_to_out=True):
        # Currently there (still!) doesn't seem to be any callback for player EOF:
        #  http://lists.pjsip.org/pipermail/pjsip_lists.pjsip.org/2010-June/011112.html
        player_id = self.lib.create_player(path, loop=loop)
        try:
            player_port = self.lib.player_get_slot(player_id)
            if connect_to_out: self.conf_port_connect(player_port)
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
        ts_diff, ts_diff_max = self.wav_length(path), self.conf.audio_klaxon_max_length
        if ts_diff_max > 0: ts_diff = min(ts_diff, ts_diff_max)
        with self.wav_play(path) as player_port:
            self.log.debug('Started blocking playback of wav for time: %.1fs', ts_diff)
            time.sleep(ts_diff + ts_diff_pad)



### CLI and such

def pprint_infos(infos, title=None, pre=None, buff=None):
    p = print if not buff else ft.partial(print, file=buff)
    if title:
        p('{}:'.format(title))
        if pre is None: pre = ' '*2
    pre = pre or ''
    if isinstance(infos, dict): infos = infos.values()
    for info in infos:
        info_id = '[{}] '.format(info['id']) if 'id' in info else ''
        p('{}{}{}'.format(pre, info_id, info['name']))
        for k, v in sorted(info.viewitems()):
            if k in ['id', 'name']: continue
            p('{}  {}: {}'.format(pre, k, v))

def pprint_conf(conf, title=None):
    cat, chk = None, re.compile(
        '^({})_(.*)$'.format('|'.join(map(re.escape, conf._conf_sections))) )
    if title: print(';; {}'.format(title))
    for k in sorted(dir(conf)):
        m = chk.search(k)
        if not m: continue
        if m.group(1) != cat:
            cat = m.group(1)
            print('\n[{}]'.format(cat))
        v = conf.get(k)
        if isinstance(v, bool): v = ['no', 'yes'][v]
        print('{} = {}'.format(m.group(2), v))

def main(args=None, defaults=None):
    args, defaults = sys.argv[1:] if args is None else args, defaults or Conf()

    # Running jack client in the same pid as pjsua doesn't work correctly.
    # This is likely because of global state in libjack with two clients from same pid.
    if defaults.audio_jack_client_arg in args: return JackClient.run_in_slave_pid()

    import argparse
    parser = argparse.ArgumentParser(
        usage='%(prog)s [options] [conf [conf ...]]',
        description='SIP-based Announcement / PA / Paging / Public Address Server system.')

    group = parser.add_argument_group('configuration options')
    group.add_argument('conf', nargs='*',
        help='Extra config files to load on top of default ones.'
            ' Values in latter ones override those in the former, cli values override all.'
            ' Initial files (always loaded, if exist): {}'.format(' '.join(defaults._conf_paths)))
    group.add_argument('--dump-conf', action='store_true',
        help='Print all configuration settings, which will be used with'
            ' currently detected (and/or specified) configuration files, and exit.')
    group.add_argument('--dump-conf-defaults', action='store_true',
        help='Print all default settings, which would be used'
            ' if no configuration files were overriding these, and exit.')

    group = parser.add_argument_group('startup options')
    group.add_argument('--systemd', action='store_true',
        help='Use systemd service'
            ' notification/watchdog mechanisms in daemon modes, if available.')

    group = parser.add_argument_group(
        'pjsua output configuration and testing',
        'Options related to sound output from SIP calls (pjsua client).')
    group.add_argument('--dump-pjsua-devices', action='store_true',
        help='Dump the list of sound devices that pjsua/portaudio detects and exit.')
    group.add_argument('--dump-pjsua-conf-ports', action='store_true',
        help='Dump the list of conference ports that pjsua creates after init and exit.')
    group.add_argument('--dump-jack-ports', action='store_true',
        help='Dump the list of jack input/output ports that are available.')
    group.add_argument('--test-audio-file', metavar='path',
        help='Play specified wav file from pjsua output and exit.'
            ' Can be useful to test whether sound output from SIP calls is setup and working correctly.')

    group = parser.add_argument_group(
        'debugging, logging and other misc options',
        'Use these to understand more about what'
            ' is failing or going on. Can be especially useful on first runs.')
    group.add_argument('-d', '--debug',
        action='store_true', help='Verbose operation mode.')
    group.add_argument('--pjsua-log-level',
        metavar='0-10', type=int,
        help='pjsua lib logging level. Only used when --debug is enabled.'
            ' Zero is only for fatal errors, higher levels are more noisy.'
            ' Default: {}'.format(defaults.server_pjsua_log_level))
    group.add_argument('--sentry-dsn', metavar='dsn',
        help='Use Sentry to capture errors/logging using "raven" module.'
            ' Default: {}'.format(defaults.server_sentry_dsn))
    group.add_argument('--version', action='version',
        version='%(prog)s version-unknown (see python package version)')

    opts = parser.parse_args(args)

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

    if opts.dump_conf_defaults:
        pprint_conf(defaults, 'Default configuration options')
        return

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

    if opts.dump_conf:
        pprint_conf(conf, 'Current configuration options')
        return

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
                if ts is None: ts = mono_time()
                delay = ts - sd_cycle.ts_next
                if delay > 0: time.sleep(delay)
                sd_cycle.ts_next += sd_cycle.delay
            else: sd_cycle.ts_next = None
            if sd_cycle.wdt: daemon.notify('WATCHDOG=1')
        sd_cycle.ts_next = mono_time()
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

    if opts.dump_pjsua_devices:
        with server_ctx as server:
            devs = server.get_pj_out_devs()
            pprint_infos(devs, 'Detected sound devices')
        return

    if opts.dump_pjsua_conf_ports:
        with server_ctx as server:
            ports = server.get_pj_conf_ports()
            pprint_infos(ports, 'Detected conference ports')
        return

    if opts.dump_jack_ports:
        import jack
        client = jack.Client( 'port-list',
            servername=conf.audio_jack_server_name or None,
            no_start_server=not conf.audio_jack_autostart )
        ports = dict()
        for p in client.get_ports(is_audio=True):
            port = dict()
            for k in dir(p):
                if k not in ['name', 'uuid']: continue
                port[k] = getattr(p, k)
            port['type'] = 'input (player or other sound source)'\
                if p.is_output else 'output (speakers, audio card or such)'
            ports[port['name']] = port
        pprint_infos(ports, 'Detected jack ports')
        return

    if opts.test_audio_file:
        opts.test_audio_file = ffmpeg_towav(opts.test_audio_file)
        with server_ctx as server:
            try:
                server.init_outputs()
                server.wav_play_sync(opts.test_audio_file)
            except PSConfigurationError as err:
                print(bytes(err), file=sys.stderr)
                return 1
        return

    if not isfile(conf.audio_klaxon):
        parser.error(( 'Specified klaxon file does not exists'
            ' (set empty value there to disable using it entirely): {!r}' ).format(conf.audio_klaxon))

    if conf.audio_klaxon and not conf.audio_klaxon.endswith('.wav'):
        conf.audio_klaxon = ffmpeg_towav( conf.audio_klaxon,
            max_len=conf.audio_klaxon_max_length, tmp_dir=conf.audio_klaxon_tmpdir )
        if not conf.audio_klaxon_tmpdir: conf.audio_klaxon_tmpdir = ffmpeg_towav.tmp_dir

    log.info('Starting PagingServer...')
    with server_ctx as server:
        for sig in signal.SIGINT, signal.SIGTERM:
            signal.signal(sig, lambda sig,frm: server.destroy())
        try: server.run()
        except (PSConfigurationError, PSAuthError) as err:
            print('ERROR [{}]: {}'.format(err.__class__.__name__, err), file=sys.stderr)
            return 1
        except KeyboardInterrupt: pass
    log.info('Finished')

if __name__ == '__main__': sys.exit(main())
