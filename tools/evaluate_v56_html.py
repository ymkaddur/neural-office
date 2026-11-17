"""Evaluate the manual static corpus; semantic probes are reported, not passed.

Run from any directory with Python 3.12. This tool makes no model calls, network
requests or changes to the corpus. JSON goes to stdout, or a new --output file.
Exit 0 means contract cases matched; it does not mean semantic probes passed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from neural_office.audit import audit_html  # noqa: E402


def evaluate():
    corpus_path = ROOT / 'examples' / 'html-review-corpus.json'
    raw = corpus_path.read_bytes()
    corpus = json.loads(raw)
    if not corpus['cases']:
        raise ValueError('A corpus with no contract cases cannot pass evaluation')
    results = {}
    for section in ('cases', 'semantic_probes'):
        rows = []
        for case in corpus[section]:
            source = case['html'].encode(case.get('byte_encoding', 'utf-8'))
            observed = audit_html(source)
            expected = case['expected_findings']
            rows.append({'id': case['id'], 'expected': expected, 'observed': observed,
                         'matched': observed == expected})
        results['contract' if section == 'cases' else section] = {
            'case_count': len(rows), 'matched_count': sum(row['matched'] for row in rows),
            'not_matched_count': sum(not row['matched'] for row in rows), 'cases': rows}
    return {
        'schema': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'static HTML, no model; manually authored synthetic expectations',
        'corpus_sha256': hashlib.sha256(raw).hexdigest(),
        'auditor_sha256': hashlib.sha256((ROOT / 'neural_office' / 'audit.py').read_bytes()).hexdigest(),
        'model_calls': 0,
        'contract_passed': results['contract']['not_matched_count'] == 0,
        'results': results,
        'limitations': corpus['limitations'],
        'interpretation': 'Contract matches and semantic omissions are separate. These counts are not WCAG conformance, real-world accuracy or model quality.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Write a new JSON file; existing files are rejected')
    args = parser.parse_args(argv)
    report = evaluate()
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.output:
        with args.output.open('x', encoding='utf-8', newline='\n') as target:
            target.write(text)
    else:
        sys.stdout.write(text)
    return 0 if report['contract_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
