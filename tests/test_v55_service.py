import base64
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from neural_office.desktop_contract import MAX_MESSAGE_BYTES, decode_command
from neural_office.desktop_service import DesktopService, discover_models
from neural_office.desktop_stdio import respond, serve
from neural_office.ledger import Denied, Ledger, canonical, digest

SOURCE = b'<html><title>Example</title><img src="x"></html>'
PROFILE = {'mode': 'fixture', 'model': 'explicit-test-fixture', 'model_digest': 'a'*64}


class FixtureBackend:
    calls = 0

    def __init__(self, *args): self.stopped = False
    def start(self): pass
    def infer(self, payload):
        type(self).calls += 1
        return {'done': True, 'message': {'content': 'Synthetic test commentary, not real model inference.'}}
    def request_stop(self): self.stopped = True
    def terminate(self): self.stopped = True
    def close(self): pass


class BlockingBackend(FixtureBackend):
    entered = threading.Event()
    released = threading.Event()

    def infer(self, payload):
        type(self).entered.set()
        if not type(self).released.wait(5): raise RuntimeError('FIXTURE_TIMEOUT')
        return super().infer(payload)
    def request_stop(self):
        super().request_stop()
        type(self).released.set()


class DesktopServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / 'example.html'
        self.file.write_bytes(SOURCE)
        self.clock = [100.0]
        FixtureBackend.calls = 0
        BlockingBackend.entered.clear()
        BlockingBackend.released.clear()
        self.ledger = Ledger(self.root / 'office.sqlite3')
        self.service = self.new_service()

    def new_service(self, **kwargs):
        service = DesktopService(self.ledger, backend_factory=kwargs.get('backend_factory', FixtureBackend),
                                 model_discovery=lambda: [dict(PROFILE)], clock=lambda: self.clock[0])
        self.addCleanup(service.close)
        return service

    def command(self, method, params=None, service=None):
        return (service or self.service).dispatch(canonical({'version': 1, 'id': 'test-request',
                                                            'method': method, 'params': params or {}}).encode())

    def test_office_identity_survives_restart_and_separates_ledgers(self):
        original = self.command('describe')
        reopened = self.command('describe', service=self.new_service())
        self.assertEqual(original['office_id'], reopened['office_id'])
        self.assertNotEqual(original['session_id'], reopened['session_id'])
        separate = DesktopService(Ledger(self.root / 'separate.sqlite3'))
        self.addCleanup(separate.close)
        self.assertNotEqual(original['office_id'], self.command('describe', service=separate)['office_id'])
        self.assertEqual(original['office_id'], self.service.snapshot()['office_id'])

    def preview(self, service=None, objective='Audit the explicitly selected test source.', project='example'):
        service = service or self.service
        source = service.host_capture(project, self.file)
        return service.preview(project, source['entry_token'], PROFILE['model_digest'], 1, objective)

    def start(self, preview, key='one', service=None):
        return (service or self.service).start(preview['approval_token'], key, preview['expected_revision'])

    def finish(self, service=None):
        service = service or self.service
        service._worker.join(5)
        self.assertFalse(service._worker.is_alive())

    def test_frozen_source_and_complete_fixture_path(self):
        preview = self.preview()
        self.file.write_bytes(b'<html lang="es"><title>Changed</title></html>')
        result = self.start(preview)
        self.finish()
        row = self.service.attempt(result['id'])
        self.assertEqual(row['state'], 'ACCEPTED')
        self.assertEqual(row['source_sha256'], digest(SOURCE))
        self.assertEqual(row['mode'], 'fixture')
        self.assertEqual(self.ledger.attempt(row['id'])['snapshot'], SOURCE)
        self.assertEqual(self.service.snapshot()['projects'][0]['simulated_versions'], 1)
        self.assertEqual(self.service.snapshot()['projects'][0]['verified_versions'], 0)

    def test_oversized_first_prompt_is_denied_before_approval_or_reservation(self):
        grant = self.service.host_capture('example', self.file)
        objective = '🙂' * 1800
        with self.assertRaisesRegex(Denied, 'PROMPT_BYTE_BUDGET'):
            self.service.preview('example', grant['entry_token'], PROFILE['model_digest'], 1, objective)
        before = self.service.snapshot()
        with self.assertRaisesRegex(Denied, 'PROMPT_BYTE_BUDGET'):
            self.ledger.reserve('example', objective, SOURCE, {**PROFILE, 'roles': 1}, 'first', admit=True)
        self.assertEqual(self.service.snapshot(), before)

    def test_preview_never_consumes_an_attempt(self):
        preview = self.preview()
        self.assertEqual(preview['attempts_consumed'], 0)
        self.assertEqual(self.service.snapshot()['attempts'], [])

    def test_review_only_releases_accepted_deliveries(self):
        from neural_office.audit import make_report
        self.service.host_capture('example', self.file)
        attempt = self.ledger.reserve('example', 'Review the selected source.', SOURCE,
                                      {**PROFILE, 'roles': 1}, 'incomplete', admit=True)
        generation = self.ledger.acquire(attempt, 'fixture')
        self.ledger.release_after_termination(attempt, generation)
        artifact = make_report(SOURCE, [])
        self.assertEqual(self.ledger.finalize(attempt, artifact), 'REJECTED')
        self.assertEqual(bytes(self.ledger.attempt(attempt)['artifact']), artifact)
        self.assertFalse(self.service.attempt(attempt)['report_available'])
        from neural_office.__main__ import main
        with self.assertRaisesRegex(Denied, 'REPORT_NOT_ACCEPTED'):
            main(['--state', str(self.ledger.path), 'report', attempt])
        for method, params in [('report.get', {}), ('report.read', {'offset': 0, 'limit': 128})]:
            with self.assertRaisesRegex(Denied, 'REPORT_NOT_ACCEPTED'):
                self.command(method, {'attempt_id': attempt, **params})

    def test_static_inspection_is_bound_to_the_capture_and_has_no_attempt_cost(self):
        source = self.service.host_capture('example', self.file)
        self.file.write_bytes(b'<html lang="en"><title>Different file</title></html>')
        params = {'project_id': 'example', 'entry_token': source['entry_token'], 'offset': 0}
        before = self.service.snapshot()
        with patch.object(self.service, 'models', side_effect=AssertionError('Unexpected catalog access')):
            first = self.command('source.check', params)
            self.assertEqual(first, self.command('source.check', params))
        self.assertEqual(first['source_sha256'], digest(SOURCE))
        self.assertEqual(first['session_id'], source['session_id'])
        self.assertEqual(first['total'], 2)
        self.assertEqual(set(first), {'session_id','project_id','source_sha256','offset','findings','total'})
        self.assertEqual(self.service.snapshot(), before)
        for changed in ({'project_id': 'different'}, {'entry_token': 'expired'}):
            with self.assertRaisesRegex(Denied, 'SOURCE_GRANT_INVALID_OR_EXPIRED'):
                self.command('source.check', {**params, **changed})
        self.clock[0] += 120
        with self.assertRaisesRegex(Denied, 'SOURCE_GRANT_INVALID_OR_EXPIRED'):
            self.command('source.check', params)

    def test_static_overview_and_model_admission_at_finding_limit(self):
        for count in (0, 1, 23, 24, 25):
            with self.subTest(count=count):
                content = b'<html lang="es"><title>T</title>' + b'<img>' * count + b'</html>'
                self.file.write_bytes(content)
                grant = self.service.host_capture('example', self.file)
                params = {'project_id':'example', 'entry_token':grant['entry_token'], 'offset':0}
                view = self.command('source.check', params)
                self.assertEqual((view['total'], len(view['findings'])), (count, min(24, count)))
                args = ('example', grant['entry_token'], PROFILE['model_digest'], 1, 'Review the frozen input.')
                if count <= 24:
                    self.service.preview(*args)
                else:
                    page = self.command('source.check', {**params, 'offset': 24})
                    self.assertEqual((page['offset'], page['total'], len(page['findings'])), (24, 25, 1))
                    with self.assertRaisesRegex(Denied, 'FINDING_OFFSET_RANGE'):
                        self.command('source.check', {**params, 'offset': 25})
                    with self.assertRaisesRegex(Denied, 'PILOT_FINDINGS_LIMIT'):
                        self.service.preview(*args)
                    with self.assertRaisesRegex(Denied, 'PILOT_FINDINGS_LIMIT'):
                        self.ledger.reserve('example', args[-1], content, {**PROFILE, 'roles': 1}, 'large', admit=True)
                self.assertEqual(self.service.snapshot()['attempts'], [])

    def test_duplicate_start_returns_same_identity_without_new_call_or_revision(self):
        preview = self.preview()
        first = self.start(preview)
        self.finish()
        revision = self.service.snapshot()['revision']
        second = self.start(preview)
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(FixtureBackend.calls, 1)
        self.assertEqual(self.service.snapshot()['revision'], revision)
        self.assertEqual(self.service.snapshot()['projects'][0]['attempts_consumed'], 1)

    def test_approval_cannot_be_reused_for_another_key(self):
        preview = self.preview()
        self.start(preview)
        self.finish()
        with self.assertRaisesRegex(Denied, 'APPROVAL_ALREADY_USED'):
            self.start(preview, key='another')

    def test_changed_content_conflicts_with_old_durable_key(self):
        self.start(self.preview())
        self.finish()
        another = self.preview(objective='A materially different objective for this source.')
        with self.assertRaisesRegex(Denied, 'IDEMPOTENCY_CONFLICT'):
            self.start(another)
        self.assertEqual(self.service.snapshot()['projects'][0]['attempts_consumed'], 1)

    def test_expiry_at_exact_ttl_denies_without_consumption(self):
        preview = self.preview()
        self.clock[0] += 120
        with self.assertRaisesRegex(Denied, 'APPROVAL_INVALID_OR_EXPIRED'):
            self.start(preview)
        self.assertEqual(self.service.snapshot()['attempts'], [])

    def test_source_expiry_during_discovery_cannot_mint_new_approval(self):
        source = self.service.host_capture('example', self.file)
        def slow_discovery():
            self.clock[0] += 121
            return [dict(PROFILE)]
        self.service.model_discovery = slow_discovery
        with self.assertRaisesRegex(Denied, 'SOURCE_GRANT_INVALID_OR_EXPIRED'):
            self.service.preview('example', source['entry_token'], PROFILE['model_digest'], 1,
                                 'Audit this explicitly selected test source.')
        self.assertEqual(self.service._approvals, {})

    def test_source_grant_is_project_and_session_bound(self):
        source = self.service.host_capture('example', self.file)
        for service, project in ((self.service, 'other'), (self.new_service(), 'example')):
            with self.assertRaisesRegex(Denied, 'SOURCE_GRANT_INVALID_OR_EXPIRED'):
                service.preview(project, source['entry_token'], PROFILE['model_digest'], 1, 'Audit this explicit source.')

    def test_same_root_cannot_be_renamed_into_fresh_project_budget(self):
        self.service.host_capture('example', self.file)
        with self.assertRaisesRegex(Denied, 'PROJECT_ROOT_ALREADY_REGISTERED'):
            self.service.host_capture('renamed-project', self.file)
        self.assertEqual(len(self.service.snapshot()['projects']), 1)

    def test_approval_cannot_cross_session(self):
        preview = self.preview()
        with self.assertRaisesRegex(Denied, 'APPROVAL_INVALID_OR_EXPIRED'):
            self.start(preview, service=self.new_service())

    def test_stale_preview_revision_denies_before_reservation(self):
        preview = self.preview()
        self.ledger.revoke('example')
        with self.assertRaisesRegex(Denied, 'DESKTOP_REVISION_CHANGED'):
            self.start(preview)
        self.assertEqual(self.service.snapshot()['attempts'], [])

    def test_lost_response_is_resolved_by_durable_lookup_after_restart(self):
        first = self.start(self.preview(), key='lost-response')
        self.finish()
        self.service.close()
        reopened = self.new_service()
        found = reopened.lookup('example', 'lost-response')
        self.assertTrue(found['found'])
        self.assertEqual(found['attempt']['id'], first['id'])
        self.assertEqual(found['attempt']['state'], 'ACCEPTED')
        self.assertEqual(FixtureBackend.calls, 1)

    def test_commit_before_worker_crash_is_visible_and_recovery_does_not_refund(self):
        preview = self.preview()
        with patch.object(self.service, '_launch', side_effect=RuntimeError('SIMULATED_PROCESS_EXIT')):
            with self.assertRaisesRegex(RuntimeError, 'SIMULATED_PROCESS_EXIT'):
                self.start(preview, key='committed')
        reopened = self.new_service()
        row = reopened.lookup('example', 'committed')['attempt']
        self.assertEqual(row['state'], 'QUEUED')
        restored = reopened.recover(row['id'], row['revision'])
        self.assertEqual(restored['state'], 'CANCELLED')
        self.assertEqual(FixtureBackend.calls, 0)
        self.assertEqual(reopened.snapshot()['projects'][0]['attempts_consumed'], 1)

    def test_real_process_exit_after_reservation_is_recoverable_without_inference(self):
        script = '''import os, sys
from neural_office.desktop_service import DesktopService
from neural_office.ledger import Ledger
from tests.test_v55_service import FixtureBackend, PROFILE
class ExitAfterCommit(DesktopService):
    def _launch(self, attempt, roles): os._exit(91)
service = ExitAfterCommit(Ledger(sys.argv[1]), backend_factory=FixtureBackend,
                         model_discovery=lambda: [dict(PROFILE)])
source = service.host_capture('process-crash', sys.argv[2])
preview = service.preview('process-crash', source['entry_token'], PROFILE['model_digest'], 1,
                          'Audit this explicitly selected test source.')
service.start(preview['approval_token'], 'exit-after-commit', preview['expected_revision'])
'''
        child = subprocess.run([sys.executable, '-B', '-c', script, str(self.ledger.path), str(self.file)],
                               capture_output=True, timeout=15)
        self.assertEqual(child.returncode, 91, child.stderr.decode(errors='replace'))
        row = self.service.lookup('process-crash', 'exit-after-commit')['attempt']
        self.assertEqual(row['state'], 'QUEUED')
        self.assertEqual(self.service.recover(row['id'], row['revision'])['state'], 'CANCELLED')
        self.assertEqual(self.service.snapshot()['projects'][0]['attempts_consumed'], 1)
        self.assertEqual(FixtureBackend.calls, 0)

    def test_reader_can_cancel_worker_and_cannot_recover_live_controller(self):
        self.service.backend_factory = BlockingBackend
        first = self.start(self.preview())
        self.assertTrue(BlockingBackend.entered.wait(5))
        with self.assertRaisesRegex(Denied, 'OFFICE_RUNNER_STILL_ACTIVE'):
            self.service.recover(first['id'], self.service.attempt(first['id'])['revision'])
        cancelled = self.command('attempt.cancel', {'attempt_id': first['id']})
        self.assertIn(cancelled['state'], ('STOPPING', 'CANCELLED'))
        self.finish()
        self.assertEqual(self.service.attempt(first['id'])['state'], 'CANCELLED')
        self.assertEqual(self.service.snapshot()['projects'][0]['attempts_consumed'], 1)

    def test_live_worker_uses_cached_catalog_and_preview_cannot_block_cancel(self):
        self.service.backend_factory = BlockingBackend
        preview = self.preview()
        row = self.start(preview)
        self.assertTrue(BlockingBackend.entered.wait(5))
        with patch.object(self.service, 'model_discovery', side_effect=AssertionError('NETWORK_MUST_NOT_RUN')):
            catalog = self.command('models.list')
            self.assertTrue(catalog['cached'])
            self.assertEqual(catalog['models'][0]['model_digest'], PROFILE['model_digest'])
            with self.assertRaisesRegex(Denied, 'GLOBAL_INFERENCE_BUSY'):
                self.service.preview('example', 'unused', PROFILE['model_digest'], 1, 'A fresh explicit objective.')
            self.command('attempt.cancel', {'attempt_id': row['id']})
        self.finish()
        self.assertEqual(self.service.attempt(row['id'])['state'], 'CANCELLED')

    def test_terminal_recovery_is_read_even_while_unrelated_worker_lives(self):
        first = self.start(self.preview())
        self.finish()
        terminal = self.service.attempt(first['id'])
        self.service.backend_factory = BlockingBackend
        next_preview = self.preview(objective='Review this source again with explicit fresh authority.')
        self.start(next_preview, key='second')
        self.assertTrue(BlockingBackend.entered.wait(5))
        self.assertEqual(self.service.recover(first['id'], terminal['revision'])['state'], 'ACCEPTED')
        BlockingBackend.released.set()
        self.finish()

    def test_recovery_revision_of_queued_attempt_must_match(self):
        preview = self.preview()
        with patch.object(self.service, '_launch'):
            row = self.start(preview)
        with self.assertRaisesRegex(Denied, 'DESKTOP_REVISION_CHANGED'):
            self.service.recover(row['id'], row['revision']+1)
        self.assertEqual(self.service.attempt(row['id'])['state'], 'QUEUED')

    def test_budget_three_is_core_authority_and_new_session_cannot_reset(self):
        for ordinal in range(3):
            self.start(self.preview(), key=f'attempt-{ordinal}')
            self.finish()
        reopened = self.new_service()
        fourth = self.preview(service=reopened)
        with self.assertRaisesRegex(Denied, 'ATTEMPT_BUDGET_EXHAUSTED'):
            self.start(fourth, key='fourth', service=reopened)
        self.assertEqual(reopened.snapshot()['projects'][0]['attempts_consumed'], 3)

    def test_report_chunks_reassemble_exact_durable_bytes_and_hash(self):
        row = self.start(self.preview())
        self.finish()
        metadata = self.service.report(row['id'])
        offset, parts = 0, []
        while True:
            chunk = self.service.report_read(row['id'], offset, 11)
            data = base64.b64decode(chunk['base64'])
            self.assertEqual(digest(data), chunk['chunk_sha256'])
            parts.append(data)
            offset = chunk['next_offset']
            if chunk['eof']: break
        assembled = b''.join(parts)
        self.assertEqual(digest(assembled), metadata['sha256'])
        self.assertEqual(len(assembled), metadata['bytes'])
        self.assertEqual(json.loads(assembled)['model_commentary_status'], 'UNVERIFIED_ASSISTANCE')
        with self.assertRaisesRegex(Denied, 'REPORT_OFFSET_RANGE'):
            self.service.report_read(row['id'], metadata['bytes']+1, 1)

    def test_event_pages_have_no_job_path_and_replay_without_gaps(self):
        self.start(self.preview())
        self.finish()
        events, after = [], 0
        while True:
            page = self.service.events(after, 2)
            events.extend(page['events'])
            after = page['next_after']
            if not page['has_more']: break
        self.assertEqual([event['seq'] for event in events], list(range(1, after+1)))
        self.assertTrue(all(type(event['stamp_ns']) is str for event in events))
        self.assertTrue(all('job' not in event['payload'] and 'root' not in event['payload'] for event in events))
        self.assertEqual(self.service.events(0, 2)['events'], events[:2])
        with self.assertRaisesRegex(Denied, 'EVENT_CURSOR_AHEAD'):
            self.service.events(after+1, 1)

    def test_snapshot_paginates_projects_and_attempts_independently(self):
        self.start(self.preview())
        self.finish()
        for index in range(3):
            folder = self.root / f'project-{index}'
            folder.mkdir()
            self.ledger.register(f'p-{index}', folder)
        one = self.service.snapshot(limit=1)
        two = self.service.snapshot(**one['next'], limit=1)
        self.assertNotEqual(one['projects'][0]['id'], two['projects'][0]['id'])
        self.assertEqual(two['attempts'], [])
        self.assertTrue(two['has_more']['projects'])
        self.assertNotIn('snapshot', one['attempts'][0])
        self.assertNotIn('root', one['projects'][0])

    def test_frontend_cannot_supply_native_capture_or_arbitrary_paths(self):
        for method, params in (('host.source.capture', {'project_id': 'x', 'path': str(self.file)}),
                               ('source.pick', {'project_id': 'x', 'path': str(self.file)})):
            with self.assertRaises(Denied): self.command(method, params)
        with self.assertRaisesRegex(Denied, 'NATIVE_PICKER_REQUIRED'):
            self.command('source.pick', {'project_id': 'x'})

    def test_stdio_frames_are_bounded_and_eof_cancels_owned_work(self):
        self.service.backend_factory = BlockingBackend
        self.start(self.preview())
        self.assertTrue(BlockingBackend.entered.wait(5))
        output = io.BytesIO()
        self.assertEqual(serve(self.service, io.BytesIO(b'x'*(MAX_MESSAGE_BYTES+2)), output), 2)
        response = json.loads(output.getvalue())
        self.assertEqual(response['error']['code'], 'DESKTOP_FRAME_SIZE_OR_TERMINATION')
        self.assertFalse(self.service._worker.is_alive())
        self.assertEqual(self.ledger.status()['attempts'][0]['state'], 'CANCELLED')

    def test_real_stdio_process_roundtrip_has_no_private_path_in_response(self):
        requests = [
            {'version': 1, 'id': 'describe', 'method': 'describe', 'params': {}},
            {'version': 1, 'id': 'capture', 'method': 'host.source.capture',
             'params': {'project_id': 'native-picked', 'path': str(self.file)}},
            {'version': 1, 'id': 'snapshot', 'method': 'snapshot.get',
             'params': {'project_after': 0, 'attempt_after': 0, 'limit': 100}},
        ]
        child = subprocess.run([sys.executable, '-B', '-m', 'neural_office.desktop_stdio',
                                '--state', str(self.ledger.path)],
                               input=b'\n'.join(canonical(request).encode() for request in requests)+b'\n',
                               capture_output=True, timeout=15)
        self.assertEqual(child.returncode, 0, child.stderr.decode(errors='replace'))
        responses = [json.loads(line) for line in child.stdout.splitlines()]
        self.assertEqual([response['id'] for response in responses], ['describe', 'capture', 'snapshot'])
        self.assertTrue(all(response['ok'] for response in responses))
        self.assertEqual(responses[0]['result']['inference'], 'owned-local-model')
        self.assertEqual(responses[1]['result']['filename'], 'example.html')
        self.assertNotIn(str(self.root), child.stdout.decode())

    def test_response_does_not_leak_exception_path(self):
        raw = canonical({'version': 1, 'id': 'test', 'method': 'models.list', 'params': {}}).encode()
        with patch.object(self.service, 'models', side_effect=OSError('C:/private/personal.txt')):
            response = respond(self.service, raw)
        self.assertNotIn(b'private', response)
        self.assertEqual(json.loads(response)['error']['code'], 'DESKTOP_OPERATION_FAILED')

    def test_framing_rejects_duplicate_keys_nan_and_boolean_chunk(self):
        for raw in (b'{"id":"a","id":"b"}', b'{"id":NaN}', b'\xff'):
            self.assertFalse(json.loads(respond(self.service, raw))['ok'])
        with self.assertRaises(Denied):
            self.command('report.read', {'attempt_id': 'a', 'offset': 0, 'limit': True})

    def test_catalog_rejects_excessive_metadata_before_quadratic_selection(self):
        with patch('neural_office.desktop_service.local_metadata', return_value={'models': [{}]*257}), \
             patch('neural_office.desktop_service.select_model') as select:
            with self.assertRaisesRegex(Denied, 'MODEL_CATALOG_LIMIT'):
                discover_models()
            select.assert_not_called()

    def test_default_is_owned_backend_and_injected_tests_are_labelled(self):
        self.assertEqual(self.command('describe')['inference'], 'injected-test-backend')
        from neural_office.ollama import OwnedOllama
        self.service.backend_factory = OwnedOllama
        self.assertEqual(self.command('describe')['inference'], 'owned-local-model')


if __name__ == '__main__': unittest.main()
