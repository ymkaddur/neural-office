"""Cancellation must close process admission, including an unassigned bootstrap."""
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

from neural_office.ledger import Ledger
from neural_office.ollama import OwnedOllama
from neural_office.runner import run
from neural_office.windows_job import Job


@unittest.skipUnless(os.name == 'nt', 'Windows owned process lifecycle')
class CancellationAdmission(unittest.TestCase):
    def run_ordering(self, cancel_before_spawn):
        with tempfile.TemporaryDirectory(prefix='neural-office-cancel-') as temp:
            root = Path(temp)
            ready = root/'child-ready'
            ledger = Ledger(root/'state.sqlite3'); ledger.initialize(); ledger.register('p', root)
            profile = {'mode':'fixture', 'model':'synthetic', 'model_digest':'a'*64, 'roles':1}
            attempt = ledger.reserve('p', 'Audit this controlled synthetic source.',
                b'<html lang="en"><title>Fixture</title></html>', profile, 'stable', admit=True)
            reached = threading.Event(); resume = threading.Event(); stopped = threading.Event()
            jobs = []; spawns = []; outcomes = []
            class SyntheticJob(Job):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs); jobs.append(self)
                def start(self, command, env=None, log=None):
                    process = super().start([sys.executable, '-B', '-c',
                        'import pathlib,sys,time;pathlib.Path(sys.argv[1]).write_text("ready");time.sleep(60)',
                        str(ready)], env=env, log=log)
                    deadline = time.monotonic()+5
                    while not ready.exists() and process.poll() is None and time.monotonic()<deadline:
                        time.sleep(.01)
                    if not ready.exists(): raise RuntimeError('FIXTURE_PROCESS_NOT_READY')
                    spawns.append(self.active())
                    return process
            original_event = OwnedOllama._startup_event
            original_stop = OwnedOllama.request_stop
            def event(backend, stage, **fields):
                original_event(backend, stage, **fields)
                target = 'BOOTSTRAP_SPAWN_BEGIN' if cancel_before_spawn else 'BOOTSTRAP_LAUNCHED'
                if stage == target:
                    reached.set()
                    if not resume.wait(10): raise RuntimeError('FIXTURE_GATE_TIMEOUT')
            def stop(backend):
                original_stop(backend); stopped.set()
            def work():
                try: outcomes.append(run(ledger, attempt, 1))
                except BaseException as exc: outcomes.append(exc)
            with patch('neural_office.ollama.Job', SyntheticJob), \
                 patch('neural_office.ollama.shutil.which', return_value=sys.executable), \
                 patch('neural_office.ollama.local_metadata', return_value={}), \
                 patch.object(OwnedOllama, '_assert_owned_listener'), \
                 patch.object(OwnedOllama, 'check_model'), \
                 patch.object(OwnedOllama, '_startup_event', event), \
                 patch.object(OwnedOllama, 'request_stop', stop):
                worker = threading.Thread(target=work); worker.start()
                try:
                    self.assertTrue(reached.wait(5))
                    self.assertEqual(ledger.cancel(attempt), 'STOPPING')
                    self.assertTrue(stopped.wait(5))
                    self.assertTrue(all(job.active() == 0 for job in jobs))
                finally:
                    resume.set(); worker.join(15)
                    if worker.is_alive():
                        for job in jobs: job.terminate()
                        worker.join(5)
                self.assertFalse(worker.is_alive())
            self.assertEqual(outcomes, ['CANCELLED'])
            self.assertIsNone(ledger.status()['lease']['attempt'])
            self.assertEqual(ledger.status()['projects'][0]['attempts_consumed'], 1)
            return spawns

    def test_cancel_before_spawn_prevents_late_process_admission(self):
        self.assertEqual(self.run_ordering(True), [])

    def test_cancel_after_spawn_terminates_owned_descendants(self):
        spawns = self.run_ordering(False)
        self.assertEqual(len(spawns), 1)
        self.assertGreater(spawns[0], 0)

    def test_stop_terminates_bootstrap_not_yet_assigned_to_job(self):
        with tempfile.TemporaryDirectory(prefix='neural-office-bootstrap-') as temp:
            backend = OwnedOllama('Local\\NeuralOfficeStop_'+uuid.uuid4().hex, {}, Path(temp)/'log')
            # This real harmless process stands in for the Popen -> AssignProcessToJobObject window.
            process = subprocess.Popen([sys.executable, '-B', '-c', 'import time;time.sleep(60)'],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW)
            backend.job.process = process
            try:
                self.assertEqual(backend.job.active(), 0)
                backend.request_stop()
                self.assertIsNotNone(process.poll(), 'Unassigned owned bootstrap survives stop')
            finally:
                backend.terminate(); backend.close()


if __name__ == '__main__': unittest.main()
