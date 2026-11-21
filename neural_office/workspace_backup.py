"""Portable desktop data bound to an independently retained continuity witness."""
from contextlib import closing
from hashlib import file_digest
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from zipfile import BadZipFile, ZIP_STORED, ZipFile

from . import attachments, continuity
from .files import local_path
from .ledger import Denied, Ledger, canonical

CHECKPOINT = 'WORKSPACE_BACKUP_CHECKPOINT'
PRIMARY = 'ledger.sqlite3'
DESKTOP = 'attachments.sqlite3'


def _sha(path):
    with path.open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()


def _reader(path):
    if not path.is_file() or path.is_symlink() or path.is_junction():
        raise Denied('BACKUP_MISSING_OR_UNSAFE')
    con = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA trusted_schema=OFF')
    return con


def _copy_db(source, dest):
    with closing(_reader(source)) as reader, closing(sqlite3.connect(dest)) as writer:
        reader.backup(writer)
        if writer.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise Denied('BACKUP_VERIFICATION_FAILED')


def _desktop_summary(path, office):
    with closing(_reader(path)) as db:
        if (db.execute('PRAGMA application_id').fetchone()[0] != attachments.APPLICATION_ID
                or db.execute('PRAGMA user_version').fetchone()[0] not in (1, attachments.SCHEMA)
                or [r[0] for r in db.execute('SELECT office FROM owner')] != [office]):
            raise Denied('ATTACHMENT_STORAGE_UNSAFE')
        for r in db.execute('SELECT project,thread,id FROM captures'):
            attachments.verified_content(db, *r, need_bytes=False, cancelled=lambda: False)
        for r in db.execute('SELECT project,thread,id FROM reports'):
            if attachments.recover_report(db, *r) is None:
                raise Denied('ATTACHMENT_REPORT_NOT_FOUND')
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
        return {table: db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] if table in tables else 0
                for table in ('captures', 'reports', 'decisions', 'library_versions')}


def create(ledger, destination):
    target = local_path(destination).absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp, continuity.run_guard(ledger.path), continuity.guard(ledger.path):
        stage = Path(tmp)
        sidecar = attachments.AttachmentStore(ledger).path
        members = [PRIMARY]
        with ledger.transaction(seal_unchanged=False) as con:
            if con.execute("SELECT 1 FROM attempts WHERE state NOT IN ('ACCEPTED','REJECTED','FAILED','CANCELLED') LIMIT 1").fetchone():
                raise Denied('BACKUP_REQUIRES_IDLE_OFFICE')
            office = con.execute('SELECT office FROM continuity_meta WHERE id=1').fetchone()[0]
            checkpoint = {'attachments_sha256': None}
            counts = dict(captures=0, reports=0, decisions=0, library_versions=0)
            if sidecar.exists() or sidecar.is_symlink():
                _copy_db(sidecar, stage / DESKTOP)
                counts = _desktop_summary(stage / DESKTOP, office)
                checkpoint['attachments_sha256'] = _sha(stage / DESKTOP)
                members.append(DESKTOP)
            last = con.execute('SELECT kind,payload FROM events ORDER BY seq DESC LIMIT 1').fetchone()
            if last is None or tuple(last) != (CHECKPOINT, canonical(checkpoint)):
                ledger._event(con, CHECKPOINT, checkpoint)
        receipt = continuity.backup(ledger, stage / PRIMARY)
        staged_archive = stage / 'backup.zip'
        with ZipFile(staged_archive, 'x', compression=ZIP_STORED) as archive:
            for name in members:
                archive.write(stage / name, name)
        with ZipFile(staged_archive) as archive:
            if archive.testzip() is not None:
                raise Denied('BACKUP_VERIFICATION_FAILED')
        # Windows rename fails when a concurrent caller already published the destination.
        staged_archive.rename(target)
    return {'office': office, 'revision': receipt['revision'], **counts, 'attachments_included': DESKTOP in members,
            'witness_included': False, 'retained_witness': str(continuity.witness_path(ledger.path).absolute())}


def restore(ledger, archive_file, retained_witness):
    source, witness = local_path(archive_file).absolute(), local_path(retained_witness).absolute()
    target = local_path(ledger.path).absolute()
    folder = target.parent
    if folder == folder.parent or folder.is_symlink() or folder.is_junction() or target.is_symlink():
        raise Denied('WORKSPACE_DESTINATION_IN_USE')
    if not source.is_file() or source.is_symlink():
        raise Denied('BACKUP_MISSING_OR_UNSAFE')
    with continuity.run_guard(target), continuity.guard(target):
        if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
            raise Denied('WORKSPACE_DESTINATION_IN_USE')
        with tempfile.TemporaryDirectory(dir=folder.parent) as tmp:
            stage = Path(tmp)
            recovered = stage / 'workspace'
            recovered.mkdir()
            staged_ledger = Ledger(recovered / target.name)
            staged_witness = continuity.witness_path(staged_ledger.path)
            try:
                _copy_db(witness, staged_witness)
            except sqlite3.DatabaseError as exc:
                raise Denied('WORKSPACE_RETAINED_WITNESS_INVALID') from exc
            sidecar = attachments.AttachmentStore(staged_ledger).path
            try:
                with ZipFile(source) as archive:
                    entries = archive.infolist()
                    names = [item.filename for item in entries]
                    if (sorted(names) not in ([PRIMARY], sorted([PRIMARY, DESKTOP]))
                            or any(i.compress_type != ZIP_STORED or i.file_size != i.compress_size for i in entries)):
                        raise Denied('WORKSPACE_ARCHIVE_INVALID')
                    for item in entries:
                        path = stage / PRIMARY if item.filename == PRIMARY else sidecar
                        with archive.open(item) as reader, path.open('xb') as out:
                            shutil.copyfileobj(reader, out)
            except BadZipFile as exc:
                raise Denied('WORKSPACE_ARCHIVE_INVALID') from exc
            try:
                result = continuity.restore(staged_ledger, stage / PRIMARY)
            except sqlite3.DatabaseError as exc:
                raise Denied('WORKSPACE_ARCHIVE_INVALID') from exc
            if result['restored_revision'] != result['backup_revision']:
                raise Denied('WORKSPACE_CHECKPOINT_SUPERSEDED')
            with staged_ledger.connection() as con:
                last = con.execute('SELECT kind,payload FROM events ORDER BY seq DESC LIMIT 1').fetchone()
                if last is None or last['kind'] != CHECKPOINT:
                    raise Denied('WORKSPACE_CHECKPOINT_MISSING')
                fingerprint = json.loads(last['payload'])['attachments_sha256']
            if fingerprint != (_sha(sidecar) if sidecar.exists() else None):
                raise Denied('WORKSPACE_ATTACHMENTS_CHANGED')
            counts = (_desktop_summary(sidecar, result['office']) if sidecar.exists() else
                      dict(reports=0, captures=0, decisions=0, library_versions=0))
            # Publish all databases in one directory rename. Only an empty placeholder may be removed.
            placeholder = folder.exists()
            if placeholder:
                folder.rmdir()
            try:
                os.rename(recovered, folder)
            except BaseException:
                if placeholder and not folder.exists():
                    folder.mkdir()
                raise
            return {**result, **counts, 'state': str(target)}
