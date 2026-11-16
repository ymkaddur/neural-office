import sys, tempfile, unittest, json
from pathlib import Path

BASE = Path(sys.argv.pop(1)).resolve()
sys.path.insert(0, str(BASE / 'runtime'))
from controlplane import WorkLedger, PolicyViolation
from director import DirectorStore
from contracts import digest
from orchestration import GRAPH, prompt_for, ExecutionDenied

class Regressions(unittest.TestCase):
    def test_gate_b_packaged_path(self):
        text = (BASE/'operations/COMPAT_GATE_B_CPU64K_OPERATOR.ps1').read_text('utf-8')
        self.assertIn("'..\\profiles\\Modelfile_CPU64K_FOR_OPERATOR.txt'", text)
        self.assertTrue((BASE/'profiles/Modelfile_CPU64K_FOR_OPERATOR.txt').is_file())

    def test_gate_c_packaged_path(self):
        text = (BASE/'operations/COMPAT_GATE_C_ROUTE_OPERATOR.ps1').read_text('utf-8')
        self.assertIn("'..\\runtime\\routepatch.py'", text)
        self.assertTrue((BASE/'runtime/routepatch.py').is_file())

    def test_verified_count_distinct_from_legacy_ordinal(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DirectorStore(Path(tmp)/'state.sqlite3')
            store.initialize()
            for i in range(3):
                task = store.propose('web-auditor', 'Audit the exact candidate and evidence')
                proof = Path(tmp)/f'{i}.txt'
                proof.write_text(f'evidence {i}', encoding='utf-8')
                store.submit_receipt(task, digest(proof.read_bytes()), proof)
                store.verify(task, 'APRUEBO_VERIFICACION_V45', i == 1)
            project = next(x for x in store.status()['projects'] if x['project']=='web-auditor')
            self.assertEqual((project['verified_count'], project['completed'], project['attempted']), (1,2,3))

    def test_status_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'absent.sqlite3'
            try:
                WorkLedger(path).status()
            except PolicyViolation:
                pass
            self.assertFalse(path.exists())

    def test_transfer_contains_actual_evidence(self):
        result = {'role':'director','text':'immutable boundary evidence'}
        prior = {'scope': {'sha256':digest(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'))), 'result':result}}
        prompt = prompt_for(GRAPH[1], 'Audit the exact candidate and evidence', prior, provenance={})
        self.assertIn('immutable boundary evidence', prompt)

    def test_changed_evidence_is_not_transferred(self):
        result = {'role':'director','text':'changed after the digest'}
        prior = {'scope': {'sha256':'0'*64, 'result':result}}
        with self.assertRaisesRegex(ExecutionDenied,'UPSTREAM_EVIDENCE_CHANGED'):
            prompt_for(GRAPH[1], 'Audit the exact candidate and evidence', prior, provenance={})

    def test_oversized_transfer_stops_instead_of_truncating(self):
        result = {'role':'director','text':'é'*40000}
        prior = {'scope': {'sha256':digest(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'))), 'result':result}}
        with self.assertRaisesRegex(ExecutionDenied,'UPSTREAM_CONTEXT_EXCEEDS_BYTE_BUDGET'):
            prompt_for(GRAPH[1], 'Audit the exact candidate and evidence', prior, provenance={})

if __name__ == '__main__': unittest.main()
