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


MODEL={'mode':'ollama-owned','model':'example:local','model_digest':'b'*64,'num_gpu':0,'num_ctx':8192,
       'num_predict':128,'timeout_seconds':300}
SOURCE=b'<html lang="es"><title>A</title>\n<img src="a"><input id="nombre"></html>'
GOAL='Explica cómo arreglar la imagen y el campo del formulario. Incluye un límite de esta revisión.'


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
            self.assertIn('prior decision',request['messages'][-1]['content'])
            self.assertGreaterEqual(len(request['format']['enum']),2)
