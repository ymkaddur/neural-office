"""R13 discriminants. These controlled scenarios are not historical attribution."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from neural_office.ledger import Denied
from neural_office.ollama import OwnedOllama
from test_v52 import PROFILE


class StartupScenarios(unittest.TestCase):
    def scenario(self, metadata=None, owner=None, identity=None, clock=None, poll=None):
        with tempfile.TemporaryDirectory() as tmp, patch('neural_office.ollama.Job') as jobs, \
                patch('neural_office.ollama.shutil.which', return_value='ollama'), \
                patch('neural_office.ollama.local_metadata', side_effect=metadata), \
                patch.object(OwnedOllama, '_assert_owned_listener', side_effect=owner), \
                patch.object(OwnedOllama, 'check_model', side_effect=identity), \
                patch('neural_office.ollama.time.monotonic', side_effect=clock or [0, 0]), \
                patch('neural_office.ollama.time.sleep'):
            jobs.return_value.start.return_value.poll.return_value = None
            if poll is not None:
                jobs.return_value.start.return_value.poll.side_effect = poll
                jobs.return_value.start.return_value.returncode = poll[-1]
            jobs.return_value.start.return_value.pid = 123
            jobs.return_value.active.return_value = 1
            path = Path(tmp) / 'trace.jsonl'; backend = OwnedOllama('synthetic', PROFILE, path)
            error = None
            try: backend.start()
            except Exception as exc: error = exc
            finally:
                if backend.log: backend.log.close()
                backend.close()
            return error, [json.loads(line) for line in path.read_text().splitlines()]

    def test_unavailable_health_reproduces_timeout_in_metadata_phase(self):
        error, events = self.scenario(metadata=ConnectionRefusedError(), clock=[0, 0, 31])
        self.assertIsInstance(error, Denied)
        self.assertEqual(str(error), 'OWNED_BACKEND_START_TIMEOUT')
        self.assertEqual(events[-1]['phase'], 'metadata')

    def test_one_owner_read_timeout_can_recover_on_the_same_bootstrap(self):
        failure = subprocess.TimeoutExpired('synthetic-query', 15)
        error, events = self.scenario(owner=[failure, None], clock=[0, 0, 15, 15])
        self.assertIsNone(error)
        stages = [e['stage'] for e in events]
        self.assertEqual(stages.count('BOOTSTRAP_LAUNCHED'), 1)
        self.assertEqual(stages.count('STARTUP_RETRY'), 1)
        self.assertEqual([e['phase'] for e in events if e['stage']=='STARTUP_PHASE'],
                         ['listener_owner','listener_owner','model_identity'])
        self.assertEqual(stages[-1], 'OWNED_BACKEND_READY')

    def test_owner_timeout_retry_has_a_budget_and_a_deadline(self):
        failure = subprocess.TimeoutExpired('synthetic-query', 15)
        for clock, probes in (([0, 0, 15, 15], 2), ([0, 0, 31], 1)):
            with self.subTest(probes=probes):
                error, events = self.scenario(owner=failure, clock=clock)
                self.assertIsInstance(error, Denied)
                self.assertEqual(str(error), 'OWNED_BACKEND_START_TIMEOUT')
                self.assertIs(error.__cause__, failure)
                self.assertEqual((events[-1]['stage'],events[-1]['phase'],events[-1]['probe']),
                                 ('STARTUP_SUBPROCESS_FAILED','listener_owner',probes))
                self.assertFalse(any(e.get('phase')=='model_identity' for e in events))

    def test_lost_process_or_unowned_listener_cannot_pass_on_retry(self):
        failure = subprocess.TimeoutExpired('synthetic-query', 15)
        for poll,owner,reason in [
            ([None,1],[failure],'OWNED_BACKEND_START_FAILED'),
            ([None,None],[failure,Denied('BACKEND_NOT_OWNED_BY_OFFICE')],'BACKEND_NOT_OWNED_BY_OFFICE'),
        ]:
            with self.subTest(reason=reason):
                error, events = self.scenario(owner=owner, poll=poll, clock=[0,0,15,15])
                self.assertEqual(str(error), reason)
                self.assertFalse(any(e.get('phase')=='model_identity' or e['stage']=='OWNED_BACKEND_READY' for e in events))

    def test_unavailable_model_metadata_reproduces_timeout_later(self):
        error, events = self.scenario(identity=ConnectionRefusedError(), clock=[0, 0, 31])
        self.assertEqual(str(error), 'OWNED_BACKEND_START_TIMEOUT')
        self.assertEqual(events[-1]['phase'], 'model_identity')

    def test_listener_denial_is_not_silently_retried_as_startup_timeout(self):
        error, events = self.scenario(owner=Denied('BACKEND_NOT_OWNED_BY_OFFICE'))
        self.assertEqual(str(error), 'BACKEND_NOT_OWNED_BY_OFFICE')
        self.assertFalse(any(e['stage'] == 'START_TIMEOUT' for e in events))

    def test_retry_window_does_not_claim_a_hard_end_to_end_deadline(self):
        ticks = [0]
        # An admitted operation may complete after the retry-window boundary.
        # Existing code does not recheck the clock before READY. Document it;
        # changing this policy requires a separate contract decision.
        def slow_identity(): ticks[0] = 31
        error, events = self.scenario(clock=lambda: ticks[0], identity=slow_identity)
        self.assertIsNone(error)
        self.assertEqual(ticks[0], 31)
        self.assertEqual(events[-1]['stage'], 'OWNED_BACKEND_READY')


if __name__ == '__main__': unittest.main()
