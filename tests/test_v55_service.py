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
from neural_office.runner import run

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

    def test_failure_receipt_reopens_with_a_public_reason_and_source_basename(self):
        class KnownFailure(FixtureBackend):
            def start(self): raise Denied('MODEL_METADATA_UNAVAILABLE')
        class PrivateFailure(FixtureBackend):
            def start(self): raise RuntimeError('private fixture detail must stay local')

        ids = []
        for backend, expected in [(KnownFailure, 'MODEL_METADATA_UNAVAILABLE'), (PrivateFailure, 'EXECUTION_FAILED')]:
            owner = self.new_service(backend_factory=backend)
            item = self.start(self.preview(owner), key=expected, service=owner)
            self.finish(owner)
            ids.append(item['id'])
            reopened = self.new_service()
            row = reopened.attempt(item['id'])
            self.assertEqual((row['state'], row['source_name'], row['execution_error_code']),
                             ('FAILED', 'example.html', expected))
            self.assertEqual(reopened.lookup('example', expected)['attempt']['id'], item['id'])
            self.assertNotIn('private fixture', canonical(row))
            self.assertEqual(row['calls'], [])
        self.assertNotEqual(*ids)
        self.assertEqual(self.service.snapshot()['projects'][0]['attempts_consumed'], 2)

    def test_older_signed_failure_with_no_recorded_cause_stays_unknown(self):
        class Fail(FixtureBackend):
            def start(self): raise Denied('MODEL_METADATA_UNAVAILABLE')
        owner = self.new_service(backend_factory=Fail)
        write_event = self.ledger._event
        def legacy_event(con, kind, payload):
            # Generate the V5.7 record before its digest is computed.
            return write_event(con, kind, {k: v for k, v in payload.items() if k not in ('error_code', 'source_name')})
        with patch.object(self.ledger, '_event', side_effect=legacy_event):
            item = self.start(self.preview(owner), service=owner)
            self.finish(owner)
        row = self.new_service().attempt(item['id'])
        self.assertEqual(row['state'], 'FAILED')
        self.assertIsNone(row['source_name'])
        self.assertIsNone(row['execution_error_code'])
        self.assertEqual(row['source_sha256'], digest(SOURCE))

    def test_activity_is_attempt_scoped_across_pages_and_service_restart(self):
        first = self.start(self.preview(), key='old')['id']
        self.finish()
        second = self.start(self.preview(), key='new')['id']
        self.finish()
        reader = self.new_service()
        before = reader.snapshot()
        for target in (first, second):
            cursor, all_events = 0, []
            while True:
                page = self.command('attempt.events', {'attempt_id':target,'before':cursor,'limit':2}, reader)
                self.assertEqual((page['session_id'],page['office_id'],page['attempt_id']),
                                 (reader.session_id,before['office_id'],target))
                batch = page['events']
                self.assertEqual([e['seq'] for e in batch],sorted(e['seq'] for e in batch))
                self.assertTrue(all(e['payload']['attempt']==target and 'job' not in e['payload'] for e in batch))
                all_events = batch + all_events
                if not page['has_more']: break
                self.assertTrue(page['next_before']>0 and (not cursor or page['next_before']<cursor))
                cursor = page['next_before']
            with self.ledger.connection() as con:
                expected = [r[0] for r in con.execute(
                    "SELECT seq FROM events WHERE json_extract(payload,'$.attempt')=? ORDER BY seq", (target,))]
            self.assertEqual([e['seq'] for e in all_events], expected)
            self.assertEqual(reader.attempt_events(target,expected[0],2)['events'], [])
            detail = reader.attempt(target)
            self.assertEqual(len(detail['calls']), 1)
            call, = detail['calls']
            with self.ledger.connection() as con:
                times = dict(con.execute(
                    "SELECT kind, stamp_ns / 1000000 FROM events WHERE json_extract(payload,'$.call')=? "
                    "AND json_extract(payload,'$.attempt')=?", (call['seq'], target)))
            self.assertEqual(call['started_ms'], times['MODEL_CALL_ADMITTED'])
            self.assertEqual(call['completed_ms'], times['MODEL_CALL_COMPLETED'])
            self.assertIsInstance(detail['observed_ms'], int)
        with self.assertRaises(Denied): self.command('attempt.events', {'attempt_id':first,'before':0,'limit':0},reader)
        with self.assertRaises(Denied): reader.attempt_events('missing',0,2)
        self.assertEqual(reader.snapshot(), before)

    def test_running_call_has_no_completion_time_before_an_answer(self):
        owner = self.new_service(backend_factory=BlockingBackend)
        item = self.start(self.preview(owner), service=owner)
        try:
            self.assertTrue(BlockingBackend.entered.wait(3))
            live, = owner.attempt(item['id'])['calls']
            self.assertEqual(live['state'], 'STARTED')
            self.assertIsInstance(live['started_ms'], int)
            self.assertNotIn('completed_ms', live)
        finally:
            BlockingBackend.released.set()
            self.finish(owner)
        done, = self.new_service().attempt(item['id'])['calls']
        self.assertEqual((done['seq'], done['started_ms']), (live['seq'], live['started_ms']))
        self.assertEqual(done['state'], 'DONE')
        self.assertIsInstance(done['completed_ms'], int)

    def test_real_controller_loss_recovers_the_original_charge_and_call(self):
        # This process owns its runner lock. The fixture waits only after real admission.
        code = """
import pathlib,sys,threading
sys.path.insert(0,'tests')
from test_v55_service import FixtureBackend,PROFILE
from neural_office.desktop_service import DesktopService
from neural_office.ledger import Ledger
class Waiting(FixtureBackend):
    entered=threading.Event()
    def infer(self,payload):
        self.entered.set()
        threading.Event().wait(30)
        return super().infer(payload)
root=pathlib.Path(sys.argv[1])
service=DesktopService(Ledger(root/'office.sqlite3'),backend_factory=Waiting,model_discovery=lambda:[dict(PROFILE)])
grant=service.host_capture('example',root/'example.html')
ap=service.preview('example',grant['entry_token'],PROFILE['model_digest'],1,'Review a synthetic document after interruption.')
row=service.start(ap['approval_token'],'controller-key',ap['expected_revision'])
assert Waiting.entered.wait(10)
print(row['id'],flush=True)
threading.Event().wait(30)
"""
        child = subprocess.Popen([sys.executable, '-B', '-c', code, str(self.root)],
                                 cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, text=True)
        try:
            identity = child.stdout.readline().strip()
            self.assertRegex(identity, r'^[0-9a-f]{32}$')
            original = self.service.attempt(identity)
            self.assertEqual((original['state'],len(original['calls'])), ('RUNNING',1))
        finally:
            child.terminate()
            child.wait(timeout=10)
            child.stdout.close()
        reopened = self.new_service()
        row = reopened.lookup('example','controller-key')['attempt']
        self.assertEqual(row['id'],identity)
        repaired = reopened.recover(identity,row['revision'])
        self.assertEqual((repaired['id'],repaired['state'],repaired['execution_error_code']),
                         (identity,'FAILED','ATTEMPT_INTERRUPTED'))
        self.assertEqual(original['calls'][0]['state'],'STARTED')
        self.assertEqual(repaired['calls'],[{**original['calls'][0], 'state':'INTERRUPTED'}])
        again = self.new_service()
        self.assertEqual(again.recover(identity,repaired['revision'])['execution_error_code'],'ATTEMPT_INTERRUPTED')
        self.assertEqual(again.snapshot()['projects'][0]['attempts_consumed'],1)

    def test_active_attempt_is_addressable_outside_the_visible_history_page(self):
        old = self.start(self.preview(), key='archive')['id']
        self.finish()
        owner = self.new_service(backend_factory=BlockingBackend)
        BlockingBackend.released.clear()
        try:
            current = self.start(self.preview(owner), key='active', service=owner)['id']
            self.assertTrue(BlockingBackend.entered.wait(5))
            page = self.service.snapshot(limit=1)
            self.assertEqual([a['id'] for a in page['attempts']], [old])
            self.assertTrue(page['has_more']['attempts'])
            self.assertEqual(page['current_attempt']['id'],current)
            self.assertEqual(self.service.attempt(old)['state'],'ACCEPTED')
        finally:
            BlockingBackend.released.set()
            self.finish(owner)

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
        # Finish a real ledger sequence before exercising the read-only cursor.
        self.ledger.register('example', self.root)
        attempt = self.ledger.reserve('example', 'Review the pagination fixture.', SOURCE,
                                      {**PROFILE, 'roles': 1}, 'one', admit=True)
        self.assertEqual(run(self.ledger, attempt, 1, backend_factory=FixtureBackend), 'ACCEPTED')
        events, after = [], 0
        while True:
            page = self.service.events(after, 2)
            events.extend(page['events'])
            after = page['next_after']
            if not page['has_more']: break
        self.assertIn('LEASE_ACQUIRED', [event['kind'] for event in events])
        self.assertEqual(events[-1]['kind'], 'FINAL_VERDICT')
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

    def test_scoped_history_crosses_global_page_without_changing_authority(self):
        self.ledger.initialize()
        with self.ledger.transaction() as con:
            for index in range(50):
                project = 'sample-' + str(index)
                con.execute('INSERT INTO projects(id,root) VALUES (?,?)', (project, project))
                for ordinal in range(1, 4):
                    key = f'a-{index}-{ordinal}'
                    con.execute('INSERT INTO attempts(id,project,ordinal,request_key,request_digest,'
                                'objective,profile,snapshot,snapshot_sha,state,created,last_seen) '
                                "VALUES (?,?,?,?,?,?,?,?,?,'CANCELLED',0,0)",
                                (key, project, ordinal, key, '0'*64, 'Public synthetic task',
                                 canonical({**PROFILE, 'roles':1}), SOURCE, digest(SOURCE)))
        before = self.service.snapshot()
        self.assertTrue(before['has_more']['attempts'])
        for i in (0, 33, 49):
            project = 'sample-' + str(i)
            page = self.command('project.history', {'project_id': project})
            self.assertEqual([a['id'] for a in page['attempts']], [f'a-{i}-{j}' for j in (3,2,1)])
            self.assertTrue(all(row['project_id'] == project for row in page['attempts']))
            self.assertEqual((page['office_id'], page['revision']), (before['office_id'], before['revision']))
        self.assertEqual(self.command('project.history', {'project_id':'empty'})['attempts'], [])
        self.assertEqual(self.service.snapshot(), before)

    def test_desktop_read_uses_one_continuity_check_and_verifies_captured_bytes(self):
        from unittest.mock import patch
        from neural_office import continuity
        item = self.start(self.preview())
        self.finish()
        with patch.object(continuity, 'signature', wraps=continuity.signature) as counted:
            read = self.service.attempt(item['id'])
        self.assertEqual((read['report_available'], counted.call_count), (True, 1))
        with self.ledger.transaction() as con:
            con.execute('UPDATE outputs SET content=? WHERE attempt=?', ('Different fixture text', item['id']))
        with self.assertRaisesRegex(Denied, 'OUTPUT_CHANGED'):
            self.service.attempt(item['id'])

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
