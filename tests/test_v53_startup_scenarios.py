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
    def scenario(self, metadata=None, owner=None, identity=None, clock=None):
        with tempfile.TemporaryDirectory() as tmp, patch('neural_office.ollama.Job') as jobs, \
                patch('neural_office.ollama.shutil.which', return_value='ollama'), \
                patch('neural_office.ollama.local_metadata', side_effect=metadata), \
                patch.object(OwnedOllama, '_assert_owned_listener', side_effect=owner), \
                patch.object(OwnedOllama, 'check_model', side_effect=identity), \
                patch('neural_office.ollama.time.monotonic', side_effect=clock or [0, 0]), \
                patch('neural_office.ollama.time.sleep'):
            jobs.return_value.start.return_value.poll.return_value = None
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

    def test_owner_subprocess_timeout_has_a_different_signature(self):
        error, events = self.scenario(owner=subprocess.TimeoutExpired('synthetic-query', 15))
        self.assertIsInstance(error, subprocess.TimeoutExpired)
        self.assertFalse(any(e['stage'] == 'START_TIMEOUT' for e in events))
        self.assertEqual(events[-1]['phase'], 'listener_owner')

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
