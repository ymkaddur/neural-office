"""The private pipe stays interruptible even when an unrelated read cannot return."""
import json
import importlib.util
import os
from pathlib import Path
from queue import Empty, Queue
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from neural_office.desktop_service import DesktopService
from neural_office.desktop_stdio import serve
from neural_office.ledger import Denied, Ledger, canonical
from neural_office.windows_job import Job


PROFILE = {'mode': 'fixture', 'model': 'controlled-fixture', 'model_digest': 'a' * 64}
SOURCE = b'<html lang="en"><title>Example</title><img src="x"></html>'


class Pipe:
    """Two real OS pipes and the production frame loop, with an optional lost reply."""
    def __init__(self, service):
        self.outbox = Queue()
        self.arrived = {}
        self.drop_reply = None
        to_server, to_server_writer = os.pipe()
        to_client, to_client_writer = os.pipe()
        self.writer = os.fdopen(to_server_writer, 'wb', buffering=0)
        self.exit_code = None

        def host():
            with os.fdopen(to_server, 'rb') as reader, os.fdopen(to_client_writer, 'wb') as writer:
                self.exit_code = serve(service, reader, writer)

        def drain():
            with os.fdopen(to_client, 'rb') as reader:
                for frame in reader:
                    response = json.loads(frame)
                    if response['id'] != self.drop_reply:
                        self.outbox.put(response)

        self.server = threading.Thread(target=host)
        self.receiver = threading.Thread(target=drain)
        self.server.start()
        self.receiver.start()

    def send(self, key, method, **params):
        raw = canonical({'id': key, 'method': method, 'version': 1, 'params': params})
        self.writer.write(raw.encode() + b'\n')

    def packet(self, key):
        while key not in self.arrived:
            try:
                packet = self.outbox.get(timeout=1.8)
            except Empty:
                raise AssertionError(f'{key} did not arrive while barrier was held') from None
            self.arrived[packet['id']] = packet
        return self.arrived.pop(key)

    def result(self, key):
        packet = self.packet(key)
        if not packet['ok']:
            raise AssertionError(packet['error'])
        return packet['result']

    def close(self):
        self.writer.close()
        self.server.join(15)
        self.receiver.join(2)
        if self.server.is_alive() or self.receiver.is_alive() or self.exit_code != 0:
            raise AssertionError(f'sidecar failed to close ({self.exit_code})')


class ControlTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / 'office.sqlite3'
        self.ledger = Ledger(self.path)
        self.service = DesktopService(self.ledger, model_discovery=lambda: [dict(PROFILE)])
        self.addCleanup(self.service.close)
        self.file = self.root / 'example.html'
        self.file.write_bytes(SOURCE)
        self.source = self.service.host_capture('A', self.file)

    def observe(self):
        con = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=2)
        try:
            return con.execute("""
              SELECT (SELECT count(*) FROM events WHERE kind='CANCELLATION_REQUESTED'),
                     (SELECT count(*) FROM attempts WHERE project='A'),
                     (SELECT count(*) FROM calls JOIN attempts ON attempts.id=calls.attempt WHERE project='A'),
                     (SELECT state FROM attempts WHERE project='A' ORDER BY ordinal DESC LIMIT 1),
                     (SELECT revision FROM continuity_meta WHERE id=1)
            """).fetchone()
        finally:
            con.close()

    def test_free_html_during_held_catalog(self):
        held, release = threading.Event(), threading.Event()

        def slow_catalog():
            held.set()
            if not release.wait(12):
                raise AssertionError('catalogue barrier expired')
            return [dict(PROFILE)]

        self.service.model_discovery = slow_catalog
        pipe = Pipe(self.service)
        self.addCleanup(pipe.close)
        self.addCleanup(release.set)
        pipe.send('models', 'models.list')
        self.assertTrue(held.wait(5))
        pipe.send('check', 'source.check', project_id='A', entry_token=self.source['entry_token'], offset=0)
        self.assertGreater(pipe.result('check')['total'], 0)
        self.assertEqual(self.observe()[:3], (0, 0, 0))
        release.set()
        self.assertEqual(pipe.result('models')['models'][0]['model_digest'], PROFILE['model_digest'])

    def test_free_html_with_exhausted_quota_and_empty_or_offline_catalog(self):
        for key in ('one', 'two', 'three'):
            attempt = self.ledger.reserve('A', 'Inspect this selected document.',
                                          SOURCE, {**PROFILE, 'roles': 1}, key, admit=True)
            self.assertEqual(self.ledger.cancel(attempt), 'CANCELLED')
        before = self.observe()
        self.assertEqual(before[:3], (3, 3, 0))
        pipe = Pipe(self.service)
        self.addCleanup(pipe.close)
        for key, catalog in [('empty', []), ('offline', Denied('MODEL_METADATA_UNAVAILABLE'))]:
            with self.subTest(key=key), patch.object(self.service, 'model_discovery') as discovery:
                if isinstance(catalog, Exception):
                    discovery.side_effect = catalog
                else:
                    discovery.return_value = catalog
                pipe.send('model-' + key, 'models.list')
                outcome = pipe.packet('model-' + key)
                if outcome['ok']:
                    self.assertEqual((key, outcome['result']['models']), ('empty', []))
                else:
                    self.assertEqual((key, outcome['error']['code']), ('offline', 'MODEL_METADATA_UNAVAILABLE'))
                pipe.send(key, 'source.check', project_id='A', entry_token=self.source['entry_token'], offset=0)
                self.assertGreater(pipe.result(key)['total'], 0)
                self.assertEqual(self.observe(), before)

    def test_stop_during_pdf_and_zip_reader_in_another_project(self):
        from examples.multiformat.build_example import pdf_bytes
        from neural_office.attachments import _send_input

        folder = self.root / 'B'
        folder.mkdir()
        pdf, archive = folder / 'plazo.pdf', folder / 'entrega.zip'
        pdf.write_bytes(pdf_bytes([['Primera respuesta en 24 horas.']]))
        with zipfile.ZipFile(archive, 'w') as writer:
            writer.writestr('manifest.json', '{"hours": 48}')
        pipe = Pipe(self.service)
        self.addCleanup(pipe.close)
        pipe.send('files', 'host.attachments.capture', project_id='B', thread_id='delivery',
                  paths=[str(pdf), str(archive)])
        captured = pipe.result('files')
        for ordinal, item in enumerate(captured, 1):
            with self.subTest(kind=item['kind']):
                held, release = threading.Event(), threading.Event()
                entered, cancelled = threading.Event(), threading.Event()

                class Model:
                    def __init__(self, *args): pass
                    def start(self): pass
                    def infer(self, payload):
                        entered.set()
                        if not cancelled.wait(10): raise AssertionError('model barrier expired')
                        raise Denied('CANCELLED')
                    def request_stop(self): cancelled.set()
                    def terminate(self): pass
                    def close(self): pass

                def hold_input(writer, data):
                    held.set()  # The real isolated decoder exists and is waiting for these bytes.
                    try:
                        if not release.wait(8): raise AssertionError('attachment barrier expired')
                    finally:
                        _send_input(writer, data)

                self.service.backend_factory = Model
                grant = self.service.preview('A', self.source['entry_token'], PROFILE['model_digest'],
                                             1, 'Inspect this selected example file.')
                pipe.send('start', 'attempt.start', approval_token=grant['approval_token'],
                          idempotency_key=item['kind'], expected_revision=grant['expected_revision'])
                active = pipe.result('start')['id']
                try:
                    self.assertTrue(entered.wait(3))
                    with patch('neural_office.attachments._send_input', hold_input):
                        pipe.send('view-b', 'attachments.view', project_id='B', thread_id='delivery',
                                  capture_id=item['id'], page=1, member='')
                        self.assertTrue(held.wait(4))
                        pipe.send('stop-a', 'attempt.cancel', attempt_id=active)
                        self.assertIn(pipe.result('stop-a')['state'], ('STOPPING', 'CANCELLED'))
                        self.service._worker.join(4)
                        self.assertEqual(self.observe()[:4], (ordinal, ordinal, ordinal, 'CANCELLED'))
                        self.assertFalse(release.is_set())
                        release.set()
                        view = pipe.result('view-b')
                    self.assertEqual((view['attachment_id'], view['sha256']), (item['id'], item['sha256']))
                    expected_status = ('unavailable' if item['kind'] == 'pdf' and
                                       importlib.util.find_spec('pypdfium2') is None else 'ok')
                    self.assertEqual(view['status'], expected_status)
                finally:
                    cancelled.set()
                    release.set()

    def test_stop_committed_and_confirmed_before_project_b_read_returns(self):
        history_held, report_held, release = threading.Event(), threading.Event(), threading.Event()
        infer, stopped, terminated = threading.Event(), threading.Event(), threading.Event()
        processes = []
        job_sizes = []

        class Model:
            def __init__(self, name, *_):
                self.job = Job(name)

            def start(self):
                processes.append(self.job.start([sys.executable, '-B', '-c', 'import time; time.sleep(15)']))
                deadline = time.monotonic() + 5
                while self.job.active() < 2:
                    if time.monotonic() > deadline:
                        raise AssertionError('controlled child did not join the Windows Job')
                    time.sleep(.01)
                job_sizes.append(self.job.active())
            def infer(self, payload):
                infer.set()
                if not stopped.wait(12):
                    raise AssertionError('stop barrier expired')
                raise Denied('CANCELLED')
            def request_stop(self): stopped.set()
            def terminate(self):
                if not terminated.wait(12):
                    raise AssertionError('termination barrier expired')
                self.job.terminate()
                job_sizes.append(self.job.active())
            def close(self): self.job.close()

        project_b = self.root / 'B'
        project_b.mkdir()
        other = project_b / 'entrega.html'
        other.write_bytes(SOURCE)
        selected = self.service.host_capture('B', other)
        saved = self.service.preview('B', selected['entry_token'], PROFILE['model_digest'], 1, 'Inspect the archived delivery.')

        class PreviousModel:
            def __init__(self, *args): pass
            def start(self): pass
            def infer(self, _): return {'done': True, 'message': {'content': 'Controlled historical comment.'}}
            def request_stop(self): pass
            def terminate(self): pass
            def close(self): pass

        self.service.backend_factory = PreviousModel
        previous = self.service.start(saved['approval_token'], 'previous', saved['expected_revision'])['id']
        self.service._worker.join(5)
        stored_report = self.service.report_read(previous, 0, 65536)
        self.service.backend_factory = Model
        grant = self.service.preview('A', self.source['entry_token'], PROFILE['model_digest'],
                                     1, 'Inspect this selected example file.')
        start = dict(approval_token=grant['approval_token'], expected_revision=grant['expected_revision'],
                     idempotency_key='one')
        read_b = self.service.project_history
        read_report = self.service.report_read

        def blocked_history(project_id):
            original = read_b(project_id)
            self.assertEqual(project_id, 'B')
            history_held.set()
            if not release.wait(12):
                raise AssertionError('history barrier expired')
            return original

        def blocked_report(attempt_id, offset, limit):
            self.assertEqual(attempt_id, previous)
            actual = read_report(attempt_id, offset, limit)
            report_held.set()
            if not release.wait(12):
                raise AssertionError('report barrier expired')
            return actual

        with patch.object(self.service, 'project_history', blocked_history), patch.object(self.service, 'report_read', blocked_report):
            pipe = Pipe(self.service)
            self.addCleanup(pipe.close)
            for gate in (release, stopped, terminated):
                self.addCleanup(gate.set)
            pipe.send('start', 'attempt.start', **start)
            attempt = pipe.result('start')['id']
            self.assertTrue(infer.wait(5))
            pipe.send('read-b', 'project.history', project_id='B')
            pipe.send('report-b', 'report.read', attempt_id=previous, offset=0, limit=65536)
            self.assertTrue(history_held.wait(5))
            self.assertTrue(report_held.wait(5))
            # Both read workers are occupied. Two queued reads are allowed;
            # further readers receive a bounded refusal and consume no authority.
            for i in range(3):
                pipe.send(f'pressure-{i}', 'events.read', after=0, limit=1)
            self.assertEqual(pipe.packet('pressure-2')['error']['code'], 'HOST_BUSY')
            pipe.drop_reply = 'stop'
            sent = time.perf_counter_ns()
            pipe.send('stop', 'attempt.cancel', attempt_id=attempt)
            stop = self.observe()
            while stop[0] == 0 and (time.perf_counter_ns() - sent) < 1_800_000_000:
                time.sleep(.003)
                stop = self.observe()
            self.receipt_latency_ms = (time.perf_counter_ns() - sent) / 1_000_000
            self.assertEqual(stop[:4], (1, 1, 1, 'STOPPING'))
            # The peer's first ACK is lost. Read the same right to stop from
            # a fresh desktop session on the same durable office.
            new_session = DesktopService(Ledger(self.path))
            reconnected = Pipe(new_session)
            self.addCleanup(reconnected.close)
            reconnected.send('retry-stop', 'attempt.cancel', attempt_id=attempt)
            retry = reconnected.result('retry-stop')
            self.assertEqual((retry['state'], retry['id']), ('STOPPING', attempt))
            self.assertEqual(self.observe(), stop)
            self.assertTrue(stopped.wait(5))
            terminated.set()
            self.service._worker.join(5)
            self.assertEqual(self.observe()[:4], (1, 1, 1, 'CANCELLED'))
            self.assertEqual(job_sizes[-1], 0)
            self.assertGreaterEqual(job_sizes[0], 2)
            self.assertIsNotNone(processes[0].poll())
            self.assertFalse(release.is_set())
            pipe.send('retry-start', 'attempt.start', **start)
            self.assertEqual(pipe.result('retry-start')['id'], attempt)
            self.assertEqual(self.observe()[:4], (1, 1, 1, 'CANCELLED'))
            release.set()
            self.assertEqual(pipe.result('read-b')['project_id'], 'B')
            self.assertEqual(pipe.result('report-b'), stored_report)
            for i in range(2):
                pipe.result(f'pressure-{i}')

    def test_repeated_cancel_has_one_receipt_and_one_revision(self):
        attempt = self.ledger.reserve('A', 'Inspect this controlled example.', SOURCE,
                                      {**PROFILE, 'roles': 1}, 'one', admit=True)
        generation = self.ledger.acquire(attempt, 'test-only-lease')
        self.assertEqual(self.ledger.cancel(attempt), 'STOPPING')
        stop = self.observe()
        self.assertEqual(self.ledger.cancel(attempt), 'STOPPING')
        self.assertEqual(self.observe(), stop)
        self.ledger.release_after_termination(attempt, generation)
        terminal = self.observe()
        self.assertEqual(self.ledger.cancel(attempt), 'CANCELLED')
        self.assertEqual(self.observe(), terminal)

    def test_eof_terminates_reader_blocked_on_input_and_revokes_queued_reader(self):
        from neural_office.attachments import _send_input

        asset = self.root / 'large.json'
        asset.write_text(json.dumps({'text': 'a' * 700_000}), encoding='utf-8')
        item, = self.service.host_attachments_capture('A', 'files', [str(asset)])
        params = dict(project_id='A', thread_id='files', capture_id=item['id'], page=1, member='')
        writing = threading.Event()
        children = []
        system_popen = subprocess.Popen

        def unresponsive_reader(args, **kwargs):
            self.assertEqual(Path(args[3]).name, 'attachment_worker.py')
            child = system_popen([sys.executable, '-B', '-c', 'import time; time.sleep(15)'], **kwargs)
            children.append(child)
            return child

        def write_to_os_pipe(handle, content):
            writing.set()
            _send_input(handle, content)

        with patch('neural_office.attachments.subprocess.Popen', unresponsive_reader), \
             patch('neural_office.attachments._send_input', write_to_os_pipe):
            pipe = Pipe(self.service)
            self.addCleanup(pipe.close)
            pipe.send('running', 'attachments.view', **params)
            self.assertTrue(writing.wait(4))
            pipe.send('other-thread', 'attachments.cancel', project_id='A', thread_id='different')
            self.assertEqual(pipe.result('other-thread'), {'cancelled': 0})
            pipe.send('queued', 'attachments.view', **params)
            self.assertIsNone(children[0].poll())
            pipe.writer.close()
            self.assertEqual(pipe.packet('running')['error']['code'], 'ATTACHMENT_READ_CANCELLED')
            self.assertEqual(pipe.packet('queued')['error']['code'], 'DESKTOP_SESSION_CLOSED')
            self.assertEqual(len(children), 1)
            self.assertIsNotNone(children[0].poll())
            self.assertEqual(self.observe()[:3], (0, 0, 0))


def measure_control(samples=30):
    """Upper bound from sending the stop frame to observing its committed record over SQLite."""
    import hashlib
    import math
    import platform
    import statistics

    root = Path(__file__).resolve().parents[1]
    paths = ('neural_office/desktop_stdio.py', 'neural_office/desktop_service.py', 'neural_office/ledger.py',
             'neural_office/continuity.py', 'neural_office/runner.py', 'neural_office/windows_job.py',
             'tests/test_v513_control.py')

    def fingerprints():
        return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in paths}

    before = fingerprints()
    timings = []
    for _ in range(samples):
        case = ControlTests('test_stop_committed_and_confirmed_before_project_b_read_returns')
        result = unittest.TestResult()
        case.run(result)
        if not result.wasSuccessful():
            raise AssertionError([message for _, message in result.errors + result.failures])
        timings.append(round(case.receipt_latency_ms, 3))
    if fingerprints() != before:
        raise RuntimeError('Source changed during measurement')
    return {
        'version': 'V5.13-Polished', 'python': platform.python_version(), 'windows': platform.version(),
        'architecture': platform.machine(), 'scope': 'Production Python frame loop over two Windows OS pipes, '
        'Windows Job with two controlled processes, local SQLite. The Tauri renderer and Ollama inference are outside this run.',
        'setup': 'Fresh temporary office per run. One accepted report in B and an active model fixture in A. '
        'Read B history and report through two independent held callbacks, queue two observers, refuse a fifth. '
        'Discard the first stop reply and retry after reconnecting; release B only after termination is observed.',
        'measurement': 'Elapsed milliseconds from before client write to first successful independent SQLite read '
        'of CANCELLATION_REQUESTED. Observations poll at a requested 3 ms interval. Includes OS scheduling.',
        'stats': 'Median and nearest-rank p95, all observations included.',
        'samples': len(timings), 'raw_ms': timings,
        'p50_ms': round(statistics.median(timings), 3), 'p95_ms': sorted(timings)[math.ceil(.95*len(timings))-1],
        'max_ms': max(timings), 'design_budget_ms': 300, 'over_budget_ms': [v for v in timings if v > 300],
        'reproduce': 'python -B -m tests.test_v513_control --measure',
        'source_sha256': before,
    }


if __name__ == '__main__':
    if sys.argv[1:] == ['--measure']:
        print(json.dumps(measure_control(), indent=2))
    else:
        unittest.main()
