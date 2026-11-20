"""Integration across the private picker pipe, the public protocol and the existing ledger."""
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest

from neural_office import excerpt_review
from neural_office.desktop_contract import decode_command
from neural_office.desktop_service import DesktopService
from neural_office.desktop_stdio import respond
from neural_office.ledger import Denied, Ledger, canonical, digest


def envelope(method, **params):
    return canonical({'version': 1, 'id': 'boundary-test', 'method': method, 'params': params}).encode()


class RecordingFixture:
    """One labelled reply; construction and input are observable by the test."""
    def __init__(self, payloads):
        self.payloads = payloads

    def start(self): pass

    def infer(self, payload):
        self.payloads.append(payload)
        return {'done': True, 'message': {'content': 'Comentario sintético de prueba.'}}

    def request_stop(self): pass
    def terminate(self): pass
    def close(self): pass


@unittest.skipUnless(os.name == 'nt', 'The native capture uses a Windows read handle')
class AttachmentBoundary(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.project = self.root / 'selected'
        self.project.mkdir()
        self.file = self.project / 'ficha.html'
        self.file.write_bytes(b'<html lang="es"><body>SENSITIVE-UNRELATED-HTML</body></html>')
        self.payloads = []
        self.ledger = Ledger(self.root / 'office.db')
        self.service = self.open()
        self.target = {'project_id': 'Portal', 'thread_id': 'issue-1'}

    def open(self):
        service = DesktopService(
            self.ledger, backend_factory=lambda *_: RecordingFixture(self.payloads),
            model_discovery=lambda: [{'mode': 'fixture', 'model': 'explicit-test-model', 'model_digest': 'f'*64}])
        self.addCleanup(service.close)
        return service

    def captures(self):
        wire = envelope('host.attachments.capture', **self.target, paths=[str(self.file)])
        with self.assertRaisesRegex(Denied, 'METHOD_UNSUPPORTED'):
            self.service.dispatch(wire)
        reply = json.loads(respond(self.service, wire))
        self.assertTrue(reply['ok'], reply)
        self.assertNotIn(str(self.project), str(reply))
        return reply['result']

    def test_private_capture_reopen_and_no_spend(self):
        capture, = self.captures()
        self.assertEqual(capture['sha256'], digest(self.file.read_bytes()))
        with self.assertRaisesRegex(Denied, 'PARAMETER_FIELDS'):
            decode_command(envelope('attachments.pick', **self.target, path=str(self.file)))
        self.assertEqual(self.service.dispatch(envelope('attachments.list', **self.target)), [capture])
        self.assertEqual(self.service.dispatch(envelope('attachments.list', project_id='Portal', thread_id='other')), [])
        reports = self.service.dispatch(envelope('attachments.inspect', **self.target,
                                                attachment_ids=[capture['id']], objective=''))
        self.assertEqual((reports['reservations'], reports['model_calls']), (0, 0))
        self.file.write_text('changed on disk', encoding='utf-8')
        reopened = self.open()
        view = reopened.dispatch(envelope('attachments.view', **self.target, capture_id=capture['id'], member='', page=1))
        self.assertEqual(view['sha256'], capture['sha256'])
        self.assertIn('SENSITIVE-UNRELATED-HTML', view['text'])
        self.assertEqual(reopened.dispatch(envelope('attachments.threads', project_id='Portal'))[0]['id'], 'issue-1')
        self.assertEqual(reopened.dispatch(envelope('attachments.report', **self.target, report_id=reports['id'])), reports)
        self.assertEqual(reopened.snapshot()['projects'][0]['attempts_consumed'], 0)
        self.assertEqual(self.payloads, [])

    def test_scope_receipt_reservation_replay_and_recovery(self):
        captured, = self.captures()
        objective = 'Explica la comprobación del título del documento.'
        inspection = self.service.dispatch(envelope('attachments.inspect', **self.target,
                                                    attachment_ids=[captured['id']], objective=objective))
        grant_args = dict(report_id=inspection['id'], model_digest='f'*64, objective=objective)
        with self.assertRaisesRegex(Denied, 'ATTACHMENT_REPORT_NOT_FOUND'):
            self.service.dispatch(envelope('attachments.preview', project_id='Portal', thread_id='other', **grant_args))
        preview = self.service.dispatch(envelope('attachments.preview', **self.target, **grant_args))
        self.assertEqual(self.payloads, [])
        self.assertEqual(preview['attempts_remaining'], 3)
        self.assertEqual(preview['roles'], 1)
        self.assertEqual(preview['fragments'][0]['quote'], 'DOCUMENT_TITLE_MISSING')
        start = envelope('attempt.start', approval_token=preview['approval_token'],
                         idempotency_key='single-reservation', expected_revision=preview['expected_revision'])
        attempt = self.service.dispatch(start)
        self.service._worker.join(8)
        self.assertFalse(self.service._worker.is_alive())
        replay = self.service.dispatch(start)
        self.assertEqual(replay['id'], attempt['id'])
        self.assertEqual(replay['state'], 'ACCEPTED')
        self.assertEqual(len(self.payloads), 1)
        self.assertEqual(json.loads(self.payloads[0]['messages'][1]['content'])['authorized_fragments'], preview['fragments'])
        self.assertNotIn('SENSITIVE-UNRELATED-HTML', canonical(self.payloads))
        reopened = self.open()
        history = reopened.project_history('Portal')['attempts'][0]
        self.assertEqual((history['thread_id'], history['inspection_id']), ('issue-1', inspection['id']))
        self.assertEqual(reopened.snapshot()['projects'][0]['attempts_consumed'], 1)
        row, raw = reopened._report(attempt['id'])
        parsed = json.loads(raw)
        self.assertEqual(parsed['scope'], excerpt_review.SCOPE)
        self.assertEqual(parsed['authorized_fragments'], preview['fragments'])
        self.assertTrue(excerpt_review.verify_report(bytes(row['snapshot']), raw)['passed'])
        parsed['authorized_fragments'][0]['quote'] = 'unrelated'
        self.assertFalse(excerpt_review.verify_report(bytes(row['snapshot']), canonical(parsed).encode())['passed'])

    def test_stopping_authorized_excerpts_releases_owned_worker_and_preserves_single_charge(self):
        started = threading.Event()
        stopped = threading.Event()

        class Waiting(RecordingFixture):
            def infer(self, payload):
                started.set()
                if not stopped.wait(8):
                    raise TimeoutError('Fixture did not receive the stop signal')
                return super().infer(payload)

            def request_stop(self):
                stopped.set()

        self.service.backend_factory = lambda *_: Waiting(self.payloads)
        captured, = self.captures()
        objective = 'Explica la evidencia de esta revisión.'
        report = self.service.dispatch(envelope('attachments.inspect', **self.target,
                                                attachment_ids=[captured['id']], objective=objective))
        grant = self.service.dispatch(envelope('attachments.preview', **self.target, report_id=report['id'],
                                               model_digest='f'*64, objective=objective))
        row = self.service.dispatch(envelope('attempt.start', approval_token=grant['approval_token'],
                                            idempotency_key='cancelled-once', expected_revision=grant['expected_revision']))
        self.assertTrue(started.wait(5))
        self.service.dispatch(envelope('attempt.cancel', attempt_id=row['id']))
        self.service._worker.join(8)
        self.assertTrue(stopped.is_set())
        self.assertFalse(self.service._worker.is_alive())
        target = self.open()
        self.assertEqual(target.attempt(row['id'])['state'], 'CANCELLED')
        self.assertEqual(target.snapshot()['lease']['attempt_id'], None)
        self.assertEqual(target.project_history('Portal')['attempts'][0]['thread_id'], self.target['thread_id'])
        self.assertEqual(target.snapshot()['projects'][0]['attempts_consumed'], 1)
        self.assertEqual(target.dispatch(envelope('attachments.report', **self.target, report_id=report['id'])), report)
