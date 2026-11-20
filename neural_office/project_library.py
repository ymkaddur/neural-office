"""Project-scoped human notes and versioned instructions. Entries grant no execution rights."""
import time

from .attachments import recover_report
from .ledger import Denied


class ProjectLibrary:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def _table(db):
        db.execute('''CREATE TABLE IF NOT EXISTS library_versions (
            project TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL, kind TEXT NOT NULL,
            title TEXT NOT NULL, body TEXT NOT NULL, proposal TEXT, retired INTEGER NOT NULL,
            operation TEXT NOT NULL, thread TEXT NOT NULL, report TEXT NOT NULL, at REAL NOT NULL,
            PRIMARY KEY(project,id,revision))''')

    def read(self, project_id):
        office, root = self.store._authority(project_id)
        if not root:
            return []
        with self.store._db(office) as db:
            self._table(db)
            rows = db.execute('''SELECT v.* FROM library_versions v JOIN
                (SELECT id, MAX(revision) AS revision FROM library_versions WHERE project=? GROUP BY id) last
                USING(id,revision) WHERE v.project=? ORDER BY v.at DESC,v.id''', (project_id, project_id))
            return [dict(row) for row in rows]

    def history(self, project_id, entry_id):
        office, root = self.store._authority(project_id)
        if not root:
            return []
        with self.store._db(office) as db:
            self._table(db)
            return [dict(r) for r in db.execute('''SELECT * FROM library_versions WHERE project=? AND id=?
                ORDER BY revision DESC''', (project_id, entry_id))]

    def change(self, project_id, thread_id, report_id, entry_id, kind, title, body, operation, expected_revision):
        office, root = self.store._authority(project_id)
        if not root:
            raise Denied('LIBRARY_PROJECT_REQUIRED')
        title, body = title.strip(), body.strip()
        if not title or len(title) > 120 or len(body) > 1500:
            raise Denied('LIBRARY_TEXT_INVALID')
        with self.store._db(office) as db:
            self._table(db)
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM library_versions WHERE project=? AND id=? ORDER BY revision DESC LIMIT 1',
                             (project_id, entry_id)).fetchone()
            if (old['revision'] if old else 0) != expected_revision:
                raise Denied('LIBRARY_REVISION_CHANGED')
            if expected_revision >= 48:
                raise Denied('LIBRARY_STORAGE_LIMIT')
            if recover_report(db, project_id, thread_id, report_id) is None:
                raise Denied('LIBRARY_SOURCE_REQUIRED')
            if old and (old['kind'], old['thread'], old['report']) != (kind, thread_id, report_id):
                raise Denied('LIBRARY_SOURCE_CHANGED')
            if old and old['retired']:
                raise Denied('LIBRARY_ENTRY_RETIRED')
            active, proposal, retired = (old['body'], old['proposal'], 0) if old else ('', None, 0)
            if operation == 'create' and not old and body:
                if db.execute('SELECT COUNT(*) FROM library_versions WHERE project=? AND revision=1', (project_id,)).fetchone()[0] >= 64:
                    raise Denied('LIBRARY_STORAGE_LIMIT')
                if kind == 'skill':
                    proposal = body
                else:
                    active = body
            elif old and operation == 'retire':
                retired, proposal = 1, None
            elif old and kind == 'memory' and operation == 'edit' and body:
                active = body
            elif old and kind == 'skill' and operation == 'propose' and proposal is None and body and body != active:
                proposal = body
            elif old and kind == 'skill' and proposal is not None and operation in ('accept', 'discard'):
                if operation == 'accept':
                    active = proposal
                elif not active:
                    retired = 1
                proposal = None
            else:
                raise Denied('LIBRARY_TRANSITION_INVALID')
            if old and operation != 'edit':
                title = old['title']
            values = (project_id, entry_id, expected_revision+1, kind, title, active, proposal, retired,
                      operation, thread_id, report_id, time.time())
            db.execute('INSERT INTO library_versions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', values)
            db.commit()
            return dict(id=entry_id, revision=expected_revision+1)
