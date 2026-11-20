from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
import hashlib
import json
import os
import tempfile
import unittest
import wave
from zipfile import ZipFile

from neural_office.attachment_formats import classify, read
from neural_office.attachments import AttachmentStore
from neural_office.ledger import Denied, Ledger, canonical, digest
from neural_office.project_library import ProjectLibrary
from neural_office.team_review import ROLES
from examples.multiformat.build_example import pdf_bytes


def package(parts):
    stream = BytesIO()
    with ZipFile(stream, 'w') as zip_file:
        for name, body in parts.items():
            zip_file.writestr(name, body)
    return stream.getvalue()


class GeneralReaderTests(unittest.TestCase):
    def test_any_extension_text_or_opaque(self):
        for name, data, expected in [
            ('README', 'café'.encode(), 'café'),
            ('requisitos.md', 'Primera respuesta'.encode('utf-16'), 'Primera respuesta'),
            ('datos.csv', b'campo,valor\nplazo,48\n', 'plazo,48'),
            ('servicio.py', b'print("contenido")', 'print("contenido")'),
            ('dibujos.svg', b'<svg></svg>', '<svg></svg>'),
        ]:
            with self.subTest(name=name):
                result = read(classify(name, data), data)
                self.assertEqual(result['status'], 'ok')
                self.assertIn(expected, result['text'])
        data = bytes(range(37))
        binary = read(classify('archivo.desconocido',data), data)
        self.assertEqual((binary['status'], binary['bytes']), ('metadata', 37))
        self.assertEqual(bytes.fromhex(binary['signature']), data[:32])
        self.assertNotIn('text', binary)

    def test_office_families_and_zip_limits(self):
        cases = (
            ('documento.docx', {'word/document.xml':'<document><p><r><t>Alcance real</t></r></p></document>'},'Alcance real'),
            ('diapositivas.pptx', {'ppt/slides/slide10.xml':'<root><p><t>Última</t></p></root>',
                                   'ppt/slides/slide2.xml':'<root><p><t>Antes</t></p></root>'}, 'Antes\nÚltima'),
            ('coste.xlsx', {'xl/sharedStrings.xml':'<sst><si><t>Coste</t></si></sst>',
                            'xl/worksheets/sheet1.xml':'<worksheet><sheetData><row><c r="B1" t="s"><v>0</v></c><c r="B2"><v>12</v></c></row></sheetData></worksheet>'},'B1  Coste'),
            ('notas.odt',{'content.xml':'<office><p>Notas de trabajo</p></office>'},'Notas de trabajo'),
            ('tabla.ods',{'content.xml':'<office><p>31</p></office>'},'31'),
            ('charla.odp',{'content.xml':'<office><p>Agenda</p></office>'},'Agenda'),
        )
        for name, parts, expected in cases:
            with self.subTest(name=name):
                data=package(parts)
                kind=classify(name,data)
                self.assertEqual(kind,Path(name).suffix[1:])
                result=read(kind,data)
                self.assertEqual(result['status'],'ok')
                self.assertIn(expected,result['text'])
        data=package({'not-the-document.xml':'hello'})
        self.assertEqual(read('docx',data)['status'],'invalid')

    def test_audio_and_a_file_without_a_suffix(self):
        audio=BytesIO()
        with wave.open(audio,'wb') as w:
            w.setparams((1,2,8000,0,'NONE','not compressed'))
            w.writeframes(b'\0'*16000)
        data=audio.getvalue()
        self.assertEqual(classify('voice',data),'wav')
        self.assertIn('8000 Hz',read('wav',data)['detail'])
        self.assertEqual(read('wav', data[:-4])['status'], 'invalid')
        damaged_rate = data[:24] + bytes(4) + data[28:]
        self.assertEqual(read('wav', damaged_rate)['status'], 'invalid')
        self.assertEqual(read('other',b'plain text')['text'],'plain text')


@unittest.skipUnless(os.name=='nt','Windows local capture')
class OfficeWorkflowTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)
        self.ledger=Ledger(self.root/'office.db')
        self.ledger.initialize()
        self.store=AttachmentStore(self.ledger)
        self.project='Entregas'
        self.thread='principal'
        f=self.root/'decisiones.md'
        f.write_text('Conservar el plazo de 24 horas.',encoding='utf-8')
        b=self.root/'fotometria.medicion'
        b.write_bytes(bytes(range(60)))
        files=self.store.capture(self.project,[f,b],thread_id=self.thread)
        self.ids=[f['id'] for f in files]

    def inspect(self):
        return self.store.inspect(self.project,self.ids,'Inspecciona los archivos.',thread_id=self.thread)

    def test_receipts_real_inputs_reopen_and_ledger(self):
        report=self.inspect()
        team=report['team']
        self.assertEqual([r['role'] for r in team['receipts']], list(ROLES)*3)
        self.assertEqual([r['round'] for r in team['receipts']], [1]*6+[2]*6+[3]*6)
        previous=None
        for row in team['receipts']:
            self.assertEqual(row['parent'], previous)
            previous=digest(canonical([row['round'], row['role'], previous, report['objective'], row['action'], row['details']]))
            self.assertEqual(row['sha256'],previous)
        self.assertIn('24 horas', ' '.join(team['delivery']['results']))
        self.assertTrue(team['delivery']['limitations'])
        self.assertEqual(digest(canonical(team['delivery'])),team['delivery_sha256'])
        reopened=AttachmentStore(self.ledger).report(self.project,report['id'],thread_id=self.thread)
        self.assertEqual(reopened['team'],team)
        self.assertEqual(self.inspect()['team'],team)
        with self.ledger.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM calls').fetchone()[0],0)

    def test_nonstandard_large_file_keeps_only_a_verified_identity(self):
        path=self.root/'camera.recording'
        chunk=bytes(range(256))*4096
        sha=hashlib.sha256()
        with path.open('wb') as f:
            for _ in range(9):
                f.write(chunk)
                sha.update(chunk)
        item,=self.store.capture(self.project,[path],thread_id=self.thread)
        self.assertEqual((item['kind'],item['bytes'],item['sha256']),('identity',9*len(chunk),sha.hexdigest()))
        path.unlink()
        view=self.store.preview(self.project,item['id'],thread_id=self.thread)
        self.assertEqual(view['status'],'metadata')
        self.assertEqual(bytes.fromhex(view['signature']),chunk[:32])
        self.assertNotIn('text',view)
        office,_=self.store._authority(self.project)
        with self.store._db(office) as db:
            self.assertEqual(db.execute('SELECT length(content) FROM captures WHERE id=?',(item['id'],)).fetchone()[0],32)

    def test_literal_search_and_tampered_receipt(self):
        report=self.store.inspect(self.project,self.ids,'Busca «24 horas» en los archivos.',thread_id=self.thread)
        by_name={r['title']:r for r in report['findings']}
        self.assertEqual(by_name['decisiones.md']['sources'][0]['line'],1)
        self.assertIn('24 horas',by_name['decisiones.md']['sources'][0]['quote'])
        self.assertEqual(by_name['fotometria.medicion']['status'],'insufficient')
        office,_=self.store._authority(self.project)
        with self.store._db(office) as db:
            report['team']['receipts'][0]['details']=['He pasado doce pruebas.']
            changed=canonical(report)
            db.execute('UPDATE reports SET payload=?,payload_sha=? WHERE id=?',(changed,digest(changed),report['id']))
        with self.assertRaisesRegex(Denied,'INTEGRITY'):
            self.store.report(self.project,report['id'],thread_id=self.thread)

    def test_director_greets_and_requests_clarification_without_delegating(self):
        for question, rule in [('¡Hola, Director!', 'greeting'), ('Buenos días.', 'greeting'),
                               ('Qué puedes hacer?', 'greeting'), ('Resuelve lo de ayer.', 'scope')]:
            with self.subTest(question=question):
                report = self.store.inspect(self.project, self.ids, question, thread_id=self.thread)
                self.assertEqual(report['findings'][0]['rule'], rule)
                self.assertNotIn('team', report)
                self.assertEqual(report['model_calls'], 0)
                self.assertEqual(self.store.report(self.project, report['id'], thread_id=self.thread)['findings'], report['findings'])

    def test_literal_search_identifies_the_second_pdf_page(self):
        document = self.root / 'acta.pdf'
        document.write_bytes(pdf_bytes([['Convocatoria'], ['El plazo aprobado es de 72 horas.']]))
        captured, = self.store.capture(self.project, [document], thread_id=self.thread)
        result = self.store.inspect(self.project, [captured['id']], 'Busca «72 horas».', thread_id=self.thread)
        source, = result['findings'][0]['sources']
        self.assertEqual(source['name'], 'acta.pdf')
        self.assertEqual(source['page'], 2)
        self.assertIn('72 horas', source['quote'])

    def test_library_provenance_revisions_scope_and_competing_accept(self):
        report=self.inspect()
        library=ProjectLibrary(self.store)
        base=dict(project_id=self.project,thread_id=self.thread,report_id=report['id'],entry_id='revision',kind='skill',title='Citar la fuente')
        def change(op, revision, body=''):
            return library.change(**base,body=body,operation=op,expected_revision=revision)
        change('create',0,'Cita la fuente y la página.')
        self.assertEqual(library.read(self.project)[0]['body'],'')
        def accept():
            try:
                return change('accept',1)['revision']
            except Denied as exc:
                return str(exc)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(lambda _:accept(),range(2)))
        self.assertCountEqual(outcomes,[2,'LIBRARY_REVISION_CHANGED'])
        change('propose',2,'Cita también la hoja.')
        self.assertEqual(library.read(self.project)[0]['body'],'Cita la fuente y la página.')
        change('discard',3)
        change('retire',4)
        saved=ProjectLibrary(AttachmentStore(self.ledger))
        self.assertEqual(saved.read(self.project)[0]['retired'],1)
        self.assertEqual([r['revision'] for r in saved.history(self.project,'revision')],[5,4,3,2,1])
        self.assertEqual(saved.read('Otro'),[])
        with self.assertRaises(Denied):
            library.change(**{**base,'thread_id':'otro','entry_id':'intruso'},operation='create',expected_revision=0,body='Texto')
