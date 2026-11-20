"""Trusted, read-only HTML receiver for the first durable office workflow."""
import json


def evaluate(operation, source, parents, prior):
    from .audit import audit_html, make_report
    from .ledger import Denied, canonical, digest

    if operation == 'deliver':
        report = json.loads(make_report(source, []))
        verified = prior[0]['facts']
        if (verified['source_sha256'] != report['source_sha256']
                or verified['findings_sha256'] != digest(canonical(report['findings']))):
            raise Denied('OFFICE_FACTS_DISAGREE')
        return report
    findings = audit_html(source)
    facts = dict(source_sha256=digest(source), findings_total=len(findings),
                 findings_sha256=digest(canonical(findings)), sample=findings[:12])
    if operation == 'inspect':
        return facts
    if operation == 'verify' and prior == [facts]:
        return dict(facts=facts, checked=parents[0])
    raise Denied('OFFICE_FACTS_DISAGREE')


if __name__ == '__main__':
    from pathlib import Path
    import sys

    if len(sys.argv) != 4:
        raise SystemExit(2)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from neural_office.ledger import Ledger
    from neural_office.office_protocol import receive
    receive(Ledger(sys.argv[1]), sys.argv[2], sys.argv[3])
