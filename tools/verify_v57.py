"""Recompute the published V5.7 comparison from synthetic evidence, without inference."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]


def require(condition, issue):
    if not condition:
        raise ValueError(issue)


def verify():
    fixtures = ROOT / 'examples/v57-tasks.json'
    evidence = json.loads((ROOT / 'docs/evidence/V5_7_COMPARISON.json').read_bytes())
    frozen = fixtures.read_bytes().replace(b'\r\n', b'\n')
    spec = json.loads(frozen)
    require(hashlib.sha256(frozen).hexdigest() == evidence['corpus_sha256'], 'corpus identity')
    require(spec['digest'] == evidence['environment']['model_digest'], 'model identity')
    rows = evidence['trials']
    order = [(t['id'], arm) for t in spec['tasks'] for arm in t['order']]
    require([(r['task'], r['profile']) for r in rows] == order and len(set(order)) == 18, 'trial order')
    tasks = {t['id']: t for t in spec['tasks']}
    ratings = {}
    for r in rows:
        case = tasks[r['task']]
        require(hashlib.sha256(case['html'].encode()).hexdigest() == r['source_sha256'], 'source identity')
        got = Counter(tuple(f) for f in r['observed'])
        wanted = Counter(tuple(f) for f in case['expected'])
        counts = (sum((got & wanted).values()), sum((got - wanted).values()), sum((wanted - got).values()))
        require(counts == (r['tp'], r['fp'], r['fn']), 'finding positions')
        arm = r['profile']
        require(r['state'] == ('ACCEPTED' if arm else 'STATIC'), 'unexpected historical outcome')
        require(len(r['calls']) == arm == len(r['paragraph_indices']), 'response count')
        require(r['attempts'] == int(bool(arm)) and (not arm or r['termination_verified'] is True), 'attempt or cleanup')
        for index in r['paragraph_indices']:
            require(type(index) is int and 0 <= index < len(evidence['distinct_synthetic_model_paragraphs']), 'paragraph index')
        ratings[r['blind_id']] = dict(id=r['blind_id'], task=r['task'], decision_points=r['points'],
            extra=r['extra'], unsupported=r['unsupported'], added_language=r['added_language'], reason=r['reason'])
    rating_order = evidence['rating_order']
    require(len(set(rating_order)) == len(rating_order) == len(ratings) == 18, 'rating identities')
    grading = [ratings[k] for k in rating_order]
    raw = (json.dumps(grading, indent=2, ensure_ascii=False) + '\n').encode()
    require(hashlib.sha256(raw).hexdigest() == evidence['rating_file_sha256_before_unmasking'], 'frozen ratings')

    require([s['profile'] for s in evidence['summaries']] == [0, 1, 3], 'summary profiles')
    for summary in evidence['summaries']:
        arm = summary['profile']
        group = [r for r in rows if r['profile'] == arm]
        calls = [call for r in group for call in r['calls']]
        wall = [r['wall_s'] for r in group]
        jobs = [r['backend'] for r in group if r['backend'] is not None]
        require(len(jobs) == (len(group) if arm else 0), 'backend coverage')
        computed = dict(profile=arm, tasks=len(group), tp=sum(r['tp'] for r in group),
            fp=sum(r['fp'] for r in group), fn=sum(r['fn'] for r in group),
            exact_tasks=sum(r['fp'] == r['fn'] == 0 for r in group), decision_points=sum(r['points'] for r in group),
            extra_tasks=sum(r['extra'] for r in group), unsupported_tasks=sum(r['unsupported'] for r in group),
            attempts=sum(r['attempts'] for r in group), calls=len(calls),
            tokens_in=sum(c['prompt_eval_count'] for c in calls), tokens_out=sum(c['eval_count'] for c in calls),
            truncated=sum(c['done_reason'] == 'length' for c in calls),
            wall_s_median=statistics.median(wall), wall_s_range=[min(wall), max(wall)],
            job_cpu_s_median=statistics.median(j['cpu_seconds'] for j in jobs) if jobs else None,
            max_sampled_job_working_set_MiB=max(j['sampled_peak_working_set_sum_bytes'] for j in jobs)/2**20 if jobs else None,
            max_job_commit_MiB=max(j['job_peak_commit_bytes'] for j in jobs)/2**20 if jobs else None,
            samples=sum(j['sample_count'] for j in jobs) if jobs else None,
            incomplete_samples=sum(j['incomplete_samples'] for j in jobs) if jobs else None)
        require(computed == summary, f'summary for profile {arm}')
    return len(rows)


if __name__ == '__main__':
    print(f'{verify()} published trials match their frozen corpus, ratings and summaries.')
