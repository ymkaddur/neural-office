"""Opt-in real local-model integration probe; creates a new synthetic office.

This exercises DesktopService with an observed OwnedOllama, not Tauri or a mock.
No historical ledger, user source, model download or runtime installation is used.
Run from the repository: python -B -m tools.smoke_v55_real --model NAME --output NEW_DIR
"""
import argparse
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import threading
import time

from neural_office.desktop_service import DesktopService
from neural_office.diagnostics import MeasuredBackend, environment, safe_error
from neural_office.ledger import Ledger, TERMINAL, digest
from neural_office.ollama import local_metadata, select_model


EXPECTED = [
    {'code': 'DOCUMENT_TITLE_MISSING', 'line': 1, 'column': 1},
    {'code': 'HTML_LANGUAGE_MISSING', 'line': 2, 'column': 1},
    {'code': 'IMAGE_ALT_MISSING', 'line': 6, 'column': 3},
    {'code': 'CONTROL_LABEL_CANDIDATE', 'line': 7, 'column': 3},
]


def probe(model, output):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve().parents[1] / 'examples' / 'audit-sample.html'
    snapshot = source.read_bytes()
    selected = root / 'audit-sample.html'
    selected.write_bytes(snapshot)
    profile = {**select_model(model, local_metadata()['models']), 'roles': 1}
    started_call = threading.Event()
    backends = []

    class ObservedRealBackend(MeasuredBackend):
        def infer(self, payload):
            started_call.set()
            return super().infer(payload)

    def factory(*args):
        instance = ObservedRealBackend(*args)
        backends.append(instance)
        return instance

    service = DesktopService(Ledger(root / 'office.sqlite3'), backend_factory=factory,
                             model_discovery=lambda: [dict(profile)])
    result = {'schema': 1, 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'real DesktopService / OwnedOllama; excludes native GUI and whole-app RAM',
              'model': model, 'source_sha256': digest(snapshot), 'environment': environment(profile),
              'machine_architecture': platform.machine(), 'trials': [], 'checks': {}, 'error': None}

    def prepare(key):
        captured = service.host_capture('synthetic-v55', selected)
        preview = service.preview('synthetic-v55', captured['entry_token'], profile['model_digest'],
                                  1, 'Review the packaged synthetic HTML and report its static findings.')
        return service.start(preview['approval_token'], key, preview['expected_revision'])

    def finish(attempt, label, began):
        deadline = time.monotonic() + 180
        while service._worker.is_alive() and time.monotonic() < deadline:
            service._worker.join(0.25)
        if service._worker.is_alive():
            service.cancel(attempt['id'])
            service._worker.join(20)
            raise RuntimeError('PROBE_DEADLINE')
        row = service.attempt(attempt['id'])
        result['trials'].append({'label': label, 'state': row['state'], 'mode': row['mode'],
                                'wall_seconds': time.monotonic() - began,
                                'call_states': [call['state'] for call in row['calls']],
                                'error_code': row['execution_error_code'],
                                'backend': backends[-1].receipt() if backends else None})
        return row

    try:
        began = time.monotonic()
        first = prepare('v55-real-complete')
        completed = finish(first, 'complete', began)
        result['checks']['real_attempt_accepted'] = completed['state'] == 'ACCEPTED'
        if completed['state'] != 'ACCEPTED':
            raise RuntimeError('REAL_ATTEMPT_NOT_ACCEPTED')
        meta = service.report(first['id'])
        chunks, offset = [], 0
        while True:
            chunk = service.report_read(first['id'], offset, 65536)
            data = base64.b64decode(chunk['base64'], validate=True)
            assert digest(data) == chunk['chunk_sha256']
            chunks.append(data)
            offset = chunk['next_offset']
            if chunk['eof']:
                break
        data = b''.join(chunks)
        report = json.loads(data.decode('utf-8', errors='strict'))
        result['checks']['report_digest'] = digest(data) == meta['sha256']
        result['checks']['manual_four_finding_oracle'] = report['findings'] == EXPECTED
        result['checks']['source_digest'] = report['source_sha256'] == digest(snapshot)
        result['checks']['commentary_is_unverified'] = report['model_commentary_status'] == 'UNVERIFIED_ASSISTANCE'
        result['report_sha256'] = meta['sha256']
        result['findings'] = report['findings']
        before = service.snapshot()
        office = before['office_id']
        service.close()
        service = DesktopService(Ledger(root / 'office.sqlite3'), backend_factory=factory,
                                 model_discovery=lambda: [dict(profile)])
        lookup = service.lookup('synthetic-v55', 'v55-real-complete')
        reopened = service.snapshot()
        result['checks']['restart_identity'] = lookup['found'] and lookup['attempt']['id'] == first['id']
        result['checks']['restart_office'] = reopened['office_id'] == office
        result['checks']['restart_does_not_consume'] = reopened['projects'][0]['attempts_consumed'] == 1
        result['checks']['restart_does_not_execute'] = len(backends) == 1

        started_call.clear()
        began = time.monotonic()
        second = prepare('v55-real-cancel')
        call_observed = started_call.wait(90)
        if call_observed:
            time.sleep(0.25)
        cancelled_from = service.attempt(second['id'])
        requested = time.monotonic()
        service.cancel(second['id'])
        cancelled = finish(second, 'cancel-after-real-call-entry', began)
        result['cancellation'] = {'call_entry_observed': call_observed,
                                  'state_at_request': cancelled_from['state'],
                                  'seconds_until_worker_join': time.monotonic() - requested}
        result['checks']['cancellation_preceded_terminal'] = cancelled_from['state'] not in TERMINAL
        result['checks']['cancelled'] = call_observed and cancelled['state'] == 'CANCELLED'
        result['checks']['cancel_preserves_consumption'] = service.snapshot()['projects'][0]['attempts_consumed'] == 2
        result['checks']['owned_backends_terminated'] = all(b.cleaned for b in backends)
    except Exception as error:
        result['error'] = safe_error(error)
    finally:
        service.close()
        result['passed'] = result['error'] is None and bool(result['checks']) and all(result['checks'].values())
        (root / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'checks': result['checks'], 'error': result['error']}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    raise SystemExit(probe(args.model, args.output))
