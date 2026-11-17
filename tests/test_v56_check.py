"""The deterministic path must not initialize state, contact Ollama or run a worker."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from neural_office.__main__ import main
from neural_office.ledger import Denied, digest


class StaticCheckTests(unittest.TestCase):
    def test_check_reports_manual_oracle_without_model_or_state(self):
        source = b'<html><head><title></title></head><body><img src="x"></body></html>'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / 'source.html'
            file.write_bytes(source)
            output = io.StringIO()
            with patch('neural_office.__main__.Ledger', side_effect=AssertionError('ledger touched')), \
                 patch('neural_office.__main__.local_metadata', side_effect=AssertionError('network touched')), \
                 patch('neural_office.__main__.run', side_effect=AssertionError('worker started')), redirect_stdout(output):
                main(['--state', str(root / 'must-not-exist.sqlite3'), 'check', '--root', str(root), '--file', str(file)])
            report = json.loads(output.getvalue())
            self.assertEqual(report['source_sha256'], digest(source))
            self.assertEqual(report['role_outputs'], [])
            self.assertEqual({item['code'] for item in report['findings']},
                             {'HTML_LANGUAGE_MISSING', 'DOCUMENT_TITLE_MISSING', 'IMAGE_ALT_MISSING'})
            self.assertNotIn(str(file), output.getvalue())
            self.assertEqual(file.read_bytes(), source)
            self.assertEqual(list(root.iterdir()), [file])

    def test_check_keeps_existing_capture_boundary(self):
        with patch('neural_office.__main__.Ledger', side_effect=AssertionError('ledger touched')):
            with self.assertRaisesRegex(Denied, 'NETWORK_INPUT_EXCLUDED'):
                main(['check', '--root', r'\\example.invalid\share', '--file', r'\\example.invalid\share\x.html'])

    def test_valueless_input_type_is_checked_like_the_empty_default(self):
        from neural_office.audit import audit_html
        for attr in ('', ' type', ' type=""', ' type="text"'):
            html = f'<html lang="es"><title>T</title>\n<input{attr}></html>'.encode()
            self.assertEqual(audit_html(html), [{'code':'CONTROL_LABEL_CANDIDATE','line':2,'column':1}])

    def test_capture_requires_an_ordinary_file_component(self):
        from neural_office.files import capture_html
        with patch.object(Path, 'resolve', side_effect=AssertionError('Filesystem consulted early')):
            with self.assertRaisesRegex(Denied, 'FILE_STREAM_EXCLUDED'):
                capture_html('sample:notes.html', '.')


if __name__ == '__main__':
    unittest.main()
