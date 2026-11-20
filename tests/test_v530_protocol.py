"""Windows process cuts and real local receipts. Every test owns its ledger and source."""
import ctypes
from ctypes import wintypes
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
from neural_office import continuity, office_protocol as office
from neural_office.desktop_service import DesktopService
from neural_office.ledger import Denied, Ledger, MAX_CALLS, canonical, digest
from neural_office.windows_job import EXTENDED_LIMIT, ExtendedLimits, Job

HTML = b'<html><head><title>Portal</title></head><body>\n<img src="a"><p>Ayuda</p></body></html>'
OBJECTIVE = 'Comprobar la evidencia HTML del portal'
FIRST, SECOND, THIRD = (step['id'] for step in office.permit('delivery', 'portal.html', 3, 1)['steps'])
CUT_CODE = 83


def cli(db, *args, check=True):
    proc = subprocess.run([sys.executable, '-B', '-m', 'neural_office', '--state', str(db), *args],
                          cwd=ROOT, capture_output=True, encoding='utf-8', timeout=30)
    if check and proc.returncode:
        raise AssertionError((args, proc.stderr))
    return json.loads(proc.stdout) if check else proc


def start(ledger, **values):
    args = dict(project='Portal', thread='delivery', root=ledger.path.parent, file=ledger.path.with_name('portal.html'),
                objective=OBJECTIVE, key='request-1', max_dispatches=4, tries_per_step=2)
    return office.start(ledger, **(args | values))


def abrupt(cut):
    print(cut, flush=True)
    os._exit(CUT_CODE)


def wait_marker(marker, process):
    deadline = time.monotonic() + 15
    while not marker.is_file():
        if process.poll() is not None or time.monotonic() >= deadline:
            raise RuntimeError(f'Receiver missed barrier: {process.poll()}')
        time.sleep(0.02)


def stopped_process(pid):
    dll = ctypes.WinDLL('kernel32', use_last_error=True)
    dll.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    dll.OpenProcess.restype = wintypes.HANDLE
    dll.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    dll.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = dll.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE only, never retain a Job handle
    if not handle:
        return ctypes.get_last_error() == 87
    try:
        return dll.WaitForSingleObject(handle, 5000) == 0
    finally:
        dll.CloseHandle(handle)


def receiver_barrier(cut, db, attempt, token, marker):
    from neural_office import office_receiver

    def hold():
        temporary = marker.with_suffix('.writing')
        temporary.write_text(str(os.getpid()), encoding='ascii')
        temporary.replace(marker)
        time.sleep(45)  # only the owner's death or cancellation should end this receiver
        raise AssertionError('Uncontained receiver')

    original_eval = office_receiver.evaluate
    original_event = Ledger._event

    def evaluate(*args):
        if cut in ('after_send', 'live_cancel'):
            hold()
        response = original_eval(*args)
        if cut == 'after_response':
            hold()
        return response

    def event(self, con, kind, payload):
        original_event(self, con, kind, payload)
        if cut == 'before_receipt_commit' and kind == 'OFFICE_RECEIVER_RECORDED':
            hold()

    with patch.object(office_receiver, 'evaluate', evaluate), patch.object(Ledger, '_event', event):
        office.receive(Ledger(db), attempt, token)
        if cut == 'after_receipt_commit':
            hold()


def controller(cut, db, attempt, step, marker):
    ledger = Ledger(db)
    original_event = Ledger._event
    original_start = Job.start

    def event(self, con, kind, payload):
        original_event(self, con, kind, payload)
        if (cut, kind) in (('inside_reserve', 'ATTEMPT_RESERVED'), ('inside_prepare', 'OFFICE_STEP_RESERVED'),
                           ('inside_dispatch', 'OFFICE_DISPATCH_INTENT'), ('inside_ack', 'OFFICE_TRANSPORT_SETTLED'),
                           ('inside_close', 'FINAL_VERDICT')):
            abrupt(cut)

    def launch(job, command):
        actual = [sys.executable, '-B', str(Path(__file__).resolve()), '_receiver', cut,
                  str(db), attempt, command[-1], str(marker)]
        child = original_start(job, actual)
        if cut != 'live_cancel':
            wait_marker(marker, child)
            abrupt(cut)
        return child

    with patch.object(Ledger, '_event', event):
        if cut in ('before_reserve', 'inside_reserve', 'after_reserve'):
            if cut == 'before_reserve':
                abrupt(cut)
            start(ledger)
            abrupt(cut)
        hooks = {'after_prepare': '_prepare', 'after_dispatch': '_dispatch', 'before_ack': '_exchange',
                 'after_ack': '_settle', 'after_close': '_close'}
        if cut in hooks:
            original = getattr(office, hooks[cut])
            def after(*args, **kwargs):
                original(*args, **kwargs)
                abrupt(cut)
            with patch.object(office, hooks[cut], after):
                office.run_step(ledger, attempt, step)
        elif cut in ('after_send', 'after_response', 'before_receipt_commit', 'after_receipt_commit', 'live_cancel'):
            with patch.object(Job, 'start', launch):
                office.run_step(ledger, attempt, step)
        else:
            office.run_step(ledger, attempt, step)


class DurableOffice(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def store(self, name):
        folder = self.base / name
        folder.mkdir()
        (folder / 'portal.html').write_bytes(HTML)
        return Ledger(folder / 'office.db')

    def cut(self, ledger, point, attempt='unused', step=FIRST):
        marker = ledger.path.with_suffix('.marker')
        proc = subprocess.run([sys.executable, '-B', __file__, '_client', point, str(ledger.path), attempt, step, str(marker)],
                              cwd=ROOT, capture_output=True, encoding='utf-8', timeout=25)
        self.assertEqual((proc.returncode, proc.stdout.strip()), (CUT_CODE, point), proc.stderr)
        if marker.exists():
            self.assertTrue(stopped_process(int(marker.read_text(encoding='ascii'))))

    def test_cli_two_clients_reopen_permit_dependencies_and_real_output(self):
        ledger = self.store('clients')
        args = ['office-start', '--project', 'Portal', '--thread', 'delivery', '--root', str(ledger.path.parent),
                '--file', str(ledger.path.with_name('portal.html')), '--objective', OBJECTIVE, '--key', 'request-1']
        with ThreadPoolExecutor(max_workers=2) as pool:
            views = [f.result() for f in [pool.submit(cli, ledger.path, *args) for _ in range(2)]]
        self.assertEqual(views[0], views[1])
        self.assertEqual((views[0]['next_action'], views[0]['next_step']), ('request_step', FIRST))
        attempt = views[0]['attempt']
        self.assertEqual((views[0]['project_ordinal'], views[0]['project_attempts_remaining']), (1, 2))
        self.assertIsNone(office.lookup(ledger, 'Portal', 'other', 'request-1'))
        self.assertIsNone(office.lookup(ledger, 'Other', 'delivery', 'request-1'))
        revision = ledger.status()['audit']['head']
        self.assertEqual(cli(ledger.path, *args), views[0])
        with self.assertRaisesRegex(Denied, 'IDEMPOTENCY_CONFLICT'):
            start(ledger, thread='other')
        with self.assertRaisesRegex(Denied, 'IDEMPOTENCY_CONFLICT'):
            start(ledger, max_dispatches=6)
        with self.assertRaisesRegex(Denied, 'OFFICE_DEPENDENCY_PENDING'):
            office.run_step(ledger, attempt, SECOND)
        self.assertEqual(ledger.status()['audit']['head'], revision)
        ledger.path.with_name('portal.html').write_bytes(b'<html lang="es"><title>Cambiado</title></html>')
        with self.assertRaisesRegex(Denied, 'IDEMPOTENCY_CONFLICT'):
            start(ledger, max_dispatches=3, tries_per_step=1)
        for step in (FIRST, SECOND, THIRD):
            snapshot = cli(ledger.path, 'office-step', attempt, step)
            self.assertEqual(cli(ledger.path, 'office-step', attempt, step), snapshot)
        receipt = cli(ledger.path, 'office-output', attempt, SECOND)
        first = cli(ledger.path, 'office-output', attempt, FIRST)
        self.assertEqual(receipt['output']['checked'], dict(step=FIRST, transport=first['transport'], sha256=first['output_sha']))
        self.assertEqual(receipt['depends_on'], [receipt['output']['checked']])
        self.assertEqual(cli(ledger.path, 'office-output', attempt, THIRD)['depends_on'],
                         [dict(step=SECOND, transport=receipt['transport'], sha256=receipt['output_sha'])])
        self.assertEqual((snapshot['next_action'], snapshot['next_step']), ('closed', None))
        report = cli(ledger.path, 'report', attempt)
        self.assertEqual(report['source_sha256'], digest(HTML))
        self.assertIn('IMAGE_ALT_MISSING', [f['code'] for f in report['findings']])
        self.assertEqual(report['role_outputs'], [])
        self.assertEqual((snapshot['state'], snapshot['dispatch_intents'], snapshot['receiver_receipts'],
                          snapshot['model_calls'], snapshot['project_attempts_consumed']), ('ACCEPTED', 3, 3, 0, 1))
        self.assertEqual(len({t['id'] for t in snapshot['transports']}), 3)
        self.assertEqual(snapshot['artifact_sha256'], digest(canonical(report)))
        self.assertEqual(cli(ledger.path, 'office-lookup', '--project', 'Portal', '--thread', 'delivery', '--key', 'request-1'), snapshot)
        with closing(DesktopService(ledger)) as desktop:
            self.assertEqual(desktop.attempt(attempt)['transports'], snapshot['transports'])
            self.assertEqual(desktop.project_history('Portal')['attempts'][0]['state'], 'ACCEPTED')
            self.assertEqual(desktop.report(attempt)['sha256'], snapshot['artifact_sha256'])
        requests = [dict(version=1, id=name, method=method, params=dict(attempt_id=attempt))
                    for name, method in [('state', 'attempt.get'), ('report', 'report.get')]]
        requests.append(dict(version=1, id='activity', method='attempt.events', params=dict(attempt_id=attempt, before=0, limit=64)))
        child = subprocess.run([sys.executable, '-B', '-m', 'neural_office.desktop_stdio', '--state', str(ledger.path)],
                               input=b''.join((canonical(req) + '\n').encode() for req in requests),
                               cwd=ROOT, capture_output=True, timeout=15, check=True)
        replies = {reply['id']: reply for reply in map(json.loads, child.stdout.splitlines())}
        self.assertEqual(set(replies), {'state', 'report', 'activity'})
        self.assertTrue(all(reply['ok'] for reply in replies.values()), replies)
        self.assertEqual(replies['state']['result']['transports'], snapshot['transports'])
        self.assertEqual(replies['report']['result']['sha256'], snapshot['artifact_sha256'])
        activity = replies['activity']['result']['events']
        received = [e['payload'] for e in activity if e['kind'] == 'OFFICE_RECEIVER_RECORDED']
        self.assertEqual([(p['step'], p['transport'], p['output_sha'], p['outcome']) for p in received],
                         [(t['step'], t['id'], t['output_sha'], 'OK') for t in snapshot['transports']])
        self.assertTrue(all(set(p) == {'attempt', 'step', 'transport', 'output_sha', 'outcome'} for p in received))

    def test_cuts_around_atomic_reservation_include_schema_and_witness(self):
        for point in ('before_reserve', 'inside_reserve', 'after_reserve'):
            with self.subTest(point=point):
                ledger = self.store(point)
                ledger.initialize()
                self.cut(ledger, point)
                with ledger.connection() as con:
                    committed = point == 'after_reserve'
                    self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0], 3 if committed else 2)
                    self.assertEqual(con.execute('SELECT count(*) FROM attempts').fetchone()[0], int(committed))
                first = start(ledger)
                self.assertEqual(start(ledger), first)
                self.assertEqual(office.status(ledger, first)['project_attempts_consumed'], 1)

    def test_process_cuts_preserve_the_right_side_of_each_commit(self):
        cases = (
            ('inside_prepare', None, 0), ('after_prepare', 'PREPARED', 0), ('inside_dispatch', 'PREPARED', 0),
            ('after_dispatch', 'DISPATCHED', 0), ('after_send', 'DISPATCHED', 0),
            ('after_response', 'DISPATCHED', 0), ('before_receipt_commit', 'DISPATCHED', 0),
            ('after_receipt_commit', 'DISPATCHED', 1), ('before_ack', 'DISPATCHED', 1),
            ('inside_ack', 'DISPATCHED', 1), ('after_ack', 'CONFIRMED', 1),
        )
        for cut, expected_state, received in cases:
            with self.subTest(cut=cut):
                ledger = self.store(cut)
                attempt = start(ledger)
                self.cut(ledger, cut, attempt)
                before = office.status(ledger, attempt)
                self.assertEqual([r['state'] for r in before['transports']], [expected_state] if expected_state else [])
                self.assertEqual(before['receiver_receipts'], received)
                if expected_state == 'DISPATCHED':
                    with self.assertRaisesRegex(Denied, 'OFFICE_RECONCILIATION_REQUIRED'):
                        office.run_step(ledger, attempt, SECOND)
                recovered = office.reconcile(ledger, attempt)
                self.assertEqual(recovered['dispatch_intents'], before['dispatch_intents'])
                self.assertEqual(office.reconcile(ledger, attempt), recovered)
                if received:
                    self.assertEqual(recovered['transports'][0]['state'], 'CONFIRMED')
                after = office.run_step(ledger, attempt, FIRST)
                self.assertEqual(after['project_attempts_consumed'], 1)
                self.assertEqual((after['receiver_receipts'], after['transports'][-1]['state']), (1, 'CONFIRMED'))
                if expected_state == 'DISPATCHED' and not received:
                    self.assertEqual([t['state'] for t in after['transports']], ['ABSENT', 'CONFIRMED'])
                    self.assertEqual([t['ordinal'] for t in after['transports']], [1, 2])
                    self.assertNotEqual(after['transports'][0]['id'], after['transports'][1]['id'])
                    self.assertEqual(after['transports'][0]['request_sha'], after['transports'][1]['request_sha'])
                else:
                    self.assertEqual(after['reserved_transports'], 1)

    def test_final_receipt_and_close_can_be_reconciled_without_dispatch(self):
        for cut in ('after_ack', 'inside_close', 'after_close'):
            with self.subTest(cut=cut):
                ledger = self.store(cut)
                attempt = start(ledger)
                office.run_step(ledger, attempt, FIRST)
                office.run_step(ledger, attempt, SECOND)
                self.cut(ledger, cut, attempt, THIRD)
                initial = office.status(ledger, attempt)
                self.assertEqual(initial['state'], 'ACCEPTED' if cut == 'after_close' else 'VERIFYING')
                with patch.object(Job, 'start', side_effect=AssertionError('unexpected new dispatch')):
                    recovered = office.reconcile(ledger, attempt)
                    self.assertEqual(office.run_step(ledger, attempt, THIRD), recovered)
                self.assertEqual((recovered['state'], recovered['receiver_receipts']), ('ACCEPTED', 3))
                self.assertTrue(recovered['verdict']['passed'])

    def test_real_worker_cancel_competing_client_and_delayed_delivery(self):
        ledger = self.store('live')
        attempt = start(ledger)
        marker = ledger.path.with_suffix('.marker')
        args = [sys.executable, '-B', __file__, '_client', 'live_cancel', str(ledger.path), attempt, FIRST, str(marker)]
        with subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            try:
                wait_marker(marker, process)
                pid = int(marker.read_text(encoding='ascii'))
                self.assertEqual(office.status(ledger, attempt)['state'], 'RUNNING')
                with self.assertRaisesRegex(Denied, 'OFFICE_RUNNER_STILL_ACTIVE'):
                    office.reconcile(ledger, attempt)
                with self.assertRaisesRegex(Denied, 'OFFICE_RUNNER_STILL_ACTIVE'):
                    office.run_step(ledger, attempt, FIRST)
                self.assertEqual(ledger.cancel(attempt), 'STOPPING')
                _, err = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 0, err)
                self.assertTrue(stopped_process(pid))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
        view = office.status(ledger, attempt)
        self.assertEqual((view['state'], view['dispatch_intents'], view['receiver_receipts']), ('CANCELLED', 1, 0))
        self.assertEqual(ledger.cancel(attempt), 'CANCELLED')
        with self.assertRaisesRegex(Denied, 'OFFICE_ADMISSION_CLOSED'):
            office.run_step(ledger, attempt, FIRST)
        self.assertEqual(office.reconcile(ledger, attempt), view)

    def test_budget_revocation_limits_and_old_attempts(self):
        ledger = self.store('mixed')
        ledger.initialize()
        ledger.register('Portal', ledger.path.parent)
        legacy = dict(mode='fixture', model='fixture', model_digest='a' * 64, roles=1)
        previous = ledger.reserve('Portal', OBJECTIVE, HTML, legacy, 'old-request', admit=True)
        ledger.cancel(previous)
        bounded = start(ledger, max_dispatches=1)
        with closing(DesktopService(ledger)) as desktop:
            rev = office.status(ledger, bounded)['revision']
            self.assertEqual(desktop.recover(bounded, rev)['state'], 'QUEUED')
        measured = {}
        native = Job.start
        def observe(job, args):
            observed = ExtendedLimits()
            if not job.dll.QueryInformationJobObject(job.handle, EXTENDED_LIMIT, ctypes.byref(observed),
                                                     ctypes.sizeof(observed), None):
                raise ctypes.WinError(ctypes.get_last_error())
            measured.update(memory=observed.JobMemoryLimit, cpu=observed.BasicLimitInformation.PerJobUserTimeLimit)
            return native(job, args)
        with patch.object(Job, 'start', observe):
            partial = office.run_step(ledger, bounded, FIRST)
        self.assertEqual(measured, dict(memory=office.JOB_MEMORY, cpu=office.JOB_CPU * 10_000_000))
        self.assertEqual((partial['state'], partial['verdict']['reason'], partial['receiver_receipts']),
                         ('FAILED', 'OFFICE_DISPATCH_LIMIT', 1))
        self.assertEqual(office.output(ledger, bounded, FIRST)['output']['source_sha256'], digest(HTML))
        third = start(ledger, key='last')
        self.assertEqual(office.status(ledger, third)['project_attempts_remaining'], 0)
        ledger.revoke('Portal')
        self.assertEqual(ledger.attempt(third)['state'], 'CANCELLED')
        self.assertEqual(ledger.attempt(previous)['profile'], legacy)
        with self.assertRaisesRegex(Denied, 'ATTEMPT_BUDGET_EXHAUSTED'):
            start(ledger, key='fourth')
        with self.assertRaisesRegex(Denied, 'OFFICE_PROTOCOL_MISMATCH'):
            office.reconcile(ledger, previous)
        self.assertEqual(MAX_CALLS, 12)

    def test_failed_process_launch_preserves_lease_and_frozen_retry_limit(self):
        ledger = self.store('launch')
        attempt = start(ledger, max_dispatches=3, tries_per_step=1)
        with patch.object(Job, 'start', side_effect=OSError('injected start failure')):
            with self.assertRaisesRegex(Denied, 'OFFICE_EXCHANGE_RECONCILE'):
                office.run_step(ledger, attempt, FIRST)
        initial = office.status(ledger, attempt)
        self.assertEqual((initial['state'], initial['dispatch_intents'], initial['receiver_receipts']),
                         ('RECOVERY_REQUIRED', 1, 0))
        with self.assertRaisesRegex(Denied, 'OFFICE_RECONCILIATION_REQUIRED'):
            office.run_step(ledger, attempt, FIRST)
        with patch.object(Job, 'start', side_effect=AssertionError('unauthorized retry')):
            result = office.reconcile(ledger, attempt)
        self.assertEqual((result['state'], result['verdict']['reason'], result['project_attempts_consumed']),
                         ('FAILED', 'OFFICE_RETRY_LIMIT', 1))
        self.assertEqual(result['transports'][0]['state'], 'ABSENT')

    def test_expired_prepared_and_cancel_after_receiver_commit(self):
        ledger = self.store('expiry')
        attempt = start(ledger)
        self.cut(ledger, 'after_prepare', attempt)
        with patch('neural_office.ledger.time.time', return_value=time.time() + 3601):
            with self.assertRaisesRegex(Denied, 'CLOCK_OR_ATTEMPT_DEADLINE'):
                office.run_step(ledger, attempt, FIRST)
            result = office.reconcile(ledger, attempt)
        self.assertEqual((result['state'], result['verdict']['reason'], result['transports'][0]['state'],
                          result['dispatch_intents']), ('FAILED', 'CLOCK_OR_ATTEMPT_DEADLINE', 'FAILED', 0))
        attempt = start(ledger, key='second')
        self.cut(ledger, 'after_receipt_commit', attempt)
        self.assertEqual(ledger.cancel(attempt), 'STOPPING')
        cancelled = office.reconcile(ledger, attempt)
        self.assertEqual((cancelled['state'], cancelled['transports'][0]['state'], cancelled['receiver_receipts']),
                         ('CANCELLED', 'CANCELLED', 1))
        with self.assertRaisesRegex(Denied, 'OFFICE_OUTPUT_NOT_CONFIRMED'):
            office.output(ledger, attempt, FIRST)
        with self.assertRaisesRegex(Denied, 'OFFICE_ADMISSION_CLOSED'):
            office.run_step(ledger, attempt, SECOND)

    def test_restore_old_backup_preserves_new_receipt_and_historical_ceiling(self):
        ledger = self.store('restore')
        ledger.initialize()
        ledger.register('Portal', ledger.path.parent)
        profile = dict(mode='fixture', model='fixture', model_digest='b' * 64, roles=1)
        old = ledger.reserve('Portal', OBJECTIVE, HTML, profile, 'old', admit=True)
        ledger.cancel(old)
        backup = self.base / 'before.sqlite3'
        continuity.backup(ledger, backup)
        attempt = start(ledger)
        office.run_step(ledger, attempt, FIRST)
        before = office.status(ledger, attempt)
        restored = continuity.restore(ledger, backup)
        self.assertGreater(restored['restored_revision'], restored['backup_revision'])
        self.assertEqual(office.status(ledger, attempt), before)
        self.assertEqual((before['project_ordinal'], before['project_attempts_remaining']), (2, 1))
        self.assertEqual(ledger.attempt(old)['state'], 'CANCELLED')
        ledger.cancel(attempt)
        last = ledger.reserve('Portal', OBJECTIVE, HTML, profile, 'legacy-after-upgrade', admit=True)
        generation = ledger.acquire(last, 'synthetic-historical-call-test')
        for n in range(12):
            seq, _ = ledger.start_call(last, generation, f'checkpoint-{n}', {'n': n}, f'key-{n}')
            ledger.finish_call(last, generation, seq, dict(done=True, message=dict(content=f'fixture-{n}')))
        with self.assertRaisesRegex(Denied, 'CALL_BUDGET_EXHAUSTED'):
            ledger.start_call(last, generation, 'excess', {'n': 12}, 'excess-key')


if __name__ == '__main__':
    if sys.argv[1:2] == ['_client']:
        controller(sys.argv[2], Path(sys.argv[3]), sys.argv[4], sys.argv[5], Path(sys.argv[6]))
    elif sys.argv[1:2] == ['_receiver']:
        receiver_barrier(sys.argv[2], Path(sys.argv[3]), sys.argv[4], sys.argv[5], Path(sys.argv[6]))
    else:
        unittest.main()
