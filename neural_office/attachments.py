"""Durable, project- and thread-scoped capture of locally selected review inputs."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time

from .attachment_formats import MAX_FILE, classify, result
from .desktop_contract import valid
from .files import capture_local, local_path
from .ledger import Denied, canonical, digest


SCHEMA = 1
APPLICATION_ID = 0x4E4F4154
RULE_VERSION = 'local-inspection-1'
MAX_CAPTURE_BATCH = 8
MAX_REPORT = 300_000
READERS = threading.BoundedSemaphore(2)
CAPTURE_FIELDS = 'id,source_id,name,kind,bytes,sha256,created_at'
ACTIONS = {'pdf': 'Leer páginas y localizar el requisito', 'json': 'Validar JSON y localizar el campo',
           'zip': 'Inventariar el paquete', 'png': 'Comprobar la imagen', 'jpeg': 'Comprobar la imagen',
           'html': 'Ejecutar reglas HTML', 'other': 'Identificar el archivo'}


def _send_input(pipe, content):
    try:
        with pipe:
            pipe.write(content)
    except (BrokenPipeError, OSError):
        # The decoder may already have exited or been cancelled.
        pass


def decode(kind, data, *, page, member, mode, cancelled, deadline):
    if cancelled():
        raise Denied('ATTACHMENT_READ_CANCELLED')
    if not READERS.acquire(blocking=False):
        raise Denied('ATTACHMENT_READER_BUSY')
    try:
        command = canonical(dict(kind=kind, page=page, member=member, mode=mode,
                                 captured_bytes=len(data), captured_sha256=digest(data)))
        worker = Path(__file__).with_name('attachment_worker.py').resolve()
        with subprocess.Popen([sys.executable, '-I', '-B', str(worker), command],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as process:
            # On Windows communicate(input=...) writes synchronously. A full
            # pipe must not prevent the owning thread from enforcing its deadline.
            pipe, process.stdin = process.stdin, None
            writer = threading.Thread(target=_send_input, args=(pipe, data), daemon=True)
            writer.start()
            try:
                while True:
                    if cancelled():
                        raise Denied('ATTACHMENT_READ_CANCELLED')
                    left = deadline - time.monotonic()
                    if left <= 0:
                        return result(kind, 'timeout', 'El lector alcanzó su límite de tiempo. Puedes elegir otra copia.')
                    try:
                        output, _ = process.communicate(timeout=min(left, 0.12))
                        break
                    except subprocess.TimeoutExpired:
                        continue
                if cancelled():
                    raise Denied('ATTACHMENT_READ_CANCELLED')
                if process.returncode or len(output) > 1_300_000:
                    return result(kind, 'unavailable', 'El lector terminó sin entregar una respuesta válida.')
                return json.loads(output)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
                writer.join()
    finally:
        READERS.release()


def comparison(attachments, views):
    clause = 'Se compara el plazo de primera respuesta del PDF con /response_sla_hours del JSON, en horas.'
    finding = dict(rule='first_response_hours', status='insufficient', title='Plazo de primera respuesta',
                   detail=clause, sources=[])
    docs = [item for item in attachments if item['kind'] == 'pdf']
    manifests = [item for item in attachments if item['kind'] == 'json']
    if len(docs) != 1 or len(manifests) != 1:
        finding['detail'] = 'Selecciona una especificación PDF y un manifiesto JSON para identificar las dos fuentes.'
        return finding
    doc, manifest = docs[0], manifests[0]
    pdf, data = views[doc['id']], views[manifest['id']]
    citations = pdf.get('candidates', [])
    hours = data.get('hours')
    for item, ref in ((doc, citations[0] if len(citations) == 1 else None), (manifest, hours)):
        if ref:
            finding['sources'].append(dict(ref, attachment_id=item['id'], name=item['name'],
                                           kind=item['kind'], sha256=item['sha256'], unit='h'))
    if pdf['status'] != 'ok' or not pdf.get('complete'):
        finding['detail'] = 'La cobertura del texto PDF es parcial. Revisa las páginas o aporta una copia con texto.'
    elif len(citations) != 1:
        finding['detail'] = 'El PDF debe contener un único requisito explícito de primera respuesta en horas.'
    elif not citations[0].get('region'):
        finding['detail'] = 'Se leyó el texto PDF, pero no se pudo verificar su posición en la página.'
    elif data['status'] != 'ok' or not hours:
        finding['detail'] = 'El manifiesto válido debe declarar un entero positivo en /response_sla_hours.'
    else:
        expected, declared = citations[0]['value'], hours['value']
        finding['status'] = 'match' if expected == declared else 'mismatch'
        finding['title'] = 'El plazo coincide' if expected == declared else 'Hay un plazo que no coincide'
        finding['detail'] = f'La especificación fija la primera respuesta en {expected} h. El manifiesto declara {declared} h.'
    return finding


def scope(project_id, thread_id):
    if not valid('project', project_id) or not valid('id', thread_id):
        raise Denied('DESKTOP_PARAMETER_INVALID')


def metadata(row):
    return {key: row[key] for key in CAPTURE_FIELDS.split(',')} | {'origin': 'native_picker'}


def report_identity(version, project_id, thread_id, objective, inputs, findings):
    return digest(canonical([version, project_id, thread_id, objective, inputs, findings]))[:32]


def recover_report(db, project_id, thread_id, identity):
    row = db.execute('SELECT payload,payload_sha FROM reports WHERE project=? AND thread=? AND id=?',
                     (project_id, thread_id, identity)).fetchone()
    if row is None:
        return None
    if digest(row['payload']) != row['payload_sha']:
        raise Denied('ATTACHMENT_INTEGRITY_FAILED')
    record = json.loads(row['payload'])
    if ((record['project_id'], record['thread_id'], record['id']) != (project_id, thread_id, identity)
            or report_identity(record['rule_version'], project_id, thread_id, record['objective'],
                               record['attachments'], record['findings']) != identity):
        raise Denied('ATTACHMENT_INTEGRITY_FAILED')
    for item in record['attachments']:
        owner = db.execute('SELECT sha256 FROM captures WHERE id=? AND project=? AND thread=?',
                           (item['id'], project_id, thread_id)).fetchone()
        if owner is None or owner[0] != item['sha256']:
            raise Denied('ATTACHMENT_INTEGRITY_FAILED')
    return record


class AttachmentStore:
    def __init__(self, ledger):
        self.ledger = ledger
        self.path = Path(str(ledger.path) + '.attachments.sqlite3')
        self._local_reads = {}
        self._lock = threading.Lock()
        self._closed = False

    def _authority(self, project_id):
        with self.ledger.connection() as con:
            office = con.execute('SELECT office FROM continuity_meta WHERE id=1').fetchone()[0]
            project = con.execute('SELECT root FROM projects WHERE id=?', (project_id,)).fetchone()
        return office, Path(project[0]) if project else None

    @contextmanager
    def _db(self, office):
        # Attachment BLOBs must not enlarge or repeatedly rehash the authority witness.
        # This auxiliary database cannot create an attempt or change a project balance.
        for suffix in ('', '-journal', '-wal', '-shm'):
            if Path(str(self.path) + suffix).is_symlink():
                raise Denied('ATTACHMENT_STORAGE_UNSAFE')
        db = sqlite3.connect(self.path, isolation_level=None, timeout=3)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA trusted_schema=OFF')
            db.execute('PRAGMA synchronous=FULL')
            app_id = db.execute('PRAGMA application_id').fetchone()[0]
            if app_id == 0:
                db.execute('BEGIN IMMEDIATE')
                app_id = db.execute('PRAGMA application_id').fetchone()[0]
                if app_id == 0:
                    if db.execute('SELECT 1 FROM sqlite_schema LIMIT 1').fetchone():
                        raise Denied('ATTACHMENT_STORAGE_UNSAFE')
                    db.execute('CREATE TABLE owner(office TEXT PRIMARY KEY)')
                    db.execute('INSERT INTO owner VALUES(?)', (office,))
                    db.execute('''CREATE TABLE captures(id TEXT PRIMARY KEY,project TEXT,thread TEXT,
                        source_id TEXT,name TEXT,kind TEXT,bytes INTEGER,sha256 TEXT,created_at REAL,content BLOB NOT NULL)''')
                    db.execute('CREATE INDEX capture_scope ON captures(project,thread,created_at)')
                    db.execute('''CREATE TABLE reports(id TEXT PRIMARY KEY,project TEXT,thread TEXT,
                        created_at REAL,objective TEXT,attachment_count INTEGER,finding_count INTEGER,
                        payload TEXT NOT NULL,payload_sha TEXT NOT NULL)''')
                    db.execute('CREATE INDEX report_scope ON reports(project,thread,created_at)')
                    db.execute(f'PRAGMA application_id={APPLICATION_ID}')
                    db.execute(f'PRAGMA user_version={SCHEMA}')
                db.commit()
            if (db.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID
                    or db.execute('PRAGMA user_version').fetchone()[0] != SCHEMA
                    or not db.execute('SELECT 1 FROM owner WHERE office=?', (office,)).fetchone()):
                raise Denied('ATTACHMENT_STORAGE_UNSAFE')
            yield db
        finally:
            if db.in_transaction:
                db.rollback()
            db.close()

    def capture(self, project_id, paths, *, thread_id='main'):
        scope(project_id, thread_id)
        if not isinstance(paths, (list, tuple)) or not 1 <= len(paths) <= MAX_CAPTURE_BATCH:
            raise Denied('ATTACHMENT_SELECTION_LIMIT')
        office, existing = self._authority(project_id)
        choices = [local_path(path) for path in paths]
        root = existing or choices[0].parent.absolute()
        rows = {}
        total = 0
        for candidate in choices:
            if len(candidate.name) > 240:
                raise Denied('ATTACHMENT_NAME_LIMIT')
            data, file_identity = capture_local(candidate, root, maximum=MAX_FILE, allow_empty=True)
            total += len(data)
            if total > 24 * 1024 * 1024:
                raise Denied('ATTACHMENT_SELECTION_LIMIT')
            sha = digest(data)
            source_id = digest(canonical([office, project_id, file_identity]))
            capture_id = digest(canonical([source_id, thread_id, sha, candidate.name]))
            rows[capture_id] = (capture_id, project_id, thread_id, source_id, candidate.name, classify(candidate.name, data),
                                len(data), sha, time.time(), data)
        if existing is None:
            try:
                self.ledger.register(project_id, root)
            except sqlite3.IntegrityError:
                raise Denied('PROJECT_ROOT_ALREADY_REGISTERED') from None
        with self._db(office) as db:
            db.execute('BEGIN IMMEDIATE')
            for row in rows.values():
                db.execute('INSERT OR IGNORE INTO captures VALUES(?,?,?,?,?,?,?,?,?,?)', row)
            count, size = db.execute('SELECT COUNT(*),SUM(bytes) FROM captures WHERE project=?', (project_id,)).fetchone()
            total_bytes = db.execute('SELECT SUM(bytes) FROM captures').fetchone()[0] or 0
            if count > 160 or size > 64 * 1024 * 1024 or total_bytes > 256 * 1024 * 1024:
                raise Denied('ATTACHMENT_STORAGE_LIMIT')
            db.commit()
            return [metadata(db.execute(f'SELECT {CAPTURE_FIELDS} FROM captures WHERE id=?', (identity,)).fetchone())
                    for identity in rows]

    def list(self, project_id, *, thread_id='main'):
        scope(project_id, thread_id)
        office, root = self._authority(project_id)
        if root is None:
            return []
        with self._db(office) as db:
            return [metadata(row) for row in db.execute(
                f'SELECT {CAPTURE_FIELDS} FROM captures WHERE project=? AND thread=? ORDER BY created_at,id',
                (project_id, thread_id))]

    def _content(self, office, project_id, thread_id, identity):
        if not valid('digest', identity):
            raise Denied('ATTACHMENT_NOT_FOUND')
        with self._db(office) as db:
            row = db.execute(f'SELECT {CAPTURE_FIELDS},content FROM captures WHERE id=? AND project=? AND thread=?',
                             (identity, project_id, thread_id)).fetchone()
        if not row:
            raise Denied('ATTACHMENT_NOT_FOUND')
        data = row['content']
        expected_id = digest(canonical([row['source_id'], thread_id, row['sha256'], row['name']]))
        if (len(data) != row['bytes'] or len(data) > MAX_FILE or digest(data) != row['sha256']
                or identity != expected_id or classify(row['name'], data) != row['kind']):
            raise Denied('ATTACHMENT_INTEGRITY_FAILED')
        return metadata(row), data

    @contextmanager
    def _reading(self, project_id, thread_id):
        key = (project_id, thread_id)
        signal = threading.Event()
        with self._lock:
            if self._closed:
                raise Denied('ATTACHMENT_READ_CANCELLED')
            self._local_reads.setdefault(key, set()).add(signal)
        try:
            yield signal.is_set
        finally:
            with self._lock:
                group = self._local_reads[key]
                group.remove(signal)
                if not group:
                    del self._local_reads[key]

    def close(self):
        with self._lock:
            self._closed = True
            for group in self._local_reads.values():
                for signal in group:
                    signal.set()

    def cancel_reads(self, project_id, *, thread_id='main'):
        scope(project_id, thread_id)
        with self._lock:
            pending = self._local_reads.get((project_id, thread_id), ())
            for event in pending:
                event.set()
            return len(pending)

    def preview(self, project_id, attachment_id, *, page=1, member='', thread_id='main'):
        scope(project_id, thread_id)
        if type(page) is not int or not 1 <= page <= 10000 or not isinstance(member, str) or len(member) > 512:
            raise Denied('DESKTOP_PARAMETER_INVALID')
        office, _ = self._authority(project_id)
        info, content = self._content(office, project_id, thread_id, attachment_id)
        with self._reading(project_id, thread_id) as cancelled:
            view = decode(info['kind'], content, page=page, member=member, mode='preview', cancelled=cancelled,
                          deadline=time.monotonic() + 8)
        return dict(view, attachment_id=attachment_id, name=info['name'], sha256=info['sha256'])

    def inspect(self, project_id, attachment_ids, objective='', *, thread_id='main'):
        scope(project_id, thread_id)
        if (not isinstance(attachment_ids, list) or not 1 <= len(attachment_ids) <= MAX_CAPTURE_BATCH
                or any(not valid('digest', item) for item in attachment_ids) or len(set(attachment_ids)) != len(attachment_ids)
                or not isinstance(objective, str) or len(objective) > 2000):
            raise Denied('DESKTOP_PARAMETER_INVALID')
        office, _ = self._authority(project_id)
        inputs = []
        views = {}
        steps = []
        findings = []
        created = time.time()
        deadline = time.monotonic() + 26
        with self._reading(project_id, thread_id) as cancelled:
            for identity in attachment_ids:
                started = time.monotonic()
                info, data = self._content(office, project_id, thread_id, identity)
                kind = info['kind']
                view = decode(kind, data, page=1, member='', mode='inspect', cancelled=cancelled,
                              deadline=min(deadline, time.monotonic() + 7))
                if cancelled():
                    raise Denied('ATTACHMENT_READ_CANCELLED')
                inputs.append(dict(info, status=view['status'], detail=view['detail']))
                views[identity] = view
                steps.append(dict(at=time.time(), duration_ms=round((time.monotonic()-started)*1000),
                                  actor='Lector local', action=ACTIONS[kind], detail=view['detail'],
                                  status=view['status'], attachment_id=identity))
                if kind == 'html' and view['status'] == 'ok':
                    lines = data.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n').split('\n')
                    findings.append(dict(rule='static_html', status='observed', title='Comprobación HTML',
                                         detail=f"{view['findings_total']} hallazgos en las cuatro comprobaciones locales.",
                                         sources=[dict(attachment_id=identity, name=info['name'], sha256=info['sha256'],
                                                       kind=kind, line=row['line'], column=row['column'], code=row['code'],
                                                       quote=lines[row['line']-1][max(0, row['column']-25):row['column']+130])
                                                  for row in view['findings'][:24]], total=view['findings_total']))
            if any(i['kind'] in ('pdf', 'json') for i in inputs):
                started = time.monotonic()
                check = comparison(inputs, views)
                findings.append(check)
                steps.append(dict(at=time.time(), duration_ms=round((time.monotonic()-started)*1000),
                                  actor='Verificador local', action='Comparar el plazo de primera respuesta',
                                  status=check['status'], detail=check['detail']))
            if cancelled():
                raise Denied('ATTACHMENT_READ_CANCELLED')
            # A retry that reproduces the facts reopens the same report. A
            # previously unavailable reader can still record a corrected result.
            identity = report_identity(RULE_VERSION, project_id, thread_id, objective, inputs, findings)
            report = dict(id=identity, project_id=project_id, thread_id=thread_id, objective=objective,
                          created_at=created, rule_version=RULE_VERSION, attachments=inputs, findings=findings,
                          steps=steps, reservations=0, model_calls=0)
            payload = canonical(report)
            if len(payload.encode('utf-8')) > MAX_REPORT:
                raise Denied('ATTACHMENT_REPORT_LIMIT')
            with self._db(office) as db:
                db.execute('BEGIN IMMEDIATE')
                old = recover_report(db, project_id, thread_id, identity)
                if old:
                    db.commit()
                    return old
                if db.execute('SELECT COUNT(*) FROM reports WHERE project=?', (project_id,)).fetchone()[0] >= 300:
                    raise Denied('ATTACHMENT_STORAGE_LIMIT')
                if cancelled():
                    raise Denied('ATTACHMENT_READ_CANCELLED')
                db.execute('INSERT INTO reports VALUES(?,?,?,?,?,?,?,?,?)',
                           (identity, project_id, thread_id, created, objective, len(inputs), len(findings), payload, digest(payload)))
                db.commit()
            return report

    def history(self, project_id, *, thread_id='main'):
        scope(project_id, thread_id)
        office, root = self._authority(project_id)
        if root is None:
            return []
        with self._db(office) as db:
            rows = db.execute('''SELECT id,project AS project_id,thread AS thread_id,objective,created_at,
                attachment_count,finding_count FROM reports WHERE project=? AND thread=? ORDER BY created_at DESC,id''',
                              (project_id, thread_id))
            return [dict(row) for row in rows]

    def report(self, project_id, report_id, *, thread_id='main'):
        scope(project_id, thread_id)
        office, _ = self._authority(project_id)
        with self._db(office) as db:
            record = recover_report(db, project_id, thread_id, report_id)
        if record is None:
            raise Denied('ATTACHMENT_REPORT_NOT_FOUND')
        return record

    def threads(self, project_id):
        scope(project_id, 'main')
        office, root = self._authority(project_id)
        if root is None:
            return []
        with self._db(office) as db:
            rows = db.execute('''WITH seen AS (
                SELECT thread, created_at FROM captures WHERE project=?
                UNION ALL SELECT thread, created_at FROM reports WHERE project=?)
                SELECT thread AS id, MAX(created_at) AS created_at,
                    COALESCE((SELECT objective FROM reports r WHERE r.project=? AND r.thread=s.thread
                              AND length(trim(r.objective))>0 ORDER BY r.created_at DESC,r.id LIMIT 1),
                             (SELECT name FROM captures c WHERE c.project=? AND c.thread=s.thread
                              ORDER BY c.created_at,c.id LIMIT 1)) AS objective
                FROM seen s GROUP BY thread ORDER BY created_at DESC,id''',
                              (project_id, project_id, project_id, project_id))
            return [dict(row) for row in rows]
