"""Opt-in V5.3 experiments. Fresh synthetic workspaces; no historical state.

The default operation only starts/stops the owned backend. Inference requires
the explicit `benchmark` subcommand and uses the packaged synthetic HTML only.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time
import uuid

from . import __version__
from .ledger import Ledger, Denied, canonical, digest
from .measurements import JobSampler, generation_metrics
from .ollama import OwnedOllama, local_metadata, select_model
from .runner import run


class MeasuredBackend(OwnedOllama):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events, self.calls, self.resource_summary = [], [], None
        self.origin_ns = time.perf_counter_ns()
        self.sampler = JobSampler(self.job)
        self.sample_started = False
        self.cleaned = False

    def event(self, stage, **fields):
        self.events.append({'stage': stage, 'elapsed_ns': time.perf_counter_ns() - self.origin_ns, **fields})

    def _startup_event(self, stage, **fields):
        # PID/port and absolute timestamps remain only in the private native log.
        allowed = {k: v for k, v in fields.items() if k in ('phase', 'probe', 'error_type', 'last_error', 'active_processes', 'returncode')}
        self.event(stage, **allowed)
        super()._startup_event(stage, **fields)

    def _assert_owned_listener(self):
        self.event('OWNER_QUERY_BEGIN')
        try:
            result = super()._assert_owned_listener()
        except Exception as exc:
            self.event('OWNER_QUERY_ERROR', error_type=type(exc).__name__)
            raise
        self.event('OWNER_QUERY_END')
        return result

    def check_model(self):
        self.event('MODEL_IDENTITY_BEGIN')
        try:
            result = super().check_model()
        except Exception as exc:
            self.event('MODEL_IDENTITY_ERROR', error_type=type(exc).__name__)
            raise
        self.event('MODEL_IDENTITY_END')
        return result

    def start(self):
        self.sampler.start(); self.sample_started = True
        self.event('START_BEGIN')
        try:
            super().start()
        except Exception as exc:
            self.event('START_ERROR', error_type=type(exc).__name__)
            raise
        self.event('START_END')

    def infer(self, payload):
        started = time.perf_counter_ns()
        self.event('CALL_BEGIN', ordinal=len(self.calls) + 1)
        response = super().infer(payload)
        execution = response.get('_neural_office_execution', {})
        self.calls.append({
            'ordinal': len(self.calls) + 1,
            'wall_seconds': (time.perf_counter_ns() - started) / 1e9,
            'request_sha256': digest(canonical(payload)),
            'model_allocated_vram_bytes': execution.get('size_vram'),
            'context_length': execution.get('context_length'),
            **generation_metrics(response),
        })
        self.event('CALL_END', ordinal=len(self.calls))
        return response

    def terminate(self):
        self.event('TERMINATE_BEGIN')
        try:
            super().terminate()
            self.cleaned = self.job.active() == 0
            self.event('TERMINATE_END', active_processes=self.job.active())
        finally:
            if self.sample_started:
                self.resource_summary = self.sampler.stop()
                self.sample_started = False

    def receipt(self):
        return {'events': self.events, 'calls': self.calls, 'resources': self.resource_summary,
                'termination_verified': self.cleaned}


def safe_error(exc):
    # Exception messages may contain private paths, responses or hostnames.
    reason = str(exc)
    codes = {'OWNED_BACKEND_START_TIMEOUT', 'OWNED_BACKEND_START_FAILED',
             'BACKEND_STILL_ACTIVE', 'BENCHMARK_REQUIRES_NON_LEGACY_DIRECTORY',
             'REPEATS_MUST_BE_1_TO_3', 'ROLE_PROFILES_INVALID', 'LOCAL_MODEL_NOT_FOUND',
             'CLOUD_MODEL_EXCLUDED', 'INSTALL_OLLAMA_FIRST', 'METADATA_UNAVAILABLE',
             'BACKEND_NOT_OWNED_BY_OFFICE', 'MODEL_DIGEST_CHANGED',
             'SAMPLER_TERMINATION_UNCONFIRMED'}
    return {'type': type(exc).__name__,
            'code': reason if reason in codes else None}


def new_output(path):
    root = Path(path).resolve()
    root.mkdir(parents=True, exist_ok=False)
    return root


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as out:
        json.dump(value, out, indent=2, ensure_ascii=False, allow_nan=False)
        out.write('\n')


def environment(profile):
    return {
        'app_version': __version__, 'python': platform.python_version(), 'system': platform.system(),
        'runtime_version': local_metadata('/api/version').get('version'),
        'model_digest': profile['model_digest'],
        'profile': {k: profile[k] for k in ('num_ctx', 'num_predict', 'num_gpu', 'timeout_seconds')},
        'backend_source_sha256': hashlib.sha256(Path(__file__).with_name('ollama.py').read_bytes()).hexdigest(),
        'runner_source_sha256': hashlib.sha256(Path(__file__).with_name('runner.py').read_bytes()).hexdigest(),
        'diagnostics_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'measurements_source_sha256': hashlib.sha256(Path(__file__).with_name('measurements.py').read_bytes()).hexdigest(),
        'clock': 'perf_counter_ns_relative',
    }


def startup_trial(profile, log_path, factory=MeasuredBackend):
    backend = factory('Local\\NeuralOffice53Probe_' + uuid.uuid4().hex, profile, log_path)
    error = cleanup_error = None
    started = time.perf_counter_ns()
    try:
        backend.start()
    except Exception as exc:
        error = safe_error(exc)
    finally:
        try:
            backend.terminate()
        except Exception as exc:
            cleanup_error = safe_error(exc)
        finally:
            backend.close()
    return {'wall_seconds': (time.perf_counter_ns() - started) / 1e9,
            'error': error, 'cleanup_error': cleanup_error, 'inference_calls': 0, **backend.receipt()}


def measured_attempt(ledger, profile, project, snapshot, key, factory=MeasuredBackend):
    roles = profile['roles']
    attempt = ledger.reserve(project, 'Audit the packaged synthetic HTML for the V5.3 measurement.', snapshot, profile, key, admit=True)
    instances = []
    def create(*args):
        backend = factory(*args); instances.append(backend); return backend
    started = time.perf_counter_ns(); error = None
    try:
        run(ledger, attempt, roles, backend_factory=create)
    except Exception as exc:
        error = safe_error(exc)
    row = ledger.attempt(attempt)
    return {
        'roles': roles, 'wall_seconds': (time.perf_counter_ns() - started) / 1e9,
        'state': row['state'], 'error': error,
        'artifact_sha256': digest(bytes(row['artifact'])) if row['artifact'] else None,
        'verdict': json.loads(row['verdict']) if row['verdict'] else None,
        'backend': instances[0].receipt() if instances else None,
    }


def aggregate(trials):
    result = []
    for roles in sorted({trial['roles'] for trial in trials}):
        rows = [t for t in trials if t['roles'] == roles]
        values = [t['wall_seconds'] for t in rows if t['state'] == 'ACCEPTED']
        result.append({'roles': roles, 'attempts': len(rows), 'accepted': len(values),
            'wall_seconds_min': min(values) if values else None,
            'wall_seconds_median': statistics.median(values) if values else None,
            'wall_seconds_max': max(values) if values else None})
    return result


def benchmark(root, profile, repeats, role_counts):
    if type(repeats) is not int or not 1 <= repeats <= 3:
        raise ValueError('REPEATS_MUST_BE_1_TO_3')
    if not role_counts or len(set(role_counts)) != len(role_counts) or any(type(n) is not int or n not in (1, 3, 7) for n in role_counts):
        raise ValueError('ROLE_PROFILES_INVALID')
    from .legacy import PATHS
    target = Path(root).resolve()
    if any((parent / PATHS['v1']).is_file() for parent in (target, *target.parents)):
        raise Denied('BENCHMARK_REQUIRES_NON_LEGACY_DIRECTORY')
    root = new_output(root)
    fixture = Path(__file__).resolve().parents[1] / 'examples' / 'audit-sample.html'
    snapshot = fixture.read_bytes()
    ledger = Ledger(root / 'benchmark.sqlite3'); ledger.initialize()
    trials = []
    for roles in role_counts:
        project = 'synthetic-roles-' + str(roles)
        project_root = root / project; project_root.mkdir()
        (project_root / 'audit-sample.html').write_bytes(snapshot)
        ledger.register(project, project_root)
        for repetition in range(repeats):
            result = measured_attempt(ledger, {**profile, 'roles': roles}, project, snapshot, str(repetition))
            result['repetition'] = repetition + 1
            trials.append(result)
            write_json(root / f'trial-{roles}-{repetition + 1}.json', result)
            print(canonical({'roles': roles, 'repetition': repetition + 1, 'state': result['state'],
                             'wall_seconds': result['wall_seconds']}), flush=True)
            if result['error'] or result['state'] != 'ACCEPTED' or not result['backend'] or not result['backend']['termination_verified']:
                return trials, 'stopped_after_unsuccessful_attempt'
        ledger.park(project)
    return trials, 'completed'


def main(argv=None):
    parser = argparse.ArgumentParser(description='V5.3 isolated measurements; never uses the default office ledger.')
    commands = parser.add_subparsers(dest='action', required=True)
    for name in ('startup', 'benchmark'):
        command = commands.add_parser(name)
        command.add_argument('--model', required=True)
        command.add_argument('--output', required=True, help='New private directory; existing paths are rejected')
        if name == 'startup':
            command.add_argument('--trials', type=int, choices=range(1, 13), default=3)
        else:
            command.add_argument('--repeats', type=int, choices=range(1, 4), default=2)
            command.add_argument('--roles', type=int, choices=(1, 3, 7), nargs='+', default=[1, 3, 7])
    args = parser.parse_args(argv)
    profile = select_model(args.model, local_metadata()['models'])
    header = {'schema': 'neural-office.measurement.v1', 'kind': args.action,
              'created_at_utc': datetime.now(timezone.utc).isoformat(), 'environment': environment(profile),
              'scope': 'owned CPU backend; synthetic tasks only; advisory quality not graded',
              'cache_control': 'new backend each attempt; filesystem cache and other apps uncontrolled',
              'ui_memory_included': False, 'power_and_temperature_measured': False}
    if args.action == 'startup':
        root = new_output(args.output); trials = []; status = 'completed'
        for number in range(args.trials):
            trial = startup_trial(profile, root / f'startup-{number + 1}.log')
            trials.append(trial); write_json(root / f'trial-{number + 1}.json', trial)
            print(canonical({'trial': number + 1, 'wall_seconds': trial['wall_seconds'],
                'error': trial['error'], 'termination_verified': trial['termination_verified']}), flush=True)
            if trial['error'] or trial['cleanup_error'] or not trial['termination_verified']:
                status = 'stopped_after_unsuccessful_trial'; break
        report = {**header, 'status': status, 'trials': trials}
    else:
        root = Path(args.output).resolve()
        trials, status = benchmark(root, profile, args.repeats, args.roles)
        report = {**header, 'status': status, 'trials': trials, 'comparison': aggregate(trials)}
    write_json(root / 'summary.json', report)
    return 0 if status == 'completed' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Denied, OSError, ValueError, RuntimeError) as exc:
        print(canonical({'error': safe_error(exc)}), file=sys.stderr)
        raise SystemExit(2)
