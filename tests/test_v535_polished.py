from pathlib import Path
import tempfile
import unittest

from examples.multiformat.build_example import pdf_bytes
from neural_office.attachments import AttachmentStore
from neural_office.ledger import Denied, Ledger
from neural_office.project_library import ProjectLibrary


class PolishedWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        ledger = Ledger(root / 'office.db')
        ledger.initialize()
        self.store = AttachmentStore(ledger)
        bodies = {'mal.xml': b'<registro>', 'valido.json': b'{"valor": 24}',
                  'otro.json': b'{"otra": 12}', 'notas.md': 'Inicio\u2028Segunda Faro-28\nFin'.encode(),
                  'manual.pdf': pdf_bytes([['Primera'], ['Segunda']])}
        for name, body in bodies.items():
            (root / name).write_bytes(body)
        files = self.store.capture('Portal', [root / name for name in bodies], thread_id='revision')
        self.ids = {f['name']: f['id'] for f in files}

    def inspect(self, objective, names):
        return self.store.inspect('Portal', [self.ids[n] for n in names], objective, thread_id='revision')

    def test_selected_files_do_not_override_the_requested_source(self):
        for names in (list(self.ids), list(reversed(self.ids))):
            with self.subTest(names=names):
                xml = self.inspect('Valida la sintaxis del XML.', names)['findings']
                self.assertFalse(any('JSON es válida' in f['title'] for f in xml))
                self.assertIn('mal.xml', str(xml))
                self.assertTrue(xml[0]['title'].startswith('Error de sintaxis XML'))
                self.assertEqual(xml[0]['sources'][0]['line'],1)
                pages = self.inspect('¿Cuántas páginas tiene notas.md?', names)['findings']
                self.assertTrue(all(f['status'] == 'insufficient' for f in pages))
                self.assertIn('notas.md', str(pages))
                json = self.inspect('Valida la sintaxis de valido.json.', names)['findings']
                self.assertEqual([c['name'] for f in json for c in f['sources']], ['valido.json'])
                missing = self.inspect('Valida la sintaxis de ausente.json.', names)['findings']
                self.assertTrue(all(f['status'] == 'insufficient' for f in missing))
                named = self.inspect('Valida el JSON valido.json.', names)['findings']
                self.assertEqual([c['name'] for f in named for c in f['sources']], ['valido.json'])
                conflicting=self.inspect('Valida el XML valido.json.',names)['findings']
                self.assertTrue(all(f['status']=='insufficient' for f in conflicting))
                mixed=self.inspect('Valida la sintaxis de valido.json y notas.md.',names)['findings']
                self.assertEqual([f['status'] for f in mixed],['observed','insufficient'])
                self.assertIn('notas.md',mixed[1]['detail'])

    def test_compound_goal_preserves_unfulfilled_part_and_quoted_text(self):
        for joiner in (' y ', '; '):
            findings = self.inspect('Valida el JSON' + joiner + 'redacta una respuesta al cliente.', ['valido.json'])['findings']
            self.assertEqual(len(findings), 2)
            self.assertEqual(findings[0]['status'], 'observed')
            self.assertEqual(findings[1]['status'], 'insufficient')
            self.assertIn('redacta', (findings[1]['detail']+findings[1]['title']).lower())
        for phrase in ('“Faro-28”', "'Faro-28'", 'Faro-28'):
            answer = self.inspect('Busca '+phrase+' en notas.md.', list(self.ids))
            self.assertEqual(len(answer['findings']), 1)
            ref, = answer['findings'][0]['sources']
            self.assertEqual((ref['name'], ref['line'], ref['quote']), ('notas.md', 2, 'Segunda Faro-28'))
        parts = self.inspect('Valida valido.json y valida otro.json.', list(self.ids))['findings']
        self.assertEqual([c['name'] for f in parts for c in f['sources']], ['valido.json', 'otro.json'])
        polite = self.inspect('¿Puedes buscar «Faro-28» en el documento notas.md?', list(self.ids))
        self.assertEqual(polite['findings'][0]['sources'][0]['line'],2)
        intro = self.inspect('Hola, Director. ¿Cuántas páginas tiene el PDF?', list(self.ids))
        self.assertEqual([(f['rule'],f['title']) for f in intro['findings']],[('pages','2 páginas')])

    def test_partial_pdf_reports_the_exact_unread_page(self):
        root = Path(self.store._authority('Portal')[1])
        name = 'cuarenta-y-una.pdf'
        (root/name).write_bytes(pdf_bytes([['Primera parte']]*40+[['Faro-28']]))
        file, = self.store.capture('Portal',[root/name],thread_id='revision')
        self.ids[name]=file['id']
        finding, = self.inspect('Busca «Faro-28».',[name])['findings']
        self.assertEqual(finding['status'],'insufficient')
        self.assertEqual((finding['coverage']['examined_pages'],finding['coverage']['total_pages']),(40,41))
        self.assertIn('Falta la página 41',finding['detail'])

    def test_retirement_is_possible_without_republishing_a_damaged_source(self):
        report = self.inspect('Inspecciona los archivos.', ['notas.md'])
        library = ProjectLibrary(self.store)
        args = dict(project_id='Portal', thread_id='revision', report_id=report['id'], entry_id='nota',
                    kind='memory', title='Nota', body='Contenido original')
        library.change(**args, operation='create', expected_revision=0)
        office, _ = self.store._authority('Portal')
        with self.store._db(office) as db:
            db.execute("UPDATE reports SET payload_sha='dañado' WHERE id=?", (report['id'],))
        with self.assertRaises(Denied):
            library.change(**args, operation='edit', expected_revision=1)
        library.change(**args, operation='retire', expected_revision=1)
        versions = library.history('Portal', 'nota')
        self.assertEqual([(r['retired'], r['revision']) for r in versions], [(1, 2), (0, 1)])
        self.assertEqual(versions[0]['report'], report['id'])

    def test_skill_is_revalidated_at_use_and_history_keeps_later_objectives(self):
        initial = self.inspect('Inspecciona los archivos.', ['notas.md'])
        next_report = self.inspect('Busca «Faro-28» en notas.md.', ['notas.md'])
        hits = self.store.search('Portal', 'FARO-28')
        self.assertEqual([(r['id'],r['thread_id']) for r in hits], [(next_report['id'],'revision')])
        self.assertEqual(self.store.search('Otro proyecto', 'Faro-28'), [])
        library = ProjectLibrary(self.store)
        args = dict(project_id='Portal', thread_id='revision', report_id=initial['id'], entry_id='buscar',
                    kind='skill', title='Buscar', body='Conservar la cita.')
        library.change(**args, operation='create', expected_revision=0)
        with self.assertRaises(Denied):
            library.for_draft('Portal','buscar',1)
        library.change(**args, operation='accept', expected_revision=1)
        self.assertEqual(library.for_draft('Portal','buscar',2)['body'],args['body'])
        library.change(**args, operation='retire', expected_revision=2)
        with self.assertRaisesRegex(Denied,'LIBRARY_ENTRY_RETIRED'):
            library.for_draft('Portal','buscar',2)
