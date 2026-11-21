from contextlib import closing
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest

from examples.multiformat.build_example import pdf_bytes
from neural_office.attachments import AttachmentStore
from neural_office.desktop_service import DesktopService
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

    def test_scope_restrictions_do_not_certify_a_different_question(self):
        cases = (
            'Valida el esquema de valido.json.',
            'Lee el contenido de los archivos sin consultar el de ayer.',
            'Cuenta las páginas de manual.pdf solo si son pertinentes.',
        )
        for objective in cases:
            with self.subTest(objective=objective):
                report = self.inspect(objective, list(self.ids))
                self.assertTrue(all(f['status'] == 'insufficient' for f in report['findings']))
                self.assertTrue(all(not f['sources'] for f in report['findings']))
                self.assertFalse(any(f.get('status') == 'ok' for f in report['attachments']))
        for objective in ('Lee el contenido de notas.md sin consultar valido.json.',
                          'Lee el contenido de los archivos. No leas valido.json.'):
            report = self.inspect(objective,list(self.ids))
            self.assertTrue(any(c['name']=='notas.md' for f in report['findings'] for c in f['sources']))
            self.assertNotIn('valido.json',[f['name'] for f in report['attachments']])
        count, = self.inspect('Cuenta las páginas que mencionan «Ausente» en manual.pdf.',list(self.ids))['findings']
        self.assertEqual((count['status'],count['title']),('observed','0 páginas con «Ausente»'))
        guard, = self.inspect('Cuenta las páginas de manual.pdf solo si contiene «Ausente».',list(self.ids))['findings']
        self.assertEqual((guard['rule'],guard['title']),('condition','La condición no se cumple'))
        literal = self.inspect('Busca «sin consultar» en notas.md.', list(self.ids))
        self.assertEqual(literal['findings'][0]['rule'], 'literal')

    def test_shared_search_verb_keeps_each_phrase_and_target(self):
        report = self.inspect('Busca «Faro-28» en notas.md y «valor» en valido.json.', list(self.ids))
        sources = [f['sources'][0] for f in report['findings']]
        self.assertEqual([s['name'] for s in sources], ['notas.md', 'valido.json'])
        self.assertIn('Faro-28', sources[0]['quote'])
        self.assertIn('valor', sources[1]['quote'])

    def test_attachment_name_does_not_become_an_instruction(self):
        root = Path(self.store._authority('Portal')[1])
        (root/'legal.json').write_text('{"valor": 18}', encoding='utf-8')
        item, = self.store.capture('Portal', [root/'legal.json'], thread_id='revision')
        self.ids['legal.json'] = item['id']
        ordinary = self.inspect('Valida valido.json.', ['valido.json'])['findings']
        named = self.inspect('Valida legal.json.', ['legal.json'])['findings']
        self.assertEqual([f['rule'] for f in named], [f['rule'] for f in ordinary])
        self.assertEqual(named[0]['sources'][0]['name'], 'legal.json')
        explicit = self.inspect('Comprueba la validez legal de legal.json.', ['legal.json'])
        self.assertEqual(explicit['findings'][0]['status'], 'insufficient')

    def test_same_file_refers_only_to_the_immediately_preceding_source(self):
        files = ['valido.json', 'otro.json']
        report = self.inspect('Lee el contenido de valido.json y busca «otra» en ese mismo archivo.', files)
        result, = [f for f in report['findings'] if f['rule'] == 'literal']
        self.assertEqual([s['name'] for s in result['sources']], ['valido.json'])
        self.assertIn('no aparece', result['detail'])
        ambiguous = self.inspect('Busca «otra» en ese mismo archivo.', files)
        self.assertEqual([f['status'] for f in ambiguous['findings']], ['insufficient'])
        self.assertFalse(any(f['sources'] for f in ambiguous['findings']))

    def test_luego_keeps_unfulfilled_part_and_preserves_quoted_literal(self):
        for separator in (', luego ', ' y luego '):
            result = self.inspect('Lee el contenido de notas.md' + separator + 'tradúcelo al francés.', ['notas.md'])
            self.assertEqual([f['status'] for f in result['findings']], ['observed', 'insufficient'])
            self.assertIn('tradúcelo', result['findings'][1]['title'])
        quoted = self.inspect('Busca «Inicio, luego fin» en notas.md.', ['notas.md'])
        self.assertEqual([f['rule'] for f in quoted['findings']], ['literal'])

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
        library.change(**{**args, 'body':'Texto por revisar.'}, operation='propose', expected_revision=2)
        pending = library.for_draft('Portal', 'buscar', 3)
        self.assertEqual((pending['revision'], pending['active_revision'], pending['body']), (3, 2, args['body']))
        library.change(**args, operation='retire', expected_revision=3)
        with self.assertRaisesRegex(Denied,'LIBRARY_ENTRY_RETIRED'):
            library.for_draft('Portal','buscar',2)
        with self.assertRaisesRegex(Denied,'LIBRARY_ENTRY_NOT_FOUND'):
            library.for_draft('Portal', 'sin-entrada', 1)

    def test_saving_the_same_note_preserves_its_revision_after_validating_ownership(self):
        report = self.inspect('Inspecciona los archivos.', ['notas.md'])
        library = ProjectLibrary(self.store)
        args = dict(project_id='Portal', thread_id='revision', report_id=report['id'], entry_id='recordar',
                    kind='memory', title='Nota', body='Revisar los límites.')
        library.change(**args, operation='create', expected_revision=0)
        saved = library.change(**args, operation='edit', expected_revision=1)
        self.assertEqual((saved['revision'], len(library.history('Portal','recordar'))), (1, 1))
        with self.assertRaisesRegex(Denied, 'LIBRARY_SOURCE_CHANGED'):
            library.change(**{**args,'thread_id':'otro'}, operation='edit', expected_revision=1)
        renamed = library.change(**{**args,'title':'Nueva nota'}, operation='edit', expected_revision=1)
        self.assertEqual(renamed['revision'], 2)
        self.assertEqual([r['title'] for r in library.history('Portal','recordar')], ['Nueva nota','Nota'])

    def test_copy_to_draft_is_ordered_with_retirement_and_idempotent_across_lost_ack(self):
        report = self.inspect('Inspecciona los archivos.', ['notas.md'])
        library = ProjectLibrary(self.store)
        core = DesktopService(self.store.ledger)
        self.addCleanup(core.close)
        target = dict(project_id='Portal', thread_id='revision', report_id=report['id'], entry_id='skill',
                      kind='skill', title='Citar', body='Conserva la cita.')
        library.change(**target, operation='create', expected_revision=0)
        library.change(**target, operation='accept', expected_revision=1)
        address = dict(project_id='Portal', thread_id='destino', session_id=core.session_id)
        def call(method, **params):
            return core.dispatch(json.dumps(dict(version=1, id='caso', method=method, params=address | params)).encode())
        draft = call('draft.put', expected_revision=0, edit_id='propio', after_edit='none', text='Texto del autor.')
        intent = dict(entry_id='skill', expected_revision=2, active_revision=2, draft_revision=draft['revision'], edit_id='copia')
        with self.assertRaisesRegex(Denied, 'DRAFT_REVISION_CHANGED'):
            call('library.copy_to_draft', **(intent | {'draft_revision':0}))
        receipt = call('library.copy_to_draft', **intent)
        self.assertNotIn('text', receipt)
        library.change(**target, operation='retire', expected_revision=2)
        self.assertEqual(call('library.copy_to_draft', **intent), receipt)
        applied = call('draft.get')
        self.assertEqual(applied['text'], 'Texto del autor.\nConserva la cita.')
        with self.assertRaisesRegex(Denied, 'LIBRARY_ENTRY_RETIRED'):
            call('library.copy_to_draft', **(intent | {'edit_id':'otra','draft_revision':applied['revision']}))
        self.assertEqual(call('draft.get')['revision'], applied['revision'])

    def test_copy_holds_the_store_write_lock_and_overlong_copy_preserves_the_draft(self):
        report = self.inspect('Inspecciona los archivos.', ['notas.md'])
        library = ProjectLibrary(self.store)
        target = dict(project_id='Portal', thread_id='revision', report_id=report['id'], entry_id='skill',
                      kind='skill', title='Citar', body='Cita la fuente.')
        library.change(**target, operation='create', expected_revision=0)
        library.change(**target, operation='accept', expected_revision=1)
        with library.accepted_instruction('Portal','skill',2,for_copy=True):
            with closing(sqlite3.connect(self.store.path, timeout=0)) as peer:
                with self.assertRaisesRegex(sqlite3.OperationalError,'locked'):
                    peer.execute('BEGIN IMMEDIATE')
        with closing(sqlite3.connect(self.store.path, timeout=0)) as peer:
            peer.execute('BEGIN IMMEDIATE')
        core = DesktopService(self.store.ledger)
        self.addCleanup(core.close)
        original = core._session_draft(core.session_id, 'Portal','destino',0,'A'*1998,'propio','none')
        with self.assertRaisesRegex(Denied, 'LIBRARY_DRAFT_TOO_LONG'):
            core._copy_skill_to_draft(library, core.session_id, 'Portal','destino','skill',2,2,original['revision'],'intento')
        self.assertEqual(core._session_draft(core.session_id, 'Portal','destino'),original)
