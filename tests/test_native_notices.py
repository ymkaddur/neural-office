import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.collect_native_notices import CollectionError, main, override_notice, sha256


class NativeNoticeTests(unittest.TestCase):
    def fixture(self, root):
        package = {'name': 'synthetic', 'version': '1.0.0', 'license': 'MIT'}
        text = b'Synthetic license fixture, not a third-party license.\n'
        (root / 'LICENSE').write_bytes(text)
        (root / '.cargo_vcs_info.json').write_text(json.dumps({'git': {'sha1': 'a' * 40}}))
        override = {'synthetic@1.0.0': {'license': 'MIT', 'file': 'LICENSE',
                    'sha256': sha256(text), 'upstream_commit': 'a' * 40,
                    'origin_url': 'https://example.org/pinned-license'}}
        return package, override, text

    def test_missing_override_fails_instead_of_silently_omitting_license(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package, _, _ = self.fixture(root)
            with self.assertRaisesRegex(CollectionError, 'Missing license and exact override'):
                override_notice(package, root, {}, root)

    def test_exact_override_preserves_bytes_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package, override, text = self.fixture(root)
            self.assertEqual(override_notice(package, root, override, root)[1], text)
            (root / 'LICENSE').write_bytes(text + b'Altered.\n')
            with self.assertRaisesRegex(CollectionError, 'Override hash mismatch'):
                override_notice(package, root, override, root)

    def test_same_license_from_different_source_commit_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package, override, _ = self.fixture(root)
            (root / '.cargo_vcs_info.json').write_text(json.dumps({'git': {'sha1': 'b' * 40}}))
            with self.assertRaisesRegex(CollectionError, 'Override source commit changed'):
                override_notice(package, root, override, root)

    def test_existing_output_is_not_reused_or_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = root / 'sentinel'
            sentinel.write_bytes(b'unchanged')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--output', str(root)]), 1)
            self.assertEqual(sentinel.read_bytes(), b'unchanged')
            self.assertEqual([p.name for p in root.iterdir()], ['sentinel'])


if __name__ == '__main__':
    unittest.main()
