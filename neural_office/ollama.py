"""A dedicated, owned Ollama process tree; the user's existing service is untouched."""
import ctypes
from ctypes import wintypes
import hashlib
import http.client
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import socket
import struct
import subprocess
import threading
import time

from .ledger import Denied, canonical
from .files import capture_local
from .windows_job import Job


def json_unique(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('DUPLICATE_JSON_KEY')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def local_metadata(route='/api/tags',port=11434):
    con=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
    try:
        con.request('GET',route)
        response=con.getresponse()
        data=response.read(2_000_001)
        if response.status!=200 or len(data)>2_000_000: raise Denied('METADATA_UNAVAILABLE')
        return json_unique(data)
    finally: con.close()


def select_model(name,models):
    found=[m for m in models if m.get('name')==name]
    if len(found)!=1 or not found[0].get('digest') or found[0].get('size',0)<=0:
        raise Denied('LOCAL_MODEL_NOT_FOUND')
    if ':cloud' in name.lower() or found[0].get('remote_host') or found[0].get('remote_model'):
        raise Denied('CLOUD_MODEL_EXCLUDED')
    return {'mode':'ollama-owned','model':name,'model_digest':found[0]['digest'],
            'num_ctx':8192,'num_predict':128,'num_gpu':0,'timeout_seconds':300}


TEAM_POLICY = 'local-team-v1'
MULTILINE_BROWSER_FORMAT = 'locations-and-browser-check-v2'
LEGACY_MULTILINE_BROWSER_FORMAT = 'locations-and-browser-check-v1'
POLISHED_TEAM = 'project-warm-v1'


def review_profile(model, roles):
    profile = {**model, 'roles': roles}
    if roles == 7 and model.get('mode') == 'ollama-owned':
        profile.update(execution_policy=TEAM_POLICY, num_gpu=-1, citation_format=MULTILINE_BROWSER_FORMAT,
                       team_session=POLISHED_TEAM)
    return profile


def inference_options(profile):
    options = {'num_ctx': 8192, 'num_predict': 128, 'num_gpu': 0, 'temperature': 0}
    if 'team_session' in profile and (profile['team_session'] != POLISHED_TEAM or profile.get('execution_policy') != TEAM_POLICY):
        raise Denied('MODEL_PROFILE_MISMATCH')
    if 'execution_policy' in profile:
        if (profile['execution_policy'] != TEAM_POLICY or profile.get('roles') != 7
                or profile.get('mode') != 'ollama-owned' or profile.get('analysis_scope')
                or profile.get('num_gpu') != -1):
            raise Denied('MODEL_PROFILE_MISMATCH')
        options.update(num_gpu=-1, num_thread=1)
    elif profile.get('num_gpu', 0) != 0:
        raise Denied('MODEL_PROFILE_MISMATCH')
    return options


def listener_pids(port):
    """Read the local IPv4 listener table in process. Each OS row is six DWORDs."""
    query = ctypes.WinDLL('iphlpapi', winmode=0x800).GetExtendedTcpTable  # LOAD_LIBRARY_SEARCH_SYSTEM32
    query.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL,
                      wintypes.ULONG, ctypes.c_int, wintypes.ULONG]
    query.restype = wintypes.DWORD
    size = wintypes.DWORD(4096)
    for _ in range(4):
        buf = ctypes.create_string_buffer(size.value)
        error = query(buf, ctypes.byref(size), False, socket.AF_INET, 3, 0)  # TCP_TABLE_OWNER_PID_LISTENER
        if error == 122 and 0 < size.value <= 16 * 1024 * 1024:
            continue
        if error or size.value < 4 or size.value > len(buf):
            break
        count, = struct.unpack_from('<I', buf)
        end = 4 + count * 24
        if end > size.value:
            break
        loopback = int.from_bytes(socket.inet_aton('127.0.0.1'), 'little')
        port_word = socket.htons(port)
        return {pid for state, address, local_port, _, _, pid in struct.iter_unpack('<6I', buf.raw[4:end])
                if state == 2 and address == loopback and local_port == port_word}
    raise Denied('BACKEND_LISTENER_OWNER_UNKNOWN')


def _matching_bytes(path, root, expected):
    data, _ = capture_local(path, root, maximum=65536)
    if hashlib.sha256(data).hexdigest() != expected:
        raise Denied('MODEL_DIGEST_CHANGED')
    return data


def _team_model_files(root, profile, version):
    """Attest a plain v2 tag against the live catalog before using per-file checks."""
    if version != '0.40.16' or profile.get('execution_policy') != TEAM_POLICY or not root.is_absolute():
        return ()
    match = re.fullmatch(r'([a-z0-9][a-z0-9_.-]{0,100}):([a-z0-9][a-z0-9_.-]{0,100})', profile['model'])
    if not match or any(p.endswith('.') or PureWindowsPath(p).is_reserved() for p in match.groups()):
        return ()
    model, tag = match.groups()
    if re.fullmatch(r'(?:sha256-)?[a-f0-9]{12,64}', model):
        return ()
    manifest = root / 'manifests-v2' / 'ollama.com' / 'library' / model / tag
    try:
        raw, _ = capture_local(manifest, root, maximum=65536)
        info = json_unique(raw)
        if (not isinstance(info, dict) or info.get('schemaVersion') != 2
                or info.get('mediaType') != 'application/vnd.docker.distribution.manifest.v2+json'):
            return ()
        config = info.get('config')
        if not isinstance(config, dict) or not isinstance(config.get('digest'), str):
            return ()
        sha = re.fullmatch(r'sha256:([a-f0-9]{64})', config['digest'])
        if not sha:
            return ()
        if hashlib.sha256(raw).hexdigest() != profile['model_digest']:
            raise Denied('MODEL_DIGEST_CHANGED')
        blob = root / 'blobs' / ('sha256-' + sha[1])
        _matching_bytes(blob, root, sha[1])
    except Denied as exc:
        if str(exc) == 'MODEL_DIGEST_CHANGED':
            raise
        return ()
    except (OSError, ValueError):
        # An unrecognized or unavailable layout continues with the live catalog.
        return ()
    return ((manifest, profile['model_digest']), (blob, sha[1]))


class OwnedOllama:
    def __init__(self,job_name,profile,log_path):
        self.job=Job(job_name)
        self.profile=profile
        self.port=None
        self.log_path=Path(log_path)
        self.log=None
        self.telemetry=[]
        self._model_files=()
        self._process_lock=threading.Lock()
        self._stop_requested=False
        self.reused = False
        self.resident_before_turn = False

    def resume(self):
        with self._process_lock:
            if self._stop_requested or self.job.active() == 0:
                raise Denied('BACKEND_CANCELLED_BEFORE_START')
            self._assert_owned_listener()
            self.check_model()
            models = local_metadata('/api/ps', self.port).get('models', [])
            self.resident_before_turn = (len(models) == 1 and models[0].get('digest') == self.profile['model_digest']
                                         and models[0].get('context_length') == self.profile['num_ctx'])
            self.telemetry.clear()
            self.reused = True

    def _startup_event(self,stage,**fields):
        if self.log:
            self.log.write((canonical({'stage':stage,'time_ns':time.time_ns(),
                                      'perf_counter_ns':time.perf_counter_ns(),**fields})+'\n').encode('utf-8'))
            self.log.flush()

    def start(self):
        executable=shutil.which('ollama')
        if executable is None: raise Denied('INSTALL_OLLAMA_FIRST')
        with socket.socket() as port_socket:
            port_socket.bind(('127.0.0.1',0))
            self.port=port_socket.getsockname()[1]
        allowed={'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA',
                 'PROGRAMFILES','PROGRAMFILES(X86)','SYSTEMDRIVE','NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE'}
        env={k:v for k,v in os.environ.items() if k.upper() in allowed}
        env.update({'OLLAMA_HOST':f'127.0.0.1:{self.port}','OLLAMA_NO_CLOUD':'1',
                    'OLLAMA_NUM_PARALLEL':'1','OLLAMA_MAX_LOADED_MODELS':'1',
                    'OLLAMA_CONTEXT_LENGTH':'8192','OLLAMA_KEEP_ALIVE':'5m',
                    'OLLAMA_MODELS':os.environ.get('OLLAMA_MODELS',str(Path.home()/'.ollama/models'))})
        if self.profile.get('team_session') == POLISHED_TEAM:
            env['GOMAXPROCS'] = '1'
        self.log_path.parent.mkdir(parents=True,exist_ok=True)
        self.log=self.log_path.open('ab')
        self._startup_event('BOOTSTRAP_SPAWN_BEGIN')
        # A stop closes admission even when no process exists yet. Keep network
        # readiness probes outside this lock so cancellation can interrupt them.
        with self._process_lock:
            if self._stop_requested: raise Denied('BACKEND_CANCELLED_BEFORE_START')
            process=self.job.start([executable,'serve'],env=env,log=self.log)
        self._startup_event('BOOTSTRAP_LAUNCHED',pid=process.pid,port=self.port)
        deadline=time.monotonic()+30
        owner_read_retried=False
        last_error=None; probe=0; phase='metadata'
        while time.monotonic()<deadline:
            if process.poll() is not None:
                self._startup_event('BOOTSTRAP_EXITED',returncode=process.returncode)
                raise Denied('OWNED_BACKEND_START_FAILED')
            try:
                probe+=1; phase='metadata'
                self._startup_event('STARTUP_PROBE_BEGIN',probe=probe,phase=phase)
                version=local_metadata('/api/version',self.port)
                phase='listener_owner'
                self._startup_event('STARTUP_PHASE',probe=probe,phase=phase)
                self._assert_owned_listener()
                phase='model_identity'
                self._startup_event('STARTUP_PHASE',probe=probe,phase=phase)
                self.check_model()
                self._model_root=Path(env['OLLAMA_MODELS'])
                self._model_files=_team_model_files(self._model_root,self.profile,version.get('version'))
                self._startup_event('OWNED_BACKEND_READY',active_processes=self.job.active())
                return
            except (OSError,http.client.HTTPException) as exc:
                last_error=type(exc).__name__
                self._startup_event('STARTUP_RETRY',probe=probe,phase=phase,error_type=last_error)
                time.sleep(.1)
            except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
                owner_timeout=phase=='listener_owner' and isinstance(exc,subprocess.TimeoutExpired)
                if owner_timeout and not owner_read_retried and time.monotonic()<deadline:
                    # Repeat observation of the same managed process before any model call.
                    owner_read_retried=True
                    last_error=type(exc).__name__
                    self._startup_event('STARTUP_RETRY',probe=probe,phase=phase,error_type=last_error)
                    continue
                self._startup_event('STARTUP_SUBPROCESS_FAILED',probe=probe,phase=phase,
                                    error_type=type(exc).__name__,returncode=getattr(exc,'returncode',None))
                if owner_timeout:
                    raise Denied('OWNED_BACKEND_START_TIMEOUT') from exc
                raise
        self._startup_event('START_TIMEOUT',active_processes=self.job.active(),last_error=last_error,phase=phase,probe=probe)
        raise Denied('OWNED_BACKEND_START_TIMEOUT')

    def _assert_owned_listener(self):
        identities=listener_pids(self.port)
        if not identities: raise Denied('BACKEND_LISTENER_OWNER_UNKNOWN')
        dll=self.job.dll
        dll.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]; dll.OpenProcess.restype=wintypes.HANDLE
        dll.IsProcessInJob.argtypes=[wintypes.HANDLE,wintypes.HANDLE,ctypes.POINTER(wintypes.BOOL)]; dll.IsProcessInJob.restype=wintypes.BOOL
        if len(identities)!=1: raise Denied('BACKEND_LISTENER_AMBIGUOUS')
        handle=dll.OpenProcess(0x1000,False,next(iter(identities)))
        if not handle: raise Denied('BACKEND_PROCESS_UNAVAILABLE')
        try:
            belongs=wintypes.BOOL()
            if not dll.IsProcessInJob(handle,self.job.handle,ctypes.byref(belongs)) or not belongs.value:
                raise Denied('BACKEND_NOT_OWNED_BY_OFFICE')
        finally: dll.CloseHandle(handle)

    def check_model(self):
        if self._model_files:
            for path, expected in self._model_files:
                try:
                    _matching_bytes(path, self._model_root, expected)
                except OSError as exc:
                    raise Denied('MODEL_IDENTITY_UNAVAILABLE') from exc
            return
        selected=select_model(self.profile['model'],local_metadata('/api/tags',self.port)['models'])
        if selected['model_digest']!=self.profile['model_digest']: raise Denied('MODEL_DIGEST_CHANGED')

    def infer(self,payload):
        self.check_model()
        self._assert_owned_listener()
        options = inference_options(self.profile)
        if payload['model']!=self.profile['model'] or payload['options']!=options:
            raise Denied('MODEL_PROFILE_MISMATCH')
        data=canonical(payload).encode('utf-8')
        if len(data)>6144: raise Denied('PROMPT_BYTE_BUDGET')
        con=http.client.HTTPConnection('127.0.0.1',self.port,timeout=300)
        try:
            con.request('POST','/api/chat',data,{'Content-Type':'application/json'})
            response=con.getresponse()
            body=response.read(1_048_577)
            if response.status!=200 or len(body)>1_048_576: raise Denied('BACKEND_RESPONSE_REJECTED')
            result=json_unique(body)
            if type(result) is not dict or result.get('done') is not True: raise Denied('BACKEND_COMPLETION_UNPROVEN')
            self.check_model()
            running=local_metadata('/api/ps',self.port).get('models',[])
            rows=[r for r in running if r.get('digest')==self.profile['model_digest']]
            if len(rows)!=1 or type(rows[0].get('size_vram')) is not int or rows[0]['size_vram'] < 0:
                raise Denied('MODEL_ALLOCATION_NOT_OBSERVED')
            if options['num_gpu'] == 0 and rows[0]['size_vram'] != 0: raise Denied('CPU_ALLOCATION_NOT_OBSERVED')
            if rows[0].get('context_length')!=8192: raise Denied('CONTEXT_ALLOCATION_MISMATCH')
            self.telemetry.append({'size_vram':rows[0]['size_vram'],'model_size':rows[0].get('size'),
                'num_gpu_requested':options['num_gpu'],'num_thread_requested':options.get('num_thread'),
                'context_length':rows[0].get('context_length'),
                'prompt_eval_count':result.get('prompt_eval_count'),'eval_count':result.get('eval_count'),
                'total_duration':result.get('total_duration'),'done_reason':result.get('done_reason')})
            result['_neural_office_execution']={**self.telemetry[-1],'model_digest':self.profile['model_digest'],
                                                'model_identity_check':'manifest-and-config' if self._model_files else 'catalog',
                                                'owned_job':True,'mode':'GPU allocation' if rows[0]['size_vram'] else 'CPU'}
            if self.profile.get('team_session') == POLISHED_TEAM:
                result['_neural_office_execution'].update(runtime_instance=self.job.name, reused_runtime=self.reused,
                                                          resident_before_turn=self.resident_before_turn)
            return result
        finally: con.close()

    def request_stop(self):
        with self._process_lock:
            self._stop_requested=True
            # Also terminate the owned bootstrap before it joins the Job.
            self.job.terminate()

    def terminate(self):
        try:
            self.job.terminate()
            if self.job.active()!=0: raise Denied('BACKEND_STILL_ACTIVE')
        finally:
            if self.log: self.log.close(); self.log=None

    def close(self): self.job.close()
