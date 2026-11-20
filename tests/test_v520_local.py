"""Local planning, scoped answers and recovery using a real attachment store."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from examples.multiformat.build_example import example_files
from neural_office import attachments
from neural_office.attachments import AttachmentStore
from neural_office.inspection_intent import requested_checks
from neural_office.ledger import Denied, Ledger


class DirectorScope(unittest.TestCase):
    def test_scoped_requests_and_compound_questions(self):
        cases = {
            '¿Cuál es el plazo de devolución?': ['clarify'],
            'Comprueba los plazos de facturación.': ['clarify'],
            'Comprueba el plazo fiscal.': ['clarify'],
            'Compara los dos plazos. Indica qué dato debe confirmar la persona responsable.': ['hours'],
            '¿Qué hay dentro del ZIP?': ['zip'],
            '¿Con cuál nos quedamos?': ['decision'],
            '¿Qué decidimos sobre el precio?': ['clarify'],
            '¿Qué decidimos sobre el plazo de primera respuesta?': ['decision'],
            '¿Qué decidimos y cuántas páginas tiene el PDF?': ['decision', 'pages'],
            '¿Cuántas páginas tiene el PDF? ¿Qué decidimos?': ['pages', 'decision'],
            '¿Qué decidimos? ¿Cuánto cuesta el envío?': ['decision', 'clarify'],
            'Compara el plazo de devolución y valida el JSON.': ['clarify', 'syntax'],
            'Valida el JSON y comprueba el plazo de devolución.': ['syntax', 'clarify'],
            'No compares el plazo.': ['clarify'],
            '¿Coinciden o no los plazos?': ['hours'],
            'Revisa la entrega del portal y compara el plazo de primera respuesta.': ['hours'],
        }
        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertEqual(requested_checks(question, {'pdf', 'json', 'zip'}), expected)

    def test_reopen_recall_and_decline_unrelated_metric(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            ledger = Ledger(base / 'office.db')
            ledger.initialize()
            store = AttachmentStore(ledger)
            captured = store.capture('Portal', example_files(base / 'inputs'), thread_id='review')
            ids = [item['id'] for item in captured]
            question = 'Compara el plazo de primera respuesta.'
            # Write a report under the previous identity, then use the new reader.
            with patch.object(attachments, 'RULE_VERSION', 'local-inspection-2'):
                initial = store.inspect('Portal', ids, question, thread_id='review')
            store.decide('Portal', 'review', initial['id'], 'json', 0)
            reopened = AttachmentStore(ledger)

            def ask(objective, sources=ids):
                return reopened.inspect('Portal', sources, objective, thread_id='review')

            self.assertEqual(ask(question)['id'], initial['id'])
            with patch.object(attachments, 'decode', side_effect=AssertionError('unexpected decoder')):
                answer = ask('¿Con cuál nos quedamos?')
                self.assertEqual(answer['findings'][0]['title'], 'Se eligieron 48 h')
                self.assertEqual(answer['findings'][0]['origin_report'], initial['id'])
                self.assertEqual((answer['model_calls'], answer['reservations']), (0, 0))
                self.assertEqual(ask('¿Con cuál nos quedamos?', ids[:-1])['findings'][0]['status'], 'insufficient')
                with self.assertRaisesRegex(Denied, 'ATTACHMENT_NOT_FOUND'):
                    reopened.inspect('Otro', ids, '¿Qué decidimos?', thread_id='review')
            compound = ask('¿Qué decidimos y cuántas páginas tiene el PDF?')
            self.assertEqual([f['title'] for f in compound['findings']], ['Se eligieron 48 h', '2 páginas'])
            refund = ask('¿Cuál es el plazo de devolución?')['findings']
            self.assertEqual([(f['rule'], f['status'], f['sources']) for f in refund],
                             [('scope', 'insufficient', [])])
            inventory = ask('¿Qué hay dentro del ZIP?')['findings'][0]
            self.assertEqual((inventory['title'], inventory['sources'][0]['kind']), ('4 entradas en el ZIP', 'zip'))
            for member in ('documentacion/especificacion.pdf', 'manifiesto.json', 'visual/movil.jpg', 'visual/portada.png'):
                self.assertIn(member, inventory['detail'])
            with closing(sqlite3.connect(reopened.path)) as db:
                db.execute('UPDATE captures SET content=? WHERE id=?', (b'{}', ids[0]))
                db.commit()
            with self.assertRaisesRegex(Denied, 'ATTACHMENT_INTEGRITY_FAILED'):
                ask('¿Con cuál nos quedamos?')


class OfflineOfficePlan(unittest.TestCase):
    def test_cli_dependencies_and_zero_side_effects(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / 'unused.db'
            command = [sys.executable, '-B', '-m', 'neural_office', '--state', str(state),
                       'office-plan', '--objective', 'Revisar una entrega local']
            result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, encoding='utf-8', check=True, timeout=10)
            plan = json.loads(result.stdout)
            self.assertEqual(plan['mode'], 'plan_only')
            self.assertEqual(plan['objective'], 'Revisar una entrega local')
            self.assertEqual(plan['planned_model_calls'], 22)
            self.assertEqual(plan['current_call_limit'], 12)
            self.assertEqual((plan['rounds'], plan['specialists_per_round']), (3, 6))
            self.assertEqual((plan['model_calls'], plan['reservations']), (0, 0))
            self.assertEqual(list(Path(folder).iterdir()), [])
            steps = plan['steps']
            known = set()
            previous = []
            for number in range(1, 4):
                gate, *employees = [step for step in steps if step['round'] == number and step['kind'] != 'delivery']
                self.assertEqual((gate['role'], gate['depends_on']), ('director', previous))
                self.assertEqual(len(employees), 6)
                self.assertEqual(len({step['role'] for step in employees}), 6)
                self.assertTrue(all(step['depends_on'] == [gate['id']] for step in employees))
                previous = [step['id'] for step in employees]
            self.assertEqual((steps[-1]['role'], steps[-1]['kind'], steps[-1]['depends_on']),
                             ('director', 'delivery', previous))
            for step in steps:
                self.assertTrue(set(step['depends_on']) <= known)
                self.assertNotIn(step['id'], known)
                known.add(step['id'])
            self.assertEqual(len(known), 22)
