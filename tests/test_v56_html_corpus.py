"""Manual synthetic expectations; no model, generated oracle or browser execution.

Only the contract collection is a regression gate. The separate semantic probes
are reported by tools/evaluate_v56_html.py, never counted as passing tests.
Read the corpus limits before interpreting counts as quality or accessibility.
"""
import json
from pathlib import Path
import unittest

from neural_office.audit import audit_html


CORPUS_PATH = Path(__file__).resolve().parents[1] / 'examples' / 'html-review-corpus.json'
CORPUS = json.loads(CORPUS_PATH.read_text(encoding='utf-8'))
if not CORPUS['cases']:
    raise ValueError('A corpus with no contract cases cannot be a regression gate')


class ManualHtmlCorpus(unittest.TestCase):
    pass


def case_test(case):
    def test(self):
        source = case['html'].encode(case.get('byte_encoding', 'utf-8'))
        self.assertEqual(audit_html(source), case['expected_findings'],
                         f"{case['id']}: {case['rationale']}")
    test.__doc__ = case['purpose']
    return test


identities = set()
for case in CORPUS['cases']:
    identity = case['id']
    if identity in identities or not identity.isidentifier():
        raise ValueError('Corpus cases must have unique Python-compatible identities')
    identities.add(identity)
    setattr(ManualHtmlCorpus, 'test_' + identity, case_test(case))


if __name__ == '__main__':
    unittest.main()
