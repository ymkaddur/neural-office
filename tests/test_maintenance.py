"""User-facing maintenance paths, legacy accounting boundaries and startup evidence."""
from contextlib import closing, redirect_stdout
import io
import json
import os
from pathlib import Path
import sqlite3
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock

from neural_office.__main__ import main
from neural_office.ledger import Ledger, Denied, digest
from neural_office.continuity import protect, witness_path
from neural_office.legacy import reconcile, PATHS, rebind
from neural_office.ollama import OwnedOllama
from test_legacy import fixture
from test_v52 import HTML, PROFILE


class Maintenance(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.ledger=Ledger(self.root/'office.sqlite3')
        self.ledger.initialize()
        project=self.root/'project'; project.mkdir(); self.ledger.register('p',project)

    def command(self,*args):
        output=io.StringIO()
        with redirect_stdout(output):main(['--state',str(self.ledger.path),*map(str,args)])
        return json.loads(output.getvalue())

    def test_cli_backup_restore_keeps_consumption(self):
        a=self.ledger.reserve('p','Audit the upgrade fixture.',HTML,PROFILE,'one',admit=True)
        self.ledger.cancel(a); self.command('backup',self.root/'copy.sqlite3')
        a=self.ledger.reserve('p','Audit the upgrade fixture.',HTML,PROFILE,'two',admit=True)
        self.ledger.cancel(a)
        self.assertTrue(self.command('restore',self.root/'copy.sqlite3')['used_retained_witness'])
        self.assertEqual(self.command('status')['projects'][0]['attempts_consumed'],2)

    def test_explicit_schema_one_upgrade_preserves_three_attempts(self):
        for n in range(3):
            self.ledger.cancel(self.ledger.reserve('p','Audit the upgrade fixture.',HTML,PROFILE,str(n),admit=True))
        before=self.ledger.status()
        # Remove only schema-2 additions to construct a schema-1 compatibility fixture.
        with closing(sqlite3.connect(self.ledger.path)) as con:
            con.executescript('DROP TABLE legacy_roots; DROP TABLE legacy_bindings; DROP TABLE continuity_meta; PRAGMA user_version=1;')
        witness_path(self.ledger.path).unlink()
        with self.assertRaisesRegex(Denied,'UPGRADE_REQUIRED'):self.ledger.status()
        self.assertTrue(self.command('protect')['protected'])
        self.assertEqual(before,self.ledger.status())
        with self.assertRaisesRegex(Denied,'BUDGET_EXHAUSTED'):
            self.ledger.reserve('p','Audit the upgrade fixture.',HTML,PROFILE,'four',admit=True)

    def test_inspect_does_not_initialize_destination_and_import_does_not_arm(self):
        source=self.root/'historical'; fixture(source)
        absent=self.root/'absent.sqlite3'; output=io.StringIO()
        with redirect_stdout(output):main(['--state',str(absent),'legacy-inspect',str(source)])
        self.assertFalse(absent.exists())
        receipt=self.command('legacy-reconcile',source)
        self.assertFalse(receipt['authority_transferred'])
        copy=self.root/'copy';copy.mkdir()
        self.command('legacy-rebind','web-auditor',copy)
        p=next(p for p in self.command('status')['projects'] if p['id']=='web-auditor')
        self.assertEqual((p['attempts_consumed'],p['approved']),(1,False))

    def test_old_controller_admission_during_enrollment_blocks_upgrade(self):
        with closing(sqlite3.connect(self.ledger.path)) as con:
            con.executescript('DROP TABLE legacy_roots; DROP TABLE legacy_bindings; DROP TABLE continuity_meta; PRAGMA user_version=1;')
        witness_path(self.ledger.path).unlink()
        original=os.open
        def intervening_open(*args,**kwargs):
            fd=original(*args,**kwargs)
            if Path(args[0])==witness_path(self.ledger.path):
                with closing(sqlite3.connect(self.ledger.path)) as con:
                    con.execute("UPDATE lease SET attempt='synthetic-older-controller'");con.commit()
            return fd
        with patch('neural_office.continuity.os.open',side_effect=intervening_open):
            with self.assertRaisesRegex(Denied,'IDLE_OFFICE'):protect(self.ledger)
        with closing(sqlite3.connect(self.ledger.path)) as con:
            self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0],1)
            self.assertEqual(con.execute('SELECT attempt FROM lease').fetchone()[0],'synthetic-older-controller')

    def test_corrupt_old_audit_is_not_sealed_as_new_truth(self):
        with closing(sqlite3.connect(self.ledger.path)) as con:
            con.executescript("DROP TABLE legacy_roots; DROP TABLE legacy_bindings; DROP TABLE continuity_meta; PRAGMA user_version=1; UPDATE events SET digest='tampered';")
        witness_path(self.ledger.path).unlink()
        with self.assertRaisesRegex(Denied,'EVENT_CHAIN_CHANGED'):protect(self.ledger)

    def test_parent_and_nested_alias_cannot_bypass_reserved_project(self):
        source=self.root/'historical';fixture(source);reconcile(self.ledger,source)
        with self.assertRaisesRegex(Denied,'ROOT_ALREADY_BOUND'):
            self.ledger.register('other',source/'studio/workspaces')
        with self.assertRaisesRegex(Denied,'ROOT_ALREADY_BOUND'):
            rebind(self.ledger,'web-auditor',source/'studio/workspaces/design-system-qa')

    def test_director_last_verified_ordinal_is_not_verified_count(self):
        source=self.root/'historical';fixture(source,runs=0)
        path=source/PATHS['director5'];path.parent.mkdir(parents=True)
        with closing(sqlite3.connect(path)) as con:
            con.executescript('CREATE TABLE project(id TEXT,attempted INTEGER,completed INTEGER); CREATE TABLE task(id TEXT,project TEXT,version INTEGER,state TEXT); CREATE TABLE audit(stamp TEXT,kind TEXT,payload TEXT,prev TEXT,hash TEXT);')
            con.execute("INSERT INTO project VALUES('web-auditor',3,3)")
            for n,state in enumerate(('rejected','rejected','verified'),1):
                con.execute('INSERT INTO task VALUES(?,?,?,?)',(str(n),'web-auditor',n,state))
            con.commit()
        reconcile(self.ledger,source)
        p=next(p for p in self.ledger.status()['projects'] if p['id']=='web-auditor')
        self.assertEqual((p['attempts_consumed'],p['verified_versions']),(3,0))
        with closing(sqlite3.connect(path)) as con:
            con.execute("INSERT INTO audit VALUES('1','synthetic','{}',?,?)",('0'*64,'bad'));con.commit()
        with self.assertRaisesRegex(Denied,'AUDIT_CHANGED'):reconcile(self.ledger,source)

    def test_work_count_must_equal_verified_rows(self):
        source=self.root/'historical';fixture(source,runs=0)
        path=source/PATHS['work5'];path.parent.mkdir(parents=True)
        with closing(sqlite3.connect(path)) as con:
            con.executescript('CREATE TABLE projects(id TEXT,attempted INTEGER,verified INTEGER); CREATE TABLE tasks(id TEXT,project TEXT,attempt INTEGER,state TEXT); CREATE TABLE events(stamp TEXT,kind TEXT,body TEXT,previous_digest TEXT,digest TEXT);')
            con.execute("INSERT INTO projects VALUES('web-auditor',2,1)")
            con.executemany('INSERT INTO tasks VALUES(?,?,?,?)',[('a','web-auditor',1,'rejected'),('b','web-auditor',2,'verified')]);con.commit()
        reconcile(self.ledger,source)
        with closing(sqlite3.connect(path)) as con:
            con.execute('UPDATE projects SET verified=2');con.commit()
        with self.assertRaisesRegex(Denied,'VERIFIED_COUNTER_MISMATCH'):reconcile(self.ledger,source)


class StartupEvidence(unittest.TestCase):
    def test_success_records_ordered_phases_without_prompt_or_environment(self):
        with tempfile.TemporaryDirectory() as tmp, patch('neural_office.ollama.Job') as jobs, patch('neural_office.ollama.shutil.which',return_value='ollama'), patch('neural_office.ollama.local_metadata'), patch.object(OwnedOllama,'_assert_owned_listener'), patch.object(OwnedOllama,'check_model'):
            jobs.return_value.start.return_value.poll.return_value=None
            jobs.return_value.start.return_value.pid=123
            jobs.return_value.active.return_value=1
            path=Path(tmp)/'startup.jsonl';backend=OwnedOllama('synthetic',PROFILE,path)
            try:backend.start()
            finally:backend.log.close()
            rows=[json.loads(s) for s in path.read_text().splitlines()]
            self.assertEqual([r['stage'] for r in rows],['BOOTSTRAP_SPAWN_BEGIN','BOOTSTRAP_LAUNCHED','STARTUP_PROBE_BEGIN','STARTUP_PHASE','STARTUP_PHASE','OWNED_BACKEND_READY'])
            self.assertEqual([r['phase'] for r in rows if 'phase' in r],['metadata','listener_owner','model_identity'])
            self.assertEqual([r['perf_counter_ns'] for r in rows],sorted(r['perf_counter_ns'] for r in rows))
            self.assertFalse(any('model' in r or 'prompt' in r or 'environment' in r for r in rows))

    def test_timeout_records_failing_phase_and_no_ready_event(self):
        with tempfile.TemporaryDirectory() as tmp, patch('neural_office.ollama.Job') as jobs, patch('neural_office.ollama.shutil.which',return_value='ollama'), patch('neural_office.ollama.local_metadata',side_effect=ConnectionRefusedError), patch('neural_office.ollama.time.monotonic',side_effect=[0,0,31]), patch('neural_office.ollama.time.sleep'):
            jobs.return_value.start.return_value.poll.return_value=None
            jobs.return_value.start.return_value.pid=123;jobs.return_value.active.return_value=1
            path=Path(tmp)/'startup.jsonl';backend=OwnedOllama('synthetic',PROFILE,path)
            try:
                with self.assertRaisesRegex(Denied,'START_TIMEOUT'):backend.start()
            finally:backend.log.close()
            rows=[json.loads(s) for s in path.read_text().splitlines()]
            self.assertEqual((rows[-1]['stage'],rows[-1]['phase'],rows[-1]['last_error']),('START_TIMEOUT','metadata','ConnectionRefusedError'))
            self.assertNotIn('OWNED_BACKEND_READY',[r['stage'] for r in rows])


class Launcher(unittest.TestCase):
    def test_spaces_unicode_and_different_working_directory(self):
        source=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'Neural Office prueba ñ';folder.mkdir()
            shutil.copyfile(source/'run.bat',folder/'run.bat')
            shutil.copytree(source/'neural_office',folder/'neural_office',ignore=shutil.ignore_patterns('__pycache__'))
            for args,expected in [('--version',0),('--invalid-option',2)]:
                result=subprocess.run(['cmd.exe','/d','/c',str(folder/'run.bat'),args],cwd=tmp,capture_output=True,text=True,timeout=15)
                self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
                if expected==0:self.assertEqual(result.stdout.strip(),'5.6.0')
            self.assertFalse(list(folder.glob('*.sqlite3')))
