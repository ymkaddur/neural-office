"""Rollback, missing witnesses, process failure and retained evidence."""
from pathlib import Path
from contextlib import closing
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

from neural_office.ledger import Ledger, Denied
from neural_office.continuity import backup, protect, restore, witness_path, signature
from neural_office.runner import recover, run
from neural_office.windows_job import Job
from test_v52 import HTML, PROFILE, FakeBackend


class Continuity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = Ledger(self.root/'office.sqlite3'); self.ledger.initialize()
        self.ledger.register('p', self.root)

    def reserve(self, key):
        return self.ledger.reserve('p', 'Audit the continuity test fixture.', HTML, PROFILE, key, admit=True)

    def test_old_copy_does_not_refund_three_cancelled_attempts(self):
        old = self.root/'old.sqlite3'
        for n in range(3):
            self.ledger.cancel(self.reserve(str(n)))
            if n == 0: backup(self.ledger, old)
        shutil.copyfile(old, self.ledger.path)
        with self.assertRaisesRegex(Denied, 'CONTINUITY_DIVERGENCE'): self.ledger.status()
        with self.assertRaises(Denied): self.reserve('fourth')
        receipt = restore(self.ledger, old)
        self.assertGreater(receipt['restored_revision'], receipt['backup_revision'])
        p = self.ledger.status()['projects'][0]
        self.assertEqual((p['attempts_consumed'], p['active']), (3, False))
        with self.assertRaisesRegex(Denied, 'BUDGET_EXHAUSTED'): self.reserve('fourth')

    def test_backup_does_not_contain_witness_or_change_history(self):
        before = self.ledger.status()
        receipt = backup(self.ledger, self.root/'copy.sqlite3')
        self.assertFalse(receipt['witness_included'])
        self.assertFalse(witness_path(self.root/'copy.sqlite3').exists())
        self.assertEqual(before, self.ledger.status())

    def test_missing_witness_blocks_reads_reservations_and_restore(self):
        old = self.root/'old.sqlite3'; backup(self.ledger, old)
        witness_path(self.ledger.path).rename(self.root/'retained-witness.sqlite3')
        for operation in (self.ledger.status, lambda: self.reserve('one'), lambda: restore(self.ledger, old), lambda: protect(self.ledger)):
            with self.assertRaisesRegex(Denied, 'WITNESS_MISSING'): operation()

    def test_deleted_primary_cannot_initialize_fresh_budget(self):
        a = self.reserve('one'); self.ledger.cancel(a)
        old = self.root/'old.sqlite3'; backup(self.ledger, old)
        self.ledger.path.rename(self.root/'retained-primary.sqlite3')
        with self.assertRaisesRegex(Denied, 'RESTORE_REQUIRED'): self.ledger.initialize()
        restore(self.ledger, old)
        self.assertEqual(self.ledger.status()['projects'][0]['attempts_consumed'], 1)

    def test_foreign_office_backup_rejected(self):
        other = Ledger(self.root/'other.sqlite3'); other.initialize()
        with self.assertRaisesRegex(Denied, 'BACKUP_NOT_IN_RETAINED_HISTORY'):
            restore(self.ledger, other.path)

    def test_altered_backup_rejected(self):
        old = self.root/'old.sqlite3'; backup(self.ledger, old)
        with closing(sqlite3.connect(old)) as con:
            con.execute('UPDATE projects SET approved=1'); con.commit()
        with self.assertRaisesRegex(Denied, 'BACKUP_NOT_IN_RETAINED_HISTORY'): restore(self.ledger, old)

    def test_existing_backup_not_overwritten(self):
        old = self.root/'old.sqlite3'; old.write_bytes(b'preserve')
        with self.assertRaises(FileExistsError): backup(self.ledger, old)
        self.assertEqual(old.read_bytes(), b'preserve')

    def test_failed_verification_never_publishes_a_partial_backup(self):
        target = self.root / 'copy.sqlite3'
        def fail_on_copy(connection):
            db_path = Path(connection.execute('PRAGMA database_list').fetchone()[2])
            if db_path != self.ledger.path:
                raise sqlite3.OperationalError('test read failure')
            return signature(connection)
        with patch('neural_office.continuity.signature', side_effect=fail_on_copy):
            with self.assertRaisesRegex(sqlite3.OperationalError, 'test read failure'):
                backup(self.ledger, target)
        self.assertFalse(target.exists())
        receipt = backup(self.ledger, target)
        self.assertFalse(receipt['attachments_included'])
        self.assertTrue(target.is_file())

    def test_report_and_receipts_survive_newer_witness_recovery(self):
        old = self.root/'old.sqlite3'; backup(self.ledger, old)
        attempt = self.reserve('one'); run(self.ledger, attempt, 1, backend_factory=FakeBackend)
        expected = self.ledger.attempt(attempt)
        restore(self.ledger, old)
        actual = self.ledger.attempt(attempt)
        self.assertEqual(actual['artifact'], expected['artifact'])
        self.assertEqual(actual['outputs'], expected['outputs'])
        self.assertEqual(actual['state'], 'ACCEPTED')
        self.assertEqual(self.ledger.status()['projects'][0]['simulated_versions'], 1)

    def test_active_owned_job_blocks_restore_then_recovery_preserves_consumption(self):
        old = self.root/'old.sqlite3'; backup(self.ledger, old)
        attempt = self.reserve('one')
        name = 'Local\\NeuralContinuityTest_' + uuid.uuid4().hex
        with Job(name) as job:
            self.ledger.acquire(attempt, name)
            job.start([sys.executable, '-B', '-c', 'import time;time.sleep(30)'])
            import time
            until = time.monotonic() + 5
            while not job.active() and time.monotonic() < until: time.sleep(.01)
            self.assertGreater(job.active(), 0)
            with self.assertRaisesRegex(Denied, 'JOB_STILL_ACTIVE'): restore(self.ledger, old)
        restore(self.ledger, old)
        self.assertEqual(self.ledger.status()['lease']['attempt'], attempt)
        self.assertEqual(recover(self.ledger, attempt), 'FAILED')
        self.assertEqual(self.ledger.status()['projects'][0]['attempts_consumed'], 1)

    def test_atomic_failure_rolls_back_primary_and_witness(self):
        from neural_office import continuity
        before = self.ledger.status()
        original = continuity.seal
        def fail(con):
            original(con)
            raise OSError('injected before commit')
        with patch.object(continuity, 'seal', fail):
            with self.assertRaisesRegex(OSError, 'injected'): self.reserve('one')
        self.assertEqual(self.ledger.status(), before)

    def test_process_death_before_commit_recovers_both_databases(self):
        before = self.ledger.status()
        code = '''import os,sys
from neural_office import continuity
from neural_office.ledger import Ledger
original=continuity.seal
def die(con):
 original(con)
 os._exit(23)
continuity.seal=die
Ledger(sys.argv[1]).activate('p')
'''
        child = subprocess.run([sys.executable, '-B', '-c', code, str(self.ledger.path)], timeout=15)
        self.assertEqual(child.returncode, 23)
        self.assertEqual(self.ledger.status(), before)

    def test_reversion_of_every_copy_is_explicitly_not_detectable(self):
        old = self.root/'old.sqlite3'; backup(self.ledger, old)
        old_witness = self.root/'old-witness.sqlite3'
        shutil.copyfile(witness_path(self.ledger.path), old_witness)
        self.ledger.cancel(self.reserve('one'))
        shutil.copyfile(old, self.ledger.path)
        shutil.copyfile(old_witness, witness_path(self.ledger.path))
        # This is the declared boundary, not a claimed anti-rollback success.
        self.assertEqual(self.ledger.status()['projects'][0]['attempts_consumed'], 0)

    def test_non_delete_journal_is_not_silently_accepted(self):
        with closing(sqlite3.connect(self.ledger.path)) as con: con.execute('PRAGMA journal_mode=WAL')
        with self.assertRaisesRegex(Denied, 'ROLLBACK_JOURNAL'): self.ledger.status()

    def test_guard_is_released_after_exception(self):
        with self.assertRaises(Denied): self.ledger.activate('absent')
        self.assertEqual(self.ledger.status()['projects'][0]['attempts_consumed'], 0)
