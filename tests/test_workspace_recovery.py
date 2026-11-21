from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from examples.multiformat.build_example import example_files
from neural_office import continuity, workspace_backup
from neural_office.attachments import AttachmentStore
from neural_office.ledger import Denied, Ledger
from neural_office.project_library import ProjectLibrary
from test_v52 import HTML, PROFILE


class WorkspaceRecoveryTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.ledger = Ledger(self.root / 'original' / 'state.db')
        self.ledger.initialize()
        self.target = Ledger(self.root / 'recovered' / 'custom.db')
        self.archive = self.root / 'workspace.zip'
        self.witness = continuity.witness_path(self.ledger.path)

    def cli(self, ledger, *args):
        proc = subprocess.run([sys.executable, '-B', '-m', 'neural_office', '--state', str(ledger.path), *map(str,args)],
                              cwd=Path(__file__).resolve().parents[1], capture_output=True, encoding='utf-8', timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_full_office_from_normal_commands_recovers_all_34_reports_and_authority(self):
        p, t = 'Portal', 'revision'
        store = AttachmentStore(self.ledger)
        inputs = store.capture(p, example_files(self.root/'files'), thread_id=t)
        ids = [i['id'] for i in inputs]
        report = store.inspect(p, ids, '¿Coinciden los plazos?', thread_id=t)
        decision = store.decide(p,t,report['id'],'pdf',0)
        library = ProjectLibrary(store)
        library.change(p,t,report['id'],'decision','memory','Plazo','Usar el PDF.','create',0)
        for ordinal in range(33):
            store.inspect(p, [], f'Reunión semanal del cliente número {ordinal:02}', thread_id=t)
        before = {row['id']: store.report(p,row['id'],thread_id=t) for row in store.history(p,thread_id=t)}
        self.assertEqual(len(before),34)
        attempt = self.ledger.reserve(p,'Revisar el portal del proyecto.', HTML, PROFILE, 'restore-test', admit=True)
        self.ledger.cancel(attempt)
        self.target.path.parent.mkdir()
        receipt = self.cli(self.ledger,'backup',self.archive)
        actual = self.cli(self.target,'restore',self.archive,'--witness',self.witness)
        self.assertEqual((receipt['office'],receipt['revision']),(actual['office'],actual['restored_revision']))
        self.assertEqual((actual['reports'],actual['captures'],actual['decisions'],actual['library_versions']),(34,len(ids),1,1))
        restored = AttachmentStore(self.target)
        after = {r['id']: restored.report(p,r['id'],thread_id=t) for r in restored.history(p,thread_id=t)}
        self.assertEqual(before,after)
        self.assertEqual(restored.list(p,thread_id=t),store.list(p,thread_id=t))
        self.assertCountEqual(restored.list(p,thread_id=t),inputs)
        for i in ids:
            self.assertEqual(store.preview(p,i,thread_id=t),restored.preview(p,i,thread_id=t))
        self.assertEqual(after[report['id']]['decision'],decision)
        self.assertEqual(library.read(p),ProjectLibrary(restored).read(p))
        self.assertEqual(self.ledger.status(),self.target.status())
        with self.assertRaisesRegex(Denied,'DESTINATION_IN_USE'):
            workspace_backup.restore(self.target,self.archive,self.witness)

    def test_modified_sidecar_and_newer_witness_are_rejected_before_publication(self):
        store=AttachmentStore(self.ledger)
        store.inspect('Portal',[],'Conserva este encargo.',thread_id='uno')
        workspace_backup.create(self.ledger,self.archive)
        altered=self.root/'altered.zip'
        with ZipFile(self.archive) as archive, ZipFile(altered,'x') as changed:
            for name in archive.namelist():
                value=archive.read(name)
                changed.writestr(name,value+b'x' if name==workspace_backup.DESKTOP else value)
        self.target.path.parent.mkdir()
        with self.assertRaisesRegex(Denied,'WORKSPACE_ATTACHMENTS_CHANGED'):
            workspace_backup.restore(self.target,altered,self.witness)
        self.assertEqual(list(self.target.path.parent.iterdir()),[])
        self.ledger.register_text('Otro')
        with self.assertRaisesRegex(Denied,'WORKSPACE_CHECKPOINT_SUPERSEDED'):
            workspace_backup.restore(self.target,self.archive,self.witness)
        self.assertEqual(list(self.target.path.parent.iterdir()),[])

    def test_empty_workspace_and_publication_failure_leave_retriable_destination(self):
        workspace_backup.create(self.ledger,self.archive)
        self.target.path.parent.mkdir()
        publish=workspace_backup.os.rename
        def fail_once(src,dest):
            if Path(dest)==self.target.path.parent:
                raise OSError('publicación interrumpida')
            return publish(src,dest)
        with patch.object(workspace_backup.os,'rename',side_effect=fail_once):
            with self.assertRaisesRegex(OSError,'interrumpida'):
                workspace_backup.restore(self.target,self.archive,self.witness)
        self.assertEqual(list(self.target.path.parent.iterdir()),[])
        self.assertEqual(workspace_backup.restore(self.target,self.archive,self.witness)['reports'],0)
        with closing(sqlite3.connect(self.target.path)) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_non_database_witness_returns_a_structured_error_without_publishing(self):
        workspace_backup.create(self.ledger,self.archive)
        mistaken = self.root / 'notas.txt'
        mistaken.write_text('Notas de la reunión de la semana.',encoding='utf-8')
        proc=subprocess.run([sys.executable,'-B','-m','neural_office','--state',str(self.target.path),
                             'restore',str(self.archive),'--witness',str(mistaken)],capture_output=True)
        self.assertEqual(proc.returncode,2)
        self.assertEqual(json.loads(proc.stderr)['reason'],'WORKSPACE_RETAINED_WITNESS_INVALID')
        self.assertFalse(self.target.path.parent.exists())

    def test_incomplete_database_in_zip_never_publishes_a_workspace(self):
        workspace_backup.create(self.ledger,self.archive)
        incomplete=self.root/'incomplete.zip'
        with ZipFile(incomplete,'x') as archive:
            archive.writestr(workspace_backup.PRIMARY,b'incomplete database')
        with self.assertRaisesRegex(Denied,'WORKSPACE_ARCHIVE_INVALID'):
            workspace_backup.restore(self.target,incomplete,self.witness)
        self.assertFalse(self.target.path.parent.exists())
