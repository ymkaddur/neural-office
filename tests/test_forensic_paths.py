"""No resolver may touch an explicitly excluded network source before denial."""
import os
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from neural_office.files import capture_html, local_path
from neural_office.legacy import PATHS, snapshot, reconcile, rebind
from neural_office.ledger import Denied


@unittest.skipUnless(os.name == 'nt', 'Native Windows source-path policy')
class SourcePathBoundaries(unittest.TestCase):
    UNC = r'\\synthetic.invalid\share'

    def assert_denied_before_resolution(self, operation):
        with patch.object(Path, 'resolve', side_effect=AssertionError('RESOLUTION_BEFORE_DENIAL')) as resolve:
            with self.assertRaisesRegex(Denied, 'NETWORK'):
                operation()
            resolve.assert_not_called()

    def test_capture_checks_both_arguments_before_resolving_either(self):
        self.assert_denied_before_resolution(lambda: capture_html(self.UNC + r'\input.html', self.UNC))
        self.assert_denied_before_resolution(lambda: capture_html(self.UNC + r'\input.html', r'C:\synthetic'))
        self.assert_denied_before_resolution(lambda: capture_html(r'C:\synthetic\input.html', self.UNC))

    def test_legacy_entrypoints_deny_unc_before_resolution(self):
        def inspect():
            with snapshot(self.UNC):
                self.fail('Network snapshot must not be yielded')
        for operation in (inspect, lambda: reconcile(None, self.UNC), lambda: rebind(None, 'p', self.UNC)):
            with self.subTest(operation=operation):
                self.assert_denied_before_resolution(operation)

    def test_unc_spellings_and_device_namespaces_are_lexically_denied(self):
        values = (self.UNC, '//synthetic.invalid/share/input.html',
                  r'\\?\UNC\synthetic.invalid\share\input.html', r'\\?\C:\input.html', r'\\.\C:\input.html')
        for value in values:
            with self.subTest(value=value):
                self.assert_denied_before_resolution(lambda: local_path(value))

    def test_relative_paths_and_local_capture_are_preserved(self):
        with patch.object(Path, 'resolve', side_effect=AssertionError('LEXICAL_CHECK_DID_IO')):
            for value in ('input.html', '../input.html', r'C:\synthetic\..\input.html'):
                self.assertEqual(local_path(value), Path(value))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'espacio ñ.html'
            expected=b'<html lang="en"><title>Fixture</title></html>'
            source.write_bytes(expected)
            self.assertEqual(capture_html(source, root), expected)

    def test_manifest_location_denied_before_resolving_remote_path(self):
        from test_legacy import fixture
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'historical'; fixture(root)
            with closing(sqlite3.connect(root/PATHS['v1'])) as con:
                con.execute("UPDATE projects SET location=? WHERE id='web-auditor'", (self.UNC,))
                con.commit()
            original=Path.resolve
            def local_resolution(path, *args, **kwargs):
                if str(path).startswith('\\\\'):
                    self.fail('Remote manifest location reached filesystem resolution')
                return original(path, *args, **kwargs)
            with patch.object(Path, 'resolve', local_resolution):
                with self.assertRaisesRegex(Denied, 'LEGACY_NETWORK_SOURCE_EXCLUDED'):
                    with snapshot(root):
                        self.fail('Remote manifest must not be admitted')


if __name__ == '__main__':
    unittest.main()
