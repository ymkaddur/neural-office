"""Version 2 of the office protocol. Its first receiver performs local HTML checks."""
from pathlib import Path, PureWindowsPath
import json
import subprocess
import sys
import time

from .audit import verify_report
from .continuity import run_guard
from .desktop_contract import valid
from .files import capture_local
from .ledger import Denied, OFFICE_MODE, TERMINAL, canonical, digest
from .windows_job import Job


VERSION = 2
RECEIVER = 'local-html-v1'
MAX_SOURCE = 262_144
MAX_RESULT = 1_048_576
JOB_MEMORY = 256 * 1024 * 1024
JOB_CPU = 10
WALL_SECONDS = 20


def permit(thread, source_name, max_dispatches, tries_per_step):
    if (not valid('id', thread) or type(source_name) is not str or not 1 <= len(source_name) <= 4096
            or not source_name.isprintable() or PureWindowsPath(source_name).anchor
            or '..' in PureWindowsPath(source_name).parts or ':' in source_name
            or PureWindowsPath(source_name).suffix.lower() not in ('.html', '.htm')):
        raise Denied('OFFICE_SCOPE_INVALID')
    if (type(max_dispatches) is not int or not 1 <= max_dispatches <= 6
            or type(tries_per_step) is not int or tries_per_step not in (1, 2)):
        raise Denied('OFFICE_LIMIT_INVALID')
    steps = []
    for number, role, operation in ((1, 'director', 'inspect'), (2, 'verifier', 'verify'), (3, 'director', 'deliver')):
        steps.append(dict(id=f'r{number}.{role}.{operation}', round=number, role=role, operation=operation,
                          depends_on=[steps[-1]['id']] if steps else []))
    return dict(mode=OFFICE_MODE, protocol=VERSION, receiver=RECEIVER, thread_id=thread, source_name=source_name,
                steps=steps, max_dispatches=max_dispatches, tries_per_step=tries_per_step,
                retry_policy='explicit_after_verified_absence', model='Sin modelo', model_digest='', roles=0,
                job_memory_bytes=JOB_MEMORY, job_user_cpu_seconds=JOB_CPU, wall_seconds=WALL_SECONDS)


def validate_permit(profile, source):
    expected = permit(profile.get('thread_id'), profile.get('source_name'), profile.get('max_dispatches'),
                      profile.get('tries_per_step'))
    if canonical(profile) != canonical(expected):
        raise Denied('OFFICE_PERMIT_INVALID')
    if expected['max_dispatches'] < len(expected['steps']):
        raise Denied('OFFICE_DISPATCH_LIMIT')
    source.decode('utf-8-sig', errors='strict')


def install_schema(con):
    # Both the schema change and reservation commit with the retained witness.
    if con.execute('PRAGMA main.user_version').fetchone()[0] == 3:
        return
    con.execute("""CREATE TABLE office_transports(
        id TEXT PRIMARY KEY, attempt TEXT NOT NULL REFERENCES attempts(id), step TEXT NOT NULL,
        ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 1 AND 2), request_sha TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('PREPARED','DISPATCHED','CONFIRMED','ABSENT','CANCELLED','FAILED')),
        generation INTEGER, UNIQUE(attempt,step,ordinal))""")
    con.execute("""CREATE UNIQUE INDEX office_one_pending ON office_transports(attempt)
                   WHERE state IN ('PREPARED','DISPATCHED')""")
    con.execute("CREATE UNIQUE INDEX office_one_result ON office_transports(attempt,step) WHERE state='CONFIRMED'")
    con.execute("""CREATE TABLE office_receipts(transport TEXT PRIMARY KEY REFERENCES office_transports(id),
        request_sha TEXT NOT NULL, outcome TEXT NOT NULL CHECK(outcome IN ('OK','ERROR')),
        output TEXT NOT NULL, output_sha TEXT NOT NULL)""")
    con.execute('PRAGMA main.user_version=3')


def start(ledger, project, thread, root, file, objective, key, max_dispatches=3, tries_per_step=1):
    if not valid('project', project) or not valid('id', key) or not valid('objective', objective) or len(objective) < 12:
        raise Denied('OFFICE_REQUEST_INVALID')
    content, (relative, _, _) = capture_local(file, root, maximum=MAX_SOURCE, extensions=('.html', '.htm'))
    profile = permit(thread, relative, max_dispatches, tries_per_step)
    # Older versions admitted short permits. Ledger.reserve verifies the frozen
    # request digest on replay, before it can activate or charge a new attempt.
    historical_replay = (max_dispatches < len(profile['steps']) and ledger.path.is_file()
                         and lookup(ledger, project, thread, key) is not None)
    if not historical_replay:
        validate_permit(profile, content)
    ledger.initialize()
    ledger.register(project, root)
    return ledger.reserve(project, objective, content, profile, key, admit=True, source_name=Path(relative).name)


def lookup(ledger, project, thread, key):
    with ledger.connection() as con:
        row = con.execute('SELECT id,profile FROM attempts WHERE project=? AND request_key=?', (project, key)).fetchone()
        if row:
            p = json.loads(row['profile'])
            if p.get('mode') == OFFICE_MODE and p['thread_id'] == thread:
                return row['id']
        return None


def _attempt(ledger, con, attempt):
    row = ledger._row(con, attempt)
    p = json.loads(row['profile'])
    if p.get('mode') != OFFICE_MODE or p.get('protocol') != VERSION:
        raise Denied('OFFICE_PROTOCOL_MISMATCH')
    return row, p


def _step(p, identity):
    for step in p['steps']:
        if step['id'] == identity:
            return step
    raise Denied('OFFICE_STEP_NOT_AUTHORIZED')


def _transport(con, attempt, step):
    return con.execute('SELECT * FROM office_transports WHERE attempt=? AND step=? ORDER BY ordinal DESC LIMIT 1',
                       (attempt, step)).fetchone()


def _receipt(con, transport):
    row = con.execute('SELECT * FROM office_receipts WHERE transport=?', (transport['id'],)).fetchone()
    if row and (row['request_sha'] != transport['request_sha'] or digest(row['output']) != row['output_sha']):
        raise Denied('OFFICE_RECEIPT_CONFLICT')
    return row


def _parents(con, row, step):
    parents = []
    for identity in step['depends_on']:
        transport = _transport(con, row['id'], identity)
        if transport is None or transport['state'] != 'CONFIRMED':
            raise Denied('OFFICE_DEPENDENCY_PENDING')
        receipt = _receipt(con, transport)
        if receipt is None or receipt['outcome'] != 'OK':
            raise Denied('OFFICE_RECEIPT_CONFLICT')
        parents.append(dict(step=identity, transport=transport['id'], sha256=receipt['output_sha']))
    return parents


def _request(row, p, step, parents):
    return digest(canonical([VERSION, row['id'], row['request_digest'], p['receiver'], step, parents]))


def _job_name(transport):
    return 'Local\\NeuralOffice530_' + transport


def _prepare(ledger, attempt, step_id):
    with ledger.transaction(seal_unchanged=False) as con:
        row, p = _attempt(ledger, con, attempt)
        step = _step(p, step_id)
        prior = _transport(con, attempt, step_id)
        if prior and prior['state'] == 'CONFIRMED':
            return prior['id'], True
        if row['state'] in TERMINAL or row['cancelled']:
            raise Denied('OFFICE_ADMISSION_CLOSED')
        pending = con.execute("SELECT * FROM office_transports WHERE attempt=? AND state IN ('DISPATCHED','PREPARED')",
                              (attempt,)).fetchone()
        if pending and pending['state'] == 'DISPATCHED':
            raise Denied('OFFICE_RECONCILIATION_REQUIRED')
        parents = _parents(con, row, step)
        request = _request(row, p, step, parents)
        if pending:
            if pending['step'] != step_id or pending['request_sha'] != request:
                raise Denied('OFFICE_OTHER_STEP_RESERVED')
            return pending['id'], False
        ledger._authorized(con, row)
        if con.execute('SELECT attempt FROM lease').fetchone()[0] is not None:
            raise Denied('GLOBAL_INFERENCE_BUSY')
        ordinal = 1 if prior is None else prior['ordinal'] + 1
        used = con.execute('SELECT count(*) FROM office_transports WHERE attempt=?', (attempt,)).fetchone()[0]
        if used >= p['max_dispatches'] or ordinal > p['tries_per_step']:
            raise Denied('OFFICE_DISPATCH_LIMIT')
        office = con.execute('SELECT office FROM continuity_meta').fetchone()[0]
        token = digest(canonical([office, row['project'], p['thread_id'], attempt, step_id, ordinal, request]))
        con.execute("""INSERT INTO office_transports(id,attempt,step,ordinal,request_sha,state)
                       VALUES(?,?,?,?,?,'PREPARED')""", (token, attempt, step_id, ordinal, request))
        con.execute('UPDATE attempts SET revision=revision+1 WHERE id=?', (attempt,))
        ledger._event(con, 'OFFICE_STEP_RESERVED', dict(attempt=attempt, step=step_id, transport=token, ordinal=ordinal))
        return token, False


def _dispatch(ledger, attempt, token):
    with ledger.transaction() as con:
        row, _ = _attempt(ledger, con, attempt)
        ledger._authorized(con, row)
        tx = con.execute('SELECT * FROM office_transports WHERE attempt=? AND id=?', (attempt, token)).fetchone()
        if row['state'] != 'QUEUED' or tx is None or tx['state'] != 'PREPARED':
            raise Denied('OFFICE_RECONCILIATION_REQUIRED')
        lease = con.execute('SELECT attempt,generation FROM lease').fetchone()
        if lease['attempt'] is not None:
            raise Denied('GLOBAL_INFERENCE_BUSY')
        generation = lease['generation'] + 1
        con.execute('UPDATE lease SET attempt=?,generation=?,job=? WHERE id=1', (attempt, generation, _job_name(token)))
        con.execute("UPDATE office_transports SET state='DISPATCHED',generation=? WHERE id=?", (generation, token))
        con.execute("UPDATE attempts SET state='RUNNING',revision=revision+1 WHERE id=?", (attempt,))
        ledger._event(con, 'OFFICE_DISPATCH_INTENT', dict(attempt=attempt, step=tx['step'], transport=token,
                                                        receiver=RECEIVER, request_sha=tx['request_sha']))


def _active(ledger, con, attempt, token):
    row, p = _attempt(ledger, con, attempt)
    tx = con.execute('SELECT * FROM office_transports WHERE id=? AND attempt=?', (token, attempt)).fetchone()
    lease = con.execute('SELECT attempt,generation,job FROM lease').fetchone()
    if (tx is None or tx['state'] != 'DISPATCHED' or
            tuple(lease) != (attempt, tx['generation'], _job_name(token))):
        raise Denied('OFFICE_STALE_TRANSPORT')
    return row, p, tx


def receive(ledger, attempt, token):
    """Only the owned local worker runs this. The receiver commits before acknowledging to its caller."""
    from .office_receiver import evaluate
    job = Job(_job_name(token), existing=True)
    try:
        if not job.contains_current_process():
            raise Denied('OFFICE_RECEIVER_NOT_OWNED')
    finally:
        job.close()
    with ledger.connection() as con:
        row, p, tx = _active(ledger, con, attempt, token)
        if row['cancelled'] or row['state'] != 'RUNNING':
            raise Denied('OFFICE_ADMISSION_CLOSED')
        if _receipt(con, tx):
            return
        step = _step(p, tx['step'])
        parents = _parents(con, row, step)
        if _request(row, p, step, parents) != tx['request_sha'] or digest(row['snapshot']) != row['snapshot_sha']:
            raise Denied('OFFICE_RECEIPT_CONFLICT')
        prior = [json.loads(_receipt(con, _transport(con, attempt, item['step']))['output']) for item in parents]
    try:
        value = evaluate(step['operation'], row['snapshot'], parents, prior)
        body = canonical(value)
        if len(body.encode('utf-8')) > MAX_RESULT:
            raise Denied('OFFICE_OUTPUT_LIMIT')
        outcome = 'OK'
    except Denied as exc:
        if str(exc) not in ('OFFICE_OUTPUT_LIMIT', 'OFFICE_FACTS_DISAGREE'):
            raise
        outcome, body = 'ERROR', canonical(dict(reason=str(exc)))
    with ledger.transaction(seal_unchanged=False) as con:
        row, _, tx = _active(ledger, con, attempt, token)
        if _receipt(con, tx):
            return
        ledger._authorized(con, row)
        sha = digest(body)
        con.execute('INSERT INTO office_receipts VALUES(?,?,?,?,?)', (token, tx['request_sha'], outcome, body, sha))
        con.execute('UPDATE attempts SET revision=revision+1 WHERE id=?', (attempt,))
        ledger._event(con, 'OFFICE_RECEIVER_RECORDED', dict(attempt=attempt, step=tx['step'], transport=token,
                                                           outcome=outcome, output_sha=sha))


def _exchange(ledger, attempt, token):
    # run_guard covers intent, process admission, termination and settlement.
    with Job(_job_name(token), memory_bytes=JOB_MEMORY, cpu_seconds=JOB_CPU) as job:
        deadline = time.monotonic() + WALL_SECONDS
        if ledger.interruption_reason(attempt):
            return
        worker = Path(__file__).with_name('office_receiver.py').resolve()
        proc = job.start([sys.executable, '-I', '-B', str(worker), str(ledger.path.resolve()), attempt, token])
        while proc.poll() is None:
            if time.monotonic() >= deadline or ledger.interruption_reason(attempt):
                break
            try:
                proc.wait(timeout=min(0.15, max(0, deadline - time.monotonic())))
            except subprocess.TimeoutExpired:
                continue
    # Job.__exit__ terminates the entire group and observes it empty before returning.


def _failed(ledger, con, row, reason):
    verdict = canonical(dict(passed=False, reason=reason))
    con.execute("UPDATE attempts SET state='FAILED',revision=revision+1,verdict=? WHERE id=?", (verdict, row['id']))
    ledger._event(con, 'OFFICE_ATTEMPT_FAILED', dict(attempt=row['id'], reason=reason))
    ledger._park_exhausted(con, row['project'])


def _settle(ledger, attempt, token, *, explicit):
    with ledger.transaction(seal_unchanged=False) as con:
        row, p, tx = _active(ledger, con, attempt, token)
        receipt = _receipt(con, tx)
        if not receipt and not row['cancelled'] and not explicit:
            con.execute("UPDATE attempts SET state='RECOVERY_REQUIRED',revision=revision+1 WHERE id=?", (attempt,))
            ledger._event(con, 'OFFICE_RECEIPT_PENDING', dict(attempt=attempt, step=tx['step'], transport=token))
            return
        reason = None
        if not row['cancelled']:
            try:
                ledger._authorized(con, row)
            except Denied as exc:
                reason = str(exc)
        count = con.execute('SELECT count(*) FROM office_transports WHERE attempt=?', (attempt,)).fetchone()[0]
        if row['cancelled']:
            transport_state, state = 'CANCELLED', 'CANCELLED'
        elif reason or (receipt and receipt['outcome'] == 'ERROR'):
            transport_state, state = 'FAILED', 'FAILED'
            reason = reason or json.loads(receipt['output'])['reason']
        elif receipt:
            transport_state = 'CONFIRMED'
            state = 'VERIFYING' if tx['step'] == p['steps'][-1]['id'] else 'QUEUED'
        else:
            # For this receiver the only published effect is the SQLite receipt.
            # After proven termination, absence is meaningful; no other adapter may use this rule.
            transport_state, state = 'ABSENT', 'QUEUED'
            if tx['ordinal'] >= p['tries_per_step']:
                reason = 'OFFICE_RETRY_LIMIT'
        if state == 'QUEUED' and count >= p['max_dispatches']:
            reason = 'OFFICE_DISPATCH_LIMIT'
        con.execute('UPDATE office_transports SET state=? WHERE id=?', (transport_state, token))
        con.execute('UPDATE lease SET attempt=NULL,job=NULL WHERE id=1')
        ledger._event(con, 'OFFICE_TRANSPORT_SETTLED', dict(attempt=attempt, step=tx['step'], transport=token, state=transport_state,
                                                           output_sha=receipt['output_sha'] if receipt else None))
        if reason:
            _failed(ledger, con, row, reason)
        else:
            con.execute('UPDATE attempts SET state=?,revision=revision+1 WHERE id=?', (state, attempt))
            if state == 'CANCELLED':
                ledger._park_exhausted(con, row['project'])


def _close(ledger, attempt):
    with ledger.transaction(seal_unchanged=False) as con:
        row, p = _attempt(ledger, con, attempt)
        if row['state'] == 'QUEUED':
            try:
                ledger._check_authorized(con, row)
            except Denied as exc:
                con.execute("UPDATE office_transports SET state='FAILED' WHERE attempt=? AND state='PREPARED'", (attempt,))
                _failed(ledger, con, row, str(exc))
            return
        if row['state'] != 'VERIFYING':
            return
        try:
            ledger._authorized(con, row)
        except Denied as exc:
            _failed(ledger, con, row, str(exc))
            return
        transport = _transport(con, attempt, p['steps'][-1]['id'])
        if not transport or transport['state'] != 'CONFIRMED':
            raise Denied('OFFICE_RECEIPT_CONFLICT')
        receipt = _receipt(con, transport)
        if not receipt or receipt['outcome'] != 'OK':
            raise Denied('OFFICE_RECEIPT_CONFLICT')
        artifact = receipt['output'].encode('utf-8')
        verdict = verify_report(row['snapshot'], artifact)
        verdict['checks']['empty_model_output'] = json.loads(artifact)['role_outputs'] == []
        verdict['passed'] = all(verdict['checks'].values())
        state = 'ACCEPTED' if verdict['passed'] else 'REJECTED'
        con.execute('UPDATE attempts SET state=?,revision=revision+1,artifact=?,artifact_sha=?,verdict=? WHERE id=?',
                    (state, artifact, receipt['output_sha'], canonical(verdict), attempt))
        ledger._event(con, 'FINAL_VERDICT', dict(attempt=attempt, state=state, artifact_sha=receipt['output_sha'],
                                                receipt_sha=digest(canonical(verdict))))
        ledger._park_exhausted(con, row['project'])


def run_step(ledger, attempt, step_id):
    with ledger.connection() as con:
        row, p = _attempt(ledger, con, attempt)
        _step(p, step_id)
        tx = _transport(con, attempt, step_id)
        if tx and tx['state'] == 'CONFIRMED' and (row['state'] != 'VERIFYING' or step_id != p['steps'][-1]['id']):
            return status(ledger, attempt)
    with run_guard(ledger.path):
        token, done = _prepare(ledger, attempt, step_id)
        if not done:
            _dispatch(ledger, attempt, token)
            try:
                _exchange(ledger, attempt, token)
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                # Failure of the sender does not prove termination or absence of a committed receipt.
                with ledger.transaction(seal_unchanged=False) as con:
                    row, _, _ = _active(ledger, con, attempt, token)
                    if row['state'] == 'RUNNING' and not row['cancelled']:
                        con.execute("UPDATE attempts SET state='RECOVERY_REQUIRED',revision=revision+1 WHERE id=?", (attempt,))
                        ledger._event(con, 'OFFICE_EXCHANGE_INTERRUPTED', dict(attempt=attempt, step=step_id, transport=token,
                                                                              error=type(exc).__name__))
                raise Denied('OFFICE_EXCHANGE_RECONCILE') from exc
            _settle(ledger, attempt, token, explicit=False)
        _close(ledger, attempt)
    return status(ledger, attempt)


def reconcile(ledger, attempt, *, expected_revision=None):
    with ledger.connection() as con:
        row, _ = _attempt(ledger, con, attempt)
        if row['state'] in TERMINAL:
            return status(ledger, attempt)
    with run_guard(ledger.path):
        with ledger.connection() as con:
            row, _ = _attempt(ledger, con, attempt)
            if expected_revision is not None and row['revision'] != expected_revision:
                raise Denied('DESKTOP_REVISION_CHANGED')
            pending = con.execute("SELECT id FROM office_transports WHERE attempt=? AND state='DISPATCHED'",
                                  (attempt,)).fetchone()
        if pending:
            job = Job(_job_name(pending['id']), existing=True)
            try:
                if job.active():
                    if not row['cancelled']:
                        raise Denied('OWNED_JOB_STILL_RUNNING_CANCEL_FIRST')
                    job.terminate()
            finally:
                job.close()
            _settle(ledger, attempt, pending['id'], explicit=True)
        _close(ledger, attempt)
    return status(ledger, attempt)


def output(ledger, attempt, step_id):
    with ledger.connection() as con:
        row, p = _attempt(ledger, con, attempt)
        step = _step(p, step_id)
        tx = _transport(con, attempt, step_id)
        if not tx or tx['state'] != 'CONFIRMED':
            raise Denied('OFFICE_OUTPUT_NOT_CONFIRMED')
        receipt = _receipt(con, tx)
        parents = _parents(con, row, step)
        if (not receipt or receipt['outcome'] != 'OK'
                or tx['request_sha'] != _request(row, p, step, parents)):
            raise Denied('OFFICE_RECEIPT_CONFLICT')
        return dict(step=step_id, transport=tx['id'], request_sha=tx['request_sha'],
                    depends_on=parents, output_sha=receipt['output_sha'], output=json.loads(receipt['output']))


def transports_for(con, attempt):
    records = con.execute("""SELECT t.id,t.step,t.ordinal,t.state,t.request_sha,t.generation,
        r.outcome,r.output_sha FROM office_transports t LEFT JOIN office_receipts r ON r.transport=t.id
        WHERE t.attempt=? ORDER BY t.rowid""", (attempt,))
    return [dict(x) for x in records]


def status(ledger, attempt):
    from .legacy import inherited_consumption
    with ledger.connection() as con:
        row, p = _attempt(ledger, con, attempt)
        office = con.execute('SELECT office FROM continuity_meta').fetchone()[0]
        transports = transports_for(con, attempt)
        confirmed = {t['step'] for t in transports if t['state'] == 'CONFIRMED'}
        next_step = next((s['id'] for s in p['steps'] if s['id'] not in confirmed), None)
        actions = {'QUEUED': 'request_step', 'RUNNING': 'observe_or_reconcile',
                   'RECOVERY_REQUIRED': 'reconcile', 'STOPPING': 'observe_or_reconcile', 'VERIFYING': 'reconcile'}
        consumed = (inherited_consumption(con, row['project'])
                    + con.execute('SELECT count(*) FROM attempts WHERE project=?', (row['project'],)).fetchone()[0])
        return dict(protocol=VERSION, office_id=office, attempt=attempt, project=row['project'], thread=p['thread_id'],
                    request_key=row['request_key'], project_ordinal=row['ordinal'], state=row['state'], revision=row['revision'],
                    project_attempts_consumed=consumed, project_attempts_remaining=3-consumed,
                    objective=row['objective'], source_sha256=row['snapshot_sha'], permit=p, transports=transports,
                    next_action=actions.get(row['state'], 'closed'), next_step=next_step if row['state'] == 'QUEUED' else None,
                    reserved_transports=len(transports), dispatch_intents=sum(t['generation'] is not None for t in transports),
                    receiver_receipts=sum(t['outcome'] is not None for t in transports), model_calls=0,
                    verdict=json.loads(row['verdict']) if row['verdict'] else None, artifact_sha256=row['artifact_sha'])
