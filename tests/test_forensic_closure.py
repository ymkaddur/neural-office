from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from neural_office import diagnostics, excerpt_review, written_answer
from neural_office.audit import requested_rule, verify_report
from neural_office.desktop_service import DesktopService
from neural_office.desktop_stdio import respond
from neural_office.ledger import Denied, Ledger, canonical
from neural_office.legacy import PATHS
from test_legacy import fixture


class Closure(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)

    def test_project_identity_rejects_new_aliases_and_preserves_historical_accounts(self):
        ledger = Ledger(self.root/'office.db')
        ledger.initialize()
        legacy = 'Cafe\u0301'
        with ledger.transaction() as con:
            con.execute('INSERT INTO projects(id,root) VALUES(?,?)', (legacy, ledger.unbound_root(legacy)))
        ledger.register_text(legacy)  # Exact legacy identities remain usable.
        with self.assertRaisesRegex(Denied, 'PROJECT_NAME_CONFLICT'):
            ledger.register_text('Café')
        with self.assertRaisesRegex(Denied, 'NORMALIZATION_REQUIRED'):
            ledger.register(' Otra ', self.root)
        ledger.register_text('Otra')
        with self.assertRaisesRegex(Denied, 'NORMALIZATION_REQUIRED'):
            ledger.register_text('Otra ')
        with ledger.connection() as con:
            self.assertEqual({r[0] for r in con.execute('SELECT id FROM projects')},{legacy,'Otra'})

    def test_legacy_missing_table_and_column_have_structured_cli_reasons(self):
        for index, bad_sql in enumerate(['DROP TABLE meta','ALTER TABLE meta RENAME COLUMN key TO other']):
            root = self.root / str(index)
            fixture(root)
            args = [sys.executable, '-B', '-m','neural_office','--state',str(self.root/'unused.db'),
                    'legacy-inspect',str(root)]
            self.assertEqual(subprocess.run(args,capture_output=True).returncode,0)
            with closing(sqlite3.connect(root/PATHS['v1'])) as con:
                con.execute(bad_sql)
                con.commit()
            result = subprocess.run(args,capture_output=True)
            self.assertEqual(result.returncode,2)
            self.assertEqual(json.loads(result.stderr)['reason'],'LEGACY_SCHEMA_UNSUPPORTED')
            self.assertFalse((self.root/'unused.db').exists())

    def test_diagnostic_publication_is_atomic_and_offline_discovery_is_recorded(self):
        dest = self.root/'reading.json'
        with self.assertRaises(ValueError):
            diagnostics.write_json(dest,{'a':True,'invalid':float('nan')})
        self.assertEqual(list(self.root.iterdir()),[])
        diagnostics.write_json(dest,{'ok':True})
        with self.assertRaises(FileExistsError):
            diagnostics.write_json(dest,{'ok':False})
        self.assertEqual(json.loads(dest.read_bytes()),{'ok':True})
        for command in ('startup','benchmark'):
            folder = self.root / command
            with patch.object(diagnostics,'local_metadata',side_effect=ConnectionRefusedError('private')):
                self.assertEqual(diagnostics.main([command,'--model','ejemplo','--output',str(folder)]),2)
            report = json.loads((folder/'summary.json').read_bytes())
            self.assertEqual((report['trials'],report['status']),([],'metadata_unavailable'))
            self.assertNotIn('private',canonical(report))

    def test_paged_search_and_disclosure_through_public_protocol(self):
        ledger = Ledger(self.root/'office.db')
        core = DesktopService(ledger,model_discovery=lambda: self.fail('read-only operation queried models'))
        self.addCleanup(core.close)
        def rpc(method, **params):
            reply = json.loads(respond(core,canonical(dict(version=1,id='test',method=method,params=params)).encode()))
            self.assertTrue(reply['ok'],reply)
            return reply['result']
        owner = dict(project_id='Proyecto',thread_id='hilo')
        ids = {rpc('attachments.inspect',**owner,attachment_ids=[],objective=f'Encargo público {i}')['id']
               for i in range(34)}
        def page(cursor):
            return rpc('attachments.search.page',project_id=owner['project_id'],query='público',before=cursor)
        first = page('')
        self.assertEqual(len(first['items']),30)
        rpc('attachments.inspect',**owner,attachment_ids=[],objective='Encargo público adicional')
        second = page(first['next_before'])
        self.assertEqual(len(second['items']),4)
        self.assertEqual(second['next_before'],'')
        self.assertEqual(ids,{row['id'] for row in first['items'] + second['items']})
        rid = first['items'][0]['id']
        report = core.attachments.report(owner['project_id'],rid,thread_id=owner['thread_id'])
        snapshot, fragments = excerpt_review.capture_excerpts(report,*owner.values())
        size = rpc('attachments.scope',**owner,report_id=rid)
        self.assertEqual((size['allowed'],size['reason'],size['bytes'],size['fragments']),
                         (True,None,len(snapshot),len(fragments)))
        with self.assertRaises(Denied):
            core.inspection_scope('Proyecto','vecino',rid)
        self.assertFalse(core._approvals)
        self.assertEqual(core.snapshot()['attempts'],[])

    def test_measured_scope_rejects_oversized_or_absent_sources_before_approval(self):
        report = {'id':'x','objective':'Ejemplo','attachments':[{'id':'1','kind':'text','name':'ø.txt','sha256':'a'*64}],
                  'findings':[{'sources':[]}]}
        tokens = report['findings'][0]['sources']
        for sources, reason in [([], 'NO_CITED_EXCERPTS'),(['é'*3000], 'EXCERPT_BUDGET'),
                                ([f'Cita {i}' for i in range(9)],'EXCERPT_BUDGET'),(['válida'],None)]:
            tokens[:] = [dict(attachment_id='1',quote=s) for s in sources]
            size = excerpt_review.scope_size(report,'p','t')
            self.assertEqual((size['fragments'], size['allowed'],size['reason']), (len(sources),reason is None,reason))
            if reason:
                with self.assertRaisesRegex(Denied,reason):
                    excerpt_review.capture_excerpts(report,'p','t')
            else:
                self.assertEqual(size['bytes'],len(excerpt_review.capture_excerpts(report,'p','t')[0]))

    def test_written_answers_have_independent_oracles_and_keep_raw_and_legacy_receipts(self):
        for a,b in [(47,12),(19,3),(56,6),(0,0),(2,14)]:
            for text in (f'El total es {a} y salen {b}. ¿Cuántas unidades quedan? Contesta con la cantidad.',
                         f'Tengo {a} entradas y regalo {b}. ¿Cuántas conservo?',f'Calcula {a} − {b}.'):
                self.assertEqual(written_answer.contract(text)['answer'],str(a-b))
        for text, answer in [('¿Cuánto es 83+9?','92'),('Di solamente PERLA.','PERLA'),
                             ('En el acta el color elegido es verde. Di solamente el color elegido.','verde')]:
            report={'id':'i','objective':text,'attachments':[],'findings':[{'rule':'text_brief'}]}
            snapshot,_=excerpt_review.capture_excerpts(report,'p','h')
            for raw in [answer,'Respuesta distinta']:
                outputs=[dict(role='director',content=raw)]
                artifact=excerpt_review.make_report(snapshot,outputs)
                body=json.loads(artifact)
                self.assertTrue(excerpt_review.verify_report(snapshot,artifact)['passed'])
                self.assertEqual(body['answer_check']['matches'],raw==answer)
                self.assertEqual(body['answer_check']['answer'],answer)
                self.assertEqual(body['role_outputs'],outputs)
                body['answer_check']['answer']='forzado'
                self.assertFalse(excerpt_review.verify_report(snapshot,canonical(body).encode())['passed'])
            legacy=json.loads(snapshot)
            del legacy['answer_check_version']
            self.assertNotIn('answer_check',json.loads(excerpt_review.make_report(canonical(legacy).encode(),outputs)))
        for ambiguity in ['El total es 47 y salen 12 o 14. ¿Cuántas unidades quedan?',
                          'Di solamente cuál.', 'Calcula 2 + 3 y explícalo.', '¿Cuánto es 2 + 3 por persona?']:
            self.assertIsNone(written_answer.contract(ambiguity))

    def test_requested_locations_are_bound_to_the_task_and_source_across_replay(self):
        from neural_office.runner import run
        from test_v52 import FakeBackend, PROFILE
        source = b'<html lang="en"><title>Portal</title>\n<img src="portal.png">\n</html>'
        objective = 'Indica el código exacto de la imagen sin descripción y su línea en el archivo.'
        rule = 'IMAGE_ALT_MISSING'
        self.assertEqual(requested_rule(objective),rule)
        self.assertIsNone(requested_rule('Dime el código y línea de IMAGE_ALT_MISSING y HTML_LANGUAGE_MISSING.'))
        self.assertIsNone(requested_rule('Explica las limitaciones de la revisión.'))
        ledger=Ledger(self.root/'rules.db')
        ledger.initialize()
        ledger.register('Portal',self.root)
        profile={**PROFILE,'roles':7}
        identity=ledger.reserve('Portal',objective,source,profile,'same-key',admit=True)
        self.assertEqual(run(ledger,identity,7,FakeBackend),'ACCEPTED')
        row=ledger.attempt(identity)
        result=json.loads(row['artifact'])
        self.assertEqual(result['requested_rule'],rule)
        self.assertEqual([f for f in result['findings'] if f['code']==rule],[dict(code=rule,line=2,column=1)])
        self.assertEqual(len(result['role_outputs']),7)
        self.assertEqual(ledger.reserve('Portal',objective,source,profile,'same-key',admit=True),identity)
        self.assertFalse(verify_report(source,row['artifact'])['passed'])
        result['requested_rule']='HTML_LANGUAGE_MISSING'
        self.assertFalse(verify_report(source,canonical(result).encode(),rule)['passed'])
