"""One desktop session over the existing ledger, runner and process ownership.

No web server, shell command or frontend supplied file path is exposed. Production
uses OwnedOllama; tests may inject a clearly labelled fixture backend/catalog.
"""
import base64
import json
import os
import re
import secrets
import threading
import time

from . import continuity
from .audit import audit_html, make_report
from .desktop_contract import MAX_SAFE_INTEGER, decode_command, valid
from .files import capture_html, local_path
from .ledger import Denied, TERMINAL, canonical, digest
from .ollama import OwnedOllama, local_metadata, select_model
from .runner import MAX_MODEL_FINDINGS, _recover_owned, check_first_prompt, run

GRANT_TTL_SECONDS = 120
MAX_GRANTS = 32
MAX_MODELS = 64
ATTEMPT_COLUMNS = 'id,project,ordinal,state,revision,snapshot_sha,profile,objective,request_key'


def discover_models():
    """Read local metadata only; do not download, load or infer a model."""
    try:
        metadata = local_metadata()
    except (OSError, ValueError, TypeError):
        raise Denied('MODEL_METADATA_UNAVAILABLE') from None
    if type(metadata) is not dict or type(metadata.get('models')) is not list:
        raise Denied('MODEL_METADATA_INVALID')
    if len(metadata['models']) > MAX_MODELS * 4:
        raise Denied('MODEL_CATALOG_LIMIT')
    profiles = []
    for model in metadata['models']:
        if type(model) is not dict or type(model.get('name')) is not str:
            continue
        try:
            profiles.append(select_model(model['name'], metadata['models']))
        except Denied:
            continue
    return profiles


def public_error(error):
    """Never send exception text, source paths or model content as diagnostics."""
    if isinstance(error, Denied) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', str(error)):
        return str(error)
    return 'DESKTOP_OPERATION_FAILED'


class DesktopService:
    def __init__(self, ledger, *, backend_factory=OwnedOllama,
                 model_discovery=discover_models, clock=time.monotonic):
        self.ledger = ledger
        self.ledger.initialize()
        self.session_id = secrets.token_urlsafe(24)
        self.backend_factory = backend_factory
        self.model_discovery = model_discovery
        self.clock = clock
        self._sources = {}
        self._approvals = {}
        self._command_lock = threading.RLock()
        self._worker = None
        self._worker_attempt = None
        self._errors = {}
        self._closed = False
        self._catalog = None
        self._catalog_stale = False

    def _meta(self, con):
        office, revision = con.execute('SELECT office,revision FROM continuity_meta WHERE id=1').fetchone()
        cursor = con.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
        if max(revision, cursor) > MAX_SAFE_INTEGER:
            raise Denied('DESKTOP_COUNTER_RANGE')
        return {'office_id': office, 'session_id': self.session_id, 'revision': revision, 'cursor': cursor}

    def _project(self, con, row):
        from .legacy import inherited_consumption
        inherited = inherited_consumption(con, row['id'])
        counts = con.execute("SELECT count(*),coalesce(sum(state='ACCEPTED' AND json_extract(profile,'$.mode')!='fixture'),0),coalesce(sum(state='ACCEPTED' AND json_extract(profile,'$.mode')='fixture'),0) FROM attempts WHERE project=?", (row['id'],)).fetchone()
        return {'id': row['id'], 'active': bool(row['active']), 'approved': bool(row['approved']),
                'attempts_consumed': counts[0] + inherited, 'legacy_consumed': inherited,
                'verified_versions': counts[1], 'simulated_versions': counts[2]}

    def _summary(self, row):
        profile = json.loads(row['profile']) if type(row['profile']) is str else row['profile']
        return {'id': row['id'], 'project_id': row['project'], 'ordinal': row['ordinal'],
                'state': row['state'], 'revision': row['revision'],
                'source_sha256': row['snapshot_sha'], 'model': profile['model'],
                'model_digest': profile['model_digest'], 'roles': profile['roles'],
                'objective': row['objective'], 'mode': profile['mode'], 'request_key': row['request_key']}

    def snapshot(self, project_after=0, attempt_after=0, limit=100):
        with self.ledger.connection() as con:
            projects = con.execute('SELECT rowid AS page_id,* FROM projects WHERE rowid>? ORDER BY rowid LIMIT ?', (project_after, limit + 1)).fetchall()
            attempts = con.execute(f'SELECT rowid AS page_id,{ATTEMPT_COLUMNS} FROM attempts WHERE rowid>? ORDER BY rowid LIMIT ?', (attempt_after, limit + 1)).fetchall()
            lease = con.execute('SELECT attempt,generation FROM lease WHERE id=1').fetchone()
            if lease['attempt']:
                current = con.execute(f'SELECT {ATTEMPT_COLUMNS} FROM attempts WHERE id=?', (lease['attempt'],)).fetchone()
            else:
                current = con.execute(f"SELECT {ATTEMPT_COLUMNS} FROM attempts WHERE state NOT IN "
                                      "('ACCEPTED','REJECTED','FAILED','CANCELLED') ORDER BY rowid LIMIT 1").fetchone()
            return {**self._meta(con),
                    'current_attempt': self._summary(current) if current else None,
                    'projects': [self._project(con, row) for row in projects[:limit]],
                    'attempts': [self._summary(row) for row in attempts[:limit]],
                    'next': {'project_after': projects[min(len(projects), limit)-1]['page_id'] if projects else project_after,
                             'attempt_after': attempts[min(len(attempts), limit)-1]['page_id'] if attempts else attempt_after},
                    'has_more': {'projects': len(projects) > limit, 'attempts': len(attempts) > limit},
                    'lease': {'attempt_id': lease['attempt'], 'generation': lease['generation']}}

    def _execution_busy(self):
        if self._worker is not None and self._worker.is_alive():
            return True
        with self.ledger.connection() as con:
            return con.execute('SELECT attempt FROM lease WHERE id=1').fetchone()[0] is not None

    def models(self):
        # A slow metadata peer must not occupy this session's request reader
        # while its own execution needs a cancellation command. Refresh only
        # while idle; an already captured catalog is explicitly marked stale.
        if self._execution_busy():
            self._catalog_stale = True
            if self._catalog is None: raise Denied('MODEL_CATALOG_BUSY')
            return [dict(model) for model in self._catalog]
        profiles = self.model_discovery()
        if type(profiles) is not list:
            raise Denied('MODEL_METADATA_INVALID')
        # Aliases of the same weights are represented once, deterministically.
        catalog = {}
        for profile in profiles:
            if (type(profile) is not dict or not valid('digest', profile.get('model_digest'))
                    or type(profile.get('model')) is not str or not 0 < len(profile['model']) <= 200
                    or profile.get('mode') not in ('ollama-owned', 'fixture')):
                continue
            try: profile['model'].encode('utf-8')
            except UnicodeError: continue
            old = catalog.get(profile['model_digest'])
            if old is None or profile['model'] < old['model']:
                catalog[profile['model_digest']] = dict(profile)
        ordered = sorted(catalog.values(), key=lambda model: (model['model'], model['model_digest']))
        if len(ordered) > MAX_MODELS:
            raise Denied('MODEL_CATALOG_LIMIT')
        self._catalog = [dict(model) for model in ordered]
        self._catalog_stale = False
        return ordered

    def _prune(self):
        now = self.clock()
        for grants in (self._sources, self._approvals):
            for token in list(grants):
                if grants[token]['expires'] <= now:
                    del grants[token]

    def host_capture(self, project_id, path):
        """Trusted native picker only. Never route a webview path to this method."""
        with self._command_lock:
            if self._closed: raise Denied('DESKTOP_SESSION_CLOSED')
            if not valid('project', project_id): raise Denied('DESKTOP_PARAMETER_INVALID')
            self._prune()
            if len(self._sources) >= MAX_GRANTS: raise Denied('SOURCE_GRANT_LIMIT')
            source = local_path(path)
            captured = capture_html(source, source.parent)
            with continuity.guard(self.ledger.path):
                root = os.path.normcase(str(source.parent.resolve(strict=True)))
                with self.ledger.connection() as con:
                    old = con.execute('SELECT id FROM projects WHERE root=?', (root,)).fetchone()
                    if old is not None and old['id'] != project_id:
                        raise Denied('PROJECT_ROOT_ALREADY_REGISTERED')
                self.ledger.register(project_id, source.parent)
            token = secrets.token_urlsafe(32)
            grant = {'project_id': project_id, 'snapshot': captured, 'sha256': digest(captured),
                     'filename': source.name, 'expires': self.clock() + GRANT_TTL_SECONDS}
            self._sources[token] = grant
            return {'entry_token': token, 'project_id': project_id, 'filename': source.name,
                    'sha256': grant['sha256'], 'bytes': len(captured),
                    'expires_in_seconds': GRANT_TTL_SECONDS, 'session_id': self.session_id}

    def _source(self, project_id, entry_token):
        self._prune()
        source = self._sources.get(entry_token)
        if source is None or source['project_id'] != project_id:
            raise Denied('SOURCE_GRANT_INVALID_OR_EXPIRED')
        return source

    def check_source(self, project_id, entry_token, offset):
        source = self._source(project_id, entry_token)
        findings = audit_html(source['snapshot'])
        if offset and offset >= len(findings):
            raise Denied('FINDING_OFFSET_RANGE')
        return {'session_id': self.session_id, 'project_id': project_id, 'source_sha256': source['sha256'],
                'offset': offset, 'total': len(findings), 'findings': findings[offset:offset + MAX_MODEL_FINDINGS]}

    def preview(self, project_id, entry_token, model_digest, roles, objective):
        if self._execution_busy(): raise Denied('GLOBAL_INFERENCE_BUSY')
        source = self._source(project_id, entry_token)
        if len(objective) < 12: raise Denied('OBJECTIVE_SIZE')
        if len(self._approvals) >= MAX_GRANTS: raise Denied('APPROVAL_GRANT_LIMIT')
        matching = [model for model in self.models() if model['model_digest'] == model_digest]
        if len(matching) != 1: raise Denied('MODEL_DIGEST_UNAVAILABLE')
        profile = {**matching[0], 'roles': roles}
        check_first_prompt(source['snapshot'], objective, profile)
        with self.ledger.connection() as con:
            project = con.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
            if project is None: raise Denied('UNKNOWN_PROJECT')
            counts = self._project(con, project)
            meta = self._meta(con)
        if source['expires'] <= self.clock():
            raise Denied('SOURCE_GRANT_INVALID_OR_EXPIRED')
        token = secrets.token_urlsafe(32)
        self._approvals[token] = {'project_id': project_id, 'snapshot': source['snapshot'], 'source_name': source['filename'],
                                 'objective': objective, 'profile': profile, 'revision': meta['revision'],
                                 'expires': self.clock() + GRANT_TTL_SECONDS, 'used_key': None}
        return {**meta, 'approval_token': token, 'expected_revision': meta['revision'],
                'expires_in_seconds': GRANT_TTL_SECONDS, 'project_id': project_id,
                'source_sha256': source['sha256'], 'objective': objective, 'roles': roles,
                'model': profile['model'], 'model_digest': profile['model_digest'], 'mode': profile['mode'],
                'attempts_consumed': counts['attempts_consumed'],
                'attempts_remaining': max(0, 3-counts['attempts_consumed'])}

    def start(self, approval_token, idempotency_key, expected_revision):
        self._prune()
        approval = self._approvals.get(approval_token)
        if approval is None: raise Denied('APPROVAL_INVALID_OR_EXPIRED')
        if approval['used_key'] not in (None, idempotency_key):
            raise Denied('APPROVAL_ALREADY_USED')
        signature = digest(canonical([approval['objective'], digest(approval['snapshot']), approval['profile']]))
        # Hold the same OS mutex used by all ledger operations while checking
        # the observed revision and committing the durable reservation.
        with continuity.guard(self.ledger.path):
            if approval['expires'] <= self.clock():
                raise Denied('APPROVAL_INVALID_OR_EXPIRED')
            with self.ledger.connection() as con:
                old = con.execute('SELECT id,request_digest FROM attempts WHERE project=? AND request_key=?',
                                  (approval['project_id'], idempotency_key)).fetchone()
                if old:
                    if old['request_digest'] != signature: raise Denied('IDEMPOTENCY_CONFLICT')
                    approval['used_key'] = idempotency_key
                    return self.attempt(old['id'])
                revision = self._meta(con)['revision']
                if revision != expected_revision or expected_revision != approval['revision']:
                    raise Denied('DESKTOP_REVISION_CHANGED')
                if self._worker is not None and self._worker.is_alive():
                    raise Denied('GLOBAL_INFERENCE_BUSY')
                if con.execute('SELECT attempt FROM lease WHERE id=1').fetchone()[0] is not None:
                    raise Denied('GLOBAL_INFERENCE_BUSY')
            attempt = self.ledger.reserve(approval['project_id'], approval['objective'], approval['snapshot'],
                                          approval['profile'], idempotency_key, admit=True, source_name=approval['source_name'])
            approval['used_key'] = idempotency_key
        # Commit precedes the worker. A crash here leaves a visible QUEUED
        # attempt that recovery cancels without refund or automatic execution.
        self._launch(attempt, approval['profile']['roles'])
        return self.attempt(attempt)

    def _launch(self, attempt, roles):
        def work():
            try:
                run(self.ledger, attempt, roles, backend_factory=self.backend_factory)
            except BaseException as error:
                self._errors[attempt] = public_error(error)
        self._worker_attempt = attempt
        self._worker = threading.Thread(target=work, name='neural-office-desktop-runner', daemon=False)
        self._worker.start()

    def attempt(self, attempt_id):
        with self.ledger.connection() as con:
            row = self.ledger._row(con, attempt_id)
            # Verify source/output identity with the same core read boundary.
            self.ledger.attempt(attempt_id)
            meta = self._meta(con)
            outputs = [{'role': item['role'], 'sha256': item['content_sha'],
                        'bytes': len(item['content'].encode('utf-8'))} for item in con.execute(
                            'SELECT role,content,content_sha FROM outputs WHERE attempt=? ORDER BY rowid', (attempt_id,))]
            calls = [dict(item) for item in con.execute('SELECT seq,role,state FROM calls WHERE attempt=? ORDER BY seq', (attempt_id,))]
            reservation = con.execute("SELECT json_extract(payload,'$.source_name') FROM events "
                                      "WHERE kind='ATTEMPT_RESERVED' AND json_extract(payload,'$.attempt')=? "
                                      "ORDER BY seq LIMIT 1", (attempt_id,)).fetchone()
            code = self._errors.get(attempt_id)
            if row['state'] == 'FAILED':
                terminal_receipt = con.execute(
                    "SELECT json_extract(payload,'$.error_code') FROM events WHERE kind='OWNED_JOB_TERMINATED' "
                    "AND json_extract(payload,'$.attempt')=? ORDER BY seq DESC LIMIT 1", (attempt_id,)).fetchone()
                code = terminal_receipt[0] if terminal_receipt else None
            return {**self._summary(row), 'session_id': self.session_id, 'global_revision': meta['revision'],
                    'cursor': meta['cursor'], 'calls': calls, 'outputs': outputs,
                    'artifact_sha256': row['artifact_sha'], 'report_available': row['state'] == 'ACCEPTED' and row['artifact'] is not None,
                    'execution_error_code': code, 'source_name': reservation[0] if reservation else None}

    def lookup(self, project_id, idempotency_key):
        with self.ledger.connection() as con:
            row = con.execute('SELECT id FROM attempts WHERE project=? AND request_key=?', (project_id, idempotency_key)).fetchone()
            return {'found': row is not None, 'attempt': self.attempt(row['id']) if row else None,
                    **self._meta(con)}

    def cancel(self, attempt_id):
        self.ledger.cancel(attempt_id)
        return self.attempt(attempt_id)

    def recover(self, attempt_id, expected_revision):
        # Lock order must match run(): RunOwner before Continuity. A queued
        # controller can still launch, even if no OS child is visible yet.
        with self.ledger.connection() as con:
            row = self.ledger._row(con, attempt_id)
            if row['state'] in TERMINAL:
                return self.attempt(attempt_id)
        if self._worker is not None and self._worker.is_alive():
            raise Denied('OFFICE_RUNNER_STILL_ACTIVE')
        with continuity.run_guard(self.ledger.path):
            with continuity.guard(self.ledger.path):
                with self.ledger.connection() as con:
                    row = self.ledger._row(con, attempt_id)
                    if row['revision'] != expected_revision: raise Denied('DESKTOP_REVISION_CHANGED')
                    state = row['state']
                if state in TERMINAL:
                    return self.attempt(attempt_id)
                if state == 'QUEUED':
                    self.ledger.cancel(attempt_id)
                elif state == 'VERIFYING':
                    row = self.ledger.attempt(attempt_id)
                    self.ledger.finalize(attempt_id, make_report(bytes(row['snapshot']), row['outputs']))
                else:
                    _recover_owned(self.ledger, attempt_id)
                return self.attempt(attempt_id)

    def attempt_events(self, attempt_id, before, limit):
        """A page of this attempt's events, newest page first, rows in ledger order."""
        with self.ledger.connection() as con:
            self.ledger._row(con, attempt_id)
            meta = self._meta(con)
            bound = before if before else meta['cursor'] + 1
            rows = con.execute("SELECT seq,stamp_ns,kind,payload FROM events WHERE seq<? "
                               "AND json_extract(payload,'$.attempt')=? ORDER BY seq DESC LIMIT ?",
                               (bound, attempt_id, limit+1)).fetchall()
            visible = rows[:limit]
            return {**meta, 'attempt_id': attempt_id, 'has_more': len(rows)>limit,
                    'next_before': visible[-1]['seq'] if visible else 0,
                    'events': [{'seq': r['seq'], 'stamp_ns': str(r['stamp_ns']), 'kind': r['kind'],
                                'payload': {key: value for key, value in json.loads(r['payload']).items()
                                            if key in ('attempt', 'role', 'state', 'ordinal')}} for r in reversed(visible)]}

    def events(self, after, limit):
        with self.ledger.connection() as con:
            meta = self._meta(con)
            if after > meta['cursor']: raise Denied('EVENT_CURSOR_AHEAD')
            rows = con.execute('SELECT seq,stamp_ns,kind,payload FROM events WHERE seq>? ORDER BY seq LIMIT ?', (after, limit+1)).fetchall()
            safe_keys = {'attempt', 'project', 'ordinal', 'generation', 'call', 'role', 'state',
                         'payload_sha', 'content_sha', 'artifact_sha', 'receipt_sha'}
            events = [{'seq': row['seq'], 'stamp_ns': str(row['stamp_ns']), 'kind': row['kind'],
                       'payload': {key: value for key, value in json.loads(row['payload']).items() if key in safe_keys}}
                      for row in rows[:limit]]
            return {**meta, 'events': events, 'next_after': events[-1]['seq'] if events else after,
                    'has_more': len(rows) > limit}

    def _report(self, attempt_id):
        row = self.ledger.attempt(attempt_id)
        artifact = row['artifact']
        if artifact is None: raise Denied('REPORT_NOT_AVAILABLE')
        if row['state'] != 'ACCEPTED' or json.loads(row['verdict']).get('passed') is not True:
            raise Denied('REPORT_NOT_ACCEPTED')
        artifact = bytes(artifact)
        if digest(artifact) != row['artifact_sha']: raise Denied('REPORT_CHANGED')
        return row, artifact

    def report(self, attempt_id):
        row, artifact = self._report(attempt_id)
        return {'attempt_id': attempt_id, 'state': row['state'], 'sha256': row['artifact_sha'],
                'bytes': len(artifact), 'encoding': 'utf-8', 'media_type': 'application/json',
                'verdict': json.loads(row['verdict']), 'mode': row['profile']['mode']}

    def report_read(self, attempt_id, offset, limit):
        row, artifact = self._report(attempt_id)
        if offset > len(artifact): raise Denied('REPORT_OFFSET_RANGE')
        chunk = artifact[offset:offset+limit]
        return {'attempt_id': attempt_id, 'sha256': row['artifact_sha'], 'offset': offset,
                'next_offset': offset+len(chunk), 'eof': offset+len(chunk) == len(artifact),
                'chunk_sha256': digest(chunk), 'base64': base64.b64encode(chunk).decode('ascii')}

    def dispatch(self, raw):
        request = decode_command(raw)
        with self._command_lock:
            if self._closed: raise Denied('DESKTOP_SESSION_CLOSED')
            method, params = request['method'], request['params']
            if method == 'describe':
                with self.ledger.connection() as con:
                    identity = self._meta(con)
                return {**identity, 'version': 1, 'backend': 'python-ledger',
                        'inference': 'owned-local-model' if self.backend_factory is OwnedOllama else 'injected-test-backend',
                        'source_selection': 'native-host',
                        'approval_ttl_seconds': GRANT_TTL_SECONDS, 'max_attempts_per_project': 3,
                        'max_active_projects': 2, 'max_concurrent_inference': 1}
            if method == 'models.list':
                models = self.models()
                return {'models': models, 'cached': self._catalog_stale, 'session_id': self.session_id}
            if method == 'projects.list': return self.snapshot()
            if method == 'snapshot.get': return self.snapshot(**params)
            if method == 'source.pick': raise Denied('NATIVE_PICKER_REQUIRED')
            handlers = {'source.check': self.check_source, 'attempt.preview': self.preview, 'attempt.start': self.start,
                        'attempt.cancel': self.cancel, 'attempt.recover': self.recover,
                        'attempt.get': self.attempt, 'attempt.lookup': self.lookup,
                        'events.read': self.events, 'attempt.events': self.attempt_events,
                        'report.get': self.report, 'report.read': self.report_read}
            return handlers[method](**params)

    def close(self, timeout=15):
        """EOF revokes new session commands and requests owned-work cancellation."""
        with self._command_lock:
            self._closed = True
            self._sources.clear()
            self._approvals.clear()
            worker = self._worker
            if worker is not None and worker.is_alive():
                self.ledger.cancel(self._worker_attempt)
        if worker is not None: worker.join(timeout)
        return worker is None or not worker.is_alive()
