"""Volatile, session-bound editor drafts. Every assertion crosses the desktop contract."""
import json
from pathlib import Path
import tempfile
import unittest

from neural_office.desktop_service import DesktopService
from neural_office.ledger import Denied, Ledger


class SessionDrafts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ledger = Ledger(Path(tmp.name) / 'office.db')
        self.core = DesktopService(self.ledger)
        self.addCleanup(self.core.close)
        self.counter = 0

    def call(self, method, thread='main', **params):
        params = dict(session_id=self.core.session_id, project_id='Proyecto sintético', thread_id=thread) | params
        return self.core.dispatch(json.dumps(dict(version=1, id='test', method=method, params=params),
                                             ensure_ascii=False).encode())

    def write(self, value, revision=0, thread='main', **changes):
        self.counter += 1
        params = dict(text=value, expected_revision=revision, edit_id=f'edit-{self.counter}', after_edit='none') | changes
        return self.call('draft.put', thread, **params)

    def test_empty_cross_thread_and_stale_revision(self):
        self.assertEqual(self.call('draft.get')['text'], '')
        a = self.write('Borrador A 🐋\nuno')
        b = self.write('Borrador B', thread='segundo')
        with self.assertRaisesRegex(Denied, 'DRAFT_REVISION_CHANGED'):
            self.write('edición obsoleta')
        self.assertEqual(self.call('draft.get')['text'], a['text'])
        cleared = self.write('', a['revision'])
        self.assertGreater(cleared['revision'], a['revision'])
        self.assertEqual(self.call('draft.get', 'segundo')['text'], b['text'])
        self.assertEqual(self.core.snapshot()['projects'], [])
        other = DesktopService(self.ledger)
        self.addCleanup(other.close)
        with self.assertRaisesRegex(Denied, 'HOST_SESSION_CHANGED'):
            self.call('draft.get', session_id=other.session_id)
        self.assertEqual(other._session_draft(other.session_id, 'Proyecto sintético', 'segundo')['text'], '')

    def test_reload_final_edit_cannot_be_overwritten_by_late_ack(self):
        for final in ['', 'último 🐋']:
            with self.subTest(final=final):
                thread = 'fin-vacio' if not final else 'fin-con-texto'
                self.write(final, thread=thread, after_edit='en-vuelo', edit_id='final')
                with self.assertRaisesRegex(Denied, 'DRAFT_REVISION_CHANGED'):
                    self.write('valor anterior', thread=thread, edit_id='en-vuelo')
                self.assertEqual(self.call('draft.get', thread)['text'], final)
                early = self.write('primero', thread=thread+'-b', edit_id='en-vuelo')
                self.write(final, thread=thread+'-b', after_edit='en-vuelo', edit_id='final')
                self.assertNotEqual(self.call('draft.get', thread+'-b')['revision'], early['revision'])
                self.assertEqual(self.call('draft.get', thread+'-b')['text'], final)

    def test_150_dirty_threads_evict_oldest_and_preserve_active(self):
        for i in range(128):
            self.write(f'texto-{i}', thread=f'h-{i}')
        self.assertEqual(self.call('draft.get', 'h-0')['text'], 'texto-0')
        evicted = []
        for i in range(128, 150):
            evicted.append(self.write(f'texto-{i}', thread=f'h-{i}')['evicted']['thread_id'])
        self.assertEqual(evicted, [f'h-{i}' for i in range(1,23)])
        self.assertEqual(self.call('draft.get', 'h-0')['text'], 'texto-0')
        for i in range(1,150):
            self.assertEqual(self.call('draft.get', f'h-{i}')['text'], '' if i<=22 else f'texto-{i}')
        self.assertEqual(self.core.snapshot()['attempts'], [])
