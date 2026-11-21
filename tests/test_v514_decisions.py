"""V5.14 invariants for the local answer and the decision that belongs to its report."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from examples.multiformat.build_example import example_files
from neural_office.attachments import AttachmentStore
from neural_office.inspection_intent import requested_checks
from neural_office.ledger import Denied, Ledger


class DecisionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.ledger = Ledger(base / 'office.db')
        self.ledger.initialize()
        self.store = AttachmentStore(self.ledger)
        captured = self.store.capture('Portal', example_files(base / 'inputs'), thread_id='revision')
        self.files = {item['kind']: item['id'] for item in captured}

    def inspect(self, goal, kinds):
        return self.store.inspect('Portal', [self.files[kind] for kind in kinds], goal, thread_id='revision')

    def test_objectives_control_the_answer_with_the_same_sources(self):
        for goal, expected in [
            ('¿Cuántas páginas tiene el PDF?', ['pages']),
            ('Valida el JSON.', ['syntax']),
            ('¿Cuáles son las dimensiones de las imágenes?', ['dimensions', 'dimensions']),
            ('¿Es legible el título?', ['visual', 'visual']),
            ('¿Está bien redactado el HTML?', ['scope']),
            ('¿Cuál es el presupuesto publicitario?', ['scope']),
            ('¿Es contractualmente válido el plazo de primera respuesta?', ['contract']),
            ('¿Coinciden o no los plazos?', ['first_response_hours']),
            ('Valida la sintaxis JSON y compara el plazo.', ['syntax', 'first_response_hours']),
        ]:
            with self.subTest(goal=goal):
                result = self.inspect(goal, list(self.files))
                self.assertEqual([f['rule'] for f in result['findings']], expected)
                self.assertEqual(result['model_calls'], 0)
                self.assertEqual(result['reservations'], 0)
                self.assertGreaterEqual(result['completed_at'], max(s['at'] for s in result['steps']))
                if expected[0] in ('visual','scope','contract'):
                    self.assertTrue(all(f['status']=='insufficient' for f in result['findings']))
        self.assertEqual(self.inspect('Compara el plazo.', ['json'])['findings'][0]['status'], 'insufficient')
        self.assertEqual(self.inspect('Valida el JSON.', ['json'])['findings'][0]['title'], 'La sintaxis JSON es válida')
        self.assertEqual(requested_checks('No compares el plazo.', {'pdf','json'}), ['clarify'])

    def test_concurrent_decisions_replay_scope_and_reopen(self):
        report = self.inspect('Compara el plazo.', ['pdf','json'])
        key = report['id']
        gate = threading.Barrier(2)
        def commit(choice):
            gate.wait(5)
            try:
                return self.store.decide('Portal','revision',key,choice,0)
            except Denied as exc:
                return str(exc)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(commit, ['pdf','json']))
        self.assertIn('DECISION_CHANGED', results)
        accepted = next(row for row in results if isinstance(row,dict))
        recovered = AttachmentStore(self.ledger)
        self.assertEqual(recovered.report('Portal',key,thread_id='revision')['decision'], accepted)
        self.assertEqual(recovered.decide('Portal','revision',key,accepted['choice'],0), accepted)
        self.assertEqual(self.inspect('Compara el plazo.', ['pdf','json'])['decision'], accepted)
        changed = recovered.decide('Portal','revision',key,'defer',1)
        self.assertEqual(changed['revision'],2)
        with self.assertRaisesRegex(Denied,'DECISION_CHANGED'):
            self.store.decide('Portal','revision',key,'pdf',0)
        for project, thread in [('Portal','otro'), ('otro','revision')]:
            with self.assertRaisesRegex(Denied,'ATTACHMENT_REPORT_NOT_FOUND'):
                self.store.decide(project,thread,key,'pdf',0)
        ordinary = self.inspect('Valida el JSON.', ['json'])
        with self.assertRaisesRegex(Denied,'DECISION_NOT_APPLICABLE'):
            recovered.decide('Portal','revision',ordinary['id'],'pdf',0)
        self.assertEqual(len(recovered.history('Portal',thread_id='revision')),2)
        answer = self.inspect('¿Qué decidimos?', ['pdf','json'])['findings'][0]
        self.assertEqual((answer['title'], answer['origin_report']),('La decisión se aplazó',key))
        recovered.decide('Portal','revision',key,'pdf',2)
        answer = self.inspect('¿Qué decidimos?', ['pdf','json'])['findings'][0]
        self.assertEqual(answer['title'],'Se eligieron 24 h')
        thread=self.store.threads('Portal')[0]
        self.assertEqual(thread['objective'],'Compara el plazo.')
        self.assertGreaterEqual(thread['created_at'],recovered.report('Portal',key,thread_id='revision')['decision']['at'])
        self.assertEqual(self.inspect('¿Qué decidimos?', ['json'])['findings'][0]['status'],'insufficient')
        self.assertEqual(requested_checks('Revisa el plazo de pago.', {'pdf','json'}),['clarify'])

    def test_extra_image_preserves_the_choice_but_a_missing_source_does_not(self):
        report = self.inspect('Compara el plazo.', ['pdf','json'])
        self.store.decide('Portal', 'revision', report['id'], 'pdf', 0)
        for goal in ('¿Qué decidimos en este hilo?', '¿Qué decidimos sobre el plazo de primera respuesta en este hilo?'):
            with self.subTest(goal=goal):
                finding, = self.inspect(goal, ['png', 'pdf', 'json'])['findings']
                self.assertEqual(finding.get('origin_report'), report['id'])
                self.assertEqual(finding['sources'][0]['value'], 24)
                missing, = self.inspect(goal, ['png', 'json'])['findings']
                self.assertEqual(missing['status'], 'insufficient')

    def test_old_database_migrates_without_losing_its_report(self):
        report = self.inspect('Comprueba el plazo.', ['pdf','json'])
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute('DROP TABLE decisions')
            db.execute('PRAGMA user_version=1')
        second = AttachmentStore(self.ledger)
        self.assertEqual(second.report('Portal',report['id'],thread_id='revision'), report)
        self.assertEqual(second.decide('Portal','revision',report['id'],'json',0)['revision'],1)
