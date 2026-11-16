"""Regression tests for controller lifetime and interrupted witness enrollment."""
import ctypes
from ctypes import wintypes
from contextvars import Context
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

from neural_office import continuity
from neural_office.continuity import backup, protect, restore, run_guard, witness_path
from neural_office.ledger import Denied, Ledger, canonical, digest
from neural_office.runner import recover, run
from neural_office.windows_job import Job
from test_v52 import FakeBackend, HTML, PROFILE


@unittest.skipUnless(os.name == 'nt', 'Windows controller ownership')
class ControllerLifetime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = Ledger(self.root/'office.sqlite3'); self.ledger.initialize()
        self.ledger.register('p', self.root)

    def reserve(self, key='one'):
        return self.ledger.reserve('p', 'Audit a controlled synthetic document.',
                                   HTML, PROFILE, key, admit=True)

    def test_recovery_and_restore_cannot_cross_live_constructor_window(self):
        old = self.root/'old.sqlite3'; backup(self.ledger, old)
        attempt = self.reserve()
        entered = threading.Event(); resume = threading.Event(); outcomes = []
        ledger = self.ledger
        class Backend(FakeBackend):
            def __init__(self, name, *_):
                super().__init__()
                entered.set()
                if not resume.wait(10): raise RuntimeError('FIXTURE_CONSTRUCTOR_TIMEOUT')
                self.job = Job(name)
            def start(self):
                self.job.start([sys.executable, '-B', '-c', 'import time;time.sleep(20)'])
                deadline = time.monotonic() + 5
                while not self.job.active() and time.monotonic() < deadline: time.sleep(.01)
                if not self.job.active(): raise RuntimeError('FIXTURE_JOB_NOT_STARTED')
            def request_stop(self): self.job.terminate()
            def terminate(self): self.job.terminate()
            def close(self): self.job.close()
        def work():
            try: outcomes.append(run(ledger, attempt, 1, Backend))
            except BaseException as exc: outcomes.append(exc)
        worker = threading.Thread(target=work); worker.start()
        try:
            self.assertTrue(entered.wait(5))
            before = self.ledger.status()
            for action in (lambda: recover(self.ledger, attempt),
                           lambda: restore(self.ledger, old),
                           lambda: run(self.ledger, attempt, 1, FakeBackend)):
                with self.assertRaisesRegex(Denied, 'OFFICE_RUNNER_STILL_ACTIVE'): action()
                self.assertEqual(self.ledger.status(), before)
            # Cancellation remains available on the independent continuity mutex.
            self.assertEqual(self.ledger.cancel(attempt), 'STOPPING')
        finally:
            resume.set(); worker.join(15)
        self.assertFalse(worker.is_alive())
        self.assertEqual(outcomes, ['CANCELLED'])
        self.assertEqual(self.ledger.status()['projects'][0]['attempts_consumed'], 1)
        self.assertIsNone(self.ledger.status()['lease']['attempt'])

    def test_constructor_failure_releases_controller_and_does_not_refund(self):
        attempt = self.reserve()
        def fail(*_): raise RuntimeError('SYNTHETIC_CONSTRUCTOR_FAILURE')
        with self.assertRaisesRegex(RuntimeError, 'SYNTHETIC_CONSTRUCTOR_FAILURE'):
            run(self.ledger, attempt, 1, fail)
        self.assertEqual(self.ledger.attempt(attempt)['state'], 'FAILED')
        self.assertEqual(run(self.ledger, self.reserve('two'), 1, FakeBackend), 'ACCEPTED')
        self.assertEqual(self.ledger.status()['projects'][0]['attempts_consumed'], 2)

    def test_same_thread_reentry_does_not_bypass_nonblocking_ownership(self):
        def enter():
            with run_guard(self.ledger.path): pass
        with run_guard(self.ledger.path):
            with self.assertRaisesRegex(Denied, 'OFFICE_RUNNER_STILL_ACTIVE'):
                enter()
            with self.assertRaisesRegex(Denied, 'OFFICE_RUNNER_STILL_ACTIVE'):
                Context().run(enter)
        with run_guard(self.ledger.path): pass

    def test_terminal_replay_remains_readable_during_other_execution(self):
        completed = self.reserve()
        self.assertEqual(run(self.ledger, completed, 1, FakeBackend), 'ACCEPTED')
        pending = self.reserve('two')
        entered = threading.Event(); resume = threading.Event(); outcomes = []
        class Backend(FakeBackend):
            def start(self):
                entered.set()
                if not resume.wait(10): raise RuntimeError('FIXTURE_START_TIMEOUT')
        def work():
            try: outcomes.append(run(self.ledger, pending, 1, Backend))
            except BaseException as exc: outcomes.append(exc)
        worker = threading.Thread(target=work); worker.start()
        try:
            self.assertTrue(entered.wait(5))
            before = self.ledger.status()
            self.assertEqual(run(self.ledger, completed, 1, FakeBackend), 'ACCEPTED')
            with self.assertRaisesRegex(Denied, 'ROLE_PROFILE_CHANGED'):
                run(self.ledger, completed, 3, FakeBackend)
            self.assertEqual(self.ledger.status(), before)
        finally:
            resume.set(); worker.join(15)
        self.assertFalse(worker.is_alive())
        self.assertEqual(outcomes, ['ACCEPTED'])

    def test_real_process_death_releases_abandoned_controller_mutex(self):
        attempt = self.reserve()
        code = '''import os,sys
from pathlib import Path
from neural_office.continuity import run_guard
from neural_office.ledger import Ledger
with run_guard(sys.argv[1]):
 Ledger(sys.argv[1]).acquire(sys.argv[2],sys.argv[3])
 Path(sys.argv[4]).write_text('READY')
 sys.stdin.readline()
 os._exit(23)
'''
        job_name = 'Local\\NeuralOfficeMissingCrash_' + uuid.uuid4().hex
        ready = self.root/'controller-ready'
        child = subprocess.Popen([sys.executable, '-B', '-c', code, str(self.ledger.path),
                                  attempt, job_name, str(ready)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        retained = None
        dll = ctypes.WinDLL('kernel32', use_last_error=True)
        dll.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        dll.OpenMutexW.restype = wintypes.HANDLE
        dll.CloseHandle.argtypes = [wintypes.HANDLE]; dll.CloseHandle.restype = wintypes.BOOL
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(ready.exists(), 'Controller did not acquire ownership before deadline')
            name = 'Local\\NeuralOfficeRunOwner_' + digest(os.path.normcase(str(self.ledger.path.resolve())))
            retained = dll.OpenMutexW(0x100001, False, name)
            self.assertTrue(retained)
            with self.assertRaisesRegex(Denied, 'OFFICE_RUNNER_STILL_ACTIVE'):
                recover(self.ledger, attempt)
            _, stderr = child.communicate('exit\n', timeout=10)
            self.assertEqual(child.returncode, 23, stderr)
            # The retained handle keeps the abandoned mutex object alive.
            self.assertEqual(recover(self.ledger, attempt), 'FAILED')
            self.assertEqual(self.ledger.status()['projects'][0]['attempts_consumed'], 1)
            self.assertIsNone(self.ledger.status()['lease']['attempt'])
        finally:
            if child.poll() is None: child.kill(); child.communicate(timeout=10)
            if retained: dll.CloseHandle(retained)


@unittest.skipUnless(os.name == 'nt', 'Windows continuity enrollment')
class InterruptedEnrollment(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = Ledger(self.root/'office.sqlite3')
        # A valid schema-1 office with one consumed attempt, before enrollment.
        with patch.object(continuity, 'protect'): self.ledger.initialize()
        con = sqlite3.connect(self.ledger.path)
        try:
            con.execute('INSERT INTO projects(id,root) VALUES(?,?)', ('p', str(self.root)))
            con.execute('''INSERT INTO attempts(id,project,ordinal,request_key,request_digest,
                objective,profile,snapshot,snapshot_sha,state,created,last_seen)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('one','p',1,'one',digest('synthetic'),'A synthetic enrollment fixture.',
                 canonical(PROFILE),HTML,digest(HTML),'CANCELLED',time.time(),time.time()))
            con.commit()
        finally: con.close()

    def assert_consumption_preserved(self):
        status = self.ledger.status()
        self.assertEqual(status['projects'][0]['attempts_consumed'], 1)
        self.assertEqual(self.ledger.attempt('one')['snapshot'], HTML)

    def test_retry_after_first_transaction_rollback_preserves_attempts(self):
        original = continuity.seal
        def fail(con):
            original(con)
            raise OSError('SYNTHETIC_FIRST_COMMIT_FAILURE')
        with patch.object(continuity, 'seal', fail):
            with self.assertRaisesRegex(OSError, 'FIRST_COMMIT_FAILURE'): protect(self.ledger)
        self.assertFalse(protect(self.ledger)['already_protected'])
        self.assert_consumption_preserved()

    def test_real_process_death_with_hot_journals_can_retry_enrollment(self):
        code = '''import os,sys
from neural_office import continuity
from neural_office.ledger import Ledger
original=continuity.seal
def die(con):
 con.execute('PRAGMA main.cache_size=1')
 con.execute('PRAGMA continuity.cache_size=1')
 original(con)
 os._exit(23)
continuity.seal=die
continuity.protect(Ledger(sys.argv[1]))
'''
        result = subprocess.run([sys.executable, '-B', '-c', code, str(self.ledger.path)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 23, result.stderr)
        journals = (Path(str(self.ledger.path)+'-journal'), Path(str(witness_path(self.ledger.path))+'-journal'))
        self.assertTrue(any(p.exists() and p.stat().st_size > 0 for p in journals))
        self.assertFalse(protect(self.ledger)['already_protected'])
        self.assert_consumption_preserved()

    def test_commit_then_exception_is_already_protected_on_retry(self):
        connect = sqlite3.connect
        class AmbiguousCommit(sqlite3.Connection):
            def commit(self):
                super().commit()
                raise OSError('SYNTHETIC_ACKNOWLEDGEMENT_LOST')
        def factory(*args, **kwargs): return connect(*args, **kwargs, factory=AmbiguousCommit)
        with patch.object(continuity.sqlite3, 'connect', side_effect=factory):
            with self.assertRaisesRegex(OSError, 'ACKNOWLEDGEMENT_LOST'): protect(self.ledger)
        retained = witness_path(self.ledger.path).read_bytes()
        self.assertTrue(protect(self.ledger)['already_protected'])
        self.assertEqual(witness_path(self.ledger.path).read_bytes(), retained)
        self.assert_consumption_preserved()

    def test_valid_witness_is_never_reenrolled_over_schema1_copy(self):
        old = self.ledger.path.read_bytes()
        protect(self.ledger)
        retained = witness_path(self.ledger.path).read_bytes()
        self.ledger.path.write_bytes(old)
        with self.assertRaisesRegex(Denied, 'WITNESS_ALREADY_INITIALIZED'): protect(self.ledger)
        self.assertEqual(witness_path(self.ledger.path).read_bytes(), retained)
        self.assertEqual(self.ledger.path.read_bytes(), old)

    def test_empty_witness_cannot_reset_a_schema2_office(self):
        protect(self.ledger)
        witness = witness_path(self.ledger.path)
        witness.rename(self.root/'retained-witness.sqlite3')
        witness.touch()
        primary = self.ledger.path.read_bytes()
        with self.assertRaisesRegex(Denied, 'WITNESS_INVALID'): protect(self.ledger)
        self.assertEqual(self.ledger.path.read_bytes(), primary)
        self.assertEqual(witness.stat().st_size, 0)


if __name__ == '__main__': unittest.main()
