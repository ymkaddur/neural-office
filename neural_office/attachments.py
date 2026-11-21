"""Durable, project- and thread-scoped capture of locally selected review inputs."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time

from .attachment_formats import MAX_FILE, classify, legacy_kind, result
from .desktop_contract import valid
from .inspection_intent import READER_FORMATS, literal_findings, reader_findings
from .inspection_plan import Task, plan, read_plan, unsupported
from .files import FileStamp, capture_local, local_path
from .ledger import Denied, canonical, digest
from .team_review import review as review_with_team, verify_saved


SCHEMA = 2
APPLICATION_ID = 0x4E4F4154
RULE_VERSION = 'local-inspection-9'
MAX_CAPTURE_BATCH = 8
MAX_REPORT = 300_000
MAX_IDENTIFIED_FILE = 512 * 1024 * 1024
MAX_IDENTIFIED_BATCH = 1024 * 1024 * 1024
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
        if pdf.get('image_pages'):
            pages = ', '.join(str(number) for number in pdf['image_pages'])
            finding['detail'] = f'La cobertura del texto PDF es parcial. Revisa las imágenes (pág. {pages}) antes de confirmar el plazo.'
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


def stamp_id(source, thread, sha, name, size, header):
    return digest(canonical(['file-stamp-1', source, thread, sha, name, size, header.hex()]))


def stamp_view(info, header):
    return result('identity', 'metadata', 'Se recorrió el archivo completo para obtener su huella. Por tamaño se conserva solo su identidad.',
                  bytes=info['bytes'], signature=header.hex(' '))


def verified_content(db, project, thread, identity, *, need_bytes, cancelled):
    if not valid('digest', identity):
        raise Denied('ATTACHMENT_NOT_FOUND')
    row = db.execute(f'''SELECT rowid AS blob_id,typeof(content) AS storage_type,{CAPTURE_FIELDS}
                         FROM captures WHERE id=? AND project=? AND thread=?''',
                     (identity, project, thread)).fetchone()
    if not row:
        raise Denied('ATTACHMENT_NOT_FOUND')
    if row['kind'] == 'identity':
        with db.blobopen('captures', 'content', row['blob_id'], readonly=True) as blob:
            header = blob.read(33)
        if (row['storage_type'] != 'blob' or len(header) != 32 or not MAX_FILE < row['bytes'] <= MAX_IDENTIFIED_FILE
                or stamp_id(row['source_id'], thread, row['sha256'], row['name'], row['bytes'], header) != identity):
            raise Denied('ATTACHMENT_INTEGRITY_FAILED')
        return metadata(row), header
    expected_id = digest(canonical([row['source_id'], thread, row['sha256'], row['name']]))
    if expected_id != identity or row['storage_type'] != 'blob':
        raise Denied('ATTACHMENT_INTEGRITY_FAILED')
    with db.blobopen('captures', 'content', row['blob_id'], readonly=True) as blob:
        if len(blob) != row['bytes'] or len(blob) > MAX_FILE:
            raise Denied('ATTACHMENT_INTEGRITY_FAILED')
        if need_bytes:
            data = blob.read()
            prefix, sha = data[:16], digest(data)
        else:
            # An unneeded source still has to match its original bytes. Bound
            # memory for this check and keep cancellation responsive between chunks.
            data = None
            prefix = blob.read(16)
            hasher = hashlib.sha256(prefix)
            while chunk := blob.read(256 * 1024):
                if cancelled():
                    raise Denied('ATTACHMENT_READ_CANCELLED')
                hasher.update(chunk)
            sha = hasher.hexdigest()
    if sha != row['sha256'] or row['kind'] not in (classify(row['name'], prefix), legacy_kind(row['name'], prefix)):
        raise Denied('ATTACHMENT_INTEGRITY_FAILED')
    return metadata(row), data


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
    if record['rule_version'] in ('local-inspection-5', 'local-inspection-6', 'local-inspection-7', 'local-inspection-8', RULE_VERSION):
        only_guidance = all(f['rule'] in ('scope', 'greeting', 'text_brief') for f in record['findings'])
        if record['rule_version'] != 'local-inspection-5' and only_guidance:
            if 'team' in record:
                raise Denied('ATTACHMENT_INTEGRITY_FAILED')
        else:
            verify_saved(record)
    return record


def matching_legacy_report(db, project, thread, objective, inputs, findings):
    # Older readers persisted parser status for every file. Compare the facts
    # just verified, then return the original immutable report and its decision.
    candidates = db.execute('''SELECT r.id FROM reports r WHERE project=? AND thread=? AND objective=?
        AND attachment_count=? AND finding_count=? ORDER BY
        (SELECT MAX(d.at) FROM decisions d WHERE d.project=r.project AND d.thread=r.thread AND d.report=r.id) DESC,
        r.created_at DESC,r.id''', (project, thread, objective, len(inputs), len(findings)))
    for row in candidates:
        old = recover_report(db, project, thread, row['id'])
        if (old['rule_version'] not in ('local-inspection-2', 'local-inspection-3', 'local-inspection-4', 'local-inspection-5', 'local-inspection-6', 'local-inspection-7', 'local-inspection-8')
                or (old['rule_version'] == 'local-inspection-5' and all(f['rule'] in ('scope', 'greeting') for f in findings))
                or old['objective'] != objective or old['findings'] != findings
                or len(old['attachments']) != len(inputs)):
            continue
        cited_ids = {c['attachment_id'] for f in findings for c in f['sources']}
        if (old.get('team') and len(old['team']['delivery']['sources']) != len(cited_ids)
                and not db.execute('SELECT 1 FROM decisions WHERE project=? AND thread=? AND report=? LIMIT 1',
                                   (project,thread,old['id'])).fetchone()):
            # Historical deliveries included all selected captures in the source count.
            # Keep the original openable, but publish corrected provenance on a new inspection.
            continue
        if all(all(saved.get(key) == value for key, value in current.items())
               for saved, current in zip(old['attachments'], inputs)):
            return old
    return None


def with_decision(db, record):
    note = db.execute('''SELECT revision,choice,at FROM decisions WHERE project=? AND thread=?
        AND report=? ORDER BY revision DESC LIMIT 1''',
                      (record['project_id'], record['thread_id'], record['id'])).fetchone()
    if note:
        record['decision'] = dict(note)
    return record


class AttachmentStore:
    def __init__(self, ledger):
        self.ledger = ledger
        self.path = Path(str(ledger.path) + '.attachments.sqlite3')
        self._local_reads = {}
        self._inspections = {}
        self._lock = threading.Lock()
        self._closed = False

    def _authority(self, project_id):
        with self.ledger.connection() as con:
            office = con.execute('SELECT office FROM continuity_meta WHERE id=1').fetchone()[0]
            project = con.execute('SELECT root FROM projects WHERE id=?', (project_id,)).fetchone()
        return office, project[0] if project else None

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
                    db.execute('PRAGMA user_version=1')
                db.commit()
            if (db.execute('PRAGMA application_id').fetchone()[0] == APPLICATION_ID
                    and db.execute('PRAGMA user_version').fetchone()[0] == 1
                    and db.execute('SELECT 1 FROM owner WHERE office=?', (office,)).fetchone()):
                db.execute('BEGIN IMMEDIATE')
                if db.execute('PRAGMA user_version').fetchone()[0] == 1:
                    db.execute("""CREATE TABLE decisions(project TEXT NOT NULL,thread TEXT NOT NULL,
                        report TEXT NOT NULL,revision INTEGER NOT NULL,choice TEXT NOT NULL,at REAL NOT NULL,
                        PRIMARY KEY(project,thread,report,revision))""")
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
        needs_root = existing is None or existing == self.ledger.unbound_root(project_id)
        root = choices[0].parent.absolute() if needs_root else Path(existing)
        rows = {}
        total = 0
        scanned = 0
        for candidate in choices:
            if len(candidate.name) > 240:
                raise Denied('ATTACHMENT_NAME_LIMIT')
            data, file_identity = capture_local(candidate, root, maximum=min(MAX_IDENTIFIED_FILE, MAX_IDENTIFIED_BATCH-scanned),
                                                metadata_above=MAX_FILE, allow_empty=True)
            source_id = digest(canonical([office, project_id, file_identity]))
            if isinstance(data, FileStamp):
                size, sha, body, kind = data.size, data.sha256, data.header, 'identity'
                capture_id = stamp_id(source_id, thread_id, sha, candidate.name, size, body)
            else:
                size, sha, body, kind = len(data), digest(data), data, classify(candidate.name, data)
                capture_id = digest(canonical([source_id, thread_id, sha, candidate.name]))
            scanned += size
            total += len(body)
            if total > 24 * 1024 * 1024:
                raise Denied('ATTACHMENT_SELECTION_LIMIT')
            rows[capture_id] = (capture_id, project_id, thread_id, source_id, candidate.name, kind,
                                size, sha, time.time(), body)
        if needs_root:
            try:
                self.ledger.register(project_id, root)
            except sqlite3.IntegrityError:
                raise Denied('PROJECT_ROOT_ALREADY_REGISTERED') from None
        with self._db(office) as db:
            db.execute('BEGIN IMMEDIATE')
            for row in rows.values():
                db.execute('INSERT OR IGNORE INTO captures VALUES(?,?,?,?,?,?,?,?,?,?)', row)
            count, size = db.execute('SELECT COUNT(*),SUM(length(content)) FROM captures WHERE project=?', (project_id,)).fetchone()
            total_bytes = db.execute('SELECT SUM(length(content)) FROM captures').fetchone()[0] or 0
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

    @contextmanager
    def _observed_inspection(self, project, thread, sources, objective):
        key = (project, thread)
        with self._lock:
            if key in self._inspections:
                raise Denied('ATTACHMENT_READER_BUSY')
            record = {'objective': objective, 'sources': list(sources), 'finished': 0,
                      'action': 'Preparando la lectura', 'at': time.time()}
            self._inspections[key] = record
        def note(action, finished, role=None, round_number=None, phase=None):
            with self._lock:
                record.update(action=action, finished=finished, at=time.time())
                if role is not None:
                    record.update(role=role, round=round_number, phase=phase)
                else:
                    for field in ('role', 'round', 'phase'):
                        record.pop(field, None)
        try:
            yield note
        finally:
            with self._lock:
                self._inspections.pop(key, None)

    def activity(self, project_id, thread_id):
        scope(project_id, thread_id)
        with self._lock:
            item = self._inspections.get((project_id, thread_id))
            return dict(item) if item is not None else None

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
        with self._reading(project_id, thread_id) as cancelled:
            with self._db(office) as db:
                info, content = verified_content(db, project_id, thread_id, attachment_id,
                                                 need_bytes=True, cancelled=cancelled)
            view = (stamp_view(info, content) if info['kind'] == 'identity' else
                    decode(info['kind'], content, page=page, member=member, mode='preview', cancelled=cancelled,
                           deadline=time.monotonic() + 8))
        return dict(view, attachment_id=attachment_id, name=info['name'], sha256=info['sha256'])

    def inspect(self, project_id, attachment_ids, objective='', *, thread_id='main'):
        scope(project_id, thread_id)
        if (not isinstance(attachment_ids, list) or len(attachment_ids) > MAX_CAPTURE_BATCH
                or any(not valid('digest', item) for item in attachment_ids) or len(set(attachment_ids)) != len(attachment_ids)
                or not valid('inspection_objective', objective) or (not attachment_ids and not objective.strip())):
            raise Denied('DESKTOP_PARAMETER_INVALID')
        if not attachment_ids:
            self.ledger.register_text(project_id)
        office, _ = self._authority(project_id)
        inputs = []
        views = {}
        steps = []
        findings = []
        html_results = {}
        created = time.time()
        deadline = time.monotonic() + 26
        with (self._observed_inspection(project_id, thread_id, attachment_ids, objective) as note,
              self._reading(project_id, thread_id) as cancelled, self._db(office) as db):
            slots = ','.join('?' for _ in attachment_ids)
            captured = {row['id']: row for row in db.execute(
                f'SELECT id,kind,name FROM captures WHERE project=? AND thread=? AND id IN ({slots})',
                (project_id, thread_id, *attachment_ids))}
            if len(captured) != len(attachment_ids):
                raise Denied('ATTACHMENT_NOT_FOUND')
            ordered = [captured[i] for i in attachment_ids]
            tasks = plan(objective, ordered) if ordered else [Task('text_brief', (), objective)]
            checks = [t.action for t in tasks]
            modes = read_plan(tasks, ordered)
            excluded = {i for request in tasks for i in request.excluded}
            for identity in attachment_ids:
                if identity in excluded:
                    continue
                if cancelled():
                    raise Denied('ATTACHMENT_READ_CANCELLED')
                started = time.monotonic()
                mode = modes.get(identity)
                info, data = verified_content(db, project_id, thread_id, identity,
                                              need_bytes=mode is not None, cancelled=cancelled)
                kind = info['kind']
                if (kind, info['name']) != (captured[identity]['kind'], captured[identity]['name']):
                    raise Denied('ATTACHMENT_INTEGRITY_FAILED')
                if mode is None:
                    if cancelled():
                        raise Denied('ATTACHMENT_READ_CANCELLED')
                    inputs.append(info)
                    action = 'Comprobar la identidad de la captura'
                    note(action+' · '+info['name'], len(inputs))
                    steps.append(dict(at=time.time(), duration_ms=round((time.monotonic()-started)*1000),
                                      actor='Lector local', action=action, detail=info['name'],
                                      status='ok', attachment_id=identity))
                    continue
                action = 'Contar las páginas del PDF' if mode == 'page_count' else ACTIONS.get(kind, 'Inspeccionar el archivo local')
                note(action+' · '+info['name'], len(inputs))
                view = (stamp_view(info, data) if kind == 'identity' else
                        decode(kind, data, page=1, member='', mode=mode, cancelled=cancelled,
                               deadline=min(deadline, time.monotonic() + 7)))
                if cancelled():
                    raise Denied('ATTACHMENT_READ_CANCELLED')
                inputs.append(dict(info, status=view['status'], detail=view['detail']))
                views[identity] = view
                steps.append(dict(at=time.time(), duration_ms=round((time.monotonic()-started)*1000),
                                  actor='Lector local', action=action, detail=view['detail'],
                                  status=view['status'], attachment_id=identity))
                if kind == 'html' and view['status'] == 'ok':
                    lines = data.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n').split('\n')
                    html_results[identity] = dict(rule='static_html', status='observed', title='Comprobación HTML',
                                         detail=f"{view['findings_total']} hallazgos en las cuatro comprobaciones locales.",
                                         sources=[dict(attachment_id=identity, name=info['name'], sha256=info['sha256'],
                                                       kind=kind, line=row['line'], column=row['column'], code=row['code'],
                                                       quote=lines[row['line']-1][max(0, row['column']-25):row['column']+130])
                                                  for row in view['findings'][:24]], total=view['findings_total'])
                    del lines
                del data
            note('Contrastando las lecturas con el encargo', len(inputs))
            # Freeze the current human revision only after native readers have
            # finished. No decoder or network operation runs inside the write transaction.
            db.execute('BEGIN IMMEDIATE')
            for request in tasks:
                started = time.monotonic()
                task = request.action
                sources = [f for f in inputs if f['id'] in request.sources]
                guard = None
                if not request.limit and request.modifier=='if_contains':
                    test, = literal_findings(request.phrase,sources,views)
                    if not any(c['quote'] for c in test['sources']):
                        established = test['status']=='observed'
                        guard = dict(rule='condition',status=test['status'],
                                     title='La condición no se cumple' if established else 'Condición pendiente de comprobar',
                                     detail=f'La operación depende de encontrar «{request.phrase}». '+test['detail'],
                                     sources=test['sources'])
                if task == 'text_brief':
                    answers = [dict(rule='text_brief', status='observed', title='Encargo guardado en este hilo',
                                    detail='Puedes pedir al modelo local que responda con este texto o añadir archivos para una comprobación.',
                                    sources=[])]
                elif request.limit or task == 'clarify':
                    answers = [unsupported(request, sources)]
                elif guard is not None:
                    answers = [guard]
                elif request.modifier=='pages_containing':
                    pdfs=[f for f in sources if f['kind']=='pdf']
                    answers = literal_findings(request.phrase,pdfs,views,modifier='pages_containing') if pdfs else [unsupported(request,sources)]
                elif task == 'literal':
                    answers = literal_findings(request.phrase, sources, views, modifier=request.modifier)
                elif task == 'hours':
                    answers = [comparison(sources, views)]
                elif task == 'decision':
                    answers = [self._decision_answer(db, project_id, thread_id, sources)]
                elif task == 'html' and any(f['id'] in html_results for f in sources):
                    answers = [html_results.get(f['id']) or reader_findings(task, [f], views)[0]
                               for f in sources if f['kind'] == 'html']
                elif task in READER_FORMATS and not any(
                    f['kind'] in READER_FORMATS[task] or
                    (task == 'syntax' and modes.get(f['id']) == 'xml_syntax') for f in sources
                ):
                    answers = [unsupported(request, sources)]
                else:
                    answers = reader_findings(task, sources, views)
                if request.explicit and task in READER_FORMATS and answers and answers[0]['rule']!='scope':
                    omitted=[f for f in sources if f['kind'] not in READER_FORMATS[task] and
                             not (task=='syntax' and modes.get(f['id'])=='xml_syntax')]
                    if omitted:
                        answers.append(unsupported(request,omitted))
                if len(tasks) > 1:
                    for answer in answers:
                        answer['request'] = request.clause
                findings.extend(answers)
                for answer in answers:
                    steps.append(dict(at=time.time(), duration_ms=round((time.monotonic()-started)*1000),
                                      actor='Director local' if task == 'text_brief' else 'Verificador local', action='Comparar el plazo de primera respuesta' if task=='hours' else answer['title'],
                                      status=answer['status'], detail=answer['detail']))
            if cancelled():
                raise Denied('ATTACHMENT_READ_CANCELLED')
            # A retry that reproduces the facts reopens the same report. A
            # previously unavailable reader can still record a corrected result.
            identity = report_identity(RULE_VERSION, project_id, thread_id, objective, inputs, findings)
            old = recover_report(db, project_id, thread_id, identity)
            if old is None:
                old = matching_legacy_report(db, project_id, thread_id, objective, inputs, findings)
            if cancelled():
                raise Denied('ATTACHMENT_READ_CANCELLED')
            if old:
                record = with_decision(db, old)
                db.commit()
                return record
            if db.execute('SELECT COUNT(*) FROM reports WHERE project=?', (project_id,)).fetchone()[0] >= 300:
                raise Denied('ATTACHMENT_STORAGE_LIMIT')
            report = dict(id=identity, project_id=project_id, thread_id=thread_id, objective=objective,
                          created_at=created, completed_at=time.time(), rule_version=RULE_VERSION, attachments=inputs,
                          findings=findings, steps=steps, reservations=0, model_calls=0)
            if any(f['rule'] not in ('scope', 'greeting', 'text_brief') for f in findings):
                report['team'] = review_with_team(objective, inputs, findings, checks, cancelled, progress=note)
            report['completed_at'] = time.time()
            payload = canonical(report)
            if len(payload.encode('utf-8')) > MAX_REPORT:
                raise Denied('ATTACHMENT_REPORT_LIMIT')
            if cancelled():
                raise Denied('ATTACHMENT_READ_CANCELLED')
            db.execute('INSERT INTO reports VALUES(?,?,?,?,?,?,?,?,?)',
                       (identity, project_id, thread_id, created, objective, len(inputs), len(findings), payload, digest(payload)))
            db.commit()
            return report

    def _decision_answer(self, db, project, thread, inputs):
        # Keep the original selection. Additional images or other unrelated types
        # can coexist with the decision, but a second PDF/JSON may change the comparison.
        sources = {item['id'] for item in inputs}
        compared_types = {item['id'] for item in inputs if item['kind'] in ('pdf', 'json')}
        rows = db.execute("""SELECT d.report,d.revision,d.choice FROM decisions d
            WHERE d.project=? AND d.thread=? AND d.revision=(
            SELECT MAX(r.revision) FROM decisions r WHERE r.project=d.project AND r.thread=d.thread AND r.report=d.report)
            ORDER BY d.at DESC,d.report""",(project,thread))
        for row in rows:
            record = recover_report(db, project, thread, row['report'])
            if not record:
                continue
            original = {item['id'] for item in record['attachments']}
            if not (compared_types <= original <= sources):
                continue
            finding = next(f for f in record['findings'] if f['rule']=='first_response_hours' and f['status']=='mismatch')
            selected = next((s for s in finding['sources'] if s['kind']==row['choice']), None)
            return dict(rule='thread_decision', status='observed', origin_report=row['report'],
                        title=(f"Se eligieron {selected['value']} h" if selected else 'La decisión se aplazó'),
                        detail=(f"Elección guardada en este hilo · revisión {row['revision']}. "
                                + (f"Fuente elegida: {selected['name']}." if selected else 'El plazo queda pendiente.')),
                        sources=[selected] if selected else [])
        return dict(rule='thread_decision',status='insufficient',title='Todavía no hay una decisión para esta selección',
                    detail='Abre el hallazgo del hilo para elegir una fuente o aplazar la decisión.',sources=[])

    def decide(self, project_id, thread_id, report_id, choice, expected_revision):
        scope(project_id, thread_id)
        if choice not in ('pdf', 'json', 'defer') or not valid('revision', expected_revision):
            raise Denied('DESKTOP_PARAMETER_INVALID')
        office, _ = self._authority(project_id)
        with self._db(office) as db:
            db.execute('BEGIN IMMEDIATE')
            report = recover_report(db, project_id, thread_id, report_id)
            if not report:
                raise Denied('ATTACHMENT_REPORT_NOT_FOUND')
            if not any(f['rule']=='first_response_hours' and f['status']=='mismatch' for f in report['findings']):
                raise Denied('DECISION_NOT_APPLICABLE')
            previous = db.execute("""SELECT revision,choice,at FROM decisions WHERE project=? AND thread=?
                AND report=? ORDER BY revision DESC LIMIT 1""", (project_id, thread_id, report_id)).fetchone()
            revision = previous['revision'] if previous else 0
            if previous and previous['choice']==choice and expected_revision in (revision-1,revision):
                return dict(previous)
            if expected_revision != revision:
                raise Denied('DECISION_CHANGED')
            at = time.time()
            db.execute('INSERT INTO decisions VALUES(?,?,?,?,?,?)',
                       (project_id, thread_id, report_id, revision+1, choice, at))
            db.commit()
            return dict(revision=revision+1, choice=choice, at=at)

    def search(self, project_id, query):
        return self.search_page(project_id, query, '')['items']

    def search_page(self, project_id, query, before):
        from .inspection_plan import fold
        scope(project_id, 'main')
        office, root = self._authority(project_id)
        needle = fold(query.strip())
        if not root or not needle:
            if before:
                raise Denied('SEARCH_CURSOR_INVALID')
            return {'items': [], 'next_before': ''}
        with self._db(office) as db:
            sql = 'SELECT id,thread AS thread_id,objective FROM reports WHERE project=?'
            args = [project_id]
            if before:
                pivot = db.execute('SELECT created_at,objective,rowid FROM reports WHERE project=? AND id=?',
                                   (project_id, before)).fetchone()
                if not pivot or needle not in fold(pivot['objective']):
                    raise Denied('SEARCH_CURSOR_INVALID')
                sql += ' AND (created_at<? OR (created_at=? AND rowid<?))'
                args.extend((pivot['created_at'], pivot['created_at'], pivot['rowid']))
            rows = db.execute(sql + ' ORDER BY created_at DESC,rowid DESC', args)
            items = []
            for row in rows:
                if needle in fold(row['objective']):
                    if len(items) == 30:
                        return {'items': items, 'next_before': items[-1]['id']}
                    items.append(dict(row))
            return {'items': items, 'next_before': ''}

    def history(self, project_id, *, thread_id='main'):
        scope(project_id, thread_id)
        office, root = self._authority(project_id)
        if root is None:
            return []
        with self._db(office) as db:
            rows = db.execute('''SELECT id,project AS project_id,thread AS thread_id,objective,created_at,
                attachment_count,finding_count FROM reports WHERE project=? AND thread=? ORDER BY created_at DESC,rowid DESC''',
                              (project_id, thread_id))
            return [dict(row) for row in rows]

    def report(self, project_id, report_id, *, thread_id='main'):
        scope(project_id, thread_id)
        office, _ = self._authority(project_id)
        with self._db(office) as db:
            record = recover_report(db, project_id, thread_id, report_id)
            if record is None:
                raise Denied('ATTACHMENT_REPORT_NOT_FOUND')
            return with_decision(db, record)

    def threads(self, project_id):
        scope(project_id, 'main')
        office, root = self._authority(project_id)
        if root is None:
            return []
        with self._db(office) as db:
            rows = db.execute('''WITH seen AS (
                SELECT thread, created_at FROM captures WHERE project=?
                UNION ALL SELECT thread, created_at FROM reports WHERE project=?
                UNION ALL SELECT thread, at FROM decisions WHERE project=?)
                SELECT thread AS id, MAX(created_at) AS created_at,
                    COALESCE((SELECT objective FROM reports r WHERE r.project=? AND r.thread=s.thread
                              AND length(trim(r.objective))>0 ORDER BY r.created_at,r.rowid LIMIT 1),
                             (SELECT CASE WHEN COUNT(*)=1 THEN MAX(name) ELSE printf('Revisión de %d archivos', COUNT(*)) END
                              FROM captures c WHERE c.project=? AND c.thread=s.thread)) AS objective
                FROM seen s GROUP BY thread ORDER BY created_at DESC,id''',
                              (project_id, project_id, project_id, project_id, project_id))
            return [dict(row) for row in rows]
