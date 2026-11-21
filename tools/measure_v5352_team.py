"""Compare real seven-role attempts with one Ollama CLI request in PowerShell on Windows."""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'qwen2.5:0.5b'
SAMPLE = (ROOT / 'examples/audit-sample.html').read_bytes()
FORM = b'<html lang="es">\n<title>Ficha</title>\n<body>\n<p>Contacto</p>\n<input id="mail">\n</body></html>'
CLEAN = b'<html lang="es"><title>Ficha</title><body><label>Nombre<input></label></body></html>'
CASES = {
    'imagen': (SAMPLE, 'Indica el código exacto de la imagen sin descripción y su línea en el archivo.'),
    'control': (FORM, 'Indica el código y la línea del control sin etiqueta en este archivo.'),
    'limpio': (CLEAN, 'Indica si encontraste hallazgos en estas comprobaciones y qué queda fuera de la revisión.'),
    'abierto': (SAMPLE, 'Recomienda cómo corregir la imagen y el control de formulario. Indica un límite de esta revisión.'),
}
LOCATIONS = {'imagen': ('IMAGE_ALT_MISSING', 6), 'control': ('CONTROL_LABEL_CANDIDATE', 5)}


def grade(case, answer):
    text = answer.casefold()
    if case in LOCATIONS:
        code, line = LOCATIONS[case]
        return {'code': code.casefold() in text, 'line': bool(re.search(
            rf'(?:l[ií]nea|line)\s*[:=#]?\s*{line}\b|{code}\s*[:·,]\s*{line}\b', answer, re.I))}
    limit = bool(re.search(r'estátic|static|navegador|browser|render|manual|dinámic|interacci', text))
    if case == 'limpio':
        return {'no_findings': bool(re.search(r'ning[uú]n|sin (?:hallazgos|problemas)|no (?:hay|se (?:encontr|detect|observ|identific)|encontr|identifi|detect)|no findings', text)),
                'scope_limit': limit}
    return {'image_remedy': bool(re.search(r'\balt\b|texto alternativo|text alternative', text)),
            'control_remedy': bool(re.search(r'etiquet|\blabel\b|nombre accesible', text)), 'scope_limit': limit}


def preload(backend, profile, options):
    from neural_office.ollama import local_metadata
    conn = http.client.HTTPConnection('127.0.0.1', backend.port, timeout=120)
    try:
        body = {'model': MODEL, 'prompt': '', 'stream': False, 'options': options}
        conn.request('POST', '/api/generate', json.dumps(body), {'Content-Type': 'application/json'})
        reply = conn.getresponse()
        if reply.status != 200 or json.load(reply).get('done') is not True:
            raise ValueError('Warm-up failed')
    finally:
        conn.close()
    if [m['digest'] for m in local_metadata('/api/ps', backend.port)['models']] != [profile['model_digest']]:
        raise ValueError('Warm-up residency unproven')


def run_team(folder, case, profile, outer, warm):
    from neural_office import ollama
    from neural_office.ledger import Ledger
    from neural_office.measurements import job_sample
    from neural_office.runner import ROLES, run
    source, goal = CASES[case]
    profile = (ollama.review_profile(profile, 7) if hasattr(ollama, 'review_profile')
               else {**profile, 'roles': 7})
    ledger = Ledger(folder / 'office.sqlite3')
    ledger.initialize()
    ledger.register('Prueba', folder)
    attempt = ledger.reserve('Prueba', goal, source, profile, 'one', admit=True)
    checkpoints = {}
    class Preloaded(ollama.OwnedOllama):
        def start(self):
            super().start()
            preload(self, profile, ollama.inference_options(profile))
            checkpoints['ready_cpu_s'] = job_sample(outer)['cpu_seconds']
    if run(ledger, attempt, 7, backend_factory=Preloaded if warm else ollama.OwnedOllama) != 'ACCEPTED':
        raise ValueError('Real team did not deliver')
    row = ledger.attempt(attempt)
    with ledger.connection() as con:
        calls = [dict(r) for r in con.execute(
            'SELECT role,payload_sha,response FROM calls WHERE attempt=? ORDER BY seq', (attempt,))]
    if [c['role'] for c in calls] != list(ROLES) or len(row['outputs']) != 7:
        raise ValueError('Seven ordered model calls required')
    outputs = []
    for call in calls:
        response = json.loads(call['response'])
        run_info = response['_neural_office_execution']
        if (response.get('done') is not True or not run_info['owned_job']
                or run_info['model_digest'] != profile['model_digest'] or not run_info['eval_count']):
            raise ValueError('Incomplete real model receipt')
        outputs.append({'role': call['role'], 'request_sha256': call['payload_sha'],
                        'answer': response['message']['content'], **run_info})
    if len({o['request_sha256'] for o in outputs}) != 7:
        raise ValueError('Role requests must be distinct')
    product = json.loads(row['artifact'])
    if product['source_sha256'] != hashlib.sha256(source).hexdigest():
        raise ValueError('Delivery source mismatch')
    if warm:
        checkpoints['inference_cpu_s'] = job_sample(outer)['cpu_seconds'] - checkpoints['ready_cpu_s']
    return dict(answer=outputs[-1]['answer'], roles=outputs, findings=product['findings'],
                requested_rule=product.get('requested_rule'), state=row['state'], **checkpoints)


def run_terminal(folder, case, profile, warm, outer):
    from neural_office.audit import audit_html
    from neural_office.measurements import job_sample
    from neural_office.ollama import OwnedOllama, local_metadata
    source, goal = CASES[case]
    findings = audit_html(source)
    evidence = [f"{f['code']} · línea {f['line']} · columna {f['column']}" for f in findings]
    prompt = goal + '\nLecturas estáticas locales:\n' + ('\n'.join(evidence) or 'Ningún hallazgo en las cuatro comprobaciones estáticas.')
    backend = OwnedOllama('Local\\NeuralReference_' + uuid.uuid4().hex, profile, folder / 'serve.log')
    try:
        before_boot = job_sample(outer)['cpu_seconds']
        backend.start()
        after_boot = job_sample(outer)['cpu_seconds']
        if local_metadata('/api/ps', backend.port)['models']:
            raise ValueError('Reference must start with no resident model')
        if warm:
            preload(backend, profile, {})
        shell = shutil.which('pwsh') or shutil.which('powershell')
        out = folder / 'answer.txt'
        env = {**os.environ, 'OLLAMA_HOST': f'127.0.0.1:{backend.port}', 'OLLAMA_NOHISTORY': '1',
               'NEURAL_MODEL': MODEL, 'NEURAL_COMMAND': shutil.which('ollama'),
               'NEURAL_PROMPT': prompt, 'NEURAL_OUT': str(out)}
        command = ("$ErrorActionPreference='Stop'; $OutputEncoding=[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
                   "'' | & $env:NEURAL_COMMAND run --nowordwrap $env:NEURAL_MODEL $env:NEURAL_PROMPT > $env:NEURAL_OUT; exit $LASTEXITCODE")
        started_cpu = job_sample(outer)['cpu_seconds']
        started = time.perf_counter()
        subprocess.run([shell, '-NoLogo', '-NonInteractive', '-NoProfile', '-Command', command],
                       env=env, stdin=subprocess.DEVNULL, check=True, timeout=180)
        elapsed = time.perf_counter() - started
        query_cpu = job_sample(outer)['cpu_seconds'] - started_cpu
        models = local_metadata('/api/ps', backend.port)['models']
        if [r['digest'] for r in models] != [profile['model_digest']]:
            raise ValueError('Reference model identity changed')
        raw = out.read_bytes()
        answer = raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig').strip()
        return dict(answer=answer, model_loaded_before_query=warm, query_cpu_s=query_cpu, query_wall_s=elapsed,
                    startup_cpu_s=after_boot-before_boot, preload_cpu_s=started_cpu-after_boot,
                    resident={k: models[0][k] for k in ('size_vram', 'size', 'context_length')})
    finally:
        try: backend.terminate()
        finally: backend.close()


def worker(args):
    sys.path.insert(0, str(args.repo))
    from neural_office.ollama import local_metadata, select_model
    from neural_office.windows_job import Job
    folder = args.output
    outer = Job(args.job, existing=True)
    try:
        profile = select_model(MODEL, local_metadata()['models'])
        version = local_metadata('/api/version')['version']
        if args.arm in ('team', 'previous', 'team-preloaded'):
            result = run_team(folder, args.case, profile, outer, args.arm == 'team-preloaded')
        else:
            result = run_terminal(folder, args.case, profile, args.arm == 'warm', outer)
        if not result['answer'].strip():
            raise ValueError('No answer')
        result.update(grade=grade(args.case, result['answer']), model=MODEL, digest=profile['model_digest'],
                      ollama=version, source_sha256=hashlib.sha256(CASES[args.case][0]).hexdigest())
        (folder / 'result.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    finally:
        outer.close()


def capture(repo, arm, case, dest):
    from neural_office.measurements import JobSampler, job_sample
    from neural_office.windows_job import Job
    from measure_ollama_terminal import peak_cpu_cores
    name = 'Local\\NeuralTeamTrial_' + uuid.uuid4().hex
    with tempfile.TemporaryDirectory() as tmp, Job(name) as job:
        folder = Path(tmp)
        with (folder / 'worker.log').open('wb') as log:
            sampler = JobSampler(job, interval=.1)
            sampler.start()
            try:
                proc = job.start([sys.executable, '-B', str(Path(__file__).resolve()), '--job', name,
                                  '--repo', str(repo), '--arm', arm, '--case', case, '--output', tmp],
                                 env=os.environ.copy(), log=log)
                code = proc.wait(timeout=480)
            finally:
                stats = sampler.stop()
        if code:
            raise RuntimeError((folder / 'worker.log').read_text(encoding='utf-8', errors='replace')[-3000:])
        if job.active() or stats['observation_errors'] or stats['cpu_seconds'] != job_sample(job)['cpu_seconds']:
            raise RuntimeError('Incomplete job CPU accounting')
        result = json.loads((folder / 'result.json').read_bytes())
        result.update(arm=arm, case=case, finished_utc=datetime.now(timezone.utc).isoformat(), resources=stats,
                      peak_cores_1s=peak_cpu_cores(sampler.samples), system=platform.platform())
        dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(case, arm, stats['cpu_seconds'], result['grade'], flush=True)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--repo', type=Path, default=ROOT)
    p.add_argument('--previous', type=Path)
    p.add_argument('--case', choices=CASES)
    p.add_argument('--job')
    p.add_argument('--arm', choices=['team','terminal','warm','previous','team-preloaded'])
    p.add_argument('--repeats', type=int, choices=range(1, 6), default=2)
    args = p.parse_args()
    if args.job:
        worker(args)
        return
    sys.path.insert(0, str(ROOT))
    args.output.mkdir(exist_ok=False)
    summary = []
    for case in ([args.case] if args.case else CASES):
        if args.arm:
            if args.arm == 'previous' and not args.previous:
                p.error('--arm previous requires the previous checkout')
            capture(args.previous if args.arm == 'previous' else ROOT, args.arm, case, args.output / f'{case}-{args.arm}.json')
            continue
        if args.previous:
            capture(args.previous, 'previous', case, args.output / f'{case}-previous.json')
        for i in range(args.repeats):
            rows = {}
            for arm in (('terminal', 'team', 'warm') if i % 2 == 0 else ('warm', 'team', 'terminal')):
                rows[arm] = capture(ROOT, arm, case, args.output / f'{case}-{i}-{arm}.json')
            if len({(r['source_sha256'],r['digest'],r['ollama']) for r in rows.values()}) != 1:
                raise ValueError('Unmatched pair')
            team = rows['team']['resources']['cpu_seconds']
            summary.append(dict(case=case, repetition=i+1, team_cpu=team,
                                cold_ratio=team/rows['terminal']['resources']['cpu_seconds'],
                                warm_ratio=team/rows['warm']['query_cpu_s'], grade=rows['team']['grade']))
    if args.arm:
        return
    record = dict(utc=datetime.now(timezone.utc).isoformat(), samples=summary, limit=1.5,
                  passed=all(r['cold_ratio']<=1.5 and r['warm_ratio']<=1.5 and all(r['grade'].values()) for r in summary))
    (args.output / 'summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    raise SystemExit(0 if record['passed'] else 1)


if __name__ == '__main__':
    main()
