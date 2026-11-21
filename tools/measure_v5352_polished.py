"""Measure real, already-resident seven-role desktop turns against an already-open PowerShell and Ollama."""
import argparse
import base64
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.measure_v5352_team import CASES, MODEL, capture, grade
from neural_office.desktop_service import DesktopService
from neural_office.ledger import Ledger
from neural_office.measurements import job_cpu_seconds
from neural_office.runner import ROLES
from neural_office.windows_job import Job


def repair_checks(raw):
    try:
        answer = json.loads(raw)
    except (TypeError, ValueError):
        return {'structured':False}
    if not isinstance(answer,dict) or not all(isinstance(answer.get(k),str) for k in ('imagen','formulario','limite')):
        return {'structured':False}
    image, form, scope = (answer[k].casefold() for k in ('imagen','formulario','limite'))
    return {'image_action':'alt' in image and ('informaci' in image or 'función' in image)
            and ('decor' in image or 'adorna' in image),
            'label_association':'label' in form and (('for' in form and 'id' in form) or 'envuelve' in form),
            'manual_check':'navegador' in scope and ('nombre accesible' in scope or 'lector de pantalla' in scope)}


def completed_calls(state, attempt):
    with closing(sqlite3.connect(state.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        attempts = db.execute('SELECT state,objective,profile FROM attempts WHERE id=?',(attempt,)).fetchone()
        rows=db.execute('SELECT role,payload_sha,state,response FROM calls WHERE attempt=? ORDER BY seq',(attempt,)).fetchall()
    if not attempts or attempts[0]!='ACCEPTED' or [r[0] for r in rows]!=list(ROLES) or len({r[1] for r in rows})!=7:
        raise ValueError('Seven accepted, distinct ordered calls are required')
    profile=json.loads(attempts[2])
    receipts=[]
    for role, request, state, reply in rows:
        response=json.loads(reply)
        info=response['_neural_office_execution']
        if (state!='DONE' or not response['done'] or not info['owned_job'] or info['eval_count']<=0
                or info['model_digest']!=profile['model_digest'] or not response['message']['content'].strip()):
            raise ValueError('Invalid actual model receipt')
        receipts.append(dict(role=role,request=request,answer=response['message']['content'],tokens=info['eval_count'],
                             prompt_tokens=info['prompt_eval_count'],runtime=info['runtime_instance'],
                             reused=info['reused_runtime'],resident=info['resident_before_turn'],vram=info['size_vram']))
    return attempts[1],profile['model_digest'],receipts


def office_arms(folder, job_name, case):
    outer=Job(job_name, existing=True)
    if not outer.contains_current_process():
        outer.close()
        raise RuntimeError('The measured desktop worker is outside the accounting job')
    state=folder/'office.sqlite3'
    service=DesktopService(Ledger(state))
    samples=[]
    try:
        digest=next(m['model_digest'] for m in service.models() if m['model']==MODEL)
        first='limpio' if case!='limpio' else 'control'
        for index,name in enumerate((first,case,case)):
            source,goal=CASES[name]
            path=folder/f'doc-{index}.html'
            path.write_bytes(source)
            selected=service.host_capture('medicion',path)
            approval=service.preview('medicion',selected['entry_token'],digest,7,goal)
            start=job_cpu_seconds(outer)
            begin=time.perf_counter()
            admitted=service.start(approval['approval_token'],str(uuid.uuid4()),approval['expected_revision'])
            service._worker.join(420)
            if service._worker.is_alive():
                raise TimeoutError('No terminal team receipt in 420 seconds')
            report=service.report(admitted['id'])
            source_report=service.report_read(admitted['id'],0,2048)
            chunk=base64.b64decode(source_report['base64'],validate=True)
            if (not chunk or source_report['sha256']!=report['sha256']
                    or hashlib.sha256(chunk).hexdigest()!=source_report['chunk_sha256']):
                raise ValueError('Delivered bytes do not match the recorded report')
            cpu=job_cpu_seconds(outer)-start
            elapsed=time.perf_counter()-begin
            objective,model,calls=completed_calls(state,admitted['id'])
            if (objective!=goal or model!=digest or len({r['runtime'] for r in calls})!=1
                    or not all(r['reused']==bool(index) and r['resident']==bool(index) for r in calls)):
                raise ValueError('Changed goal, runtime or residency')
            if index and calls[0]['runtime']!=samples[0]['calls'][0]['runtime']:
                raise ValueError('Distinct runtime between authorized project turns')
            checks=repair_checks(calls[-1]['answer']) if name=='abierto' else grade(name,calls[-1]['answer'])
            samples.append(dict(case=name,attempt=admitted['id'],objective=goal,model_digest=model,
                                source_sha256=hashlib.sha256(source).hexdigest(),cpu_s=cpu,wall_s=elapsed,
                                calls=calls,checks=checks))
    finally:
        try:
            if not service.close():raise RuntimeError('Desktop remained active')
        finally:
            outer.close()
    return samples


def office(output, case):
    name='Local\\PolishedDesktopBench_'+uuid.uuid4().hex
    with tempfile.TemporaryDirectory() as tmp, Job(name) as job:
        folder=Path(tmp)
        with output.with_suffix('.log').open('wb') as log:
            process=job.start([sys.executable,'-B',str(Path(__file__).resolve()),'--worker',name,'--case',case,
                               '--output',str(folder)],env=os.environ.copy(),log=log)
            if process.wait(timeout=660)!=0:
                raise RuntimeError('Desktop trial failed. See '+str(output.with_suffix('.log')))
        end=time.monotonic()+5
        while job.active() and time.monotonic()<end:time.sleep(.05)
        if job.active():raise RuntimeError('Desktop left a descendant')
        result=json.loads((folder/'office.json').read_bytes())
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',choices=CASES)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--worker')
    p.add_argument('--require-target',action='store_true',help='Fail after recording all pairs if any misses CPU or quality.')
    args=p.parse_args()
    if args.worker:
        rows=office_arms(args.output,args.worker,args.case)
        (args.output/'office.json').write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
        return
    args.output.mkdir(exist_ok=False)
    results=[]
    for case in ([args.case] if args.case else CASES):
        # Two independent CLI invocations bracket the two ordinary hot desktop attempts.
        before=capture(ROOT,'warm',case,args.output/(case+'-first.json'),boundaries_only=True)
        _,first,second=office(args.output/(case+'-desktop.json'),case)
        after=capture(ROOT,'warm',case,args.output/(case+'-last.json'),boundaries_only=True)
        for team,terminal in ((first,before),(second,after)):
            if not terminal['model_loaded_before_query'] or team['model_digest']!=terminal['digest'] or team['source_sha256']!=terminal['source_sha256']:
                raise ValueError('Incomparable local inputs or model residency')
            ratio=team['cpu_s']/terminal['query_cpu_s']
            results.append(dict(case=case,team_cpu_s=team['cpu_s'],terminal_cpu_s=terminal['query_cpu_s'],
                                ratio=ratio,checks=team['checks'],passed=ratio<=1.3 and all(team['checks'].values())))
            print(case,team['cpu_s'],terminal['query_cpu_s'],round(ratio,4),team['checks'],flush=True)
        (args.output/'summary.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8',newline='\n')
    if args.require_target and not all(r['passed'] for r in results):
        raise SystemExit('At least one recorded warm pair missed a gate')


if __name__=='__main__':main()
