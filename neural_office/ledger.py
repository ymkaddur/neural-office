"""Durable authority for the V5.2 pilot. No model output grants authority."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import unicodedata
import uuid

TERMINAL = {'ACCEPTED', 'REJECTED', 'FAILED', 'CANCELLED'}
STATES = TERMINAL | {'QUEUED', 'RUNNING', 'VERIFYING', 'STOPPING', 'RECOVERY_REQUIRED'}
APPLICATION_ID = 0x4E4F3532
MAX_CALLS = 12
READABLE_SCHEMAS = (2, 3)
OFFICE_MODE = 'office-local-v2'
# Only these operational reasons may be persisted in a public-facing receipt.
EXECUTION_CODES = frozenset({
    'BACKEND_CANCELLED_BEFORE_START', 'BACKEND_COMPLETION_UNPROVEN',
    'BACKEND_LISTENER_AMBIGUOUS', 'BACKEND_LISTENER_OWNER_UNKNOWN',
    'BACKEND_NOT_OWNED_BY_OFFICE', 'BACKEND_PROCESS_UNAVAILABLE',
    'BACKEND_RESPONSE_REJECTED', 'BACKEND_STILL_ACTIVE', 'CLOUD_MODEL_EXCLUDED',
    'CONTEXT_ALLOCATION_MISMATCH', 'CPU_ALLOCATION_NOT_OBSERVED', 'INSTALL_OLLAMA_FIRST',
    'LOCAL_MODEL_NOT_FOUND', 'METADATA_UNAVAILABLE', 'MODEL_METADATA_UNAVAILABLE', 'MODEL_ALLOCATION_NOT_OBSERVED',
    'MODEL_DIGEST_CHANGED', 'MODEL_PROFILE_MISMATCH', 'OWNED_BACKEND_START_FAILED',
    'OWNED_BACKEND_START_TIMEOUT', 'PILOT_FINDINGS_LIMIT', 'PROMPT_BYTE_BUDGET',
    'ROLE_PROFILE_CHANGED', 'MONOTONIC_ATTEMPT_DEADLINE', 'ATTEMPT_INTERRUPTED',
    'CLOCK_OR_ATTEMPT_DEADLINE', 'AUTHORITY_REVOKED', 'AUTHORITY_REVOKED_OR_CANCELLED', 'CALL_BUDGET_EXHAUSTED',
})


class Denied(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode('utf-8') if isinstance(value, str) else value).hexdigest()


def default_state():
    return Path(os.environ.get('LOCALAPPDATA', Path.home()/'.local/share'))/'NeuralOffice'/'v52.sqlite3'


class Ledger:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else default_state()

    @contextmanager
    def connection(self):
        from .continuity import guard
        with guard(self.path):
            with self._connection() as con:
                yield con

    @contextmanager
    def _connection(self):
        if not self.path.is_file() or self.path.is_symlink():
            raise Denied('STATE_NOT_INITIALIZED_OR_UNSAFE')
        con = sqlite3.connect(self.path.resolve().as_uri()+'?mode=rw', uri=True,
                              timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        try:
            con.execute('PRAGMA foreign_keys=ON')
            con.execute('PRAGMA busy_timeout=10000')
            if con.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID:
                raise Denied('FOREIGN_STATE')
            from .continuity import attach, validate
            if con.execute('PRAGMA user_version').fetchone()[0] not in READABLE_SCHEMAS:
                raise Denied('CONTINUITY_UPGRADE_REQUIRED_RUN_PROTECT')
            attach(con, self.path)
            validate(con)
            yield con
        finally:
            con.close()

    @contextmanager
    def transaction(self, *, seal_unchanged=True):
        from .legacy import held_sources
        with self.connection() as con, held_sources():
            con.execute('BEGIN IMMEDIATE')
            try:
                before = con.total_changes
                yield con
                from .continuity import seal
                if seal_unchanged or con.total_changes != before:
                    seal(con)
                con.execute('COMMIT')
            except BaseException:
                con.rollback()
                raise

    def initialize(self):
        from .continuity import guard
        with guard(self.path):
            self._initialize()

    def _initialize(self):
        from .continuity import protect, witness_path
        if self.path.exists():
            with self.connection() as con:
                if con.execute('PRAGMA user_version').fetchone()[0] not in READABLE_SCHEMAS:
                    raise Denied('SCHEMA_VERSION')
            return
        if witness_path(self.path).exists():
            raise Denied('CONTINUITY_DIVERGENCE_RESTORE_REQUIRED')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.parent.is_symlink() or self.path.is_symlink():
            raise Denied('STATE_PATH_UNSAFE')
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise Denied('INITIALIZATION_CONFLICT') from None
        os.close(fd)
        con = sqlite3.connect(self.path, isolation_level=None)
        try:
            con.executescript('''
            BEGIN IMMEDIATE;
            PRAGMA application_id=0x4E4F3532;
            PRAGMA user_version=1;
            CREATE TABLE projects(id TEXT PRIMARY KEY, root TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0,1)),
                approved INTEGER NOT NULL DEFAULT 0 CHECK(approved IN (0,1)));
            CREATE TABLE attempts(id TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES projects(id),
                ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 1 AND 3),
                request_key TEXT NOT NULL, request_digest TEXT NOT NULL,
                objective TEXT NOT NULL, profile TEXT NOT NULL, snapshot BLOB NOT NULL,
                snapshot_sha TEXT NOT NULL, state TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0,
                cancelled INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, last_seen REAL NOT NULL,
                artifact BLOB, artifact_sha TEXT, verdict TEXT,
                UNIQUE(project,ordinal), UNIQUE(project,request_key),
                CHECK(state IN ('QUEUED','RUNNING','VERIFYING','STOPPING','RECOVERY_REQUIRED',
                                'ACCEPTED','REJECTED','FAILED','CANCELLED')));
            CREATE UNIQUE INDEX one_pending ON attempts(project)
                WHERE state NOT IN ('ACCEPTED','REJECTED','FAILED','CANCELLED');
            CREATE TABLE lease(id INTEGER PRIMARY KEY CHECK(id=1), attempt TEXT,
                generation INTEGER NOT NULL, job TEXT);
            INSERT INTO lease VALUES(1,NULL,0,NULL);
            CREATE TABLE calls(seq INTEGER PRIMARY KEY AUTOINCREMENT, attempt TEXT NOT NULL REFERENCES attempts(id),
                role TEXT NOT NULL, request_key TEXT NOT NULL, payload_sha TEXT NOT NULL,
                state TEXT NOT NULL, response TEXT, UNIQUE(attempt,request_key));
            CREATE TABLE outputs(attempt TEXT NOT NULL REFERENCES attempts(id), role TEXT NOT NULL,
                content TEXT NOT NULL, content_sha TEXT NOT NULL, PRIMARY KEY(attempt,role));
            CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT, stamp_ns INTEGER NOT NULL,
                kind TEXT NOT NULL, payload TEXT NOT NULL, previous TEXT NOT NULL, digest TEXT NOT NULL);
            COMMIT;
            ''')
        finally:
            con.close()
        protect(self)

    def _event(self, con, kind, payload):
        last = con.execute('SELECT digest FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        previous = last[0] if last else '0'*64
        stamp, body = time.time_ns(), canonical(payload)
        hash_value = digest(canonical([previous, stamp, kind, body]))
        con.execute('INSERT INTO events(stamp_ns,kind,payload,previous,digest) VALUES(?,?,?,?,?)',
                    (stamp, kind, body, previous, hash_value))

    @staticmethod
    def unbound_root(project):
        # No absolute filesystem path can equal this namespace. Each project
        # keeps its own UNIQUE slot until its first native file selection.
        return 'neural-office:unbound:' + digest(project)

    @staticmethod
    def _check_new_name(con, project):
        def normalized(name):
            return unicodedata.normalize('NFC', name.strip())
        if not project.strip() or project != normalized(project) or any(unicodedata.category(char)=='Cc' for char in project):
            raise Denied('PROJECT_NAME_NORMALIZATION_REQUIRED')
        if any(normalized(row[0]) == project for row in con.execute('SELECT id FROM projects')):
            raise Denied('PROJECT_NAME_CONFLICT')

    def register_text(self, project):
        if not isinstance(project, str) or not project or len(project) > 80:
            raise Denied('PROJECT_ID_INVALID')
        with self.transaction(seal_unchanged=False) as con:
            if con.execute('SELECT 1 FROM projects WHERE id=?', (project,)).fetchone():
                return
            self._check_new_name(con, project)
            con.execute('INSERT INTO projects(id,root) VALUES(?,?)', (project, self.unbound_root(project)))
            self._event(con, 'PROJECT_REGISTERED', {'project': project})

    def register(self, project, root):
        if not isinstance(project, str) or not project or len(project)>80:
            raise Denied('PROJECT_ID_INVALID')
        root = Path(root).resolve(strict=True)
        if not root.is_dir(): raise Denied('PROJECT_ROOT_NOT_DIRECTORY')
        root = os.path.normcase(str(root))
        with self.transaction(seal_unchanged=False) as con:
            from .legacy import require_reconciliation
            require_reconciliation(con, project, root)
            old = con.execute('SELECT root FROM projects WHERE id=?', (project,)).fetchone()
            if old:
                if old[0] == self.unbound_root(project):
                    con.execute('UPDATE projects SET root=? WHERE id=?', (root, project))
                    self._event(con, 'PROJECT_ROOT_BOUND', {'project': project})
                    return
                if os.path.normcase(old[0]) != os.path.normcase(root):
                    raise Denied('PROJECT_ROOT_CHANGED')
                return
            self._check_new_name(con, project)
            con.execute('INSERT INTO projects(id,root) VALUES(?,?)', (project,root))
            self._event(con, 'PROJECT_REGISTERED', {'project':project})

    def activate(self, project):
        with self.transaction() as con:
            self._activate(con,project)

    def _activate(self, con, project):
        from .legacy import check_authority, inherited_consumption
        check_authority(con, project)
        row = con.execute('SELECT * FROM projects WHERE id=?', (project,)).fetchone()
        if row is None:
            raise Denied('UNKNOWN_PROJECT')
        count = inherited_consumption(con, project) + con.execute('SELECT count(*) FROM attempts WHERE project=?', (project,)).fetchone()[0]
        if count >= 3:
            raise Denied('ATTEMPT_BUDGET_EXHAUSTED')
        if not row['active'] and con.execute('SELECT count(*) FROM projects WHERE active=1').fetchone()[0]>=2:
            raise Denied('TWO_ACTIVE_PROJECTS_MAX')
        con.execute('UPDATE projects SET active=1,approved=1 WHERE id=?', (project,))
        self._event(con, 'USER_ACTIVATION', {'project':project})

    def revoke(self, project):
        with self.transaction() as con:
            con.execute('UPDATE projects SET approved=0 WHERE id=?', (project,))
            # A subsequent activation cannot reopen a previously revoked office permit.
            pending = con.execute("""SELECT id FROM attempts WHERE project=?
                AND state NOT IN ('ACCEPTED','REJECTED','FAILED','CANCELLED') AND json_extract(profile,'$.mode')=?""",
                                  (project, OFFICE_MODE)).fetchone()
            if pending:
                self._cancel(con, pending['id'])
            self._event(con, 'USER_REVOCATION', {'project':project})

    def park(self, project):
        with self.transaction() as con:
            if con.execute("SELECT 1 FROM attempts WHERE project=? AND state NOT IN ('ACCEPTED','REJECTED','FAILED','CANCELLED')", (project,)).fetchone():
                raise Denied('UNRESOLVED_ATTEMPT')
            con.execute('UPDATE projects SET active=0,approved=0 WHERE id=?', (project,))
            self._event(con, 'PROJECT_PARKED', {'project':project})

    def reserve(self, project, objective, snapshot, profile, key, *, admit=False, source_name=None):
        if type(snapshot) is not bytes or not 0<len(snapshot)<=262144:
            raise Denied('SNAPSHOT_SIZE')
        from .excerpt_review import TEXT_SCOPE
        minimum = 1 if profile.get('analysis_scope') == TEXT_SCOPE else 12
        if not isinstance(objective,str) or not minimum<=len(objective)<=4000 or (minimum == 1 and not objective.strip()):
            raise Denied('OBJECTIVE_SIZE')
        if not isinstance(key,str) or not 1<=len(key)<=128:
            raise Denied('IDEMPOTENCY_KEY')
        if source_name is not None and (not isinstance(source_name, str) or not 0 < len(source_name) <= 255
                                        or any(c in source_name for c in '/\\\\:') or not source_name.isprintable()):
            source_name = None
        signature = digest(canonical([objective,digest(snapshot),profile]))
        with self.transaction(seal_unchanged=False) as con:
            old = con.execute('SELECT id,request_digest FROM attempts WHERE project=? AND request_key=?', (project,key)).fetchone()
            if old:
                if old['request_digest']!=signature:
                    raise Denied('IDEMPOTENCY_CONFLICT')
                return old['id']
            if admit: self._activate(con,project)
            authority = con.execute('SELECT active,approved FROM projects WHERE id=?', (project,)).fetchone()
            if authority is None or tuple(authority)!=(1,1):
                raise Denied('USER_AUTHORITY_REQUIRED')
            from .legacy import check_authority, inherited_consumption
            check_authority(con, project)
            count = inherited_consumption(con, project) + con.execute('SELECT count(*) FROM attempts WHERE project=?', (project,)).fetchone()[0]
            if count>=3:
                raise Denied('ATTEMPT_BUDGET_EXHAUSTED')
            if con.execute("SELECT 1 FROM attempts WHERE project=? AND state NOT IN ('ACCEPTED','REJECTED','FAILED','CANCELLED')", (project,)).fetchone():
                raise Denied('UNRESOLVED_ATTEMPT')
            if profile.get('mode') == OFFICE_MODE:
                from .office_protocol import validate_permit, install_schema
                validate_permit(profile, snapshot)
                install_schema(con)
            else:
                from .runner import check_first_prompt
                check_first_prompt(snapshot, objective, profile)
            stored_profile = dict(profile)
            stored_profile.pop('requested_rule',None)
            if profile.get('mode') != OFFICE_MODE and not profile.get('analysis_scope'):
                from .audit import requested_rule
                rule = requested_rule(objective)
                if rule is not None:
                    stored_profile['requested_rule'] = rule
            attempt, stamp = uuid.uuid4().hex, time.time()
            con.execute('''INSERT INTO attempts(id,project,ordinal,request_key,request_digest,objective,
                profile,snapshot,snapshot_sha,state,created,last_seen) VALUES(?,?,?,?,?,?,?,?,?,'QUEUED',?,?)''',
                (attempt,project,count+1,key,signature,objective,canonical(stored_profile),snapshot,digest(snapshot),stamp,stamp))
            receipt = {'attempt': attempt, 'project': project, 'ordinal': count+1}
            if source_name is not None:
                receipt['source_name'] = source_name
            self._event(con, 'ATTEMPT_RESERVED', receipt)
            return attempt

    def _row(self, con, attempt):
        row = con.execute('SELECT * FROM attempts WHERE id=?', (attempt,)).fetchone()
        if row is None:
            raise Denied('UNKNOWN_ATTEMPT')
        return row

    def _pilot_row(self, con, attempt):
        row = self._row(con, attempt)
        if json.loads(row['profile']).get('mode') == OFFICE_MODE:
            raise Denied('OFFICE_PROTOCOL_REQUIRED')
        return row

    def _check_authorized(self, con, row):
        from .legacy import check_authority
        check_authority(con, row['project'])
        authority = con.execute('SELECT active,approved FROM projects WHERE id=?',(row['project'],)).fetchone()
        if tuple(authority)!=(1,1) or row['cancelled']:
            raise Denied('AUTHORITY_REVOKED_OR_CANCELLED')
        now = time.time()
        if now < row['last_seen'] or now-row['created']>3600:
            raise Denied('CLOCK_OR_ATTEMPT_DEADLINE')
        return now

    def _authorized(self, con, row):
        stamp = self._check_authorized(con, row)
        con.execute('UPDATE attempts SET last_seen=? WHERE id=?',(stamp,row['id']))

    def interruption_reason(self, attempt):
        """Read-only in-flight check; revocation must reach an already admitted call."""
        with self.connection() as con:
            row=self._row(con,attempt)
            from .legacy import held_sources, check_authority
            try:
                with held_sources(): check_authority(con, row['project'])
            except (Denied,OSError,sqlite3.Error) as exc:
                return 'LEGACY_AUTHORITY_UNAVAILABLE:' + type(exc).__name__
            authority=con.execute('SELECT active,approved FROM projects WHERE id=?',(row['project'],)).fetchone()
            if row['cancelled']: return 'CANCELLED'
            if tuple(authority)!=(1,1): return 'AUTHORITY_REVOKED'
            now=time.time()
            if now<row['last_seen'] or now-row['created']>3600: return 'CLOCK_OR_ATTEMPT_DEADLINE'
        return None

    def acquire(self, attempt, job):
        with self.transaction() as con:
            row = self._pilot_row(con, attempt)
            self._authorized(con,row)
            if row['state']!='QUEUED':
                raise Denied('NOT_QUEUED')
            lease = con.execute('SELECT * FROM lease').fetchone()
            if lease['attempt'] is not None:
                raise Denied('GLOBAL_INFERENCE_BUSY')
            generation = lease['generation']+1
            con.execute('UPDATE lease SET attempt=?,generation=?,job=? WHERE id=1',(attempt,generation,job))
            con.execute("UPDATE attempts SET state='RUNNING',revision=revision+1 WHERE id=?",(attempt,))
            self._event(con,'LEASE_ACQUIRED',{'attempt':attempt,'generation':generation,'job':job})
            return generation

    def start_call(self, attempt, generation, role, payload, key):
        signature = digest(canonical(payload))
        with self.transaction() as con:
            row = self._pilot_row(con,attempt)
            self._authorized(con,row)
            lease = con.execute('SELECT * FROM lease').fetchone()
            if (lease['attempt'],lease['generation'])!=(attempt,generation) or row['state']!='RUNNING':
                raise Denied('STALE_LEASE_OR_STATE')
            old = con.execute('SELECT * FROM calls WHERE attempt=? AND request_key=?',(attempt,key)).fetchone()
            if old:
                if old['payload_sha']!=signature or old['role']!=role:
                    raise Denied('IDEMPOTENCY_CONFLICT')
                if old['state']!='DONE':
                    raise Denied('CALL_RESULT_UNRESOLVED')
                return old['seq'], json.loads(old['response'])
            if con.execute("SELECT 1 FROM calls WHERE attempt=? AND state='STARTED'",(attempt,)).fetchone():
                raise Denied('CALL_ALREADY_RUNNING')
            if con.execute('SELECT count(*) FROM calls WHERE attempt=?',(attempt,)).fetchone()[0]>=MAX_CALLS:
                raise Denied('CALL_BUDGET_EXHAUSTED')
            cur = con.execute("INSERT INTO calls(attempt,role,request_key,payload_sha,state) VALUES(?,?,?,?,'STARTED')",(attempt,role,key,signature))
            self._event(con,'MODEL_CALL_ADMITTED',{'attempt':attempt,'call':cur.lastrowid,'role':role,'payload_sha':signature})
            return cur.lastrowid, None

    def finish_call(self, attempt, generation, seq, response):
        if type(response) is not dict or response.get('done') is not True:
            raise Denied('INCOMPLETE_MODEL_RESPONSE')
        message=response.get('message')
        if type(message) is not dict or type(message.get('content')) is not str or not message['content'].strip():
            raise Denied('EMPTY_MODEL_OUTPUT')
        encoded = canonical(response)
        if len(encoded.encode('utf-8'))>1048576:
            raise Denied('RESPONSE_TOO_LARGE')
        with self.transaction() as con:
            self._pilot_row(con, attempt)
            lease = con.execute('SELECT * FROM lease').fetchone()
            call = con.execute('SELECT * FROM calls WHERE seq=? AND attempt=?',(seq,attempt)).fetchone()
            if (lease['attempt'],lease['generation'])!=(attempt,generation) or call is None:
                raise Denied('STALE_LEASE')
            if call['state']=='DONE':
                if call['response']!=encoded:
                    raise Denied('RESULT_CONFLICT')
                return
            if call['state']!='STARTED':
                raise Denied('CALL_STATE_CONFLICT')
            con.execute("UPDATE calls SET state='DONE',response=? WHERE seq=?",(encoded,seq))
            content = response['message']['content']
            if not isinstance(content,str) or not content.strip():
                raise Denied('EMPTY_MODEL_OUTPUT')
            con.execute('INSERT INTO outputs VALUES(?,?,?,?)',(attempt,call['role'],content,digest(content)))
            self._event(con,'MODEL_CALL_COMPLETED',{'attempt':attempt,'call':seq,'content_sha':digest(content)})

    def cancel(self, attempt):
        with self.transaction(seal_unchanged=False) as con:
            return self._cancel(con, attempt)

    def _cancel(self, con, attempt):
        row = self._row(con,attempt)
        if row['state'] in TERMINAL or row['cancelled']:
            return row['state']
        lease = con.execute('SELECT attempt FROM lease').fetchone()[0]
        state = 'STOPPING' if lease==attempt else 'CANCELLED'
        con.execute('UPDATE attempts SET state=?,cancelled=1,revision=revision+1 WHERE id=?',(state,attempt))
        if state == 'CANCELLED' and json.loads(row['profile']).get('mode') == OFFICE_MODE:
            con.execute("UPDATE office_transports SET state='CANCELLED' WHERE attempt=? AND state='PREPARED'", (attempt,))
        self._event(con,'CANCELLATION_REQUESTED',{'attempt':attempt,'state':state})
        if state=='CANCELLED': self._park_exhausted(con,row['project'])
        return state

    def release_completed_team(self, attempt, generation):
        """Retain a session-owned runtime only after all seven authorized responses are durable."""
        from .ollama import POLISHED_TEAM, TEAM_POLICY
        from .runner import ROLES
        with self.transaction(seal_unchanged=False) as con:
            row = self._pilot_row(con, attempt)
            profile = json.loads(row['profile'])
            lease = con.execute('SELECT attempt,generation,job FROM lease').fetchone()
            if (lease['attempt'], lease['generation']) != (attempt, generation):
                raise Denied('STALE_LEASE')
            if (profile.get('team_session') != POLISHED_TEAM or profile.get('execution_policy') != TEAM_POLICY
                    or profile.get('mode') != 'ollama-owned' or profile.get('analysis_scope') or profile.get('roles') != len(ROLES)
                    or row['state'] != 'RUNNING' or row['cancelled'] or row['ordinal'] >= 3):
                return False
            self._check_authorized(con, row)
            calls = con.execute("""SELECT role,state,
                json_extract(response,'$._neural_office_execution.runtime_instance') AS runtime,
                json_extract(response,'$._neural_office_execution.model_digest') AS model,
                json_extract(response,'$._neural_office_execution.owned_job') AS owned,
                json_extract(response,'$._neural_office_execution.eval_count') AS tokens
                FROM calls WHERE attempt=? ORDER BY seq""", (attempt,)).fetchall()
            if ([c['role'] for c in calls] != list(ROLES) or any(c['state'] != 'DONE' or c['runtime'] != lease['job']
                    or c['model'] != profile['model_digest'] or c['owned'] != 1 or type(c['tokens']) is not int
                    or c['tokens'] < 1 for c in calls)):
                return False
            con.execute("UPDATE attempts SET state='VERIFYING',revision=revision+1 WHERE id=?", (attempt,))
            con.execute('UPDATE lease SET attempt=NULL,job=NULL WHERE id=1')
            self._event(con, 'TEAM_RUNTIME_IDLE', {'attempt':attempt,'generation':generation,'state':'VERIFYING'})
            return True

    def release_after_termination(self, attempt, generation, *, failed=False, error_code=None):
        """Trusted runner invokes this only after owned OS job termination is observed."""
        with self.transaction() as con:
            row = self._pilot_row(con,attempt)
            lease = con.execute('SELECT * FROM lease').fetchone()
            if (lease['attempt'],lease['generation'])!=(attempt,generation):
                raise Denied('STALE_LEASE')
            unfinished = con.execute("SELECT 1 FROM calls WHERE attempt=? AND state='STARTED'",(attempt,)).fetchone()
            con.execute("UPDATE calls SET state='INTERRUPTED' WHERE attempt=? AND state='STARTED'",(attempt,))
            state = 'CANCELLED' if row['cancelled'] else ('FAILED' if failed or unfinished else 'VERIFYING')
            con.execute('UPDATE attempts SET state=?,revision=revision+1 WHERE id=?',(state,attempt))
            con.execute('UPDATE lease SET attempt=NULL,job=NULL WHERE id=1')
            receipt = {'attempt':attempt,'generation':generation,'state':state}
            if state == 'FAILED':
                receipt['error_code'] = error_code if error_code in EXECUTION_CODES else 'EXECUTION_FAILED'
            self._event(con,'OWNED_JOB_TERMINATED',receipt)
            if state in TERMINAL: self._park_exhausted(con,row['project'])

    def mark_unknown(self, attempt, generation):
        with self.transaction() as con:
            self._pilot_row(con, attempt)
            lease = con.execute('SELECT * FROM lease').fetchone()
            if (lease['attempt'],lease['generation'])!=(attempt,generation):
                raise Denied('STALE_LEASE')
            con.execute("UPDATE attempts SET state='RECOVERY_REQUIRED',revision=revision+1 WHERE id=?",(attempt,))
            self._event(con,'TERMINATION_UNKNOWN',{'attempt':attempt,'generation':generation})

    def _park_exhausted(self, con, project):
        from .legacy import inherited_consumption
        if inherited_consumption(con,project)+con.execute('SELECT count(*) FROM attempts WHERE project=?',(project,)).fetchone()[0]>=3:
            con.execute('UPDATE projects SET active=0,approved=0 WHERE id=?',(project,))
            self._event(con,'BUDGET_PARKED',{'project':project})

    def finalize(self, attempt, artifact):
        from .audit import verify_report
        from . import excerpt_review
        if type(artifact) is not bytes or not 0<len(artifact)<=4_194_304:
            raise Denied('ARTIFACT_SIZE_OR_TYPE')
        with self.transaction() as con:
            row = self._pilot_row(con,attempt)
            if row['state'] in TERMINAL:
                if row['artifact_sha']==digest(artifact): return row['state']
                raise Denied('TERMINAL_RESULT_CONFLICT')
            self._authorized(con,row)
            if row['state']!='VERIFYING': raise Denied('NOT_VERIFYING')
            profile = json.loads(row['profile'])
            scope = profile.get('analysis_scope')
            if scope in excerpt_review.SCOPES:
                receipt = excerpt_review.verify_report(bytes(row['snapshot']), artifact)
                receipt['checks']['authorized_scope'] = receipt['verifier'] == scope
            else:
                receipt = verify_report(bytes(row['snapshot']), artifact, profile.get('requested_rule'))
            from .runner import role_order
            stored=[dict(r) for r in con.execute('SELECT role,content,content_sha FROM outputs WHERE attempt=? ORDER BY rowid',(attempt,))]
            try:
                received=json.loads(artifact)
                receipt['checks']['canonical_encoding']=canonical(received).encode('utf-8')==artifact
                receipt['checks']['roles_complete']=[r['role'] for r in stored]==list(role_order(json.loads(row['profile'])['roles']))
                receipt['checks']['outputs_bound_to_receipts']=received.get('role_outputs')==stored
            except (ValueError,TypeError,KeyError,AttributeError):
                receipt['checks']['outputs_bound_to_receipts']=False
            receipt['passed']=all(receipt['checks'].values())
            state = 'ACCEPTED' if receipt['passed'] else 'REJECTED'
            con.execute('UPDATE attempts SET state=?,artifact=?,artifact_sha=?,verdict=?,revision=revision+1 WHERE id=?',
                        (state,artifact,digest(artifact),canonical(receipt),attempt))
            self._event(con,'FINAL_VERDICT',{'attempt':attempt,'state':state,'artifact_sha':digest(artifact),'receipt_sha':digest(canonical(receipt))})
            self._park_exhausted(con,row['project'])
            return state

    def _verified_outputs(self, con, row):
        rows = con.execute('SELECT role,content,content_sha FROM outputs WHERE attempt=? ORDER BY rowid',
                           (row['id'],)).fetchall()
        if any(digest(item['content']) != item['content_sha'] for item in rows):
            raise Denied('OUTPUT_CHANGED')
        if digest(bytes(row['snapshot'])) != row['snapshot_sha']:
            raise Denied('SNAPSHOT_CHANGED')
        return rows

    def attempt(self, attempt):
        with self.connection() as con:
            row = dict(self._row(con,attempt))
            row['outputs'] = [dict(item) for item in self._verified_outputs(con, row)]
            row['profile'] = json.loads(row['profile'])
            return row

    def status(self):
        with self.connection() as con:
            projects=[]
            for p in con.execute('SELECT * FROM projects ORDER BY id'):
                from .legacy import inherited_consumption
                inherited = inherited_consumption(con,p['id'])
                counts=con.execute("SELECT count(*),coalesce(sum(state='ACCEPTED' AND json_extract(profile,'$.mode')!='fixture'),0),coalesce(sum(state='ACCEPTED' AND json_extract(profile,'$.mode')='fixture'),0) FROM attempts WHERE project=?",(p['id'],)).fetchone()
                projects.append({'id':p['id'],'active':bool(p['active']),'approved':bool(p['approved']),
                                 'attempts_consumed':counts[0]+inherited,'legacy_consumed':inherited,
                                 'verified_versions':counts[1],'simulated_versions':counts[2]})
            attempts=[dict(r) for r in con.execute('SELECT id,project,ordinal,state,revision FROM attempts ORDER BY created')]
            lease=dict(con.execute('SELECT * FROM lease').fetchone())
            previous='0'*64
            events=con.execute('SELECT * FROM events ORDER BY seq').fetchall()
            for e in events:
                expected=digest(canonical([previous,e['stamp_ns'],e['kind'],e['payload']]))
                if e['previous']!=previous or e['digest']!=expected: raise Denied('EVENT_CHAIN_CHANGED')
                previous=e['digest']
            return {'projects':projects,'attempts':attempts,'lease':lease,
                    'audit':{'events':len(events),'head':previous,'authenticity_proven':False}}
