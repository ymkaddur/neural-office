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
import socket
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
GALLERY = (b'<html lang="es">\n<title>Demo</title>\n<body>\n  <img src="primera.jpg">\n'
           b'  <img src="decorativa.jpg" alt="">\n  <img src="ultima.jpg">\n</body></html>')
CASES = {
    'imagen': (SAMPLE, 'Indica el código exacto de la imagen sin descripción y su línea en el archivo.'),
    'control': (FORM, 'Indica el código y la línea del control sin etiqueta en este archivo.'),
    'limpio': (CLEAN, 'Indica si encontraste hallazgos en estas comprobaciones y qué queda fuera de la revisión.'),
    'abierto': (SAMPLE, 'Recomienda cómo corregir la imagen y el control de formulario. Indica un límite de esta revisión.'),
    'varias': (GALLERY, 'Indica el código y todas las líneas de la imagen sin descripción. Añade cómo contrastarlas en el navegador.'),
}
LOCATIONS = {'imagen': ('IMAGE_ALT_MISSING', 6), 'control': ('CONTROL_LABEL_CANDIDATE', 5),
             'varias': ('IMAGE_ALT_MISSING', 4)}
SAMPLE_LOCATIONS = [('DOCUMENT_TITLE_MISSING',1,1),('HTML_LANGUAGE_MISSING',2,1),
                    ('IMAGE_ALT_MISSING',6,3),('CONTROL_LABEL_CANDIDATE',7,3)]
EXPECTED_FINDINGS = {'imagen':SAMPLE_LOCATIONS,'abierto':SAMPLE_LOCATIONS,
                     'control':[('CONTROL_LABEL_CANDIDATE',5,1)],'limpio':[],
                     'varias':[('IMAGE_ALT_MISSING',4,3),('IMAGE_ALT_MISSING',6,3)]}


def grade(case, answer):
    text = answer.casefold()
    if case == 'varias':
        mentions = re.findall(r'\b(?:l[ií]neas?|lines?)\s*[:=#]?\s*(\d+(?:\s*(?:,|y|and)\s*\d+)*)', text)
        lines = {int(n) for phrase in mentions for n in re.findall(r'\d+',phrase)}
        return {'code':'image_alt_missing' in text,
                'cited_lines':lines=={line for _,line,_ in EXPECTED_FINDINGS[case]},
                'browser_check':bool(re.search(r'navegador|browser',text) and re.search(r'\bdom\b|accesibili|accessibili',text))}
    if case in LOCATIONS:
        code, line = LOCATIONS[case]
        matches = re.findall(r'\b([A-Z][A-Z_0-9]+)\b\s*[,·:]\s*(?:línea|line)\s+([0-9]+)'
                             r'(?:\s*[,·]\s*(?:columna|column)\s+([0-9]+))?', answer)
        verified = EXPECTED_FINDINGS[case]
        locations_agree = bool(matches) and all(
            any(cited == c and int(at) == ln and (not col or int(col) == column)
                for c, ln, column in verified) for cited, at, col in matches)
        return {'code': code.casefold() in text, 'line': bool(re.search(
            rf'(?:l[ií]nea|line)\s*[:=#]?\s*{line}\b|{code}\s*[:·,]\s*{line}\b', answer, re.I)),
            'cited_location': locations_agree and any(cited == code and int(at) == line for cited, at, _ in matches)}
    limit = bool(re.search(r'navegador|brows|render|manual|dinámic|interacci|code execution', text))
    if case == 'limpio':
        return {'no_findings': bool(re.search(r'ning[uú]n|sin (?:hallazgos|problemas)|no (?:hay|he encontr|se (?:encontr|detect|observ|identific)|encontr|identifi|detect)|no (?:findings|issues)', text)),
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
            checkpoints['roles_cpu_s'] = []

        def infer(self, payload):
            before = job_sample(self.job)['cpu_seconds']
            starting = time.perf_counter()
            response = super().infer(payload)
            checkpoints['roles_cpu_s'].append({'cpu_s': job_sample(self.job)['cpu_seconds']-before,
                                               'wall_s':time.perf_counter()-starting,
                                               'prompt_tokens':response['prompt_eval_count'],
                                               'output_tokens':response['eval_count']})
            return response
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
    if [(f['code'],f['line'],f['column']) for f in product['findings']] != EXPECTED_FINDINGS[case]:
        raise ValueError('Delivery contradicts the independently specified file locations')
    if product.get('requested_rule') != (LOCATIONS[case][0] if case in LOCATIONS else None):
        raise ValueError('Delivery addresses the wrong rule')
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
    class TerminalServer(OwnedOllama):
        def start(self):
            with socket.socket() as reserved:
                reserved.bind(('127.0.0.1',0))
                self.port = reserved.getsockname()[1]
            # Keep the operator's normal hardware, context and thread defaults.
            env = {**os.environ,'OLLAMA_HOST':f'127.0.0.1:{self.port}','OLLAMA_NO_CLOUD':'1'}
            self.log = self.log_path.open('wb')
            server = self.job.start([shutil.which('ollama'),'serve'], env=env, log=self.log)
            deadline = time.monotonic() + 60
            while server.poll() is None and time.monotonic() < deadline:
                try:
                    local_metadata('/api/version', self.port)
                except (OSError,http.client.HTTPException):
                    time.sleep(.05)
                    continue
                self._assert_owned_listener()
                self.check_model()
                return
            raise RuntimeError('The private terminal reference did not start')
    backend = TerminalServer('Local\\NeuralReference_' + uuid.uuid4().hex, profile, folder / 'serve.log')
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
        preload_cpu = job_sample(outer)['cpu_seconds'] - after_boot
        ready = folder / 'powershell-ready'
        env['NEURAL_BENCH_READY'] = str(ready)
        wait_for_input = ("[IO.File]::WriteAllText($env:NEURAL_BENCH_READY,'ready'); "
                          "if ([Console]::ReadLine() -ne 'run') { exit 2 }; ")
        shell_args = [shell, '-NoLogo', '-NonInteractive', '-NoProfile', '-Command', wait_for_input+command]
        client = subprocess.Popen(shell_args, env=env, stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline = time.monotonic() + 30
            while not ready.exists():
                if client.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('PowerShell did not reach its input prompt')
                time.sleep(.01)
            from neural_office.measurements import JobSampler
            from tools.measure_ollama_terminal import peak_cpu_cores
            sampler = JobSampler(outer,.1)
            sampler.start()
            started_cpu = job_sample(outer)['cpu_seconds']
            started = time.perf_counter()
            try:
                client.communicate(b'run\n',timeout=180)
                if client.returncode:
                    raise RuntimeError(f'PowerShell reference exited with {client.returncode}')
                elapsed = time.perf_counter() - started
                query_cpu = job_sample(outer)['cpu_seconds'] - started_cpu
            finally:
                sampler.stop()
        finally:
            if client.poll() is None:
                client.kill()
                client.wait(timeout=10)
        models = local_metadata('/api/ps', backend.port)['models']
        if [r['digest'] for r in models] != [profile['model_digest']]:
            raise ValueError('Reference model identity changed')
        raw = out.read_bytes()
        answer = raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig').strip()
        return dict(answer=answer, model_loaded_before_query=warm, query_cpu_s=query_cpu, query_wall_s=elapsed,
                    startup_cpu_s=after_boot-before_boot, preload_cpu_s=preload_cpu,
                    query_peak_cores_1s=peak_cpu_cores(sampler.samples),
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
    from tools.measure_ollama_terminal import peak_cpu_cores
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
                # The worker handle can be signalled before descendant accounting settles.
                # Keep the sampler attached to the whole job until two idle readings agree.
                end = time.monotonic() + 5
                previous_cpu = None
                while time.monotonic() < end:
                    end_sample = job_sample(job)
                    idle_cpu = end_sample['cpu_seconds'] if end_sample['active_processes']==0 else None
                    if idle_cpu is not None and idle_cpu==previous_cpu:
                        break
                    previous_cpu = idle_cpu
                    time.sleep(.05)
                else:
                    raise RuntimeError(f'{case}/{arm}: process accounting did not settle: {end_sample}')
            finally:
                stats = sampler.stop()
        if code:
            failure = folder / 'worker-failure.json'
            record = {'arm':arm, 'case':case, 'worker_exit_code':code,
                      'worker_failure':json.loads(failure.read_bytes()) if failure.exists() else None,
                      'worker_log_tail':(folder / 'worker.log').read_text(encoding='utf-8',errors='replace')[-3000:]}
            rejected = dest.with_suffix('.rejected.json')
            rejected.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8')
            raise RuntimeError(f'{case}/{arm}: worker exited {code}; see {rejected}')
        receipt_end = job_sample(job)
        if (receipt_end['active_processes'] or stats['observation_errors']
                or stats['cpu_seconds'] != receipt_end['cpu_seconds']):
            rejected = {'arm':arm,'case':case,'sampler':stats,'final_read':receipt_end}
            dest.with_suffix('.rejected.json').write_text(json.dumps(rejected),encoding='utf-8')
            raise RuntimeError(f'{case}/{arm}: incomplete job CPU accounting; see {dest.with_suffix(".rejected.json")}')
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
        try:
            worker(args)
        except Exception as error:
            detail = {'type':type(error).__name__, 'message':str(error)}
            (args.output/'worker-failure.json').write_text(json.dumps(detail),encoding='utf-8')
            raise
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
                                ready_server_ratio=team/rows['terminal']['query_cpu_s'],
                                warm_ratio=team/rows['warm']['query_cpu_s'], grade=rows['team']['grade']))
    if args.arm:
        return
    record = dict(utc=datetime.now(timezone.utc).isoformat(), samples=summary, limit=1.5,
                  passed=all(max(r['cold_ratio'],r['ready_server_ratio'],r['warm_ratio'])<=1.5
                             and all(r['grade'].values()) for r in summary))
    (args.output / 'summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    raise SystemExit(0 if record['passed'] else 1)


if __name__ == '__main__':
    main()
