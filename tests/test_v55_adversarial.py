"""Independent bridge regression: legal core identities remain usable through IPC."""
from pathlib import Path
import tempfile
import unittest

from neural_office.desktop_contract import decode_command
from neural_office.desktop_service import DesktopService
from neural_office.ledger import Denied, Ledger, canonical


class LegacyProjectIdentity(unittest.TestCase):
    def test_existing_core_project_can_roundtrip_through_snapshot_and_command(self):
        for project in ('Area con espacios', 'Área de revisión', 'x'*65, 'x'*80,
                        '🙂'*80, ' ', 'nul\0project'):
            with self.subTest(codepoints=len(project)), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                ledger = Ledger(root/'state.sqlite3'); ledger.initialize(); ledger.register(project, root)
                service = DesktopService(ledger)
                try:
                    saved = service.snapshot()['projects'][0]['id']
                    raw = canonical({'version': 1, 'id': 'request', 'method': 'attempt.lookup',
                                     'params': {'project_id': saved, 'idempotency_key': 'key'}}).encode()
                    self.assertEqual(decode_command(raw)['params']['project_id'], project)
                    self.assertFalse(service.dispatch(raw)['found'])
                    source = root/'source.html'; source.write_bytes(b'<html lang="en"><title>Test</title></html>')
                    captured = service.host_capture(project, source)
                    self.assertEqual(captured['project_id'], project)
                    self.assertEqual(service.snapshot()['projects'][0]['attempts_consumed'], 0)
                finally: service.close()

    def test_project_bounds_remain_distinct_from_opaque_ids(self):
        for project in ('', 'x'*81, '🙂'*81, 'invalid\ud800'):
            with self.subTest(codepoints=len(project)):
                raw = canonical({'version': 1, 'id': 'request', 'method': 'attempt.lookup',
                                 'params': {'project_id': project, 'idempotency_key': 'key'}}).encode('utf-8', errors='surrogatepass')
                with self.assertRaises(Denied): decode_command(raw)
        raw = canonical({'version': 1, 'id': 'request with spaces', 'method': 'describe', 'params': {}}).encode()
        with self.assertRaisesRegex(Denied, 'REQUEST_ID'): decode_command(raw)


if __name__ == '__main__': unittest.main()
