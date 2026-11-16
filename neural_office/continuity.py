"""A separate retained witness. It is continuity evidence, not an adversary-proof vault."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes as w
import os
from pathlib import Path
import sqlite3
import uuid

from .ledger import APPLICATION_ID, Denied, canonical, digest

WITNESS_ID = 0x4E4F4354
MAX_IMAGE = 64 * 1024 * 1024


def witness_path(path):
    return Path(str(path) + '.witness.sqlite3')


@contextmanager
def guard(path):
    """Serialize replacement as well as SQLite access, across cooperating processes."""
    if os.name != 'nt':
        raise Denied('CONTINUITY_REQUIRES_WINDOWS')
    dll = ctypes.WinDLL('kernel32', use_last_error=True)
    for name, args, result in (
        ('CreateMutexW', [ctypes.c_void_p, w.BOOL, w.LPCWSTR], w.HANDLE),
        ('WaitForSingleObject', [w.HANDLE, w.DWORD], w.DWORD),
        ('ReleaseMutex', [w.HANDLE], w.BOOL),
        ('CloseHandle', [w.HANDLE], w.BOOL),
    ):
        fn = getattr(dll, name); fn.argtypes = args; fn.restype = result
    key = digest(os.path.normcase(str(Path(path).resolve())))
    handle = dll.CreateMutexW(None, False, 'Local\\NeuralOfficeContinuity_' + key)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    held = False
    try:
        outcome = dll.WaitForSingleObject(handle, 10000)
        # An abandoned owner still requires SQLite recovery and witness validation.
        if outcome not in (0, 0x80):
            raise Denied('CONTINUITY_LOCK_UNAVAILABLE')
        held = True
        yield
    finally:
        if held: dll.ReleaseMutex(handle)
        dll.CloseHandle(handle)


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def signature(con):
    """Logical digest is stable across SQLite backup/header bookkeeping changes."""
    schema = [tuple(r) for r in con.execute(
        "SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name")]
    tables = [r[1] for r in schema if r[0] == 'table']
    data = {}
    for table in tables:
        rows = con.execute('SELECT * FROM main.' + _quote(table) + ' ORDER BY rowid')
        data[table] = [[{'blob_hex': v.hex()} if isinstance(v, bytes) else v for v in row] for row in rows]
    return digest(canonical({'schema': schema, 'tables': data,
        'application_id': con.execute('PRAGMA main.application_id').fetchone()[0],
        'user_version': con.execute('PRAGMA main.user_version').fetchone()[0]}))


def attach(con, path):
    witness = witness_path(path)
    if not witness.is_file() or witness.is_symlink():
        raise Denied('CONTINUITY_WITNESS_MISSING')
    con.execute('ATTACH DATABASE ? AS continuity', (witness.resolve().as_uri() + '?mode=rw',))
    if con.execute('PRAGMA continuity.application_id').fetchone()[0] != WITNESS_ID:
        raise Denied('CONTINUITY_WITNESS_INVALID')
    for schema in ('main', 'continuity'):
        if con.execute(f'PRAGMA {schema}.journal_mode').fetchone()[0] != 'delete':
            raise Denied('CONTINUITY_REQUIRES_ROLLBACK_JOURNAL')
        con.execute(f'PRAGMA {schema}.synchronous=FULL')


def validate(con):
    if con.execute('PRAGMA main.user_version').fetchone()[0] != 2:
        raise Denied('CONTINUITY_UPGRADE_REQUIRED_RUN_PROTECT')
    own = con.execute('SELECT office,revision FROM continuity_meta WHERE id=1').fetchone()
    last = con.execute('SELECT office,revision,logical_sha FROM continuity.latest WHERE id=1').fetchone()
    if own is None or last is None or tuple(own) != tuple(last[:2]) or signature(con) != last[2]:
        raise Denied('CONTINUITY_DIVERGENCE_RESTORE_REQUIRED')
    history = con.execute('SELECT logical_sha FROM continuity.history WHERE revision=?', (own[1],)).fetchone()
    tip = con.execute('SELECT max(revision) FROM continuity.history').fetchone()[0]
    if history is None or history[0] != last[2] or tip != own[1]:
        raise Denied('CONTINUITY_HISTORY_INVALID')


def seal(con):
    con.execute('UPDATE continuity_meta SET revision=revision+1 WHERE id=1')
    office, revision = con.execute('SELECT office,revision FROM continuity_meta WHERE id=1').fetchone()
    logical_sha = signature(con)
    image = con.serialize(name='main')
    if len(image) > MAX_IMAGE:
        raise Denied('CONTINUITY_IMAGE_LIMIT')
    image_sha = digest(image)
    con.execute('INSERT OR REPLACE INTO continuity.latest VALUES(1,?,?,?,?,?)',
                (office, revision, logical_sha, image_sha, image))
    con.execute('INSERT INTO continuity.history VALUES(?,?,?)', (revision, logical_sha, image_sha))


def protect(ledger):
    """Explicit enrollment of an existing V5.2 state; preserves its full history."""
    path = ledger.path
    with guard(path):
        if not path.is_file() or path.is_symlink(): raise Denied('STATE_NOT_INITIALIZED_OR_UNSAFE')
        if witness_path(path).exists():
            with ledger.connection(): pass
            return {'protected': True, 'already_protected': True}
        con = sqlite3.connect(path.resolve().as_uri() + '?mode=rw', uri=True, isolation_level=None)
        try:
            if con.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID:
                raise Denied('FOREIGN_STATE')
            if con.execute('PRAGMA user_version').fetchone()[0] != 1:
                raise Denied('CONTINUITY_WITNESS_MISSING')
            if con.execute('SELECT attempt FROM lease').fetchone()[0] is not None:
                raise Denied('PROTECT_REQUIRES_IDLE_OFFICE')
            if con.execute('PRAGMA journal_mode').fetchone()[0] != 'delete':
                raise Denied('CONTINUITY_REQUIRES_ROLLBACK_JOURNAL')
            fd = os.open(witness_path(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            con.execute('ATTACH DATABASE ? AS continuity', (str(witness_path(path).resolve()),))
            con.execute('PRAGMA synchronous=FULL'); con.execute('PRAGMA continuity.synchronous=FULL')
            con.execute('BEGIN IMMEDIATE')
            # A schema-1 controller does not participate in guard. Recheck only
            # after acquiring SQLite's writer lock, before adopting its state.
            if con.execute('SELECT attempt FROM lease').fetchone()[0] is not None:
                raise Denied('PROTECT_REQUIRES_IDLE_OFFICE')
            if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or con.execute('PRAGMA foreign_key_check').fetchone():
                raise Denied('STATE_INTEGRITY_FAILED')
            previous='0'*64
            for e in con.execute('SELECT stamp_ns,kind,payload,previous,digest FROM events ORDER BY seq'):
                expected=digest(canonical([previous,e[0],e[1],e[2]]))
                if e[3]!=previous or e[4]!=expected: raise Denied('EVENT_CHAIN_CHANGED')
                previous=e[4]
            con.execute('CREATE TABLE continuity_meta(id INTEGER PRIMARY KEY CHECK(id=1),office TEXT NOT NULL,revision INTEGER NOT NULL)')
            con.execute('INSERT INTO continuity_meta VALUES(1,?,0)', (uuid.uuid4().hex,))
            con.execute('CREATE TABLE legacy_bindings(project TEXT PRIMARY KEY REFERENCES projects(id),lineage TEXT NOT NULL,source_root TEXT NOT NULL,consumed INTEGER NOT NULL,receipt TEXT NOT NULL,UNIQUE(lineage,project))')
            con.execute('CREATE TABLE legacy_roots(root TEXT PRIMARY KEY,project TEXT NOT NULL REFERENCES projects(id))')
            con.execute('PRAGMA user_version=2')
            con.execute(f'PRAGMA continuity.application_id={WITNESS_ID}')
            con.execute('CREATE TABLE continuity.latest(id INTEGER PRIMARY KEY CHECK(id=1),office TEXT NOT NULL,revision INTEGER NOT NULL,logical_sha TEXT NOT NULL,image_sha TEXT NOT NULL,image BLOB NOT NULL)')
            con.execute('CREATE TABLE continuity.history(revision INTEGER PRIMARY KEY,logical_sha TEXT NOT NULL,image_sha TEXT NOT NULL)')
            seal(con)
            con.commit()
            return {'protected': True, 'already_protected': False}
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()


def backup(ledger, destination):
    target = Path(destination)
    with ledger.connection() as con:
        if con.execute('SELECT attempt FROM lease').fetchone()[0] is not None:
            raise Denied('BACKUP_REQUIRES_IDLE_OFFICE')
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        dest = sqlite3.connect(target)
        try:
            con.backup(dest)
            if signature(dest) != signature(con): raise Denied('BACKUP_VERIFICATION_FAILED')
            office, revision = con.execute('SELECT office,revision FROM continuity_meta').fetchone()
            return {'office': office, 'revision': revision, 'logical_sha': signature(dest),
                    'witness_included': False}
        finally:
            dest.close()


def restore(ledger, backup_file):
    """A valid old backup identifies the office; the retained witness supplies latest state."""
    path, source = ledger.path, Path(backup_file)
    with guard(path):
        wp = witness_path(path)
        if path.is_symlink(): raise Denied('STATE_NOT_INITIALIZED_OR_UNSAFE')
        if not wp.is_file() or wp.is_symlink(): raise Denied('CONTINUITY_WITNESS_MISSING')
        if not source.is_file() or source.is_symlink(): raise Denied('BACKUP_MISSING_OR_UNSAFE')
        wit = sqlite3.connect(wp.resolve().as_uri() + '?mode=ro', uri=True)
        old = mem = None
        try:
            old = sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)
            mem = sqlite3.connect(':memory:')
            if wit.execute('PRAGMA application_id').fetchone()[0] != WITNESS_ID:
                raise Denied('CONTINUITY_WITNESS_INVALID')
            office, revision, logical_sha, image_sha, image = wit.execute(
                'SELECT office,revision,logical_sha,image_sha,image FROM latest WHERE id=1').fetchone()
            if wit.execute('SELECT max(revision) FROM history').fetchone()[0] != revision:
                raise Denied('CONTINUITY_HISTORY_INVALID')
            if len(image) > MAX_IMAGE or digest(image) != image_sha:
                raise Denied('CONTINUITY_IMAGE_CHANGED')
            old_office, old_revision = old.execute('SELECT office,revision FROM continuity_meta WHERE id=1').fetchone()
            old_hash = wit.execute('SELECT logical_sha FROM history WHERE revision=?', (old_revision,)).fetchone()
            if old_office != office or old_revision > revision or not old_hash or signature(old) != old_hash[0]:
                raise Denied('BACKUP_NOT_IN_RETAINED_HISTORY')
            mem.deserialize(image)
            if mem.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or signature(mem) != logical_sha:
                raise Denied('CONTINUITY_IMAGE_INVALID')
            if tuple(mem.execute('SELECT office,revision FROM continuity_meta').fetchone()) != (office, revision):
                raise Denied('CONTINUITY_IDENTITY_CHANGED')
            attempt, job_name = mem.execute('SELECT attempt,job FROM lease').fetchone()
            if attempt is not None:
                from .windows_job import Job
                job = Job(job_name, existing=True)
                try:
                    if job.active(): raise Denied('RESTORE_OWNED_JOB_STILL_ACTIVE')
                finally: job.close()
            if path.exists():
                current = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
                try:
                    current_id, current_rev = current.execute('SELECT office,revision FROM continuity_meta').fetchone()
                    known = wit.execute('SELECT logical_sha FROM history WHERE revision=?', (current_rev,)).fetchone()
                    if current_id != office or current_rev > revision or not known or signature(current) != known[0]:
                        raise Denied('CURRENT_STATE_NOT_IN_RETAINED_HISTORY')
                finally: current.close()
            # All cooperating readers/writers use guard. Keep backup and witness intact.
            temp = path.with_name(path.name + '.restore-' + uuid.uuid4().hex)
            with temp.open('xb') as handle:
                handle.write(image); handle.flush(); os.fsync(handle.fileno())
            old.close()
            os.replace(temp, path)
            return {'office': office, 'backup_revision': old_revision, 'restored_revision': revision,
                    'used_retained_witness': True, 'pending_attempt': attempt,
                    'all_copies_rollback_detectable': False}
        finally:
            if mem is not None: mem.close()
            if old is not None: old.close()
            wit.close()
