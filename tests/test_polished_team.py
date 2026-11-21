import json
from pathlib import Path
import tempfile
import threading
import types
import unittest

from neural_office.audit import audit_html
from neural_office.ledger import Denied, Ledger
from neural_office.ollama import POLISHED_TEAM, review_profile
from neural_office.runner import ROLES, prompt, run
from neural_office.team_guidance import REPAIR_CHOICES, repair_language
from neural_office.team_session import TeamSession
from tools.measure_v5352_team import grade


MODEL={'mode':'ollama-owned','model':'example:local','model_digest':'b'*64,'num_gpu':0,'num_ctx':8192,
       'num_predict':128,'timeout_seconds':300}
SOURCE=b'<html lang="es"><title>A</title>\n<img src="a"><input id="nombre"></html>'
GOAL='Explica cómo arreglar la imagen y el campo del formulario. Incluye un límite de esta revisión.'


class CitationRubric(unittest.TestCase):
    def test_rule_keeps_its_location_across_markdown_and_prose(self):
        fence = '`' * 3
        block = f'{fence}cpp\nCONTROL_LABEL_CANDIDATE\n{fence}\n\n'
        for answer in (
            block + 'Este código se encuentra en la línea 5, columna 1 del archivo.',
            block.replace('\n', '\r\n') + 'This code is located on line 5, column 1.',
            'CONTROL_LABEL_CANDIDATE\nLINE 5, COLUMN 1',
            'CONTROL_LABEL_CANDIDATE · línea 5 · columna 1',
            'CONTROL_LABEL_CANDIDATE (línea 5, columna 1).',
        ):
            with self.subTest(answer=answer):
                self.assertTrue(all(grade('control', answer).values()))
        for answer in (
            block + 'Este código se encuentra en la línea 4, columna 1.',
            block + 'Este código se encuentra en la línea 5, columna 11.',
            block + 'Otro archivo contiene una excepción en la línea 5, columna 1.',
            block + 'IMAGE_ALT_MISSING, línea 5, columna 1.',
            'CONTROL_LABEL_CANDIDATE, línea 5, columna 1. ERROR, línea 9.',
            'CONTROL_LABEL_CANDIDATE, línea 5, columna 1.\n' + block + 'Este código aparece en la línea 6.',
            'CONTROL_LABEL_CANDIDATE, línea 5, columna 1. Después, CONTROL_LABEL_CANDIDATE (línea 6, columna 1).',
            block + 'Examina el código fuente.',
        ):
            with self.subTest(answer=answer):
                self.assertFalse(grade('control', answer)['cited_location'])


class RecordedEngine:
    """Controllable process stand-in for ordering, cancellation and idle handoff tests only."""
    def __init__(self, job_name, profile, log):
        self.job=types.SimpleNamespace(name=job_name)
        self.profile=profile
        self.started=self.resumed=self.terminated=self.closed=0
        self.block=False
        self.entered=threading.Event()
        self.interrupted=threading.Event()

    def start(self):self.started+=1
    def resume(self):self.resumed+=1
    def terminate(self):self.terminated+=1
    def close(self):self.closed+=1
    def request_stop(self):self.interrupted.set()

    def infer(self, payload):
        if self.block:
            self.entered.set()
            if not self.interrupted.wait(5):raise AssertionError('No stop reached the checked-out runtime')
            raise Denied('BACKEND_CANCELLED_BEFORE_START')
        return {'done':True,'message':{'content':'fixture decision'},'_neural_office_execution':{
            'runtime_instance':self.job.name,'model_digest':self.profile['model_digest'],'owned_job':True,'eval_count':2}}


class PolishedTeam(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root=Path(directory.name)
        self.ledger=Ledger(self.root/'state.sqlite3')
        self.ledger.initialize()
        self.ledger.register('p', self.root)
        self.profile=review_profile(MODEL,7)
        self.pool=TeamSession()
        self.addCleanup(self.pool.close)
        self.created=[]

    def make(self, job, profile, log):
        engine=RecordedEngine(job,profile,log)
        self.created.append(engine)
        return engine

    def reserve(self, key, profile=None):
        return self.ledger.reserve('p',GOAL,SOURCE,profile or self.profile,key,admit=True)

    def execute(self, attempt):
        return run(self.ledger,attempt,7,self.make,team_session=self.pool)

    def test_retention_is_separate_from_termination_and_last_allowance_closes(self):
        for i in range(3):
            attempt=self.reserve(str(i))
            self.assertEqual(self.execute(attempt),'ACCEPTED')
            self.assertEqual(self.execute(attempt),'ACCEPTED')
        self.assertEqual(len(self.created),1)
        engine=self.created[0]
        self.assertEqual((engine.started,engine.resumed,engine.terminated,engine.closed),(1,2,1,1))
        with self.ledger.connection() as db:
            kinds=[r[0] for r in db.execute("SELECT kind FROM events WHERE kind IN ('TEAM_RUNTIME_IDLE','OWNED_JOB_TERMINATED') ORDER BY seq")]
            self.assertEqual(kinds,['TEAM_RUNTIME_IDLE','TEAM_RUNTIME_IDLE','OWNED_JOB_TERMINATED'])
            self.assertEqual(db.execute('SELECT count(*) FROM calls').fetchone()[0],21)
            self.assertIsNone(db.execute('SELECT attempt FROM lease').fetchone()[0])

    def test_cancel_an_active_warm_attempt_discards_only_its_job(self):
        self.execute(self.reserve('cold'))
        engine=self.created[0]
        engine.block=True
        hot=self.reserve('hot')
        answers=[]
        worker=threading.Thread(target=lambda:answers.append(self.execute(hot)))
        worker.start()
        try:
            self.assertTrue(engine.entered.wait(5))
            self.ledger.cancel(hot)
        finally:
            worker.join(10)
        self.assertEqual(answers,['CANCELLED'])
        self.assertEqual((engine.terminated,engine.closed),(1,1))
        self.assertEqual(self.execute(self.reserve('fresh')),'ACCEPTED')
        self.assertEqual(len(self.created),2)
        self.assertEqual(self.created[1].resumed,0)

    def test_stale_timer_scope_switch_shutdown_and_actual_expiry(self):
        engine=RecordedEngine('first',self.profile,None)
        self.assertTrue(self.pool.retain('p',engine,lambda:True))
        old=self.pool._idle
        self.assertIs(self.pool.take('p'),engine)
        self.assertTrue(self.pool.retain('p',engine,lambda:True))
        self.pool._expire(old)
        self.assertEqual(engine.closed,0)
        self.assertIsNone(self.pool.take('different project'))
        self.assertEqual(engine.closed,1)
        stopped=threading.Event()
        expiring=RecordedEngine('ttl',self.profile,None)
        expiring.close=stopped.set
        short=TeamSession(idle_seconds=.05)
        try:
            self.assertTrue(short.retain('scope',expiring,lambda:True))
            self.assertTrue(stopped.wait(3))
            self.assertIsNone(short.take('scope'))
            self.assertEqual(expiring.terminated,1)
        finally:short.close()
        self.pool.close()
        self.assertFalse(self.pool.retain('p',engine,lambda:True))

    def test_unfinished_or_unbound_calls_cannot_settle_as_idle(self):
        a=self.reserve('partial')
        gen=self.ledger.acquire(a,'owned')
        self.assertFalse(self.ledger.release_completed_team(a,gen))
        for role in ROLES:
            seq,_=self.ledger.start_call(a,gen,role,{'role':role},role)
            self.ledger.finish_call(a,gen,seq,{'done':True,'message':{'content':'no runtime proof'}})
        self.assertFalse(self.ledger.release_completed_team(a,gen))
        self.assertEqual(self.ledger.attempt(a)['state'],'RUNNING')
        with self.assertRaisesRegex(Denied,'STALE_LEASE'):
            self.ledger.release_completed_team(a,gen+1)
        self.ledger.release_after_termination(a,gen)

    def test_repairs_depend_on_requested_scope_and_actual_source(self):
        facts=audit_html(SOURCE)
        self.assertEqual(repair_language(GOAL,facts),'es')
        self.assertEqual(repair_language('¿Puedes explicarme paso a paso cómo corregir la imagen y el formulario?',facts),'es')
        self.assertEqual(repair_language('Please explain how to fix the image and the form control.',facts),'en')
        self.assertIsNone(repair_language('No corrijas la imagen y el formulario.',facts))
        self.assertIsNone(repair_language(GOAL+' Incluye además el título.',facts))
        self.assertIsNone(repair_language('¿Puedes corregir la imagen y el formulario y traducir el texto?',facts))
        self.assertIsNone(repair_language(GOAL,audit_html(SOURCE.replace(b'<input id="nombre">',b''))))
        row=dict(profile=self.profile,snapshot=SOURCE,objective=GOAL,outputs=[])
        reply=prompt(row,'integrator')
        self.assertEqual(set(reply['format']['properties']),set(REPAIR_CHOICES['es']))
        for variants in reply['format']['properties'].values():
            self.assertGreaterEqual(len(set(variants['enum'])),2)
        legacy={**self.profile};legacy.pop('team_session')
        self.assertNotIn('format',prompt({**row,'profile':legacy},'integrator'))
        for role in ROLES[:-1]:
            request=prompt({**row,'outputs':[{'role':'director','content':'prior decision','content_sha':'a'*64}]},role)
            self.assertTrue(any('prior decision' in m['content'] for m in request['messages']))
            self.assertGreaterEqual(len(request['format']['enum']),2)

    def test_seven_calls_extend_the_committed_conversation(self):
        row=dict(profile=self.profile,snapshot=SOURCE,objective=GOAL,outputs=[])
        previous=[]
        for index,role in enumerate(ROLES):
            messages=prompt(row,role)['messages']
            self.assertEqual(messages[:len(previous)],previous)
            if index:
                self.assertEqual(messages[-2],{'role':'assistant','content':row['outputs'][-1]['content']})
            row['outputs'].append({'role':role,'content':f'note {index}','content_sha':'a'*64})
            previous=messages

    def test_complete_repair_turn_reuses_its_evidence_and_keeps_every_reply(self):
        snapshot=b'<html>\n<img src="a">\n<input id="nombre">\n</html>'
        notes=[{'role':role,'content':f'decision-{i}','content_sha':'a'*64} for i,role in enumerate(ROLES[:-1])]
        old_profile=dict(self.profile)
        old_profile.pop('repair_context')
        for language, objective in [('es', GOAL), ('en', 'Explain how to fix the image and the form.')]:
            row=dict(profile=self.profile, snapshot=snapshot, objective=objective, outputs=notes)
            current=prompt(row,'integrator')
            old=prompt({**row,'profile':old_profile},'integrator')
            self.assertEqual(current['format'],old['format'])
            self.assertEqual({k:v['enum'] for k,v in current['format']['properties'].items()},
                             {k:list(v) for k,v in REPAIR_CHOICES[language].items()})
            text='\n'.join(m['content'] for m in current['messages'])
            self.assertEqual(text.count(objective),1)
            self.assertIn('IMAGE_ALT_MISSING L2:C1',text)
            self.assertIn('CONTROL_LABEL_CANDIDATE L3:C1',text)
            self.assertIn('HTML_LANGUAGE_MISSING',old['messages'][1]['content'])
            self.assertNotIn('HTML_LANGUAGE_MISSING',text)
            self.assertNotIn('DOCUMENT_TITLE_MISSING',text)
            self.assertEqual([m['content'] for m in current['messages'] if m['role']=='assistant'],
                             [n['content'] for n in notes])
            self.assertTrue(all(text.count(n['content'])==1 for n in notes))
            self.assertIn('"guidance"',old['messages'][-1]['content'])
            # A partial recovery still carries the checked facts and its two latest notes.
            row['outputs']=[notes[0], *notes[2:], notes[1]]
            restored=prompt(row,'integrator')['messages'][-1]['content']
            self.assertIn('"source"',restored)
            self.assertIn('decision-1',restored)

    def test_integrator_can_cite_from_the_full_prefix_without_repeating_the_source(self):
        notes=[{'role':role,'content':f'decision-{i}','content_sha':'a'*64} for i,role in enumerate(ROLES[:-1])]
        old_profile=dict(self.profile)
        old_profile.pop('citation_context')
        for objective in ('Indica el código y la línea del control sin etiqueta en este archivo.',
                          'Give the exact code and line of the unlabelled control.'):
            row=dict(profile=self.profile, snapshot=b'\n'+SOURCE, objective=objective, outputs=notes)
            current=prompt(row,'integrator')
            old=prompt({**row,'profile':old_profile},'integrator')
            self.assertEqual(current['format'],old['format'])
            self.assertEqual([m for m in current['messages'] if m['role']=='assistant'],
                             [m for m in old['messages'] if m['role']=='assistant'])
            for index,role in enumerate(ROLES[:-1]):
                turn={**row,'outputs':notes[:index]}
                request=prompt(turn,role)
                self.assertEqual(current['messages'][:len(request['messages'])],request['messages'])
                self.assertEqual(request['format'],prompt({**turn,'profile':old_profile},role)['format'])
            self.assertIn('CONTROL_LABEL_CANDIDATE L3:C14',current['messages'][1]['content'])
            self.assertNotIn(objective,current['messages'][-1]['content'])
            self.assertIn(objective,old['messages'][-1]['content'])
            shifted=prompt({**row,'snapshot':b'\n\n'+row['snapshot']},'integrator')
            self.assertEqual(shifted['format'],current['format'])
            self.assertRegex(current['messages'][-1]['content'],r'CONTROL_LABEL_CANDIDATE, (línea|line) 3, (columna|column) 14$')
            self.assertRegex(shifted['messages'][-1]['content'],r'CONTROL_LABEL_CANDIDATE, (línea|line) 5, (columna|column) 14$')
