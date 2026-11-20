"""Regression tests for native capture, decoded previews and durable local inspection."""
from base64 import b64decode
from contextlib import closing
from io import BytesIO
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from neural_office.attachment_formats import json_view, read
from neural_office.attachments import AttachmentStore
from neural_office import attachments
from neural_office.ledger import Denied, Ledger, canonical, digest


from examples.multiformat.build_example import example_files, pdf_bytes


class JSONReaderTests(unittest.TestCase):
    def test_location_and_pointer_escape(self):
        view = json_view(b'{\r\n "note":"response_sla_hours",\r\n "a/b":{"~name":2},\r\n "response_sla_hours":\r\n  48}')
        self.assertEqual(view['hours']['line'], 5)
        self.assertEqual(view['hours']['column'], 3)
        self.assertEqual(view['hours']['quote'], '48')
        self.assertIn('/a~1b/~0name', [field['pointer'] for field in view['fields']])

    def test_long_json_snippet_retains_original_line(self):
        source = '{\r\n' + '  "padding": "' + 'x' * 17000 + '",\r\n  "response_sla_hours": 48\r\n}'
        view = json_view(source.encode())
        self.assertTrue(view['text_truncated'])
        self.assertEqual(view['hours']['line'], 3)
        self.assertIn('48', view['text'])
        self.assertIn('"response_sla_hours"', view['hours']['context'])

    def test_duplicates_invalid_and_non_numbers(self):
        for data in (b'{"x":1,\n"\\u0078":2}', b'{"x":}', b'{} second', b'{"x":NaN}'):
            with self.subTest(data=data):
                view = json_view(data)
                self.assertEqual(view['status'], 'invalid')
                self.assertGreaterEqual(view['line'], 1)
                self.assertGreaterEqual(view['column'], 1)
                self.assertNotIn('hours', view)
        for data in (b'{"response_sla_hours":true}', b'{"response_sla_hours":-1}', b'{"response_sla_hours":"48"}'):
            self.assertIsNone(json_view(data)['hours'])


@unittest.skipUnless(os.name == 'nt', 'La frontera de captura usa handles nativos de Windows.')
class AttachmentStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.ledger = Ledger(self.base / 'state.sqlite3')
        self.ledger.initialize()
        self.store = AttachmentStore(self.ledger)
        self.paths = example_files(self.base / 'portal')
        self.records = self.store.capture('Portal', self.paths, thread_id='review')
        self.ids = {item['kind']: item['id'] for item in self.records}

    def view(self, kind, **opts):
        return self.store.preview('Portal', self.ids[kind], thread_id='review', **opts)

    def inspect(self):
        return self.store.inspect('Portal', list(self.ids.values()), 'Verifica el plazo.', thread_id='review')

    def test_real_files_report_reopen_and_scope(self):
        report = self.inspect()
        self.assertEqual(self.inspect(), report)
        self.assertEqual(len(self.store.history('Portal', thread_id='review')), 1)
        self.assertEqual(report['reservations'], 0)
        self.assertEqual(report['model_calls'], 0)
        self.assertEqual(len(report['steps']), 6, report['steps'])
        finding = report['findings'][0]
        self.assertEqual(finding['status'], 'mismatch', report)
        pdf, field = finding['sources']
        self.assertEqual((pdf['page'], pdf['quote'], pdf['value']), (2, 'Primera respuesta en 24 horas.', 24))
        self.assertEqual(len(pdf['pdf_rect']), 4)
        self.assertEqual((field['line'], field['pointer'], field['value']), (4, '/response_sla_hours', 48))
        preview = self.view('pdf', page=2)
        self.assertEqual(preview['pages'], 2)
        self.assertIn(pdf['quote'], preview['text'])
        x, y, w, h = preview['candidates'][0]['region']
        self.assertEqual(pdf['region'], [x, y, w, h])
        self.assertTrue(0 <= x < x+w <= 1, (x, w))
        self.assertTrue(0 <= y < y+h <= 1, (y, h))
        self.assertTrue(b64decode(preview['image'].partition(',')[2]).startswith(b'\xff\xd8'))
        self.paths[2].write_text('{"response_sla_hours":24}', encoding='utf-8')
        after = self.store.capture('Portal', [self.paths[2]], thread_id='review')[0]
        self.assertNotEqual(after['id'], self.ids['json'])
        self.assertEqual(self.view('json')['hours']['value'], 48)
        self.paths[0].unlink()
        reopened = AttachmentStore(self.ledger)
        self.assertEqual(reopened.report('Portal', report['id'], thread_id='review'), report)
        self.assertEqual(reopened.threads('Portal')[0]['id'], 'review')
        self.assertEqual(reopened.history('Portal', thread_id='review')[0]['id'], report['id'])
        for project, thread in [('Portal', 'main'), ('Otro', 'review')]:
            with self.subTest(project=project, thread=thread):
                with self.assertRaisesRegex(Denied, 'ATTACHMENT_NOT_FOUND'):
                    reopened.preview(project, self.ids['pdf'], thread_id=thread)
                with self.assertRaisesRegex(Denied, 'ATTACHMENT_REPORT_NOT_FOUND'):
                    reopened.report(project, report['id'], thread_id=thread)
        match = reopened.inspect('Portal', [self.ids['pdf'], after['id']], thread_id='review')
        self.assertEqual(match['findings'][0]['status'], 'match')
        with self.ledger.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM calls').fetchone()[0], 0)

    def test_zip_image_and_bad_member(self):
        view = self.view('zip')
        self.assertEqual(len(view['entries']), 4)
        preview = self.view('zip', member='visual/movil.jpg')
        self.assertEqual((preview['kind'], preview['width'], preview['height']), ('jpeg', 360, 720))
        self.assertEqual(preview['member_sha256'], digest(self.paths[4].read_bytes()))
        self.assertEqual(preview['container_kind'], 'zip')
        self.assertEqual(self.view('zip', member='missing.png')['status'], 'not_found')
        self.assertEqual((self.view('png')['width'], self.view('jpeg')['height']), (960, 720))
        self.assertFalse((self.paths[1].parent / 'visual').exists())

    def test_file_boundary_idempotent_capture_and_checksum(self):
        repeated = self.store.capture('Portal', self.paths[:1], thread_id='review')
        self.assertEqual(repeated[0], self.records[0])
        outside = self.base / 'otro.json'
        outside.write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(Denied, 'INPUT_OUTSIDE_ROOT'):
            self.store.capture('Portal', [outside], thread_id='review')
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute('UPDATE captures SET content=? WHERE id=?', (b'{}', self.ids['json']))
            db.commit()
        with self.assertRaisesRegex(Denied, 'ATTACHMENT_INTEGRITY_FAILED'):
            self.view('json')

    def test_report_recovery_binds_evidence_to_original_identity(self):
        report = self.store.inspect('Portal', [self.ids['pdf'], self.ids['json']], thread_id='review')
        report['findings'][0]['sources'][1]['value'] = 72
        changed = canonical(report)
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute('UPDATE reports SET payload=?,payload_sha=? WHERE id=?', (changed, digest(changed), report['id']))
            db.commit()
        with self.assertRaisesRegex(Denied, 'ATTACHMENT_INTEGRITY_FAILED'):
            self.store.report('Portal', report['id'], thread_id='review')

    def test_limits_selection_and_stopped_local_read(self):
        with self.assertRaisesRegex(Denied, 'ATTACHMENT_SELECTION_LIMIT'):
            self.store.capture('Portal', self.paths * 2, thread_id='review')
        started = threading.Event()
        errors = []
        def delayed_read(*args, cancelled, **kwargs):
            started.set()
            if not wait_for(cancelled):
                raise AssertionError('No llegó la señal de cancelación.')
            raise Denied('ATTACHMENT_READ_CANCELLED')
        def run():
            try:
                self.inspect()
            except Exception as exc:
                errors.append(str(exc))
        with patch('neural_office.attachments.decode', side_effect=delayed_read):
            thread = threading.Thread(target=run)
            thread.start()
            try:
                self.assertTrue(started.wait(4))
                self.assertEqual(self.store.cancel_reads('Portal', thread_id='main'), 0)
                self.assertEqual(self.store.cancel_reads('Portal', thread_id='review'), 1)
            finally:
                thread.join(4)
        self.assertEqual(errors, ['ATTACHMENT_READ_CANCELLED'])
        self.assertEqual(self.store.history('Portal', thread_id='review'), [])

    def test_invalid_partial_ambiguous_and_legacy_html(self):
        folder = self.paths[0].parent
        values = [('ambos.pdf', pdf_bytes([['Primera respuesta en 24 horas.', 'Primera respuesta en 48 horas.']])),
                  ('parcial.pdf', pdf_bytes([['Primera respuesta en 24 horas.'], []])),
                  ('vacio.pdf', pdf_bytes([[]])), ('rota.png', b'imagen incompleta'),
                  ('roto.zip', b'PK\x03\x04 incompleto'), ('roto.json', b'{"plazo":}'),
                  ('index.html', b'<html><title>Prueba</title><img src="foto.png"></html>')]
        for name, data in values:
            (folder/name).write_bytes(data)
        infos = self.store.capture('Portal', [folder/name for name, _ in values], thread_id='review')
        data = {i['name']: i['id'] for i in infos}
        for name in ('ambos.pdf', 'parcial.pdf', 'vacio.pdf'):
            report = self.store.inspect('Portal', [data[name], self.ids['json']], thread_id='review')
            self.assertEqual(report['findings'][0]['status'], 'insufficient')
        for name in ('rota.png', 'roto.zip', 'roto.json'):
            self.assertEqual(self.store.preview('Portal', data[name], thread_id='review')['status'], 'invalid')
        blank = self.store.preview('Portal', data['vacio.pdf'], thread_id='review')
        self.assertEqual(blank['status'], 'no_text')
        self.assertTrue(blank['image'])
        html = self.store.inspect('Portal', [data['index.html']], thread_id='review')
        self.assertGreater(html['findings'][0]['total'], 0)
        self.assertEqual(html['model_calls'], 0)

    def test_image_orientation(self):
        from PIL import Image
        destination = self.paths[-1].with_name('orientation.jpg')
        exif = Image.Exif()
        exif[274] = 6
        Image.new('RGB', (36, 72), 'blue').save(destination, exif=exif)
        ident = self.store.capture('Portal', [destination], thread_id='review')[0]['id']
        view = self.store.preview('Portal', ident, thread_id='review')
        self.assertEqual((view['orientation'], view['width'], view['height']), (6, 72, 36))

    def test_close_terminates_real_decoder_waiting_on_input(self):
        entered = threading.Event()
        release = threading.Event()
        processes = []
        errors = []
        real_send = attachments._send_input
        real_popen = subprocess.Popen

        def observe(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            processes.append(process)
            return process

        def hold_stream(pipe, content):
            entered.set()
            release.wait(6)
            real_send(pipe, content)

        def preview():
            try:
                self.view('pdf')
            except Denied as error:
                errors.append(str(error))

        with patch.object(attachments, '_send_input', side_effect=hold_stream), \
                patch.object(attachments.subprocess, 'Popen', side_effect=observe):
            thread = threading.Thread(target=preview)
            thread.start()
            try:
                self.assertTrue(entered.wait(3))
                self.assertIsNone(processes[0].poll())
                self.store.close()
                self.assertTrue(wait_for(lambda: processes[0].poll() is not None))
            finally:
                release.set()
                thread.join(4)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, ['ATTACHMENT_READ_CANCELLED'])
        with self.assertRaisesRegex(Denied, 'ATTACHMENT_READ_CANCELLED'):
            self.view('pdf')

    def test_decoder_rejects_short_pipe_even_if_remaining_json_is_valid(self):
        real_send = attachments._send_input
        with patch.object(attachments, '_send_input', side_effect=lambda pipe, data: real_send(pipe, b'{}')):
            view = self.view('json')
        self.assertEqual(view['status'], 'incomplete')
        self.assertNotIn('fields', view)

    def test_raster_only_and_protected_pdf(self):
        from PIL import Image, ImageDraw
        page = Image.new('RGB', (260, 180), 'white')
        ImageDraw.Draw(page).text((20, 24), 'Primera respuesta en 24 horas.', fill='black')
        encoded = BytesIO()
        page.save(encoded, format='PDF')
        scanned = read('pdf', encoded.getvalue(), page=1)
        self.assertEqual(scanned['status'], 'no_text')
        self.assertEqual(scanned['candidates'], [])
        self.assertTrue(scanned['image'])
        # Synthetic one-page PDF, protected with the example password "ejemplo".
        encrypted = b64decode(
            b'JVBERi0xLjMKJeLjz9MKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwovUGFnZXMgMiAwIFIKPj4KZW5kb2JqCjIgMCBvYmoK'
            b'PDwKL1R5cGUgL1BhZ2VzCi9Db3VudCAxCi9LaWRzIFsgMyAwIFIgXQo+PgplbmRvYmoKMyAwIG9iago8PAovVHlwZSAvUGFn'
            b'ZQovUGFyZW50IDIgMCBSCi9NZWRpYUJveCBbIDAgMCA0NzAgNTQwIF0KL1Jlc291cmNlcyA8PAovRm9udCA8PAovRjEgNCAw'
            b'IFIKPj4KPj4KL0NvbnRlbnRzIDUgMCBSCj4+CmVuZG9iago0IDAgb2JqCjw8Ci9UeXBlIC9Gb250Ci9TdWJ0eXBlIC9UeXBl'
            b'MQovQmFzZUZvbnQgL0hlbHZldGljYQo+PgplbmRvYmoKNSAwIG9iago8PAovTGVuZ3RoIDQ3Cj4+CnN0cmVhbQqDAhVyzR/9'
            b'i3mo5avs2sd0uJ4g+KI2S3Wr0nOQa4qmgqTQW5Stn9L33SoLHvNRDgplbmRzdHJlYW0KZW5kb2JqCjYgMCBvYmoKPDwKL1Yg'
            b'MgovUiAzCi9MZW5ndGggMTI4Ci9QIDQyOTQ5NjcyOTIKL0ZpbHRlciAvU3RhbmRhcmQKL08gPDNhOTE4MTk0ZWExZjlmMDkw'
            b'M2UzOTI0ZmQyOTQ1NmUxZTQ0YTVhODIyNTQ2NjVlOTI4YmNiM2Q2MWNjYmY3Yjg+Ci9VIDw0YzgzZWExYjZjMWYxNDgxMWYy'
            b'Y2IyMWUxODdlNTc3ZDI4YmY0ZTVlNGU3NThhNDE2NDAwNGU1NmZmZmEwMTA4Pgo+PgplbmRvYmoKeHJlZgowIDcKMDAwMDAw'
            b'MDAwMCA2NTUzNSBmIAowMDAwMDAwMDE1IDAwMDAwIG4gCjAwMDAwMDAwNjQgMDAwMDAgbiAKMDAwMDAwMDEyMyAwMDAwMCBu'
            b'IAowMDAwMDAwMjUxIDAwMDAwIG4gCjAwMDAwMDAzMjEgMDAwMDAgbiAKMDAwMDAwMDQxOCAwMDAwMCBuIAp0cmFpbGVyCjw8'
            b'Ci9TaXplIDcKL1Jvb3QgMSAwIFIKL0lEIFsgPGFkZDhmNmMxYjY2ZmE2NDBiNDZiN2Q4YTU5ZGU3NmRhPiA8YWRkOGY2YzFi'
            b'NjZmYTY0MGI0NmI3ZDhhNTlkZTc2ZGE+IF0KL0VuY3J5cHQgNiAwIFIKPj4Kc3RhcnR4cmVmCjYzMwolJUVPRgo='
        )
        protected = read('pdf', encrypted)
        self.assertEqual(protected['status'], 'protected')
        self.assertNotIn('image', protected)

    def test_explicit_text_member_and_no_implicit_nested_read(self):
        zipped = BytesIO()
        with zipfile.ZipFile(zipped, 'w') as archive:
            archive.writestr('notas.txt', b'Notas')
            archive.writestr('otro.zip', self.paths[1].read_bytes())
        view = read('zip', zipped.getvalue(), member='notas.txt')
        self.assertEqual((view['status'], view['text']), ('ok', 'Notas'))
        self.assertEqual(read('zip', zipped.getvalue(), member='otro.zip')['status'], 'unsupported')


def wait_for(check):
    until = time.monotonic() + 3
    while time.monotonic() < until:
        if check():
            return True
        threading.Event().wait(0.02)
    return check()


if __name__ == '__main__':
    unittest.main()
