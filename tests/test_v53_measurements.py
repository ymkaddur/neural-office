"""Measurement errors must not become zero-cost claims or alter authority."""
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from neural_office.diagnostics import aggregate, benchmark, new_output, safe_error, startup_trial
from neural_office.ledger import Denied
from neural_office.measurements import generation_metrics, JobSampler, job_sample
from neural_office.windows_job import Job
from test_v52 import PROFILE


class MeasurementBoundaries(unittest.TestCase):
    def test_missing_invalid_and_zero_duration_are_unknown(self):
        for value in (None, True, '10', -1, 1.5, float('nan'), float('inf'), 10**1000):
            result = generation_metrics({'eval_count': value, 'eval_duration': 10})
            self.assertIsNone(result['eval_count'])
            self.assertIsNone(result['generated_tokens_per_second'])
        self.assertIsNone(generation_metrics({'eval_count': 10, 'eval_duration': 0})['generated_tokens_per_second'])
        self.assertEqual(generation_metrics({'eval_count': 10, 'eval_duration': 2_000_000_000})['generated_tokens_per_second'], 5)
        self.assertIsNone(generation_metrics({})['first_token_ms'])

    def test_existing_workspace_is_never_reused(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / 'keep'; marker.write_text('retained', encoding='utf-8')
            with self.assertRaises(FileExistsError): new_output(root)
            self.assertEqual(marker.read_text(), 'retained')

    def test_legacy_ancestor_is_denied_before_creating_benchmark_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'studio').mkdir()
            (root / 'studio' / 'studio-v1.sqlite3').write_bytes(b'identity marker')
            target = root / 'nested' / 'experiment'
            with self.assertRaisesRegex(Denied, 'NON_LEGACY_DIRECTORY'):
                benchmark(target, PROFILE, 1, [1])
            self.assertFalse(target.exists())

    def test_private_error_messages_are_not_exported(self):
        self.assertEqual(safe_error(ValueError('C:/Users/private/token=abc')),
                         {'type': 'ValueError', 'code': None})
        self.assertEqual(safe_error(Denied('OWNED_BACKEND_START_TIMEOUT'))['code'], 'OWNED_BACKEND_START_TIMEOUT')
        self.assertIsNone(safe_error(ValueError('PRIVATE_SECRET_123'))['code'])

    def test_failed_observations_stay_unknown(self):
        def denied(_): raise PermissionError('private detail')
        sampler = JobSampler(None, reader=denied)
        sampler.start(); result = sampler.stop()
        self.assertFalse(result['complete'])
        self.assertIsNone(result['sampled_peak_working_set_sum_bytes'])
        self.assertIsNone(result['cpu_seconds'])
        self.assertNotIn('private detail', json.dumps(result))

    def test_failures_not_excluded_from_acceptance_count(self):
        result = aggregate([{'roles': 1, 'state': 'FAILED', 'wall_seconds': 1},
                            {'roles': 1, 'state': 'ACCEPTED', 'wall_seconds': 9}])[0]
        self.assertEqual((result['attempts'], result['accepted'], result['wall_seconds_median']), (2, 1, 9))

    def test_final_counter_failure_does_not_reuse_a_stale_cpu_total(self):
        rows = iter([{'cpu_seconds': 1, 'unreadable_processes': 0}])
        sampler = JobSampler(None, reader=lambda _: next(rows))
        sampler.start(); result = sampler.stop()
        self.assertIsNone(result['cpu_seconds'])
        self.assertFalse(result['complete'])

    def test_startup_failure_still_terminates_and_does_not_infer(self):
        class Failing:
            closed = terminated = False
            def __init__(self, *args): pass
            def start(self): raise TimeoutError('sensitive path')
            def terminate(self): self.terminated = True
            def close(self): self.closed = True
            def receipt(self):
                return {'termination_verified': self.terminated, 'closed': self.closed}
        result = startup_trial(PROFILE, 'unused', Failing)
        self.assertEqual(result['inference_calls'], 0)
        self.assertTrue(result['termination_verified'])
        self.assertTrue(result['closed'])
        self.assertIsNone(result['error']['code'])


@unittest.skipUnless(os.name == 'nt', 'Windows Job measurements')
class WindowsMeasurement(unittest.TestCase):
    def test_reused_pid_outside_job_is_not_measured(self):
        import uuid
        with Job('Local\\NeuralOffice53PidTest_' + uuid.uuid4().hex) as job:
            original = job.dll.QueryInformationJobObject
            def reused_pid(handle, kind, info, size, returned):
                if kind != 3: return original(handle, kind, info, size, returned)
                # Force the enumeration/open race: the PID now identifies our
                # test controller, which is not a member of the measured Job.
                info._obj.assigned = info._obj.count = 1
                info._obj.pids[0] = os.getpid()
                return True
            psapi = Mock()
            with patch.object(job.dll, 'QueryInformationJobObject', side_effect=reused_pid), \
                    patch('neural_office.measurements.ctypes.WinDLL', return_value=psapi):
                result = job_sample(job)
            self.assertEqual(result['unreadable_processes'], 1)
            self.assertIsNone(result['working_set_sum_bytes'])
            psapi.GetProcessMemoryInfo.assert_not_called()

    def test_real_owned_allocation_and_cpu_are_observed(self):
        import uuid
        with Job('Local\\NeuralOffice53Test_' + uuid.uuid4().hex) as job:
            sampler = JobSampler(job, interval=0.05); sampler.start()
            process = job.start([sys.executable, '-B', '-c',
                'import time; a=bytearray(24*1024*1024); end=time.monotonic()+0.7\nwhile time.monotonic()<end: sum(range(10000))'])
            process.wait(timeout=10)
            job.terminate()
            summary = sampler.stop()
            self.assertGreater(summary['cpu_seconds'], 0)
            self.assertGreater(summary['sampled_peak_private_commit_sum_bytes'], 24 * 1024 * 1024)
            self.assertEqual(job_sample(job)['active_processes'], 0)


if __name__ == '__main__': unittest.main()
