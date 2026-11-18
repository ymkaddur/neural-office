"""Compare deterministic checks in two checkouts on the same public HTML bytes."""
import argparse
import hashlib
import importlib
import json
import math
from pathlib import Path
import statistics
import sys
from time import perf_counter_ns
from types import ModuleType


def reader(checkout, alias):
    package = ModuleType(alias)
    package.__path__ = [str(checkout.resolve(strict=True)/'neural_office')]
    sys.modules[alias] = package
    return importlib.import_module(alias+'.audit').audit_html


def compare(baseline, candidate):
    old, new = reader(baseline, 'baseline_office'), reader(candidate, 'candidate_office')
    example = (candidate/'examples/audit-sample.html').read_bytes()
    docs = [('public-example', example, 4)]
    for count in (40,800):
        rows = ''.join(f'<div><label for="f{i}">Campo {i}</label><input id="f{i}"></div>' for i in range(count))
        docs.append((f'form-{count}',f'<html lang="es"><title>Formulario</title><body>{rows}</body></html>'.encode(),0))
    output = []
    for name, source, count in docs:
        expected = old(source)
        if len(expected) != count or new(source) != expected:
            raise ValueError('The shared control cases must agree before timing')
        samples = {'baseline': [], 'candidate': []}
        versions = [('baseline',old), ('candidate',new)]
        for index in range(40):
            for label, check in versions if index%2==0 else reversed(versions):
                start = perf_counter_ns()
                result = check(source)
                samples[label].append((perf_counter_ns()-start)/1e6)
                if result != expected:
                    raise ValueError('Findings changed during timing')
        def summarize(times):
            return {'median_ms':round(statistics.median(times),3),
                    'p95_ms':round(sorted(times)[math.ceil(.95*len(times))-1],3)}
        output.append({'fixture':name,'bytes':len(source),'sha256':hashlib.sha256(source).hexdigest(),
                       'reads_each':40,'findings':count, **{k:summarize(v) for k,v in samples.items()}})
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(compare(args.baseline,args.candidate),indent=2))
