"""A dedicated, owned Ollama process tree; the user's existing service is untouched."""
import ctypes
from ctypes import wintypes
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time

from .ledger import Denied, canonical
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


class OwnedOllama:
    def __init__(self,job_name,profile,log_path):
        self.job=Job(job_name)
        self.profile=profile
        self.port=None
        self.log_path=Path(log_path)
        self.log=None
        self.telemetry=[]
        self._process_lock=threading.Lock()
        self._stop_requested=False

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
        last_error=None; probe=0; phase='metadata'
        while time.monotonic()<deadline:
            if process.poll() is not None:
                self._startup_event('BOOTSTRAP_EXITED',returncode=process.returncode)
                raise Denied('OWNED_BACKEND_START_FAILED')
            try:
                probe+=1; phase='metadata'
                self._startup_event('STARTUP_PROBE_BEGIN',probe=probe,phase=phase)
                local_metadata('/api/version',self.port)
                phase='listener_owner'
                self._startup_event('STARTUP_PHASE',probe=probe,phase=phase)
                self._assert_owned_listener()
                phase='model_identity'
                self._startup_event('STARTUP_PHASE',probe=probe,phase=phase)
                self.check_model()
                self._startup_event('OWNED_BACKEND_READY',active_processes=self.job.active())
                return
            except (OSError,http.client.HTTPException) as exc:
                last_error=type(exc).__name__
                self._startup_event('STARTUP_RETRY',probe=probe,phase=phase,error_type=last_error)
                time.sleep(.1)
            except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
                self._startup_event('STARTUP_SUBPROCESS_FAILED',probe=probe,phase=phase,
                                    error_type=type(exc).__name__,returncode=getattr(exc,'returncode',None))
                raise
        self._startup_event('START_TIMEOUT',active_processes=self.job.active(),last_error=last_error,phase=phase,probe=probe)
        raise Denied('OWNED_BACKEND_START_TIMEOUT')

    def _assert_owned_listener(self):
        shell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        command=f"@(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort {int(self.port)} -State Listen -ErrorAction Stop | Select-Object -ExpandProperty OwningProcess -Unique) | ConvertTo-Json -Compress"
        result=subprocess.run([str(shell),'-NoProfile','-NonInteractive','-Command',command],
                              capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode: raise Denied('BACKEND_LISTENER_OWNER_UNKNOWN')
        identities=json.loads(result.stdout)
        identities=identities if isinstance(identities,list) else [identities]
        dll=self.job.dll
        dll.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]; dll.OpenProcess.restype=wintypes.HANDLE
        dll.IsProcessInJob.argtypes=[wintypes.HANDLE,wintypes.HANDLE,ctypes.POINTER(wintypes.BOOL)]; dll.IsProcessInJob.restype=wintypes.BOOL
        if len(identities)!=1: raise Denied('BACKEND_LISTENER_AMBIGUOUS')
        handle=dll.OpenProcess(0x1000,False,identities[0])
        if not handle: raise Denied('BACKEND_PROCESS_UNAVAILABLE')
        try:
            belongs=wintypes.BOOL()
            if not dll.IsProcessInJob(handle,self.job.handle,ctypes.byref(belongs)) or not belongs.value:
                raise Denied('BACKEND_NOT_OWNED_BY_OFFICE')
        finally: dll.CloseHandle(handle)

    def check_model(self):
        selected=select_model(self.profile['model'],local_metadata('/api/tags',self.port)['models'])
        if selected['model_digest']!=self.profile['model_digest']: raise Denied('MODEL_DIGEST_CHANGED')

    def infer(self,payload):
        self.check_model()
        self._assert_owned_listener()
        if payload['model']!=self.profile['model'] or payload['options']!={
                'num_ctx':8192,'num_predict':128,'num_gpu':0,'temperature':0}:
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
            if len(rows)!=1 or rows[0].get('size_vram')!=0: raise Denied('CPU_ALLOCATION_NOT_OBSERVED')
            if rows[0].get('context_length')!=8192: raise Denied('CONTEXT_ALLOCATION_MISMATCH')
            self.telemetry.append({'size_vram':rows[0]['size_vram'],'context_length':rows[0].get('context_length'),
                'prompt_eval_count':result.get('prompt_eval_count'),'eval_count':result.get('eval_count'),
                'total_duration':result.get('total_duration'),'done_reason':result.get('done_reason')})
            result['_neural_office_execution']={**self.telemetry[-1],'model_digest':self.profile['model_digest'],
                                                'owned_job':True,'mode':'CPU'}
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
