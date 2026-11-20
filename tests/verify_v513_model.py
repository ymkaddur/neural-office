"""Opt-in Windows integration of real attachments, the private pipe and owned Ollama."""
import argparse
import base64
from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import queue
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from examples.multiformat.build_example import example_files
from neural_office.ledger import canonical
from neural_office.runner import prompt


def input_receipt(work, attempt, fragments):
    database = (work / 'office.db').resolve().as_uri() + '?mode=ro'
    with closing(sqlite3.connect(database, uri=True)) as con:
        snapshot, objective, profile = con.execute('SELECT snapshot,objective,profile FROM attempts WHERE id=?',
                                                   (attempt,)).fetchone()
        hashes = con.execute('SELECT payload_sha FROM calls WHERE attempt=?', (attempt,)).fetchall()
    payload = prompt(dict(snapshot=snapshot, objective=objective, profile=json.loads(profile), outputs=[]), 'director')
    body = canonical(payload).encode()
    sha = hashlib.sha256(body).hexdigest()
    user = json.loads(payload['messages'][1]['content'])
    if (hashes != [(sha,)] or set(user) != {'scope', 'objective', 'role', 'authorized_fragments'}
            or user['objective'] != objective or user['authorized_fragments'] != fragments
            or 'tools' in payload or len(payload['messages']) != 2):
        raise RuntimeError('ADMITTED_PAYLOAD_SCOPE_CHANGED')
    stages = []
    for line in (work / 'logs' / (attempt + '.log')).read_bytes().splitlines():
        try:
            record = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        if isinstance(record, dict) and type(record.get('perf_counter_ns')) is int:
            stages.append(record)
    start = next(item['perf_counter_ns'] for item in stages if item['stage'] == 'BOOTSTRAP_SPAWN_BEGIN')
    ready = next(item['perf_counter_ns'] for item in stages if item['stage'] == 'OWNED_BACKEND_READY')
    return {'admitted_payload_sha256': sha, 'payload_bytes': len(body), 'user_fields': sorted(user),
            'attachment_excerpts': len(fragments), 'local_startup_ms': round((ready - start) / 1e6),
            'startup_retries': [item['phase'] for item in stages if item['stage'] == 'STARTUP_RETRY']}


@contextmanager
def peer(state):
    process = subprocess.Popen([sys.executable, '-m', 'neural_office.desktop_stdio', '--state', str(state)],
                               cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    inbox = queue.Queue()

    def read():
        for line in process.stdout:
            inbox.put(line)
        inbox.put(None)

    pump = threading.Thread(target=read, daemon=True)
    pump.start()

    def call(method, **params):
        key = uuid.uuid4().hex
        raw = json.dumps(dict(version=1, id=key, method=method, params=params), ensure_ascii=False).encode()
        process.stdin.write(raw + b'\n')
        process.stdin.flush()
        line = inbox.get(timeout=35)
        if line is None:
            raise RuntimeError('SIDECAR_CLOSED')
        reply = json.loads(line)
        if reply['id'] != key or not reply['ok']:
            raise RuntimeError(method, reply.get('error'))
        return reply['result']

    try:
        yield call
    finally:
        process.stdin.close()
        try:
            code = process.wait(20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(5)
            raise
        pump.join(2)
        process.stdout.close()
        if code:
            raise RuntimeError('SIDECAR_EXIT', code)


def verify(work, model):
    state = work / 'office.db'
    sample = example_files(work / 'example')
    target = dict(project_id='Portal', thread_id='plazo')
    objective = 'Compara los dos plazos e identifica qué valor debe confirmar la persona responsable.'
    with peer(state) as call:
        picks = call('host.attachments.capture', **target, paths=[str(path) for path in sample])
        sources = {item['kind']: item for item in picks}
        inspection = call('attachments.inspect', **target, objective=objective, attachment_ids=[item['id'] for item in picks])
        finding = next(item for item in inspection['findings'] if item['rule'] == 'first_response_hours')
        if finding['status'] != 'mismatch' or [s['value'] for s in finding['sources']] != [24, 48]:
            raise RuntimeError('STATIC_ORACLE_MISMATCH', finding)
        pdf = call('attachments.view', **target, capture_id=sources['pdf']['id'], member='', page=2)
        manifest = call('attachments.view', **target, capture_id=sources['json']['id'], member='', page=1)
        packed = call('attachments.view', **target, capture_id=sources['zip']['id'], member='visual/movil.jpg', page=1)
        if (pdf.get('page') != 2 or not pdf.get('image') or manifest.get('hours', {}).get('value') != 48
                or packed.get('member_sha256') != sources['jpeg']['sha256']):
            raise RuntimeError('PREVIEW_BINDING_FAILED')
        catalog = call('models.list')['models']
        selected = next(item for item in catalog if item['model'] == model and item['mode'] == 'ollama-owned')
        grant = call('attachments.preview', **target, report_id=inspection['id'],
                     model_digest=selected['model_digest'], objective=objective)
        before = call('snapshot.get', project_after=0, attempt_after=0, limit=10)
        if before['projects'][0]['attempts_consumed'] or before['attempts'] or grant['roles'] != 1:
            raise RuntimeError('PREVIEW_CHARGED')
        start = dict(approval_token=grant['approval_token'], expected_revision=grant['expected_revision'],
                     idempotency_key='explicit-local-verification')
        admitted = call('attempt.start', **start)
        deadline = time.monotonic() + 330
        while True:
            row = call('attempt.get', attempt_id=admitted['id'])
            if row['state'] in ('ACCEPTED', 'FAILED', 'REJECTED', 'CANCELLED', 'RECOVERY_REQUIRED'):
                break
            if time.monotonic() >= deadline:
                call('attempt.cancel', attempt_id=row['id'])
                raise TimeoutError('OWNED_MODEL_TIMEOUT')
            time.sleep(.35)
        if row['state'] != 'ACCEPTED':
            raise RuntimeError(row['state'], row.get('execution_error_code'))
        if call('attempt.start', **start)['id'] != row['id']:
            raise RuntimeError('REPLAY_CHANGED_ATTEMPT')
    with peer(state) as call:
        reopened = call('attachments.report', **target, report_id=inspection['id'])
        snapshot = call('snapshot.get', project_after=0, attempt_after=0, limit=10)
        row = call('attempt.get', attempt_id=admitted['id'])
        meta = call('report.get', attempt_id=row['id'])
        raw = bytearray()
        while len(raw) < meta['bytes']:
            part = call('report.read', attempt_id=row['id'], offset=len(raw), limit=65536)
            block = base64.b64decode(part['base64'], validate=True)
            if not block or hashlib.sha256(block).hexdigest() != part['chunk_sha256'] or part['sha256'] != meta['sha256']:
                raise RuntimeError('CHUNK_RECEIPT_CHANGED')
            raw.extend(block)
        artifact = json.loads(raw)
        if (hashlib.sha256(raw).hexdigest() != meta['sha256'] or reopened != inspection or len(row['calls']) != 1
                or row['calls'][0]['state'] != 'DONE' or snapshot['projects'][0]['attempts_consumed'] != 1
                or artifact['authorized_fragments'] != grant['fragments'] or len(artifact['role_outputs']) != 1):
            raise RuntimeError('FINAL_RECEIPTS_MISMATCH')
        return dict(surface='Windows Python sidecar over stdio', model=model, model_digest=row['model_digest'],
                    scope=artifact['scope'], attempt_id=row['id'], inspection_id=inspection['id'],
                    inputs=[dict(name=item['name'], sha256=item['sha256']) for item in picks],
                    expected_hours=24, declared_hours=48, pdf_page=pdf['page'], json_line=manifest['hours']['line'],
                    local_calls=inspection['model_calls'], local_reservations=inspection['reservations'],
                    authorized_fragments=grant['fragments'], state=row['state'], calls=row['calls'],
                    input_receipt=input_receipt(work, row['id'], grant['fragments']),
                    project_attempts_consumed=snapshot['projects'][0]['attempts_consumed'],
                    report_sha256=meta['sha256'], output=artifact['role_outputs'][0], verdict=meta['verdict'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='qwen2.5:0.5b')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--work', type=Path, help='New directory in which to retain the isolated ledger and startup logs.')
    options = parser.parse_args()
    if options.work:
        options.work.mkdir(parents=True, exist_ok=False)
        evidence = verify(options.work, options.model)
    else:
        with tempfile.TemporaryDirectory() as directory:
            evidence = verify(Path(directory), options.model)
    with options.output.open('x', encoding='utf-8') as file:
        json.dump(evidence, file, ensure_ascii=False, indent=2)
        file.write('\n')
    print(f"{evidence['state']} {evidence['model']} {evidence['report_sha256']}")
