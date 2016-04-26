#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function

import itertools as it, operator as op, functools as ft
from os.path import join, exists, isfile, expanduser, dirname
from contextlib import contextmanager, closing
from collections import deque, OrderedDict
from heapq import heappush, heappop, heappushpop
import ConfigParser as configparser
import os, sys, io, re, types, ctypes, threading
import time, signal, logging, inspect


class Conf(object):

    sip_domain = ''
    sip_user = ''
    sip_pass = ''

    audio_klaxon = ''
    audio_klaxon_tmpdir = ''
    audio_klaxon_max_length = 10.0
    audio_klaxon_padding = 0.0
    audio_pjsua_device = '^pulse$'
    audio_pjsua_conf_port = '' # there should be only one
    audio_pulse_match = '^application\.process\.binary=mpd$'

    audio_volume_music = -1.0
    audio_volume_klaxon = -1.0
    audio_volume_call = -1.0

    audio_music_fade_in_duration = 10.0
    audio_music_fade_out_duration = 3.0
    audio_music_fade_in_offset = 0.0
    audio_music_fade_out_offset = 0.0
    audio_music_fade_in_min = 0.0
    audio_music_fade_out_min = 0.0

    calls_hold_concurrent = False
    calls_hang_up_after_minutes = 5.0

    server_debug = False
    server_dump_pulse_props = False
    server_pjsua_log_level = 0
    server_sentry_dsn = ''
    server_pjsua_cleanup_timeout = 5

    _conf_paths = ( 'paging.conf',
        '/etc/paging.conf', 'callpipe.conf', '/etc/callpipe.conf' )
    _conf_sections = 'sip', 'audio', 'calls', 'server'

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
    if path and path.endswith('.wav'): return path
    import subprocess, hashlib, base64, tempfile, atexit

    self = ffmpeg_towav
    if not hasattr(self, 'init'):
        for p in 'ffmpeg', 'avconv':
            proc = subprocess.Popen(['/bin/which', p], stdout=subprocess.PIPE)
            ffmpeg_path = proc.stdout.read()
            if proc.wait() == 0 and ffmpeg_path.strip():
                self.binary = p
                break
        else:
            raise PagingServerError(( 'ffmpeg/avconv binary is required to'
                    ' convert specified file (path: {!r}) to wav format, and it was not found in PATH.'
                ' Either ffmpeg can be installed (e.g. "apt-get install libav-tools"),'
                    ' or file should be pre-converted to wav.' ).format(path))

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
        dst_path = join(tmp_dir, '{}.wav'.format(
            base64.urlsafe_b64encode(hashlib.sha256(path).digest())[:8] ))
        if exists(dst_path): self.procs[dst_path] = None
        else:
            cmd = [self.binary, '-y', '-v', '0']
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
        self.call_queue, self.total_calls, self.call_active = deque(), 0, None
        self.hang_up_after = self.server.conf.calls_hang_up_after_minutes * 60.0
        self.log = get_logger()

    @err_report
    def call_init(self, cs):
        self.log.info('Handling call: %s', cs.caller)
        self.call_active = cs
        self.server.set_music_mute(True)
        self.server.set_volume_level('klaxon')
        self.server.wav_play_sync(self.server.conf.audio_klaxon)
        self.server.set_volume_level('call')
        cs.call.answer()
        if self.hang_up_after > 0:
            self.server.poll_callback(ft.partial(
                self.on_cs_timeout, cs, mono_time() ), self.hang_up_after)

    @err_report
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
            self.server.close()
            raise PSAuthError( 'Account registration'
                ' failure: {} {}'.format(acc.reg_status, acc.reg_reason) )

    @err_report
    def on_incoming_call(self, call):
        self.total_calls += 1
        call.pj = self.server.pj
        cs = PSCallState(self, self.total_calls, call)
        if not self.server.conf.calls_hold_concurrent\
            or not self.call_active: self.call_init(cs)
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

    @err_report
    def on_cs_timeout(self, cs, ts0=None):
        if cs.call_state in ['null', 'disconnected', 'terminated']: return
        ts_diff = mono_time() - ts0
        log.debug(
            'Terminating call [%s] (state: %s) due'
                ' to call-duration limit (%ds), elapsed: %ds',
            cs.caller, cs.call_state, self.hang_up_after, ts_diff )
        cs.call.hangup(reason='call duration limit')



class PSCallState(PSCallbacks):

    # Includes "terminated" state from pjsip/src/pjsip-ua/sip_inv.c
    # Updated on pjsua callbacks only.
    call_state_names = OrderedDict(enumerate(( 'null calling'
        ' incoming early connecting confirmed disconnected terminated' ).split()))

    @err_report
    def __init__(self, acc, call_id, call):
        self.cbs = call.pj.CallCallback(call)
        self.acc, self.call_id, self.call = acc, call_id, call
        self.pj_media_states = dict(
            (v, k.lower()) for k,v in vars(call.pj.MediaState).viewitems() )
        self.log = get_logger()

        ci = self.call.info()
        self.call_state = self.call_state_names.get(ci.state, 'unknown-init')
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
        state_last, self.call_state = self.call_state, self.call_state_names.get(ci.state, 'unknown')
        self.log.debug(
            'call [%s] state change: %r -> %r (SIP status: %s %s)',
            self.caller, state_last, self.call_state, ci.last_code, ci.last_reason )
        if self.call_state == 'disconnected': self.acc.on_cs_disconnected(self)

    @err_report
    def on_media_state(self, _state_dict=dict()):
        ci = self.call.info()
        state_last, self.media_state = self.media_state, self.pj_media_states[ci.media_state]
        self.log.debug(
            'call [%s] media-state change: %r -> %r (call time: %s)',
            self.caller, state_last, self.media_state, ci.call_time )
        if self.media_state == 'active':
            self.acc.on_cs_media_activated(self, ci.conf_slot)



### PulseAudio Client

class PulseClient(object):

    def __init__(self, si_filter_regexp, si_filter_debug=False, volume=None, fade=None):
        from pulsectl import ( Pulse, PulseSinkInputInfo,
            PulseLoopStop, PulseIndexError, PulseError )
        # Running client here might start pa pid, so defer it until we actually
        #  init audio output, and not started to just display some info and exit.
        self.si_filter_regexp, self.si_filter_debug = si_filter_regexp, si_filter_debug
        self._connect, self._si_t, self.pulse = Pulse, PulseSinkInputInfo, None
        self.PulseIndexError, self.PulseError, self.PulseLoopStop =\
            PulseIndexError, PulseError, PulseLoopStop
        self.log = get_logger()

        self.volume = dict(zip(['music', 'klaxon', 'call'], it.repeat(-1)))
        self.volume.update(volume or dict())
        self.fade = dict((t, dict(duration=0, offset=0, min=0, steps=25)) for t in ['in', 'out'])
        for t, v in self.fade.viewitems(): v.update((fade or dict()).get(t) or dict())

    def init(self):
        self.pulse = self._connect('paging-server')
        self.pulse.event_mask_set('sink_input')
        self.pulse.event_callback_set(self._handle_new_si)
        self.si_queue, self.si_pjsua, self.changes = deque(), None, dict()
        self.music_muted = False
        self.set_music_mute(False)

    def close(self):
        if self.pulse:
            self.pulse.close()
            self.pulse = None

    def set_music_mute(self, muted=None):
        if muted is None: muted = self.music_muted
        if self.music_muted and not muted: fade = 'in'
        elif not self.music_muted and muted: fade = 'out'
        else: fade = None
        self.music_muted = muted
        if fade: self.changes['music-fade'] = self._change_fade(fade)
        else: self.si_queue.append(None)

    def set_pjsua_volume(self, t):
        self.changes['pjsua-volume'] = self._change_volume(t)

    def _handle_new_si(self, ev):
        if ev.t != 'new' or ev.facility != 'sink_input': return
        self.si_queue.append(ev.index)
        raise self.PulseLoopStop

    def _match_music_si(self, si=None):
        idx, si = (si, self.pulse.sink_input_info(si))\
            if not isinstance(si, self._si_t) else (si.index, si)
        for k, v in si.proplist.viewitems():
            v = '{}={}'.format(k, v)
            m = re.search(self.si_filter_regexp, v)
            if self.si_filter_debug:
                self.log.debug(' - prop%s: %r', ['', '[MATCH]'][bool(m)], v)
            if m: return si
        # self.log.debug('Ignoring unmatched sink-input: %s', si)

    @err_report
    def _process_changes(self):
        wakeups = list()

        for k in self.changes.keys():
            c = self.changes[k]
            try: wakeup = next(c)
            except StopIteration: del self.changes[k]
            else:
                if isinstance(wakeup, (int, float)): wakeup = [wakeup]
                wakeups.extend(wakeup)

        while self.si_queue:
            si = self.si_queue.popleft()
            if si is None:
                self.si_queue.extend(self.pulse.sink_input_list())
                continue
            try:
                si = self._match_music_si(si)
                if si:
                    if not self.music_muted and self.volume['music'] >= 0:
                        self.pulse.volume_set_all_chans(si, self.volume['music'])
                    self.log.debug( 'Setting mute to %s'
                        ' for sink-input: %s', ['OFF', 'ON'][self.music_muted], si )
                    self.pulse.mute(si, self.music_muted)
            except self.PulseIndexError: continue

        return wakeups

    @err_report
    def _change_volume(self, t):
        v = self.volume[t]
        if v <= 0: return
        if self.volume[t] >= 0: v = self.volume[t]
        if not self.si_pjsua:
            pid = os.getpid()
            for si in self.pulse.sink_input_list():
                pid_chk = int(si.proplist.get('application.process.id') or 0)
                m = pid_chk == pid
                if self.si_filter_debug:
                    self.log.debug( 'Sink-input %s proc-id check: %s (si) =='
                        ' %s (pjsua)%s', si.index, pid_chk, pid, ' [MATCH]' if m else '' )
                if m: self.si_pjsua = si
        if self.si_pjsua:
            try:
                v_old = self.pulse.volume_get_all_chans(self.si_pjsua)
                if round(v, 2) != round(v_old, 2):
                    self.log.debug( 'Setting pjsua stream'
                        ' volume level: %.2f -> %.2f (%s)', v_old, v, t )
                self.pulse.volume_set_all_chans(self.si_pjsua, v)
            except self.PulseIndexError: self.si_pjsua = None
        else:
            self.log.warn( 'Failed to detect pjsua stream'
                ' in pulse sink inputs, not adjusting volume for it' )
        return; yield

    @err_report
    def _change_fade(self, t):
        s = self.fade[t]
        if s['duration'] <= 0:
            self.set_music_mute()
            return

        ts_start = mono_time() + s['offset']
        si_list = filter(self._match_music_si, self.pulse.sink_input_list())
        v_si_min, v_si_max = dict(), dict()
        if t == 'out':
            v_si_max.update(
                (si.index, self.pulse.volume_get_all_chans(si)) for si in si_list )
            v_si_min.update((si.index, s['min']) for si in si_list)
            self.volume['fade'] = v_si_max # to restore same levels on fade-in
        else:
            v_si_max_prev = self.volume.pop('fade', dict())
            for si in si_list:
                v = None
                if si.index in v_si_max_prev: v = v_si_max_prev[si.index]
                elif self.volume['music'] > 0: v = self.volume['music']
                if v is not None:
                    v_si_max[si.index], v_si_min[si.index] = v, s['min']
                    try: self.pulse.volume_set_all_chans(si, v_si_min[si.index])
                    except self.PulseIndexError: pass
            self.set_music_mute()
        v_si_len = len(set(v_si_max.keys() + v_si_min.keys()))

        self.log.debug('Starting music fade-%s for %s pulse stream(s)', t, v_si_len)
        for n in xrange(1, s['steps']+1):
            ts_step = ts_start + (s['duration'] * (n / float(s['steps'])))
            while True:
                ts = mono_time()
                if ts_step > mono_time(): yield ts_step
                else: break
            for si in si_list:
                try: v_max = v_si_max[si.index]
                except KeyError: continue
                v_min = v_si_min.get(si.index, s['min'])
                v_range, k = max(0, v_max - v_min), n / float(s['steps'])
                v = v_min + v_range * (k if t == 'in' else (1-k))
                # self.log.debug( 'Stream %s music fade-%s step'
                # 	' %s/%s: base=%.2f level=%.2f', si.index, t, n, s['steps'], v_min, v )
                try: self.pulse.volume_set_all_chans(si, v)
                except self.PulseIndexError: pass

        for si in si_list:
            if t == 'out': v = v_si_min.get(si.index, s['min'])
            else:
                v = v_si_max.get(si.index)
                if v is None: continue
            try: self.pulse.volume_set_all_chans(si, v)
            except self.PulseIndexError: pass

        self.log.debug('Finished music fade-%s sequence for %s stream(s)', t, v_si_len)
        self.set_music_mute()

    def poll_wakeup(self):
        if not self.pulse: return
        self.pulse.event_listen_stop()

    @err_report
    def poll(self, timeout=None):
        # Only safe to call pulse here, and before event_listen()
        wakeups = [mono_time() + timeout] + self._process_changes()
        delay = min(wakeups) - mono_time()
        if delay > 0:
            try: self.pulse.event_listen(delay)
            except:
                if self.pulse: raise



### Server

class PagingServerError(Exception): pass
class PSConfigurationError(PagingServerError): pass
class PSAuthError(PagingServerError): pass

class PagingServer(object):

    lib = pj_out_dev = pj_out_port = None

    @err_report
    def __init__(self, conf, sd_cycle=None):
        import pjsua
        self.pj, self.pulse = pjsua, None
        self.conf, self.sd_cycle = conf, sd_cycle
        self.log = get_logger()
        self.running, self._poll_callbacks, self._locks = None, list(), set()
        self._poll_lock, self._poll_hold = threading.Lock(), threading.Lock()


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

        try: self.pulse.init()
        except Exception as err:
            self.log.error('Failed to initialize PulseAudio controls: %s', err)
            raise

    @err_report_fatal
    def init(self):
        assert not self.lib

        self.log.debug('pulse init')
        conf_volume = dict(
            (k, getattr(self.conf, 'audio_volume_{}'.format(k)) / 100.0)
            for k in ['music', 'klaxon', 'call'] )
        conf_fade= dict( (t, dict(
            (k, getattr(self.conf, 'audio_music_fade_{}_{}'.format(t, k)))
            for k in ['duration', 'offset', 'min'] )) for t in ['in', 'out'] )
        for t, v in conf_fade.viewitems(): v['min'] /= 100.0
        self.pulse = PulseClient(
            volume=conf_volume, fade=conf_fade,
            si_filter_regexp=self.conf.audio_pulse_match,
            si_filter_debug=self.conf.server_dump_pulse_props )

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
    def close(self):
        self.stop()
        if self.lib:
            self.log.debug('pjsua cleanup')
            self.lib.destroy()
            self.lib = None
        if self.pulse:
            self.log.debug('pulse cleanup')
            self.pulse.close()
            self.pulse = None

    def __enter__(self):
        self.init()
        return self
    def __exit__(self, *err): self.close()


    @contextmanager
    def poll_wakeup(self, loop_wait=5.0, loop_interval=0.1):
        'Anything poll-related MUST be done in this context.'
        lock = self.pulse and self.running is not False
        if lock:
            with self._poll_hold:
                for n in xrange(int(loop_wait / loop_interval)):
                    # wakeup only works when loop is actually started,
                    #  which might not be the case regardless of any locks.
                    self.pulse.poll_wakeup()
                    if self._poll_lock.acquire(False): break
                    time.sleep(loop_interval)
                else:
                    raise PagingServerError('poll_wakeup() hangs, likely locking issue')
                try: yield
                finally: self._poll_lock.release()
        else: yield

    def poll_callback(self, func, delay=None, ts=None):
        with self.poll_wakeup():
            if ts is None: ts = mono_time()
            ts += delay or 0
            heappush(self._poll_callbacks, (ts, func))

    def poll_lock(self, delay):
        lock = threading.Lock()
        def lock_release_safe():
            try: lock.release()
            except: pass
        self._locks.add(lock_release_safe)
        try:
            lock.acquire()
            self.poll_callback(lock_release_safe, delay)
            lock.acquire()
        finally:
            lock_release_safe()
            self._locks.discard(lock_release_safe)

    @err_report_fatal
    def poll(self, timeout=None):
        if threading.current_thread().name != 'MainThread':
            assert timeout
            return self.poll_lock(timeout)
        ts = mono_time()
        self.running, ts_deadline = True, timeout and mono_time() + timeout
        while True:
            with self._poll_hold: self._poll_lock.acquire() # fuck threads
            try:
                ts = mono_time()
                if not self.sd_cycle or not self.sd_cycle.ts_next: delay = 600
                else:
                    delay = self.sd_cycle.ts_next - ts
                    if delay <= 0:
                        self.sd_cycle(ts)
                        continue
                if not (self.running and self.lib): break
                if ts_deadline: delay = min(delay, ts_deadline - ts)
                while self._poll_callbacks:
                    ts_cb, cb = self._poll_callbacks[0]
                    if ts >= ts_cb:
                        heappop(self._poll_callbacks)
                        cb()
                    else:
                        delay = min(delay, ts_cb - ts)
                        break
                # self.log.debug('poll delay: %.1f', delay)
                self.pulse.poll(max(0, delay))
                if self.conf.audio_klaxon_tmpdir: os.utime(self.conf.audio_klaxon_tmpdir, None)
                if ts_deadline and ts > ts_deadline: break
            finally: self._poll_lock.release()

    @err_report_fatal
    def run(self):
        assert self.lib, 'Must be initialized before run()'
        self.init_outputs()

        domain, user, pw = map(ft.partial(self.conf.get, 'sip'), ['domain', 'user', 'pass'])
        if not domain or domain == '<sip server>':
            raise PagingServerError( 'SIP account credentials'
                ' (domain, user, password) were not configured, refusing to start' )
        acc = self.lib.create_account(self.pj.AccountConfig(domain, user, pw))
        acc.set_callback(PSAccountState(self))

        self.log.debug('pjsua event loop started')
        self.poll()
        self.log.debug('pjsua event loop has been stopped')

    def stop(self):
        self.running = False
        if self._locks:
            for release_func in self._locks: release_func()
            self._locks.clear()
        self.poll_wakeup()


    def get_pj_conf_ports(self):
        return dict(
            (n, dict_with(dict_for_ctype(self.lib.c.conf_get_port_info(port_id)), id=n))
            for n, port_id in enumerate(self.lib.c.enum_conf_ports()) )

    def get_pj_out_devs(self):
        return dict( (n, dict_with(vars(dev), id=n))
            for n, dev in enumerate(self.lib.enum_snd_dev()) )

    def conf_port_connect(self, conf_port):
        self.lib.conf_connect(conf_port, self.pj_out_port)

    def set_music_mute(self, muted):
        with self.poll_wakeup(): self.pulse.set_music_mute(muted)

    def set_volume_level(self, state):
        assert state in ['klaxon', 'call']
        with self.poll_wakeup(): self.pulse.set_pjsua_volume(state)


    @contextmanager
    def wav_play(self, path, loop=False, connect_to_out=True):
        player_id = self.lib.create_player(path, loop=loop)
        try:
            port = self.lib.player_get_slot(player_id)
            if connect_to_out: self.conf_port_connect(port)
            yield port
        finally: self.lib.player_destroy(player_id)

    def wav_length(self, path, force_file=True):
        # Only useful to stop playback in a hacky ad-hoc way,
        #  because pjsua python lib doesn't export proper callback,
        #  and ctypes wrapper doesn't seem to work reliably either (see 7f1df5d)
        import wave
        if force_file and not isfile(path): # missing, fifo, etc
            raise PagingServerError(path)
        with closing(wave.open(path, 'r')) as src:
            return src.getnframes() / float(src.getframerate())

    def wav_play_sync(self, path):
        ts_diff, ts_diff_max = self.wav_length(path), self.conf.audio_klaxon_max_length
        if ts_diff_max > 0: ts_diff = min(ts_diff, ts_diff_max)
        with self.wav_play(path) as port:
            self.log.debug('Started blocking playback of wav for time: %.1fs', ts_diff)
            self.poll(ts_diff + self.conf.audio_klaxon_padding)
            self.log.debug('wav playback finished')



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
    group.add_argument('--test-audio-file', metavar='path',
        help='Play specified wav file from pjsua output and exit.'
            ' Sound will be played with call volume level, if set via'
                ' config file (see "volume-call" option in "[audio]" section there).'
            ' Can be useful to test whether sound output from SIP calls is setup and working correctly.')

    group = parser.add_argument_group(
        'debugging, logging and other misc options',
        'Use these to understand more about what'
            ' is failing or going on. Can be especially useful on first runs.')
    group.add_argument('-d', '--debug',
        action='store_true', help='Verbose operation mode.')
    group.add_argument('--dump-pulse-props', action='store_true',
        help='Dump all properties of pulse streams as they get matched. Requires --debug.')
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
    for k in 'debug', 'dump_pulse_props', 'pjsua_log_level', 'sentry_dsn':
        v = getattr(opts, k)
        if v not in [None, False]: setattr(conf, 'server_{}'.format(k), v)

    if opts.dump_conf:
        pprint_conf(conf, 'Current configuration options')
        return

    global log
    log = '%(name)s %(levelname)s :: %(message)s'
    if not opts.systemd: log = '%(asctime)s :: {}'.format(log)
    logging.basicConfig(
        format=log, datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.DEBUG if conf.server_debug else logging.WARNING )
    log = logging.getLogger('main')
    if conf.server_debug:
        for k in 'stdout', 'stderr':
            setattr(sys, k, os.fdopen(getattr(sys, k).fileno(), 'wb', 0))

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

    if opts.test_audio_file:
        opts.test_audio_file = ffmpeg_towav(opts.test_audio_file)
        with server_ctx as server:
            try:
                server.init_outputs()
                server.set_volume_level('call')
                server.wav_play_sync(opts.test_audio_file)
            except PSConfigurationError as err:
                print(bytes(err), file=sys.stderr)
                return 1
        return

    if conf.audio_klaxon:
        if not isfile(conf.audio_klaxon):
            parser.error(( 'Specified klaxon file does not exists'
                ' (set empty value there to disable using it entirely): {!r}' ).format(conf.audio_klaxon))
        if not conf.audio_klaxon.endswith('.wav'):
            conf.audio_klaxon = ffmpeg_towav( conf.audio_klaxon,
                max_len=conf.audio_klaxon_max_length, tmp_dir=conf.audio_klaxon_tmpdir )
            if not conf.audio_klaxon_tmpdir: conf.audio_klaxon_tmpdir = ffmpeg_towav.tmp_dir

    log.info('Starting PagingServer...')
    with server_ctx as server:
        for sig in signal.SIGINT, signal.SIGTERM:
            signal.signal(sig, lambda sig,frm: server.close())
        try: server.run()
        except (PSConfigurationError, PSAuthError) as err:
            print('ERROR [{}]: {}'.format(err.__class__.__name__, err), file=sys.stderr)
            return 1
        except Exception as err:
            # Logged here in case cleanup fails miserably and pid gets brutally murdered by kill -9
            log.exception('Server runtime ERROR [%s], aborting: %s', err.__class__.__name__, err)
            raise
        except KeyboardInterrupt: pass
    log.info('Finished')

if __name__ == '__main__': sys.exit(main())
