"""Measure a complete durable HTML review inside a real Windows Job."""
import argparse
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from neural_office import __version__, office_protocol as office
from neural_office.ledger import Ledger, canonical, digest
from neural_office.measurements import JobSampler
from neural_office.windows_job import Job

SOURCE = ROOT / 'examples' / 'audit-sample.html'
EXPECTED = [('DOCUMENT_TITLE_MISSING', 1, 1), ('HTML_LANGUAGE_MISSING', 2, 1),
            ('IMAGE_ALT_MISSING', 6, 3), ('CONTROL_LABEL_CANDIDATE', 7, 3)]


def run_case(folder):
    ledger = Ledger(folder / 'review.sqlite3')
    attempt = office.start(ledger, 'Portal', 'delivery', SOURCE.parent, SOURCE,
                           'Verificar los hallazgos HTML del portal', 'review-1')
    view = office.status(ledger, attempt)
    step_ms = []
    for step in view['permit']['steps']:
        start = time.perf_counter_ns()
        view = office.run_step(ledger, attempt, step['id'])
        step_ms.append(round((time.perf_counter_ns() - start) / 1e6, 2))
    steps = view['permit']['steps']
    first, second, last = [office.output(ledger, attempt, step['id']) for step in steps]
    checked = second['output']['checked']
    report = last['output']
    locations = [(f['code'], f['line'], f['column']) for f in report['findings']]
    if not (view['state'] == 'ACCEPTED' and view['verdict']['passed']
            and (view['dispatch_intents'], view['receiver_receipts'], view['model_calls'],
                 view['project_attempts_consumed']) == (3, 3, 0, 1)
            and checked == dict(step=first['step'], transport=first['transport'], sha256=first['output_sha'])
            and second['depends_on'] == [checked]
            and last['depends_on'] == [dict(step=second['step'], transport=second['transport'], sha256=second['output_sha'])]
            and report['source_sha256'] == digest(SOURCE.read_bytes()) and report['role_outputs'] == []
            and locations == EXPECTED and view['artifact_sha256'] == digest(canonical(report))):
        raise RuntimeError('REVIEW_RESULT_MISMATCH')
    (folder / 'result.json').write_text(canonical(dict(steps_ms=step_ms, report_sha256=view['artifact_sha256'],
        findings=locations, project_attempts=1, dispatch_intents=3, receiver_receipts=3, model_calls=0)), encoding='utf-8')


def measure_case(folder):
    folder.mkdir()
    log_path = folder / 'worker.log'
    with Job('Local\\NeuralOfficeMeasure_' + uuid.uuid4().hex) as group, log_path.open('wb') as log:
        sampler = JobSampler(group, interval=0.05)
        sampler.start()
        start = time.perf_counter_ns()
        try:
            process = group.start([sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--case', str(folder)], log=log)
            code = process.wait(timeout=90)
            elapsed_ms = round((time.perf_counter_ns() - start) / 1e6, 2)
            if code or group.active():
                raise RuntimeError(f'REVIEW_PROCESS_INCOMPLETE: {code}: {log_path.read_text(encoding="utf-8", errors="replace")[-900:]}')
        finally:
            stats = sampler.stop()
    if stats['cpu_seconds'] is None or not stats['job_peak_commit_bytes'] or not stats['sampled_peak_working_set_sum_bytes']:
        raise RuntimeError('RESOURCE_COUNTER_MISSING')
    return dict(elapsed_ms=elapsed_ms, cpu_s=stats['cpu_seconds'], peak_commit_bytes=stats['job_peak_commit_bytes'],
                peak_sampled_ws_bytes=stats['sampled_peak_working_set_sum_bytes'], samples=stats['sample_count'],
                incomplete_samples=stats['incomplete_samples'], sample_errors=stats['observation_errors'],
                **json.loads((folder / 'result.json').read_text(encoding='utf-8')))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--case':
        run_case(Path(sys.argv[2]))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--samples', type=int, default=7, choices=range(1, 31), metavar='1..30')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output file')
    with tempfile.TemporaryDirectory(prefix='neural-office-530-measure-') as directory:
        base = Path(directory)
        warmup = measure_case(base / 'warmup')
        runs = [measure_case(base / str(i)) for i in range(args.samples)]
    components = ('audit.py', 'ledger.py', 'continuity.py', 'office_protocol.py', 'office_receiver.py', 'windows_job.py')
    result = dict(core_version=__version__, protocol=office.VERSION, python=platform.python_version(), machine=platform.machine(),
                  windows_build=platform.version(), logical_cpus=os.cpu_count(), source_sha256=digest(SOURCE.read_bytes()),
                  component_sha256={name: digest((ROOT / 'neural_office' / name).read_bytes()) for name in components},
                  scope='owned Windows Job: controller and its nested receiver groups after joining; sampler outside',
                  sample_interval_ms=50, warmup=warmup, runs=runs)
    with args.output.open('x', encoding='utf-8', newline='\n') as destination:
        json.dump(result, destination, ensure_ascii=False, indent=2)
        destination.write('\n')


if __name__ == '__main__':
    main()
