from hashlib import sha256
from io import BytesIO
import unittest
import unicodedata
from zipfile import ZipFile

from PIL import Image

from neural_office.attachment_formats import read
from neural_office.inspection_intent import literal_findings
from neural_office.inspection_plan import plan, read_plan
from neural_office.team_review import review, verify_saved


def package(parts):
    data = BytesIO()
    with ZipFile(data,'w') as archive:
        for key,value in parts.items():
            archive.writestr(key,value)
    return data.getvalue()


class ReaderSemantics(unittest.TestCase):
    def test_json_limits_and_ambiguity_leave_the_value_undecided(self):
        for level,status in ((39,'ok'),(40,'ok'),(41,'limit')):
            value=read('json',b'['*level+b'1'+b']'*level)
            self.assertEqual(value['status'],status)
        duplicated=read('json',b'{"response_sla_hours":24,\n"response_sla_hours":48}')
        self.assertEqual((duplicated['status'],duplicated['line'],duplicated['column']),('ambiguous',2,1))
        self.assertNotIn('hours',duplicated)
        self.assertEqual(read('json',b'{"a":2,}')['status'],'invalid')

    def test_presentation_order_follows_relationships(self):
        slide=lambda text:f'<slide><p><t>{text}</t></p></slide>'
        parts={'ppt/slides/slide1.xml':slide('Conclusión'),'ppt/slides/slide9.xml':slide('Inicio'),
               'ppt/_rels/presentation.xml.rels':'<Relationships><Relationship Id="a" Type="document/slide" Target="slides/slide1.xml"/><Relationship Id="b" Type="document/slide" Target="slides/slide9.xml"/></Relationships>'}
        for sequence,expected in ((('b','a'),'Inicio\nConclusión'),(('a','b'),'Conclusión\nInicio'),(('a',),'Conclusión')):
            parts['ppt/presentation.xml']='<pres xmlns:r="urn:rels"><sldIdLst>'+''.join(f'<sldId r:id="{r}"/>' for r in sequence)+'</sldIdLst></pres>'
            self.assertEqual(read('pptx',package(parts),mode='inspect')['text'],expected)
        parts['ppt/presentation.xml']='<pres xmlns:r="urn:rels"><sldIdLst><sldId r:id="c"/></sldIdLst></pres>'
        self.assertEqual(read('pptx',package(parts))['status'],'invalid')

    def test_word_text_box_and_odf_spaces_or_typed_value(self):
        body='<document><p><r><t>A</t></r><drawing><p><r><t>B</t></r></p></drawing><r><t>C</t><tab/><t>D</t></r></p></document>'
        self.assertEqual(read('docx',package({'word/document.xml':body}))['text'],'A\nB\nC\tD')
        ns=('xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
            'xmlns:t="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
            'xmlns:o="urn:oasis:names:tc:opendocument:xmlns:office:1.0"')
        doc=f'<doc {ns}><text:p>un<text:s text:c="3"/>dos<text:tab/>tres</text:p></doc>'
        self.assertEqual(read('odt',package({'content.xml':doc}))['text'],'un   dos\ttres')
        sheet=f'<doc {ns}><t:table-cell o:value="17"/><t:table-cell o:value="17"><text:p>17 visible</text:p></t:table-cell></doc>'
        self.assertEqual(read('ods',package({'content.xml':sheet}))['text'],'17\n17 visible')

    def test_zip_proposes_only_members_a_reader_can_open(self):
        buffer=BytesIO()
        Image.new('RGB',(5,7)).save(buffer,format='GIF')
        raw=buffer.getvalue()
        wrapped=package({'vista.gif':raw,'sin.bin':b'123','paquete.zip':package({'nota.txt':'A'})})
        visible=read('zip',wrapped)
        self.assertEqual([e['readable'] for e in visible['entries']],[True,False,False])
        inner=read('zip',wrapped,member='vista.gif')
        self.assertEqual((inner['width'],inner['height'],inner['member_sha256']),(5,7,sha256(raw).hexdigest()))
        self.assertEqual(read('zip',package({'falsa.gif':b'normal text'}),member='falsa.gif')['status'],'invalid')


class RequestSemantics(unittest.TestCase):
    def setUp(self):
        self.files=[dict(id=name,name=name,kind=kind,sha256=str(i)) for i,(name,kind) in enumerate(
            [('uno.txt','text'),('café.md','text'),('a.json','json'),('b.json','json'),('imagen.gif','gif'),('libro.ods','ods')])]

    def test_binding_of_names_groups_and_ordinals(self):
        ids=lambda q:plan(q,self.files)[0].sources
        self.assertEqual(ids('Valida a.json y todos los JSON.'),('a.json','b.json'))
        self.assertEqual(ids('Valida el JSON a.json.'),('a.json',))
        self.assertEqual(ids('Lee el segundo adjunto.'),('café.md',))
        self.assertTrue(plan('Lee el octavo adjunto.',self.files)[0].limit)
        self.assertEqual(ids('Lee la hoja de cálculo.'),('libro.ods',))
        self.assertEqual(ids('Mide las dimensiones del GIF.'),('imagen.gif',))
        merged=unicodedata.normalize('NFD','café.md')
        self.assertEqual(ids(f'Busca X en {merged}.'),('café.md',))
        self.assertTrue(plan(f'Busca X en {merged}.',self.files+[dict(name=merged,kind='text',id='otro')])[0].limit)

    def test_scope_and_literals_are_independent(self):
        neg=plan('Lee todos los archivos. No leas a.json.',self.files)
        self.assertNotIn('a.json',neg[0].sources)
        self.assertEqual(neg[0].excluded,('a.json',))
        self.assertFalse(read_plan(plan('Lee los adjuntos excepto los que hablan de ayer.',self.files),self.files))
        self.assertFalse(read_plan(plan('Lee los adjuntos excepto a.json si es válido.',self.files),self.files))
        exact=plan('Busca «sin consultar» en uno.txt.',self.files)[0]
        self.assertEqual((exact.phrase,exact.excluded),('sin consultar',()))
        q=plan('Busca X en uno.txt; p. ej., muestra el contenido de a.json.',self.files)
        self.assertEqual([v.action for v in q],['literal','general'])
        self.assertEqual(plan('En uno.txt, busca X.',self.files)[0].sources,('uno.txt',))
        self.assertNotEqual(plan('¿Qué significa el riesgo alto en uno.txt?',self.files)[0].action,'dimensions')
        self.assertEqual(plan('Mide el alto en píxeles del GIF.',self.files)[0].action,'dimensions')
        domain=plan('Comprueba si uno.txt menciona example.com.',self.files)[0]
        self.assertEqual((domain.action,domain.phrase,domain.sources),('literal','example.com',('uno.txt',)))
        self.assertTrue(plan('Lee el archivo example.com.',self.files)[0].limit)
        self.assertEqual(plan('Resume el contenido de uno.txt.',self.files)[0].action,'summary')

    def test_multiple_offsets_absence_and_partial_pdf(self):
        item=self.files[0]
        views={item['id']:dict(text='CAFE\u0301 café Café\nfin')}
        def run(phrase,modifier=''):
            return literal_findings(phrase,[item],views,modifier=modifier)[0]
        matches=run('café','all')
        self.assertEqual([c['column'] for c in matches['sources']],[1,7,12])
        self.assertIn('CAFE\u0301',matches['sources'][0]['quote'])
        self.assertEqual(run('cafe','absent')['status'],'observed')
        self.assertEqual(run('café','absent')['status'],'mismatch')
        views[item['id']].update(text='una palabra',text_truncated=True)
        self.assertEqual(run('ausente','absent')['status'],'insufficient')
        views[item['id']].update(text='A '*12,text_truncated=False)
        many=run('A','all')
        self.assertEqual(len(many['sources']),8)
        self.assertIn('12 coincidencias',many['detail'])
        pdf=dict(item,kind='pdf')
        view=dict(text='clave',page_texts=[dict(page=2,text='clave clave'),dict(page=4,text='clave')],pages=4,
                  pages_examined=4,pages_with_text=2,image_pages=[1],text_truncated=True)
        found=literal_findings('clave',[pdf],{item['id']:view},modifier='pages_containing')[0]
        self.assertEqual((found['status'],[c['page'] for c in found['sources']]),('insufficient',[2,4]))

    def test_integrator_distinguishes_selected_read_and_cited(self):
        files=[dict(self.files[0],status='ok'),dict(self.files[1],status='ok'),self.files[2]]
        one=dict(attachment_id=files[0]['id'],name=files[0]['name'],sha256=files[0]['sha256'],kind='text',quote='A')
        findings=[dict(title='A',detail='Hallado',rule='literal',status='observed',sources=[one])]
        def report(legacy):
            team=review('Busca A',files,findings,['literal'],lambda:False,legacy_sources=legacy)
            verify_saved(dict(rule_version='local-inspection-8' if legacy else 'local-inspection-9',objective='Busca A',team=team,attachments=files,findings=findings))
            return team
        current,previous=report(False),report(True)
        self.assertEqual([len(current['delivery'][key]) for key in ('captures','reads','sources')],[3,2,1])
        self.assertEqual(len(previous['delivery']['sources']),3)
        self.assertNotIn('captures',previous['delivery'])
        self.assertIn('Citadas: 1',current['receipts'][-1]['details'][0])
