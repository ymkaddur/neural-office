"""Synthetic historical schemas; no private history or legacy code is required."""
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from neural_office.ledger import Ledger, Denied, canonical, digest
from neural_office.legacy import PATHS, CATALOG, PRODUCTS, reconcile, rebind, snapshot
from neural_office.continuity import backup, restore
from neural_office.runner import run
from test_v52 import HTML, PROFILE, FakeBackend


def fixture(root, runs=1, active=True, armed=True):
    root.mkdir()
    for key in ('v1','v4','plus'):
        (root/PATHS[key]).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(root/PATHS['v1'])) as con:
        con.executescript('CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE projects(id TEXT PRIMARY KEY,location TEXT,state TEXT,cycle INTEGER,certified_versions INTEGER); CREATE TABLE events(seq INTEGER PRIMARY KEY,stamp TEXT,action TEXT,project TEXT,payload TEXT);')
        con.executemany('INSERT INTO meta VALUES(?,?)', [('schema','studio-v1'),('root',str(root))])
        con.execute('INSERT INTO events VALUES(1,?,?,NULL,?)', ('synthetic-timestamp','CATALOG_INITIALIZED','{"projects":6}'))
        for p in sorted(CATALOG):
            loc=root/'studio/workspaces'/p; loc.mkdir(parents=True)
            con.execute('INSERT INTO projects VALUES(?,?,?,0,0)', (p,str(loc),'active' if active and p=='web-auditor' else 'parked'))
        con.commit()
    with closing(sqlite3.connect(root/PATHS['v4'])) as con:
        con.executescript('CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT); CREATE TABLE project(name TEXT PRIMARY KEY,state TEXT,cycle INTEGER,authorized_max INTEGER); CREATE TABLE task(id TEXT PRIMARY KEY,project TEXT); CREATE TABLE audit(seq INTEGER,ts TEXT,actor TEXT,event TEXT,payload TEXT,previous_hash TEXT,entry_hash TEXT);')
        con.execute("INSERT INTO meta VALUES('schema','4')")
        for p in sorted(CATALOG):
            con.execute('INSERT INTO project VALUES(?,?,0,?)', (p,'armed' if armed and p=='web-auditor' else 'parked',3 if armed and p=='web-auditor' else 0))
        con.commit()
    with closing(sqlite3.connect(root/PATHS['plus'])) as con:
        con.executescript('CREATE TABLE events(seq INTEGER PRIMARY KEY,project TEXT,kind TEXT,body TEXT,sha256 TEXT); CREATE TABLE tasks(id TEXT); CREATE TABLE evaluations(id TEXT);')
        for n in range(runs):
            for offset,kind in enumerate(('DIRECTOR_MESSAGE','RUN_STARTED','ANSWER','RUN_RECEIPT')):
                body=canonical({'synthetic':True,'operation':n,'event':kind})
                con.execute('INSERT INTO events VALUES(?,?,?,?,?)', (n*4+offset+1,'web-auditor',kind,body,digest(body)))
        con.commit()


class Legacy(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.source=self.root/'historical'
        fixture(self.source)
        self.ledger=Ledger(self.root/'destination.sqlite3');self.ledger.initialize()

    def info(self):
        return next(p for p in self.ledger.status()['projects'] if p['id']=='web-auditor')

    def reserve(self,key):
        return self.ledger.reserve('web-auditor','Audit the historical project fixture.',HTML,PROFILE,key,admit=True)

    def mutate(self,key,sql,args=()):
        with closing(sqlite3.connect(self.source/PATHS[key])) as con:
            con.execute(sql,args);con.commit()

    def test_observed_operation_is_not_zero_or_a_certified_report(self):
        reconcile(self.ledger,self.source)
        p=self.info()
        self.assertEqual((p['attempts_consumed'],p['legacy_consumed'],p['verified_versions'],p['active'],p['approved']),(1,1,0,False,False))
        self.assertEqual(len(self.ledger.status()['projects']),5)

    def test_both_authority_divergences_deny_admission(self):
        for v1,v4 in [('active','parked'),('parked','armed')]:
            self.mutate('v1',"UPDATE projects SET state=? WHERE id='web-auditor'",(v1,))
            self.mutate('v4',"UPDATE project SET state=? WHERE name='web-auditor'",(v4,))
            reconcile(self.ledger,self.source)
            with self.assertRaisesRegex(Denied,'AUTHORITY_DIVERGENCE'):self.reserve(v1)
            self.assertEqual(self.info()['attempts_consumed'],1)

    def test_imported_credit_plus_two_failures_exhausts_budget(self):
        reconcile(self.ledger,self.source)
        for key in ('one','two'):self.ledger.cancel(self.reserve(key))
        self.assertEqual((self.info()['attempts_consumed'],self.info()['active']),(3,False))
        with self.assertRaisesRegex(Denied,'BUDGET_EXHAUSTED'):self.reserve('three')
        self.assertEqual([a['ordinal'] for a in self.ledger.status()['attempts']],[2,3])

    def test_parked_authority_not_overridden_by_audit_admission(self):
        self.mutate('v1',"UPDATE projects SET state='parked'")
        self.mutate('v4',"UPDATE project SET state='parked'")
        reconcile(self.ledger,self.source)
        with self.assertRaisesRegex(Denied,'AUTHORITY_NOT_GRANTED'):self.reserve('one')

    def test_partial_certified_allowance_does_not_become_three_attempts(self):
        for allowance in (0,1,2):
            self.mutate('v4',"UPDATE project SET authorized_max=? WHERE name='web-auditor'",(allowance,))
            reconcile(self.ledger,self.source)
            with self.assertRaisesRegex(Denied,'ALLOWANCE_REQUIRES_MAPPING'):self.reserve(str(allowance))
        self.assertEqual(self.info()['attempts_consumed'],1)

    def test_second_start_under_one_authorization_is_not_silently_deduplicated(self):
        for seq,kind in ((5,'RUN_STARTED'),(6,'RUN_RECEIPT')):
            body=canonical({'synthetic':True,'repeated':kind})
            self.mutate('plus','INSERT INTO events VALUES(?,?,?,?,?)',(seq,'web-auditor',kind,body,digest(body)))
        with self.assertRaisesRegex(Denied,'GROUPED_INVOCATIONS_REQUIRE_MAPPING'):
            reconcile(self.ledger,self.source)

    def test_reconciliation_is_idempotent_and_never_refunds(self):
        reconcile(self.ledger,self.source);self.ledger.cancel(self.reserve('one'))
        reconcile(self.ledger,self.source)
        self.assertEqual(self.info()['attempts_consumed'],2)
        self.mutate('plus','DELETE FROM events')
        with self.assertRaisesRegex(Denied,'BUDGET_REGRESSION'):reconcile(self.ledger,self.source)
        self.assertEqual(self.info()['attempts_consumed'],2)

    def test_changed_source_denies_call_and_reports_interruption(self):
        reconcile(self.ledger,self.source);attempt=self.reserve('one')
        generation=self.ledger.acquire(attempt,'synthetic-no-backend')
        self.mutate('v1',"UPDATE projects SET state='parked'")
        self.assertIn('LEGACY_AUTHORITY_UNAVAILABLE',self.ledger.interruption_reason(attempt))
        with self.assertRaisesRegex(Denied,'SOURCE_CHANGED'):
            self.ledger.start_call(attempt,generation,'director',{},'one')
        self.ledger.release_after_termination(attempt,generation,failed=True)
        self.assertEqual(self.ledger.attempt(attempt)['state'],'FAILED')

    def test_replay_after_revocation_does_not_renew_authority(self):
        reconcile(self.ledger,self.source);attempt=self.reserve('one');self.ledger.cancel(attempt)
        self.mutate('v1',"UPDATE projects SET state='parked'")
        self.assertEqual(self.reserve('one'),attempt)
        self.assertEqual(self.info()['attempts_consumed'],2)

    def test_missing_source_is_not_treated_as_zero(self):
        (self.source/PATHS['v4']).rename(self.source/'retained-v4.sqlite3')
        with self.assertRaisesRegex(Denied,'SOURCE_MISSING'):reconcile(self.ledger,self.source)
        self.assertEqual(self.ledger.status()['projects'],[])

    def test_source_writer_prevents_inconsistent_capture(self):
        with (self.source/PATHS['v1']).open('r+b'):
            with self.assertRaisesRegex(Denied,'WRITER_OR_SOURCE'):reconcile(self.ledger,self.source)

    def test_existing_historical_root_cannot_bypass_reconciliation(self):
        with self.assertRaisesRegex(Denied,'RECONCILE_REQUIRED'):
            self.ledger.register('renamed',self.source/'studio/workspaces/web-auditor')

    def test_rebind_copy_preserves_identity_and_reserves_old_root(self):
        reconcile(self.ledger,self.source);self.ledger.cancel(self.reserve('one'))
        copied=self.root/'copy';copied.mkdir()
        rebind(self.ledger,'web-auditor',copied)
        self.assertEqual(self.info()['attempts_consumed'],2)
        self.assertFalse(self.info()['approved'])
        for root in (copied,self.source/'studio/workspaces/web-auditor'):
            with self.assertRaisesRegex(Denied,'ROOT_ALREADY_BOUND'):self.ledger.register('different-id',root)
        self.ledger.cancel(self.reserve('two'))
        self.assertEqual(self.info()['attempts_consumed'],3)

    def test_certified_versions_are_not_guessed_as_attempts(self):
        self.mutate('v1',"UPDATE projects SET certified_versions=1 WHERE id='web-auditor'")
        with self.assertRaisesRegex(Denied,'HISTORY_REQUIRES_MAPPING'):reconcile(self.ledger,self.source)
        self.assertEqual(self.ledger.status()['projects'],[])

    def test_unresolved_historical_operation_cannot_authorize(self):
        self.mutate('plus','DELETE FROM events WHERE seq>=3')
        reconcile(self.ledger,self.source)
        with self.assertRaisesRegex(Denied,'OPERATION_UNRESOLVED'):self.reserve('one')

    def test_tampered_event_is_rejected(self):
        self.mutate('plus',"UPDATE events SET body='changed' WHERE seq=2")
        with self.assertRaisesRegex(Denied,'EVENT_CHANGED'):reconcile(self.ledger,self.source)

    def test_restore_preserves_legacy_credit_and_recent_attempt(self):
        old=self.root/'old.sqlite3';backup(self.ledger,old)
        reconcile(self.ledger,self.source);self.ledger.cancel(self.reserve('one'))
        restore(self.ledger,old)
        self.assertEqual((self.info()['attempts_consumed'],self.info()['legacy_consumed']),(2,1))

    def test_source_files_are_byte_identical_after_reconciliation(self):
        paths=[self.source/PATHS[k] for k in ('v1','v4','plus')]
        before=[p.read_bytes() for p in paths]
        reconcile(self.ledger,self.source)
        self.assertEqual(before,[p.read_bytes() for p in paths])
