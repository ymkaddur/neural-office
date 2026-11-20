"""Document title, parsing coordinates and byte identity are separate contracts."""
import hashlib
import json
import unittest

from neural_office.audit import audit_html, make_report, verify_report


class DocumentChecks(unittest.TestCase):
    def test_title_belongs_to_document(self):
        for html, missing in [
            ('<svg><title>Logo</title></svg>', True),
            ('<template><title>Plantilla</title><img></template>', True),
            ('<title> </title><title>Segundo</title>', True),
            ('<svg><title>Logo</title></svg><title>Cuenta</title>', False),
            ('<title>Cuenta</title><svg><title></title></svg>', False),
            ('<title>Cuenta', False),
        ]:
            with self.subTest(html=html):
                flags = [f['code'] for f in audit_html(html.encode())]
                self.assertEqual('DOCUMENT_TITLE_MISSING' in flags, missing)
                self.assertNotIn('IMAGE_ALT_MISSING', flags)

    def test_source_coordinates_and_original_bytes(self):
        hashes = set()
        for separator in ('\r', '\n', '\r\n'):
            data = separator.join(('<html lang="es">','<title>Cuenta</title>','<body>', '  <img>', '</body></html>')).encode()
            artifact = make_report(data, [])
            report = json.loads(artifact)
            self.assertEqual(report['findings'], [{'code':'IMAGE_ALT_MISSING','line':4,'column':3}])
            self.assertEqual(report['source_sha256'], hashlib.sha256(data).hexdigest())
            self.assertTrue(verify_report(data, artifact)['passed'])
            hashes.add(report['source_sha256'])
        self.assertEqual(len(hashes), 3)

    def test_markup_inside_text_is_not_a_document_element(self):
        html = b'<html lang="es"><title> &nbsp; </title><textarea aria-label="Ejemplo"><img></textarea></html>'
        self.assertEqual([f['code'] for f in audit_html(html)], ['DOCUMENT_TITLE_MISSING'])
