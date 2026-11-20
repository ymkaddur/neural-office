"""Paired Windows measurements of real, free inspections through the desktop service."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]
CASES = {
    'comparison': 'Compara el plazo de primera respuesta.',
    'decision_and_pages': '¿Qué decidimos y cuántas páginas tiene el PDF?',
    'zip': '¿Qué hay dentro del ZIP?',
    'unknown': '¿Cuál es el plazo de devolución?',
    'recall': '¿Con cuál nos quedamos?',
    'large_image': '¿Qué dimensiones tiene la imagen?',
    'large_identity': '¿Qué decidimos?',
}


def invoke(service, method, **params):
    envelope = dict(version=1, id='measure-520', method=method,
                    params=dict(project_id='Portal', thread_id='review', **params))
    return service.dispatch(json.dumps(envelope, ensure_ascii=True).encode('ascii'))


def prepare(root, location, corpus):
    sys.path.insert(0, root)
    from examples.multiformat.build_example import example_files
    from neural_office.desktop_service import DesktopService
    from neural_office.ledger import Ledger
    from PIL import Image

    inputs = example_files(corpus)
    photo, extra = corpus / 'orientada.jpg', corpus / 'respaldo.bin'
    if not photo.exists():
        exif = Image.Exif()
        exif[274] = 6
        with Image.new('RGB', (3000, 2000), '#233154') as image:
            image.save(photo, exif=exif)
    if not extra.exists():
        extra.write_bytes(b'x' * (8 * 1024 * 1024))
    with closing(DesktopService(Ledger(location / 'office.db'))) as service:
        files = service.host_attachments_capture('Portal', 'review', [*inputs, photo, extra])
        ids = [x['id'] for x in files]
        initial = invoke(service, 'attachments.inspect', attachment_ids=ids[:5], objective='Verifica el plazo.')
        if initial['findings'][0]['status'] != 'mismatch':
            raise ValueError('Cannot seed the verified decision')
        invoke(service, 'attachments.decide', report_id=initial['id'], choice='json', expected_revision=0)
    state = dict(portal=ids[:5], photo=ids[5], extra=ids[6], origin=initial['id'],
                 digests={x['name']: x['sha256'] for x in files})
    (location / 'inputs.json').write_text(json.dumps(state), encoding='utf-8')


def check_answer(case, report, state, ids):
    findings = report['findings']
    if case == 'comparison':
        pdf, field = findings[0]['sources']
        valid = (len(findings) == 1 and findings[0]['status'] == 'mismatch'
                 and (pdf['kind'], pdf['page'], pdf['quote'], pdf['value']) == ('pdf', 2, 'Primera respuesta en 24 horas.', 24)
                 and (field['kind'], field['line'], field['pointer'], field['value']) == ('json', 4, '/response_sla_hours', 48))
    elif case in ('decision_and_pages', 'recall'):
        titles = ['Se eligieron 48 h'] + (['2 páginas'] if case == 'decision_and_pages' else [])
        selected = findings[0]['sources'][0]
        valid = ([f['title'] for f in findings] == titles and findings[0]['origin_report'] == state['origin']
                 and (selected['kind'], selected['value'], selected['pointer']) == ('json', 48, '/response_sla_hours')
                 and all(f['status'] == 'observed' for f in findings)
                 and (case != 'decision_and_pages' or findings[1]['sources'][0]['kind'] == 'pdf'))
    elif case == 'zip':
        entries = ('documentacion/especificacion.pdf', 'manifiesto.json', 'visual/portada.png', 'visual/movil.jpg')
        valid = (len(findings) == 1 and findings[0]['title'] == '4 entradas en el ZIP'
                 and findings[0]['sources'][0]['kind'] == 'zip' and all(n in findings[0]['detail'] for n in entries))
    elif case == 'large_image':
        valid = (len(findings) == 1 and findings[0]['title'] == '2000 × 3000 px'
                 and findings[0]['status'] == 'observed' and findings[0]['sources'][0]['kind'] == 'jpeg')
    else:
        rule = 'thread_decision' if case == 'large_identity' else 'scope'
        valid = [(f['rule'], f['status'], f['sources']) for f in findings] == [(rule, 'insufficient', [])]
    sources_verified = all(s['attachment_id'] in ids and s['sha256'] == state['digests'][s['name']]
                           for finding in findings for s in finding['sources'])
    if not (valid and sources_verified and [i['id'] for i in report['attachments']] == ids
            and report['model_calls'] == report['reservations'] == 0):
        raise ValueError(f'{case} did not produce the expected answer, sources and cost')


def sample(root, location, case, job_name, target):
    sys.path.insert(0, root)
    from neural_office import attachments
    from neural_office.desktop_service import DesktopService
    from neural_office.ledger import Ledger
    from neural_office.measurements import JobSampler
    from neural_office.windows_job import Job

    if Path(attachments.__file__).resolve().parents[1] != Path(root):
        raise RuntimeError('Wrong source checkout')
    state = json.loads((location / 'inputs.json').read_text(encoding='utf-8'))
    ids = {'large_image': [state['photo']], 'large_identity': [state['extra']]}.get(case, state['portal'])
    reads = []
    real_decode = attachments.decode

    def counted_decode(kind, data, **options):
        reads.append([kind, options['mode']])
        return real_decode(kind, data, **options)

    job = Job(job_name, existing=True)
    try:
        with closing(DesktopService(Ledger(location / 'office.db'))) as service:
            sampler = JobSampler(job, interval=0.05)
            attachments.decode = counted_decode
            sampler.start()
            try:
                started = time.perf_counter_ns()
                report = invoke(service, 'attachments.inspect', attachment_ids=ids, objective=CASES[case])
                wall_ms = (time.perf_counter_ns() - started) / 1e6
            finally:
                stats = sampler.stop()
                attachments.decode = real_decode
            check_answer(case, report, state, ids)
            if service.snapshot()['projects'][0]['attempts_consumed'] != 0:
                raise RuntimeError('Project budget changed')
            if stats['observation_errors'] or not sampler.samples or stats['cpu_seconds'] is None:
                raise RuntimeError('Missing Windows accounting endpoints')
            row = dict(case=case, wall_ms=round(wall_ms, 2),
                       cpu_s=round(stats['cpu_seconds'] - sampler.samples[0]['cpu_seconds'], 6),
                       sampled_peak_ws=stats['sampled_peak_working_set_sum_bytes'],
                       sampled_peak_private=stats['sampled_peak_private_commit_sum_bytes'],
                       lifetime_peak_job_commit=stats['job_peak_commit_bytes'],
                       samples=stats['sample_count'], incomplete_samples=stats['incomplete_samples'],
                       readers=reads, acceptable=True, attempts=0, model_calls=0)
            target.write_text(json.dumps(row), encoding='utf-8')
    finally:
        # The driver owns the job. The measured process only borrows a query handle.
        job.close()


def measure_block(reader, root, location, corpus, cases):
    import win32event
    import win32process
    from neural_office.windows_job import Job
    from tools.measure_ollama_terminal import launch

    script = str(Path(__file__).resolve())
    location.mkdir()
    subprocess.run([reader, '-B', script, '_prepare', str(root), str(location), str(corpus)], check=True, timeout=60)
    rows = []
    for case in cases:
        target = location / (case + '.json')
        with Job('NeuralOffice-Inspection-' + uuid.uuid4().hex) as job:
            args = [reader, '-B', script, '_sample', str(root), str(location), case, job.name, str(target)]
            process, _ = launch(job, args, os.environ.copy())
            try:
                if win32event.WaitForSingleObject(process, 60_000) != win32event.WAIT_OBJECT_0:
                    raise TimeoutError(f'{case} did not finish')
                if win32process.GetExitCodeProcess(process):
                    diagnostic = target.with_suffix('.error.txt')
                    raise RuntimeError(diagnostic.read_text(encoding='utf-8') if diagnostic.exists() else case)
            finally:
                process.Close()
        rows.append(json.loads(target.read_text(encoding='utf-8')))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--reader', required=True, type=Path)
    parser.add_argument('--pairs', type=int, choices=range(1, 21), default=8)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if os.name != 'nt' or args.output.exists() or not args.output.parent.is_dir():
        parser.error('Windows and a new output file in an existing directory are required')
    sys.path.insert(0, str(ROOT))
    reader, baseline = str(args.reader.resolve(strict=True)), args.baseline.resolve(strict=True)
    roots = {'before': baseline, 'after': ROOT}
    if not all((root / 'neural_office' / 'attachments.py').is_file() for root in roots.values()) or baseline == ROOT:
        parser.error('Two distinct Neural Office source trees are required')
    versions = {name: subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
                for name, root in roots.items()}
    modified = {name: bool(subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain',
                                                     '--', 'neural_office', 'examples', 'tools']))
                for name, root in roots.items()}
    runtime_code = ("import json, platform, sqlite3; from importlib.metadata import version; "
                    "print(json.dumps(dict(python=platform.python_version(), sqlite=sqlite3.sqlite_version, "
                    "pillow=version('Pillow'), pypdfium2=version('pypdfium2'))))")
    runtime = json.loads(subprocess.check_output([reader, '-B', '-c', runtime_code], text=True))
    captured = datetime.now(timezone.utc).isoformat()
    results = []
    with tempfile.TemporaryDirectory() as folder:
        tmp = Path(folder)
        corpus = tmp / 'inputs'
        for pair in range(args.pairs):
            order = ('before', 'after') if pair % 2 == 0 else ('after', 'before')
            cases = list(CASES)
            offset = pair % len(cases)
            for name in order:
                block = measure_block(reader, roots[name], tmp / f'{pair}-{name}', corpus, cases[offset:] + cases[:offset])
                results.extend(dict(pair=pair + 1, version=name, **row) for row in block)
            print(f'{pair + 1}/{args.pairs} pairs checked', flush=True)
        hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(corpus.iterdir())}
    evidence = dict(schema=1, captured_utc=captured, system=platform.platform(), logical_cpus=os.cpu_count(),
                    commits=versions, modified_source=modified, runtime=runtime,
                    pairs=args.pairs, scope='fresh Windows service process and descendants per task, 50 ms samples',
                    prompts=CASES, source_sha256=hashes, runs=results)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    if sys.argv[1:2] == ['_prepare']:
        prepare(sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]))
    elif sys.argv[1:2] == ['_sample']:
        output = Path(sys.argv[6])
        try:
            sample(sys.argv[2], Path(sys.argv[3]), sys.argv[4], sys.argv[5], output)
        except Exception:
            import traceback
            output.with_suffix('.error.txt').write_text(traceback.format_exc(), encoding='utf-8')
            raise
    else:
        main()
