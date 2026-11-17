"""Paired local CPU comparison. Only the six bundled synthetic inputs are accepted.

Run from a checkout on Windows with the frozen model installed:
    py -3.12 -B -m tools.compare_v57 --output NEW_PRIVATE_DIRECTORY
The full output directory contains ledgers and backend logs; keep it private.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import time
import uuid

from neural_office.audit import make_report
from neural_office.diagnostics import MeasuredBackend, environment, new_output, write_json
from neural_office.files import capture_html
from neural_office.ledger import Ledger, digest
from neural_office.ollama import local_metadata, select_model
from neural_office.runner import run


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'examples' / 'v57-tasks.json'
# Verbatim orientation shown by the baseline desktop at 42f5345.
GUIDANCE = {
    'HTML_LANGUAGE_MISSING': 'Declara en html el idioma principal del contenido, por ejemplo lang="es" si corresponde.',
    'DOCUMENT_TITLE_MISSING': 'Añade un title descriptivo en head. Debe identificar el propósito de esta página.',
    'IMAGE_ALT_MISSING': 'Describe la información o función de la imagen. Si sólo decora, usa alt=""; decide según su contexto.',
    'CONTROL_LABEL_CANDIDATE': 'Comprueba el nombre accesible en el navegador. Asocia una etiqueta descriptiva al control; placeholder no sustituye a label.',
}


def trial(source, ledger, project, profile, objective, count):
    instances = []

    def measured(*args):
        backend = MeasuredBackend(*args)
        instances.append(backend)
        return backend

    start = time.perf_counter_ns()
    snapshot = capture_html(source, source.parent)
    state, error, artifact, row = 'STATIC', None, None, None
    if not count:
        artifact = make_report(snapshot, [])
    else:
        attempt = ledger.reserve(project, objective, snapshot, {**profile, 'roles': count}, str(count), admit=True)
        try:
            run(ledger, attempt, count, backend_factory=measured)
        except Exception as exc:
            from neural_office.desktop_service import public_error
            error = public_error(exc)
        row = ledger.attempt(attempt)
        state = row['state']
        artifact = bytes(row['artifact']) if row['artifact'] is not None else None
    elapsed = (time.perf_counter_ns() - start) / 1e9
    report = json.loads(artifact) if artifact and state in ('STATIC', 'ACCEPTED') else None
    if report and report['source_sha256'] != digest(snapshot):
        raise RuntimeError('SOURCE_IDENTITY_MISMATCH')
    backend = instances[0] if instances else None
    calls = []
    if backend:
        for measured_call, telemetry in zip(backend.calls, backend.telemetry, strict=True):
            calls.append({k: measured_call[k] for k in ('prompt_eval_count', 'eval_count', 'load_duration',
                          'total_duration', 'context_length', 'model_allocated_vram_bytes')}
                         | {'done_reason': telemetry['done_reason']})
    receipt = {'task': project, 'profile': count, 'source_sha256': digest(snapshot),
               'report_sha256': digest(artifact) if artifact else None, 'state': state, 'error': error,
               'wall_s': elapsed, 'attempts': int(bool(count)), 'calls_completed': len(calls), 'calls': calls,
               'backend_resources': backend.resource_summary if backend else None,
               'termination_verified': backend.cleaned if backend else None}
    return receipt, report


def compare(output):
    corpus_bytes = CORPUS.read_bytes().replace(b'\r\n', b'\n')
    if digest(corpus_bytes) != '0e90b5804ec2845a5daccb1a8a6dc559fdace760c1b5778f6d88f1c87adaf0db':
        raise ValueError('FROZEN_CORPUS_CHANGED')
    spec = json.loads(corpus_bytes)
    profile = select_model(spec['model'], local_metadata()['models'])
    if profile['model_digest'] != spec['digest']:
        raise RuntimeError('FROZEN_MODEL_UNAVAILABLE')
    out = new_output(output)
    header = {'schema': 1, 'started_utc': datetime.now(timezone.utc).isoformat(),
              'corpus_sha256': digest(corpus_bytes), 'model': spec['model'], 'environment': environment(profile)}
    write_json(out / 'environment.json', header)
    blind, key = [], {}
    for task in spec['tasks']:
        project = task['id']
        directory = out / project
        directory.mkdir()
        source = directory / 'sample.html'
        source.write_bytes(task['html'].encode('utf-8'))
        ledger = Ledger(directory / 'lab.sqlite3')
        ledger.initialize()
        ledger.register(project, directory)
        for count in task['order']:
            receipt, report = trial(source, ledger, project, profile, spec['objective'], count)
            code = uuid.uuid4().hex[:12]
            key[code] = [project, count]
            write_json(directory / f'receipt-{count}.json', receipt)
            if report:
                write_json(directory / f'report-{count}.json', report)
            blind.append({'id': code, 'task': project,
                          'findings': report['findings'] if report else None,
                          'advice': ([GUIDANCE[f['code']] for f in report['findings']]
                                     + [item['content'] for item in report['role_outputs']]) if report else []})
            print(project, count, receipt['state'], round(receipt['wall_s'], 3), flush=True)
            if count and receipt['termination_verified'] is not True:
                raise RuntimeError('BACKEND_TERMINATION_UNCONFIRMED')
    random.SystemRandom().shuffle(blind)
    write_json(out / 'blind.json', blind)
    write_json(out / 'key.json', key)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    compare(parser.parse_args().output)
