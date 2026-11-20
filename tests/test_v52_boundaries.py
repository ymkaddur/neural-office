"""Adversarial boundaries: real processes, ownership loss and exceptional paths."""
import ctypes
import contextlib
from ctypes import wintypes
import json
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

from neural_office.ledger import Ledger, Denied, MAX_CALLS
from neural_office.runner import run
from neural_office.files import capture_html

HTML=b'<html lang="en"><title>Fixture</title></html>'
PROFILE={'mode':'fixture','model':'fixture','model_digest':'a'*64,'roles':1}


class Boundaries(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.ledger=Ledger(self.root/'state.sqlite3')
        self.ledger.initialize(); self.ledger.register('p',self.root); self.ledger.activate('p')

    def reserve(self):
        return self.ledger.reserve('p','Audit a controlled synthetic document.',HTML,PROFILE,'one')

    def test_processes_share_one_atomic_reservation(self):
        code="""import json,sys,time
from neural_office.ledger import Ledger
while time.time()<float(sys.argv[2]):time.sleep(.01)
print(Ledger(sys.argv[1]).reserve('p','Audit a controlled synthetic document.',
b'<html lang="en"><title>Fixture</title></html>',json.loads(sys.argv[3]),'one'),flush=True)
"""
        start=str(time.time()+1)
        children=[subprocess.Popen([sys.executable,'-B','-c',code,str(self.ledger.path),start,json.dumps(PROFILE)],
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(4)]
        results=[]
        try:
            for child in children:
                stdout,stderr=child.communicate(timeout=15)
                self.assertEqual(child.returncode,0,stderr); results.append(stdout.strip())
            self.assertEqual(len(set(results)),1)
            self.assertEqual(self.ledger.status()['projects'][0]['attempts_consumed'],1)
        finally:
            for child in children:
                if child.poll() is None:child.kill();child.wait()

    def test_call_budget_includes_every_admitted_role(self):
        a=self.reserve();g=self.ledger.acquire(a,'fixture')
        for n in range(MAX_CALLS):
            seq,_=self.ledger.start_call(a,g,str(n),{},str(n))
            self.ledger.finish_call(a,g,seq,{'done':True,'message':{'content':str(n)}})
        with self.assertRaisesRegex(Denied,'CALL_BUDGET'):
            self.ledger.start_call(a,g,'overflow',{},'overflow')

    def test_duplicate_admission_does_not_renew_revoked_authority(self):
        a=self.reserve();self.ledger.revoke('p')
        self.assertEqual(self.ledger.reserve('p','Audit a controlled synthetic document.',HTML,PROFILE,'one',admit=True),a)
        self.assertFalse(self.ledger.status()['projects'][0]['approved'])
        with self.assertRaisesRegex(Denied,'AUTHORITY'):self.ledger.acquire(a,'job')

    @unittest.skipUnless(os.name=='nt','Native CLI file capture')
    def test_cli_terminal_replay_after_exhausting_budget(self):
        from neural_office.__main__ import main
        from test_v52 import FakeBackend
        path=self.root/'input.html';path.write_bytes(HTML)
        args=['--state',str(self.ledger.path),'audit','--project','p','--root',str(self.root),
              '--file',str(path),'--model','fixture','--roles','1']
        def fixture_run(ledger,attempt,roles,progress):return run(ledger,attempt,roles,FakeBackend,progress)
        with patch('neural_office.__main__.local_metadata',return_value={'models':[]}), \
             patch('neural_office.__main__.select_model',return_value=dict(PROFILE)), \
             patch('neural_office.__main__.run',side_effect=fixture_run),contextlib.redirect_stdout(io.StringIO()):
            for key in ('one','two','three'):main(args+['--key',key])
            main(args+['--key','three'])
        status=self.ledger.status()['projects'][0]
        self.assertEqual((status['attempts_consumed'],status['simulated_versions'],status['active']),(3,3,False))

    def test_unconfirmed_termination_keeps_lease(self):
        class Backend:
            def __init__(self,*_):pass
            def start(self):raise RuntimeError('START_FAILED')
            def request_stop(self):pass
            def terminate(self):raise TimeoutError('TERMINATION_UNPROVEN')
            def close(self):pass
        a=self.reserve()
        with self.assertRaisesRegex(RuntimeError,'START_FAILED'):run(self.ledger,a,1,Backend)
        self.assertEqual(self.ledger.attempt(a)['state'],'RECOVERY_REQUIRED')
        self.assertEqual(self.ledger.status()['lease']['attempt'],a)

    def test_cancel_during_inference_stops_before_release(self):
        entered=threading.Event();stopped=threading.Event();observations=[]
        a=self.reserve()
        class Backend:
            def __init__(self,*_):pass
            def start(self):pass
            def infer(self,payload):
                entered.set()
                if not stopped.wait(5):raise RuntimeError('WATCHER_DID_NOT_STOP')
                raise RuntimeError('OWNED_REQUEST_STOPPED')
            def request_stop(inner):
                observations.append(self.ledger.status()['lease']['attempt']);stopped.set()
            def terminate(self):stopped.set()
            def close(self):pass
        result=[]
        worker=threading.Thread(target=lambda:result.append(run(self.ledger,a,1,Backend)))
        worker.start();self.assertTrue(entered.wait(5))
        self.assertEqual(self.ledger.cancel(a),'STOPPING')
        worker.join(10);self.assertFalse(worker.is_alive())
        self.assertEqual(result,['CANCELLED']);self.assertEqual(observations,[a])
        self.assertIsNone(self.ledger.status()['lease']['attempt'])

    def test_malformed_or_oversized_response_cannot_complete(self):
        a=self.reserve();g=self.ledger.acquire(a,'fixture');seq,_=self.ledger.start_call(a,g,'director',{},'one')
        for response in ([],{'done':True,'message':None},{'done':True,'message':{'content':42}},
                         {'done':True,'message':{'content':'x'*1048577}}):
            with self.subTest(response_type=type(response).__name__):
                with self.assertRaises(Denied):self.ledger.finish_call(a,g,seq,response)
        self.assertEqual(self.ledger.attempt(a)['outputs'],[])

    def test_revocation_interrupts_inflight_call(self):
        entered=threading.Event();stopped=threading.Event();result=[]
        a=self.reserve()
        class Backend:
            def __init__(self,*_):pass
            def start(self):pass
            def infer(self,payload):
                entered.set();stopped.wait(3)
                raise RuntimeError('REQUEST_STOPPED')
            def request_stop(self):stopped.set()
            def terminate(self):stopped.set()
            def close(self):pass
        def work():
            try:run(self.ledger,a,1,Backend)
            except RuntimeError as exc:result.append(str(exc))
        worker=threading.Thread(target=work);worker.start()
        self.assertTrue(entered.wait(3));self.ledger.revoke('p')
        try:self.assertTrue(stopped.wait(1),'Revocation did not reach the in-flight backend')
        finally:stopped.set();worker.join(5)
        self.assertFalse(worker.is_alive());self.assertEqual(result,['REQUEST_STOPPED'])
        self.assertEqual(self.ledger.attempt(a)['state'],'FAILED')

    @unittest.skipUnless(os.name=='nt','Windows file sharing')
    def test_capture_denied_while_another_writer_holds_file(self):
        path=self.root/'held.html';path.write_bytes(HTML)
        with path.open('r+b') as writer:
            with self.assertRaises(OSError):capture_html(path,self.root)
        self.assertEqual(capture_html(path,self.root),HTML)


@unittest.skipUnless(os.name=='nt','Windows job ownership')
class OwnerCrash(unittest.TestCase):
    def test_abrupt_owner_exit_terminates_descendants(self):
        from neural_office.windows_job import Job
        name='Local\\NeuralOfficeCrashTest_'+uuid.uuid4().hex
        code="""from neural_office.windows_job import Job
import os,sys,time
j=Job(sys.argv[1]);p=j.start([sys.executable,'-c','import time;time.sleep(60)'])
deadline=time.monotonic()+10
while j.active()<2 and time.monotonic()<deadline:time.sleep(.02)
print(p.pid,j.active(),flush=True)
sys.stdin.readline()
os._exit(0)
"""
        dll=ctypes.WinDLL('kernel32',use_last_error=True)
        dll.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];dll.OpenProcess.restype=wintypes.HANDLE
        dll.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];dll.WaitForSingleObject.restype=wintypes.DWORD
        dll.CloseHandle.argtypes=[wintypes.HANDLE];dll.CloseHandle.restype=wintypes.BOOL
        with tempfile.TemporaryFile(mode='w+t') as ready, subprocess.Popen(
                [sys.executable,'-B','-c',code,name],stdin=subprocess.PIPE,stdout=ready,
                stderr=subprocess.PIPE,text=True) as parent:
            try:
                deadline=time.monotonic()+15
                while not os.fstat(ready.fileno()).st_size and parent.poll() is None and time.monotonic()<deadline:
                    time.sleep(.02)
                ready.seek(0)
                pid,count=map(int,ready.readline().split())
                self.assertGreaterEqual(count,2)
                # Pin this particular process before the owner exits. A process
                # handle cannot keep the Windows job alive.
                handle=dll.OpenProcess(0x00100000,False,pid)  # SYNCHRONIZE
                self.assertTrue(handle)
                try:
                    _,stderr=parent.communicate('\n',timeout=5)
                    self.assertEqual(parent.returncode,0,stderr)
                    self.assertEqual(dll.WaitForSingleObject(handle,5000),0,'Bootstrap did not terminate')
                finally:dll.CloseHandle(handle)
            finally:
                if parent.poll() is None:parent.kill()
        # Opening a job before the owner dies would itself keep that job alive.
        with Job(name,existing=True) as remaining:
            deadline=time.monotonic()+5
            while remaining.active() and time.monotonic()<deadline:time.sleep(.02)
            self.assertEqual(remaining.active(),0)


if __name__=='__main__':unittest.main()
