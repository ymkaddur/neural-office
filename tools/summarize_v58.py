"""Reconstruct V5.8 resource measurements from the private Windows samples and ledgers."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics

from tools.compare_v57 import GUIDANCE
from tools.measure_v58 import BASE, FROZEN, ROOT, require, specification


MIB = 1024**2
def read(path):
    return json.loads(path.read_bytes())


def interval(begin, end, samples):
    duration = (end['t'] - begin['t']) / 1e9
    cpu = end['cpu_seconds'] - begin['cpu_seconds']
    require(duration > 0 and cpu >= 0, 'invalid interval')
    within = [begin, *(s for s in samples if begin['t'] < s['t'] < end['t']), end]
    valid = [s for s in within if s['unreadable_processes'] == 0]
    require(valid and len(valid) >= 2, 'missing usable memory samples')
    return {'wall_s':duration, 'cpu_s':cpu,
            'peak_ws_mib':max(s['working_set_sum_bytes'] for s in valid)/MIB,
            'peak_private_mib':max(s['private_commit_sum_bytes'] for s in valid)/MIB,
            'samples':len(within), 'incomplete_samples':len(within)-len(valid),
            'max_gap_s':max(right['t']-left['t'] for left,right in zip(within,within[1:]))/1e9}


def distribution(values):
    return {'median':statistics.median(values),'min':min(values),'max':max(values)}


def combine(rows, field):
    return {name:distribution([r[field][name] for r in rows]) for name in
            ('wall_s','cpu_s','peak_ws_mib','peak_private_mib')}


def native_window(folder):
    recorded=read(folder/'result.json')
    samples=read(folder/'sampled.json')
    arm=recorded['arm']
    expected_bin=read(ROOT/'docs/evidence/V5_8_RECONNECTION.json')['packaged_candidate']['executable']['sha256']
    require(recorded['exe_sha256']==expected_bin and recorded['job_empty'] and recorded['close']['exited']
            and not samples['observation_errors'] and len(recorded['rows'])==2,'native identity or close')
    idle=interval(*recorded['idle_bounds'],samples['tree'])
    require(idle==recorded['idle'],'native idle reconstruction')
    rows=[]
    anchor=hashlib.sha256((ROOT/'examples/audit-sample.html').read_bytes()).hexdigest()
    model=specification()['digest']
    with sqlite3.connect((folder/'office.sqlite3').as_uri()+'?mode=ro',uri=True) as con:
        attempts=con.execute('SELECT state,snapshot_sha,profile,artifact FROM attempts ORDER BY ordinal').fetchall()
        require(len(attempts)==(2 if arm else 0),'desktop attempt count')
        for state,source,profile,artifact in attempts:
            conf=json.loads(profile)
            require(state=='ACCEPTED' and source==anchor and conf['mode']=='ollama-owned' and conf['roles']==arm
                    and conf['model_digest']==model and len(json.loads(artifact)['findings'])==4,'native report')
        calls=con.execute('SELECT state,response FROM calls').fetchall()
        require(len(calls)==2*arm,'native recorded calls')
        for state,response in calls:
            resp=json.loads(response)
            ex=resp['_neural_office_execution']
            require(state=='DONE' and resp['done'] and ex['owned_job'] and ex['mode']=='CPU'
                    and ex['size_vram']==0 and ex['model_digest']==model,'native provider provenance')
    for item in recorded['rows']:
        metrics=interval(item['begin'],item['end'],samples['tree'])
        require(metrics==item['work'],'native window reconstruction')
        before,after=item['counts_before'],item['counts_after']
        require(after['calls']-before['calls']==arm and len(after['states'])-len(before['states'])==int(bool(arm)),
                'native quota per cell')
        rows.append({'phase':item['phase'],'work':metrics,'calls':arm,'attempts':int(bool(arm))})
    # The group sampler starts at readiness and keeps this label through the first form.
    # Its clock differs from the Job clock on Windows with Python 3.12.
    before_first_action = [s['groups'] for s in samples['grouped']
                           if s['complete'] and s['phase'] == 'idle_before']
    webview = [group['webview']['rss_bytes'] / MIB for group in before_first_action
               if 'webview' in group and 'python' in group]
    require(webview, 'native group coverage before the final action')
    return {'arm':arm,'exe_sha256':expected_bin,'source_sha256':anchor,'launch_to_ready_s':recorded['launch_to_ready_s'],
            'idle':idle,'before_first_action_webview_ws_mib_median':statistics.median(webview),
            'job_empty':True,'rows':rows}


def compile_series(series):
    spec, env = specification(), read(series/'environment.json')
    require(env['corpus_sha256'] == FROZEN and env['product_commit'] == BASE
            and env['profile']['model_digest'] == spec['digest'] and not env['smoke'], 'series provenance')
    instrument = (ROOT/'tools/measure_v58.py').read_bytes().replace(b'\r\n', b'\n')
    require(hashlib.sha256(instrument).hexdigest() == env['instrument_sha256'], 'instrument changed')
    previous = read(ROOT/'docs/evidence/V5_7_COMPARISON.json')
    guidance = (ROOT/'desktop/src/connected/ConnectedWorkspace.tsx').read_text(encoding='utf-8')
    require(all(f"{key}:'{value}'" in guidance for key,value in GUIDANCE.items()), 'fixed guidance changed')
    old = {(r['task'],r['profile']):r for r in previous['trials']}
    summaries, trials, variants = [], [], {}
    decisions_path = series/'variant-ratings.json'
    decisions = read(decisions_path) if decisions_path.exists() else {}
    for task in spec['tasks']:
        for arm in task['order']:
            folder = series/f"{task['id']}-{arm}"
            raw = read(folder/'samples.json')
            require(raw['job_empty'] and raw['exit'] == 0 and raw['samples'][-1]['active_processes'] == 0,
                    'block ownership or exit')
            phases = ['cold','repeat','preloaded'] if arm else ['cold','repeat']
            with sqlite3.connect((folder/'office.sqlite3').as_uri()+'?mode=ro',uri=True) as con:
                require(con.execute('SELECT count(*) FROM attempts').fetchone()[0] == (3 if arm else 0)
                        and con.execute('SELECT count(*) FROM calls').fetchone()[0] == len(phases)*arm, 'ledger totals')
                for phase in phases:
                    row = read(folder/(phase+'.json'))
                    require((row['task'],row['arm'],row['phase']) == (task['id'],arm,phase), 'cell identity')
                    require(row['source_sha256'] == hashlib.sha256(task['html'].encode()).hexdigest(), 'source identity')
                    begin, end, provider = row['begin'], row['end'], row['backend']
                    observed = [tuple(f[k] for k in ('code','line','column')) for f in row['findings']]
                    expected = Counter(tuple(f) for f in task['expected'])
                    got = Counter(observed)
                    item = {'task':task['id'],'arm':arm,'phase':phase,'state':row['state'],'attempts':row['attempts'],
                            'source_sha256':row['source_sha256'],'calls':len(row['calls']), 'observed':observed,
                            'tp':sum((expected & got).values()),'fp':sum((got-expected).values()),
                            'fn':sum((expected-got).values()),'work':interval(begin,end,raw['samples'])}
                    if phase=='cold':
                        item['startup_to_capture_s'] = (begin['t']-raw['launch'])/1e9
                        item['launch_to_delivery_s'] = (end['t']-raw['launch'])/1e9
                    require(row['attempts']==int(bool(arm)) and len(row['calls'])==len(row['paragraphs'])==arm, 'work accounting')
                    if arm:
                        dbrow = con.execute('SELECT id,state,artifact FROM attempts WHERE request_key=?',(phase,)).fetchone()
                        require(dbrow[1]==row['state']=='ACCEPTED', 'accepted durable delivery')
                        artifact = json.loads(dbrow[2])
                        require(artifact['findings']==row['findings'] and [p['content'] for p in artifact['role_outputs']]==row['paragraphs'],
                                'report differs from durable artifact')
                        dbcalls = con.execute('SELECT role,payload_sha,state,response FROM calls WHERE attempt=? ORDER BY seq',(dbrow[0],)).fetchall()
                        require(len(dbcalls)==arm and provider['empty_at_start'] and provider['cleaned'], 'backend identity, close or accounting')
                        invocation_data=[]
                        for i,(call,dbcall) in enumerate(zip(row['calls'],dbcalls,strict=True)):
                            role,payload,status,response = dbcall
                            resp=json.loads(response)
                            require(status=='DONE' and role==call['role'] and payload==call['request_sha256']
                                    and call['resident_before']==(i>0 or phase=='preloaded'), 'call identity/residency')
                            require(call['context_length']==8192 and call['model_allocated_vram_bytes']==0, 'model allocation')
                            fields=('prompt_eval_count','eval_count','load_duration','total_duration','done_reason')
                            require(all(call[k]==resp[k] for k in fields), 'provider metrics differ from SQLite')
                            invocation_data.append({'role':role,'resident_before':call['resident_before'],
                                'request_sha256':payload,**{k:call[k] for k in fields}})
                        item.update(provider_calls=invocation_data,
                            model_phase=interval(row['calls'][0]['begin'],row['calls'][-1]['end'],raw['samples']),
                            backend_cpu_s=provider['server_job']['cpu_seconds'],
                            backend_peak_commit_mib=provider['server_job']['job_peak_commit_bytes']/MIB,
                            backend_closed=True)
                        require(item['backend_cpu_s'] is not None and item['work']['cpu_s']+.032 >= item['backend_cpu_s'],
                                'outer CPU accounting unexpectedly excludes the model')
                        if phase=='preloaded':
                            pre=provider['preload']
                            require(pre['done_reason']=='load' and pre['reported_output_tokens'] in (0,None), 'preload generated tokens')
                            item['preload']=interval(pre['begin'],pre['end'],raw['samples'])
                        else:
                            require(provider['preload'] is None, 'unexpected preload')
                    else:
                        require(row['state']=='STATIC' and provider is None and not row['paragraphs'], 'static isolation')
                        item['provider_calls']=[]
                    historical=old[(task['id'],arm)]
                    old_paragraphs=[previous['distinct_synthetic_model_paragraphs'][i] for i in historical['paragraph_indices']]
                    text_key=hashlib.sha256(json.dumps([task['id'],observed,row['paragraphs']],ensure_ascii=False,
                                                       separators=(',',':')).encode()).hexdigest()
                    item['quality_key']=text_key
                    if [list(v) for v in observed]==historical['observed'] and row['paragraphs']==old_paragraphs:
                        item['quality']={k:historical[k] for k in ('points','extra','unsupported','reason')}
                        item['quality_basis']='identical findings, fixed guidance and paragraphs for this case'
                    else:
                        variants[text_key]={'task':task['id'],'findings':observed,'paragraphs':row['paragraphs']}
                        item['quality']=decisions.get(text_key)
                        item['quality_basis']='variant reviewed against the frozen rubric'
                    trials.append(item)
    require(len(trials)==48 and sum(r['calls'] for r in trials)==72,'planned denominator')
    for arm in (0,1,3):
        for phase in (('cold','repeat','preloaded') if arm else ('cold','repeat')):
            group=[r for r in trials if r['arm']==arm and r['phase']==phase]
            require(len(group)==6,'empty or duplicate case')
            calls=[c for r in group for c in r['provider_calls']]
            q=[r['quality'] for r in group]
            summary={'arm':arm,'phase':phase,'n':len(group),'work':combine(group,'work'),
                'machine_cpu_pct':distribution([100*r['work']['cpu_s']/(r['work']['wall_s']*env['logical_processors'])
                                                for r in group]),
                'attempts':sum(r['attempts'] for r in group),'calls':len(calls),
                'tokens_in':sum(c['prompt_eval_count'] for c in calls),'tokens_out':sum(c['eval_count'] for c in calls),
                'truncated_calls':sum(c['done_reason']=='length' for c in calls),
                'incomplete_samples':sum(r['work']['incomplete_samples'] for r in group),
                'tp':sum(r['tp'] for r in group),'fn':sum(r['fn'] for r in group),'fp':sum(r['fp'] for r in group),
                'exact_cases':sum(r['fn']==r['fp']==0 for r in group),
                'decision_points':sum(x['points'] for x in q) if all(q) else None,
                'additional_actions':sum(x['extra'] for x in q) if all(q) else None,
                'unsupported_cases':sum(x['unsupported'] for x in q) if all(q) else None}
            if arm:
                summary['model_phase']=combine(group,'model_phase')
                summary['first_load_s']=distribution([r['provider_calls'][0]['load_duration']/1e9 for r in group])
            if phase=='preloaded':
                summary['preload']=combine(group,'preload')
            if phase=='cold':
                summary['launch_to_delivery_s']=distribution([r['launch_to_delivery_s'] for r in group])
            summaries.append(summary)
    paired=[]
    for arm in (1,3):
        cold={r['task']:r for r in trials if r['arm']==arm and r['phase']=='repeat'}
        hot={r['task']:r for r in trials if r['arm']==arm and r['phase']=='preloaded'}
        keys=sorted(cold)
        require(set(keys)==set(hot) and len(keys)==6, 'model temperature pairs')
        require(all(cold[k]['provider_calls'][0]['request_sha256']==hot[k]['provider_calls'][0]['request_sha256']
                    for k in keys), 'first role prompt differs in paired trials')
        paired.append({'arm':arm,'n':len(keys),'definition':'weights preloaded minus normal repeat, within each task',
                       'wall_difference_s':distribution([hot[k]['work']['wall_s']-cold[k]['work']['wall_s'] for k in keys]),
                       'generation_window_difference_s':distribution([hot[k]['model_phase']['wall_s']-cold[k]['model_phase']['wall_s'] for k in keys]),
                       'work_cpu_difference_s':distribution([hot[k]['work']['cpu_s']-cold[k]['work']['cpu_s'] for k in keys])})
    return {'schema':1,'environment':env,'trials':trials,'summaries':summaries,'paired':paired,'variants':variants}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--series',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native',type=Path,action='append',default=[],help='Completed native window block; can be repeated')
    a=p.parse_args()
    result=compile_series(a.series.resolve())
    if (a.series/'hardware.json').is_file():
        result['hardware']=read(a.series/'hardware.json')
        require(result['hardware']['logical_processors']==result['environment']['logical_processors'],'hardware mismatch')
    if a.native:
        result['native']=[native_window(f.resolve()) for f in a.native]
        require(len(set(r['arm'] for r in result['native']))==len(a.native),'duplicate native block')
    with a.output.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')
    print(f"{len(result['trials'])} cells, {len(result['variants'])} distinct variants relative to V5.7.")
