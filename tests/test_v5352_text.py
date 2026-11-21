"""A written turn has its own project, authority and receipt without a file grant."""
import json
from pathlib import Path
import tempfile
import unittest

from neural_office import excerpt_review
from neural_office.desktop_service import DesktopService
from neural_office.ledger import Denied, Ledger, canonical


class WrittenTurns(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.ledger = Ledger(self.root / 'office.db')
        self.payloads = []
        self.completion = {}
        completion = self.completion
        payloads = self.payloads

        class Recorder:
            def __init__(self, *_): pass
            def start(self): pass
            def infer(self, payload):
                payloads.append(payload)
                return {'done': True, 'message': {'content': 'Respuesta sintética.'}, **completion}
            def terminate(self): pass
            def request_stop(self): pass
            def close(self): pass

        self.core = DesktopService(self.ledger, backend_factory=Recorder, model_discovery=lambda: [
            {'model': 'prueba', 'model_digest': 'a'*64, 'mode': 'fixture'}])
        self.addCleanup(self.core.close)
        self.target = {'project_id': 'Conversación', 'thread_id': 'uno'}

    def call(self, method, **params):
        wire = canonical(dict(version=1, id='turn', method=method, params=params)).encode()
        return self.core.dispatch(wire)

    def written(self, question):
        return self.call('attachments.inspect', **self.target, objective=question, attachment_ids=[])

    def test_free_turn_survives_restart_and_creates_no_file_permission(self):
        for empty in ('', '   '):
            with self.assertRaises(Denied):
                self.written(empty)
        self.assertEqual(self.core.snapshot()['projects'], [])
        record = self.written('Hola')
        self.assertEqual((record['model_calls'], record['reservations'], record['attachments']), (0, 0, []))
        self.assertNotIn('team', record)
        self.assertEqual(self.written('Hola')['id'], record['id'])
        self.assertEqual(self.core.snapshot()['projects'][0]['attempts_consumed'], 0)
        reopened = DesktopService(self.ledger)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.attachments.threads('Conversación')[0]['id'], 'uno')
        self.assertEqual(reopened.attachments.history('Conversación',thread_id='uno')[0]['id'], record['id'])
        self.assertEqual(reopened.attachments.search('Conversación','Hola')[0]['id'], record['id'])
        self.assertEqual(reopened.attachments.history('Conversación',thread_id='dos'), [])
        self.assertEqual(reopened.attachments.list('Conversación',thread_id='uno'), [])

    def approved_written_turn(self):
        question = '¿2 + 2?'
        record = self.written(question)
        args = dict(report_id=record['id'], model_digest='a'*64, objective=question)
        with self.assertRaisesRegex(Denied,'ATTACHMENT_REPORT_NOT_FOUND'):
            self.call('attachments.preview', project_id='Conversación', thread_id='dos', **args)
        with self.assertRaisesRegex(Denied,'APPROVAL_CHANGED'):
            self.call('attachments.preview', **self.target, **{**args, 'objective': 'Otro texto'})
        grant = self.call('attachments.preview', **self.target, **args)
        self.assertEqual((grant['attempts_remaining'],grant['fragments'],self.payloads), (3,[],[]))
        start = dict(approval_token=grant['approval_token'], expected_revision=grant['expected_revision'], idempotency_key='mismo')
        attempt = self.call('attempt.start', **start)
        self.core._worker.join(8)
        self.assertFalse(self.core._worker.is_alive())
        replay = self.call('attempt.start', **start)
        self.assertEqual((replay['id'],replay['state'],len(self.payloads)), (attempt['id'],'ACCEPTED',1))
        self.assertIn(question, self.payloads[0]['messages'][1]['content'])
        self.assertEqual(self.core.snapshot()['projects'][0]['attempts_consumed'], 1)
        row, data = self.core._report(attempt['id'])
        artifact = json.loads(data)
        self.assertEqual((artifact['scope'], artifact['authorized_fragments']), (excerpt_review.TEXT_SCOPE, []))
        self.assertTrue(excerpt_review.verify_report(bytes(row['snapshot']), data)['passed'])
        return attempt['id']

    def test_permission_binds_exact_words_thread_and_one_charge(self):
        key = self.approved_written_turn()
        self.assertFalse(self.call('report.get', attempt_id=key)['generation_limited'])

    def test_accepted_report_discloses_truncated_generation_after_reopening(self):
        self.completion['done_reason'] = 'length'
        key = self.approved_written_turn()
        self.assertTrue(self.call('report.get', attempt_id=key)['generation_limited'])
        reopened = DesktopService(self.ledger)
        self.addCleanup(reopened.close)
        self.assertTrue(reopened.report(key)['generation_limited'])

    def test_first_picker_binds_written_project_once_without_reset(self):
        self.approved_written_turn()
        folder = self.root / 'material'
        folder.mkdir()
        file = folder / 'dato.txt'
        file.write_text('valor', encoding='utf-8')
        captured = self.core.host_attachments_capture('Conversación', 'uno', [str(file)])
        self.assertEqual(len(captured), 1)
        self.assertEqual(self.core.snapshot()['projects'][0]['attempts_consumed'], 1)
        other = self.root / 'otra'
        other.mkdir()
        with self.assertRaisesRegex(Denied,'PROJECT_ROOT_CHANGED'):
            self.ledger.register('Conversación', other)
