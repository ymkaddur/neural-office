"""Windows resource experiment on the six frozen HTML tasks. All output is private.

From the checkout: py -3.12 -B -m tools.measure_v58 --output NEW_DIRECTORY
Use --static-smoke for a small preflight without starting Ollama.
"""
import argparse
import base64
import ctypes
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid

from neural_office.desktop_service import DesktopService
from neural_office.diagnostics import MeasuredBackend, write_json
from neural_office.ledger import Ledger, canonical, digest
from neural_office.measurements import job_sample
from neural_office.ollama import json_unique, local_metadata, select_model
from neural_office.runner import role_order
from neural_office.windows_job import Job


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'examples/v57-tasks.json'
FROZEN = '0e90b5804ec2845a5daccb1a8a6dc559fdace760c1b5778f6d88f1c87adaf0db'
BASE = 'e69885c424d80d2658b44039e915702eb10fcec3'
clock = time.perf_counter_ns


def require(value, message):
    if not value:
        raise RuntimeError(message)


def specification():
    raw = CORPUS.read_bytes().replace(b'\r\n', b'\n')
    require(digest(raw) == FROZEN, 'frozen corpus changed')
    return json.loads(raw)


def point(job):
    sample = job_sample(job)
    sample['t'] = clock()
    return sample


def loaded(backend):
    models = local_metadata('/api/ps', backend.port)['models']
    if not models:
        return False
    require(len(models) == 1, 'unexpected resident model count')
    model = models[0]
    require(model['digest'] == backend.profile['model_digest'] and model['size_vram'] == 0
            and model['context_length'] == 8192, 'resident model identity or allocation')
    return True


class ProfiledOllama(MeasuredBackend):
    """Observe the actual product backend. Only the labelled control preloads weights."""
    def __init__(self, *args, phase, outer):
        super().__init__(*args)
        self.phase = phase
        self.outer = outer
        self.costs = []
        self.preload = None
        self.empty_at_start = False

    def start(self):
        super().start()
        self.empty_at_start = not loaded(self)
        require(self.empty_at_start, 'private server unexpectedly warm at start')
        if self.phase != 'preloaded':
            return
        data = canonical({'model': self.profile['model'], 'messages': [], 'stream': False,
                          'keep_alive': '5m', 'options': {'num_ctx':8192, 'num_gpu':0,
                          'num_predict':128, 'temperature':0}}).encode()
        self._assert_owned_listener()
        before = point(self.outer)
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=120)
        try:
            conn.request('POST', '/api/chat', data, {'Content-Type':'application/json'})
            response = conn.getresponse()
            require(response.status == 200, 'preload HTTP status')
            result = json_unique(response.read(65536))
        finally:
            conn.close()
        after = point(self.outer)
        require(result.get('done') is True and result.get('done_reason') == 'load'
                and not result.get('message', {}).get('content') and not result.get('eval_count')
                and loaded(self), 'weights-only preload not established')
        self.preload = {'begin':before, 'end':after, 'done_reason':result['done_reason'],
                        'reported_output_tokens':result.get('eval_count')}

    def infer(self, payload):
        resident = loaded(self)
        require(resident == (self.phase == 'preloaded' or bool(self.calls)), 'unexpected pre-call residency')
        begin = point(self.outer)
        result = super().infer(payload)
        end = point(self.outer)
        self.costs.append({'begin':begin, 'end':end, 'resident_before':resident})
        return result


def read_delivery(service, identity):
    meta = service.report(identity)
    chunks = bytearray()
    while len(chunks) < meta['bytes']:
        page = service.report_read(identity, len(chunks), 12_288)
        chunk = base64.b64decode(page['base64'], validate=True)
        require(chunk and digest(chunk) == page['chunk_sha256'], 'report chunk')
        chunks.extend(chunk)
    require(len(chunks) == meta['bytes'] and digest(chunks) == meta['sha256'], 'report content')
    return json.loads(chunks)


def cell(outer, service, task, arm, phase, source, spec, instances):
    ledger = service.ledger
    with ledger.connection() as db:
        initial = db.execute('SELECT count(*) FROM attempts').fetchone()[0]
    begin = point(outer)
    grant = service.host_capture(task['id'], source)
    checked = service.check_source(task['id'], grant['entry_token'], 0)
    state = 'STATIC'
    outputs = []
    calls = []
    details = None
    if arm:
        preview = service.preview(task['id'], grant['entry_token'], spec['digest'], arm, spec['objective'])
        require(preview['attempts_consumed'] == initial and preview['mode'] == 'ollama-owned', 'preview authority')
        attempt = service.start(preview['approval_token'], phase, preview['expected_revision'])['id']
        service._worker.join(360)
        require(not service._worker.is_alive(), 'execution did not settle in time')
        state = service.attempt(attempt)['state']
        if state != 'ACCEPTED':
            raise RuntimeError(f"{state}: {service.attempt(attempt).get('error')}")
        report = read_delivery(service, attempt)
        end = point(outer)
        require(report['source_sha256'] == grant['sha256'] and report['findings'] == checked['findings'],
                'report and captured check disagree')
        outputs = [item['content'] for item in report['role_outputs']]
        backend = instances[0]
        require(len(instances) == 1 and backend.cleaned and len(backend.calls) == arm, 'backend completion')
        with ledger.connection() as db:
            rows = db.execute('SELECT role,payload_sha,state,response FROM calls WHERE attempt=? ORDER BY seq', (attempt,)).fetchall()
        require([row['role'] for row in rows] == list(role_order(arm)), 'call order')
        for row, invocation, bounds, telemetry in zip(rows, backend.calls, backend.costs, backend.telemetry, strict=True):
            response = json.loads(row['response'])
            require(row['state'] == 'DONE' and row['payload_sha'] == invocation['request_sha256']
                    and response['done'] is True and len(response['message']['content']) > 0
                    and invocation['model_allocated_vram_bytes'] == 0 and invocation['context_length'] == 8192,
                    'recorded generation provenance')
            for field in ('load_duration','eval_count','prompt_eval_count','eval_duration'):
                require(type(invocation[field]) is int and invocation[field] >= 0
                        and invocation[field] == response[field], 'unmeasured provider metric: ' + field)
            calls.append({**invocation, **bounds, 'done_reason':telemetry['done_reason'], 'role':row['role']})
        details = {'empty_at_start':backend.empty_at_start, 'cleaned':backend.cleaned,
                   'preload':backend.preload, 'server_job':backend.resource_summary}
    else:
        end = point(outer)
        require(not instances, 'static path started a backend')
    with ledger.connection() as db:
        consumed = db.execute('SELECT count(*) FROM attempts').fetchone()[0] - initial
    require(consumed == int(bool(arm)), 'attempt delta')
    return {'task':task['id'], 'arm':arm, 'phase':phase, 'begin':begin, 'end':end,
            'source_sha256':grant['sha256'], 'state':state, 'attempts':consumed, 'calls':calls,
            'findings':checked['findings'], 'paragraphs':outputs, 'backend':details}


def worker(folder, task_id, arm, name):
    spec = specification()
    index, task = next((i,t) for i,t in enumerate(spec['tasks']) if t['id'] == task_id)
    source = folder / 'sample.html'
    require(source.read_bytes() == task['html'].encode(), 'source changed')
    outer = Job(name, existing=True)
    require(outer.handle, 'observer job unavailable')
    # Join before starting any product process. The observer owns the job for this block.
    require(outer.dll.AssignProcessToJobObject(outer.handle, outer.dll.GetCurrentProcess()), 'join outer job')
    instances = []
    phases = ['cold', 'repeat']
    if arm and index % 2:
        phases.append('preloaded')
    elif arm:
        phases.insert(1, 'preloaded')
    def measured(*args):
        backend = ProfiledOllama(*args, phase=phase, outer=outer)
        instances.append(backend)
        return backend
    service = None
    try:
        service = DesktopService(Ledger(folder / 'office.sqlite3'), backend_factory=measured)
        for phase in phases:
            instances.clear()
            row = cell(outer, service, task, arm, phase, source, spec, instances)
            write_json(folder / (phase + '.json'), row)
            print(task_id, arm, phase, row['state'], round((row['end']['t']-row['begin']['t']) / 1e9, 3), flush=True)
    finally:
        try:
            if service is not None:
                service.close()
        finally:
            outer.close()


def block(folder, task, arm, smoke):
    folder.mkdir()
    (folder / 'sample.html').write_bytes(task['html'].encode())
    outer = Job('Local\\NeuralOfficeResource58_' + uuid.uuid4().hex)
    samples = []
    process = None
    try:
        launch = clock()
        process = subprocess.Popen([sys.executable, '-B', '-m', 'tools.measure_v58',
                                    '--worker', str(folder), task['id'], str(arm), outer.name], cwd=ROOT)
        while process.poll() is None:
            samples.append(point(outer))
            if (clock()-launch)/1e9 > 1150:
                raise TimeoutError('resource block deadline')
            time.sleep(.1)
        final = point(outer)
        samples.append(final)
        write_json(folder / 'samples.json', {'launch':launch, 'samples':samples,
                   'exit':process.returncode, 'job_empty':outer.active() == 0, 'smoke':smoke})
        require(process.returncode == 0 and outer.active() == 0, 'worker failed or owned process survived')
    finally:
        try:
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=20)
            outer.terminate()
        finally:
            outer.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--static-smoke', action='store_true')
    parser.add_argument('--worker', nargs=4, help=argparse.SUPPRESS)
    args = parser.parse_args()
    require(sys.platform == 'win32' and sys.version_info[:2] == (3,12) and __debug__, 'requires Windows / Python 3.12')
    if args.worker:
        folder, task, arm, name = args.worker
        return worker(Path(folder), task, int(arm), name)
    if args.output is None:
        parser.error('--output is required')
    spec = specification()
    subprocess.run(['git','diff','--quiet',BASE,'--','neural_office','examples/v57-tasks.json'],cwd=ROOT,check=True)
    env = {'python':platform.python_version(), 'windows_build':sys.getwindowsversion().build,
           'logical_processors':os.cpu_count(), 'epoch_utc':datetime.now(timezone.utc).isoformat(),
           'corpus_sha256':FROZEN, 'product_commit':BASE, 'smoke':args.static_smoke,
           'instrument_sha256':digest(Path(__file__).read_bytes().replace(b'\r\n',b'\n'))}
    if not args.static_smoke:
        profile = select_model(spec['model'], local_metadata()['models'])
        require(profile['model_digest'] == spec['digest'], 'required local weights unavailable')
        env.update(ollama=local_metadata('/api/version')['version'], profile=profile)
    folder = args.output.resolve()
    folder.mkdir(exist_ok=False, parents=True)
    write_json(folder / 'environment.json', env)
    for task in spec['tasks'][:1] if args.static_smoke else spec['tasks']:
        for arm in [0] if args.static_smoke else task['order']:
            block(folder / (task['id'] + '-' + str(arm)), task, arm, args.static_smoke)


if __name__ == '__main__':
    main()
