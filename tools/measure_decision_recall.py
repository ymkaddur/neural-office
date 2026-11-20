"""Measure a saved local decision including storage checks and actual decoder calls.

Run with the private readers Python and an explicit checkout. The example and
database live in a temporary directory. Output is JSON suitable for comparison.
"""
import argparse
import json
from pathlib import Path
from statistics import median
import subprocess
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--samples', type=int, default=7)
    args = parser.parse_args()
    if not 1 <= args.samples <= 100:
        parser.error('samples must be between 1 and 100')
    root = args.checkout.resolve(strict=True)
    if not (root / 'neural_office' / 'attachments.py').is_file():
        parser.error('checkout must be a Neural Office source tree')
    sys.path.insert(0, str(root))
    from examples.multiformat.build_example import example_files
    from neural_office import attachments
    from neural_office.ledger import Ledger

    with tempfile.TemporaryDirectory() as folder:
        base = Path(folder)
        ledger = Ledger(base / 'office.db')
        ledger.initialize()
        store = attachments.AttachmentStore(ledger)
        items = store.capture('Portal', example_files(base / 'portal'), thread_id='review')
        ids = [i['id'] for i in items]
        original = store.inspect('Portal', ids, 'Compara el plazo.', thread_id='review')
        store.decide('Portal', 'review', original['id'], 'json', 0)
        timings, decodes = [], []
        # One unmeasured warm-up. Each sample reopens storage in a new store.
        for index in range(args.samples + 1):
            opened = attachments.AttachmentStore(ledger)
            with patch.object(attachments, 'decode', wraps=attachments.decode) as decoder:
                start = perf_counter()
                report = opened.inspect('Portal', ids, '¿Qué decidimos?', thread_id='review')
                elapsed = (perf_counter() - start) * 1000
            finding = report['findings'][0]
            if (finding['origin_report'], finding['title'], report['reservations'], report['model_calls']) != (
                    original['id'], 'Se eligieron 48 h', 0, 0):
                raise ValueError('Recall returned a different decision or consumed authority')
            if index:
                timings.append(round(elapsed, 2))
                decodes.append(decoder.call_count)
        commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
        dirty = subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'], text=True)
        print(json.dumps(dict(commit=commit, dirty=bool(dirty), python=sys.version.split()[0],
                              files=len(ids), rule_version=report['rule_version'], samples_ms=timings,
                              median_ms=median(timings), decoder_calls=decodes, model_calls=0, reservations=0)))


if __name__ == '__main__':
    main()
