"""Read-only reconciliation of installed historical sources. Import never arms them."""
from contextlib import contextmanager, ExitStack
from contextvars import ContextVar
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from .ledger import Denied, canonical, digest, TERMINAL
from .continuity import signature

PRODUCTS = ('web-auditor', 'design-system-qa', 'skills-registry', 'agent-observability', 'agent-memory')
CATALOG = set(PRODUCTS) | {'tower-defense'}
PATHS = {
    'v1': 'studio/studio-v1.sqlite3',
    'v4': 'studio/office/neural_office_v4/state/v4.sqlite3',
    'graphs': 'studio/office/neural_office_v42/state/graphs.sqlite3',
    'plus': 'studio/office/neural_office_plus/office_plus.sqlite3',
    'director45': 'studio/office/neural_office_v45/state/director45.sqlite3',
    'director5': 'studio/office/neural_office_v5/state/director45.sqlite3',
    'work5': 'studio/office/neural_office_v5/state/work.sqlite3',
}
_held = ContextVar('legacy_sources_held', default=None)


@contextmanager
def held_sources():
    with ExitStack() as stack:
        token = _held.set((stack, {}))
        try: yield
        finally: _held.reset(token)


def _hold(path, stack):
    """Deny existing/new writers and replacement while all source files are captured."""
    import msvcrt
    dll = ctypes.WinDLL('kernel32', use_last_error=True)
    dll.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
    dll.CreateFileW.restype = w.HANDLE
    dll.CloseHandle.argtypes = [w.HANDLE]; dll.CloseHandle.restype = w.BOOL
    handle = dll.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value: raise Denied('LEGACY_WRITER_OR_SOURCE_UNAVAILABLE')
    try: fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        dll.CloseHandle(handle); raise
    source = stack.enter_context(os.fdopen(fd, 'rb'))
    if os.fstat(source.fileno()).st_size > 64 * 1024 * 1024: raise Denied('LEGACY_SOURCE_TOO_LARGE')
    return source


@contextmanager
def snapshot(root):
    if os.name != 'nt': raise Denied('LEGACY_CAPTURE_REQUIRES_WINDOWS')
    root = Path(root).resolve(strict=True)
    if str(root).startswith('\\\\'): raise Denied('LEGACY_NETWORK_SOURCE_EXCLUDED')
    with ExitStack() as stack:
        files = {}; identities = {}; data = {}; logical = {}
        for key, rel in PATHS.items():
            path = root/rel
            if not path.exists():
                if key in ('v1', 'v4'): raise Denied('LEGACY_AUTHORITY_SOURCE_MISSING')
                data[key] = None; logical[key] = None; continue
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise Denied('LEGACY_SOURCE_PATH_UNSAFE')
            journal = Path(str(path) + '-journal')
            if journal.exists() and journal.stat().st_size: raise Denied('LEGACY_RECOVERY_REQUIRED')
            files[key] = [_hold(path, stack), None]
            wal = Path(str(path) + '-wal')
            if wal.exists(): files[key][1] = _hold(wal, stack)
        # An unexpected state file must not silently disappear from the budget mapping.
        for version in ('neural_office_v45', 'neural_office_v5'):
            state_dir = root/'studio/office'/version/'state'
            for candidate in state_dir.glob('*'):
                if candidate.suffix in ('.db', '.sqlite', '.sqlite3') and candidate.relative_to(root).as_posix() not in PATHS.values():
                    raise Denied('LEGACY_UNMAPPED_STATE_FILE')
        temp = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        for key, handles in files.items():
            copied = temp/(key + '.sqlite3'); raw = handles[0].read()
            copied.write_bytes(raw); identities[key] = {'main_sha256': digest(raw)}
            if handles[1]:
                wal = handles[1].read(); Path(str(copied) + '-wal').write_bytes(wal)
                identities[key]['wal_sha256'] = digest(wal)
            con = sqlite3.connect(copied.resolve().as_uri() + '?mode=ro', uri=True)
            try:
                con.row_factory = sqlite3.Row
                con.execute('PRAGMA query_only=ON'); con.execute('PRAGMA trusted_schema=OFF')
                if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise Denied('LEGACY_SQLITE_INVALID')
                if con.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view')").fetchone():
                    raise Denied('LEGACY_SCHEMA_UNSUPPORTED')
                tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
                data[key] = {t: [dict(r) for r in con.execute('SELECT * FROM "' + t.replace('"', '""') + '" ORDER BY rowid')] for t in tables}
                logical[key] = signature(con)
            finally: con.close()
        result = assess(data, root)
        result['source_fingerprints'] = logical
        result['fingerprint'] = digest(canonical(logical))
        result['physical_sources'] = identities
        yield result


def _integer(value, maximum=3):
    if type(value) is not int or not 0 <= value <= maximum: raise Denied('LEGACY_COUNTER_INVALID')
    return value


def assess(data, root):
    """Closed mapping. Unknown histories block; certified versions are never attempts."""
    v1, v4 = data['v1'], data['v4']
    meta = {r['key']: r['value'] for r in v1['meta']}
    if meta.get('schema') != 'studio-v1' or {r['k']:r['v'] for r in v4['meta']}.get('schema') != '4':
        raise Denied('LEGACY_SCHEMA_UNSUPPORTED')
    projects = {r['id']: r for r in v1['projects']}
    armed = {r['name']: r for r in v4['project']}
    if set(projects) != CATALOG or set(armed) != CATALOG: raise Denied('LEGACY_CATALOG_MISMATCH')
    initial = [r for r in v1['events'] if r['action'] == 'CATALOG_INITIALIZED']
    if len(initial) != 1: raise Denied('LEGACY_LINEAGE_UNKNOWN')
    lineage = digest(canonical([meta.get('root'), initial[0]['stamp'], initial[0]['payload']]))
    previous = '0'*64
    for row in v4['audit']:
        expected = digest('|'.join((previous, row['ts'], row['actor'], row['event'], row['payload'])))
        if row['previous_hash'] != previous or row['entry_hash'] != expected: raise Denied('LEGACY_AUDIT_CHANGED')
        previous = row['entry_hash']
    mismatches = [p for p in CATALOG if (projects[p]['state'] == 'active') != (armed[p]['state'] == 'armed')]
    if any(p['state'] not in ('active','parked','blocked','awaiting_review') for p in projects.values()) or any(p['state'] not in ('armed','parked') for p in armed.values()):
        raise Denied('LEGACY_AUTHORITY_STATE_INVALID')
    global_reasons = ['LEGACY_AUTHORITY_DIVERGENCE'] if mismatches else []
    if sum(p['state']=='active' for p in projects.values()) > 2 or sum(p['state']=='armed' for p in armed.values()) > 2:
        global_reasons.append('LEGACY_ACTIVE_LIMIT')
    footprints = {p: {} for p in CATALOG}; unresolved = set()
    plus = data.get('plus')
    if plus is not None:
        groups = {}; inflight = {}
        for event in plus['events']:
            p, kind = event['project'], event['kind']
            if p not in CATALOG: raise Denied('LEGACY_UNKNOWN_PROJECT')
            if digest(event['body']) != event['sha256']: raise Denied('LEGACY_EVENT_CHANGED')
            if kind in ('DIRECTOR_MESSAGE','PILOT_AUTHORIZED'):
                if inflight.get(p): raise Denied('LEGACY_INTERLEAVING_UNMAPPED')
                groups[p] = 'plus:' + str(event['seq']) + ':' + event['sha256']
            elif kind == 'RUN_STARTED':
                if inflight.get(p) or p not in groups: raise Denied('LEGACY_INVOCATION_UNMAPPED')
                if groups[p] in footprints[p]:
                    raise Denied('LEGACY_GROUPED_INVOCATIONS_REQUIRE_MAPPING')
                inflight[p] = True
                footprints[p][groups[p]] = 'plus_authorized_invocation'
            elif kind in ('RUN_RECEIPT','RUN_FAILED'):
                if not inflight.get(p): raise Denied('LEGACY_RESULT_WITHOUT_START')
                inflight[p] = False
        unresolved.update(p for p, pending in inflight.items() if pending)
        if plus.get('tasks') or plus.get('evaluations'): raise Denied('LEGACY_PLUS_HISTORY_UNMAPPED')
    seen_tasks = {}
    for family in ('director45','director5','work5'):
        source = data.get(family)
        if source is None: continue
        work = family == 'work5'
        previous = '0'*64
        for event in source['events' if work else 'audit']:
            body = event['body' if work else 'payload']
            expected = digest('|'.join((previous, event['stamp'], event['kind'], body)))
            if event['previous_digest' if work else 'prev'] != previous or event['digest' if work else 'hash'] != expected:
                raise Denied('LEGACY_AUDIT_CHANGED')
            previous = expected
        table, tasks = source['projects' if work else 'project'], source['tasks' if work else 'task']
        if any(t['project'] not in {p['id'] for p in table} for t in tasks):
            raise Denied('LEGACY_ORPHAN_TASK')
        for entry in table:
            p = entry['id']
            if p not in CATALOG: raise Denied('LEGACY_UNKNOWN_PROJECT')
            rows = [r for r in tasks if r['project'] == p]
            numbers = sorted(r['attempt' if work else 'version'] for r in rows)
            attempted = _integer(entry['attempted'])
            if numbers != list(range(1, attempted+1)): raise Denied('LEGACY_ATTEMPT_ROWS_MISMATCH')
            accepted = [r for r in rows if r['state'] == 'verified']
            expected = len(accepted) if work else max([r['version'] for r in accepted], default=0)
            if _integer(entry['verified' if work else 'completed']) != expected:
                raise Denied('LEGACY_VERIFIED_COUNTER_MISMATCH')
            for task in rows:
                identity = ('work:' if work else 'director:') + task['id']
                value = canonical(task)
                if identity in seen_tasks and seen_tasks[identity] != value: raise Denied('LEGACY_DUPLICATE_ID_CONFLICT')
                seen_tasks[identity] = value
                footprints[p][identity] = 'work' if work else 'director'
                if task['state'] not in ('verified','rejected'): unresolved.add(p)
    graphs = data.get('graphs')
    if graphs is not None and (graphs['run'] or graphs['node']):
        raise Denied('LEGACY_GRAPH_HISTORY_REQUIRES_MAPPING')
    result = {}
    for p in sorted(CATALOG):
        v1_versions = _integer(projects[p]['certified_versions'])
        v4_versions = _integer(armed[p]['cycle'])
        _integer(armed[p]['authorized_max'])
        # V4 tasks are role work, not one-attempt rows. Do not guess a conversion.
        if v1_versions or v4_versions or any(r['project']==p for r in v4['task']):
            raise Denied('LEGACY_CERTIFIED_OR_ROLE_HISTORY_REQUIRES_MAPPING')
        if len(set(footprints[p].values())) > 1: raise Denied('LEGACY_CROSS_LEDGER_HISTORY_REQUIRES_MAPPING')
        consumed = len(footprints[p])
        if consumed > 3: raise Denied('LEGACY_EXISTING_BUDGET_EXCEEDED')
        location = Path(projects[p]['location']).resolve(strict=True)
        if not location.is_relative_to(root): raise Denied('LEGACY_LOCATION_RELOCATION_REQUIRES_MAPPING')
        result[p] = {'root': os.path.normcase(str(location)), 'consumed': consumed,
            'operation_ids': sorted(footprints[p]), 'v1_state': projects[p]['state'],
            'v4_state': armed[p]['state'], 'v1_certified': v1_versions, 'v4_certified': v4_versions,
            'v4_authorized_max': armed[p]['authorized_max'],
            'unresolved': p in unresolved, 'excluded': p not in PRODUCTS}
    return {'schema': 1, 'lineage': lineage, 'projects': result,
        'global_reasons': global_reasons, 'mismatches': sorted(mismatches),
        'mapping_policy': 'observed-invocations-and-shadow-attempts-v1', 'authority_transferred': False}


def _current(root):
    held = _held.get()
    if held is None: raise Denied('LEGACY_AUTHORITY_CHECK_OUTSIDE_TRANSACTION')
    stack, cache = held
    if root not in cache: cache[root] = stack.enter_context(snapshot(root))
    return cache[root]


def check_authority(con, project):
    binding = con.execute('SELECT * FROM legacy_bindings WHERE project=?', (project,)).fetchone()
    if binding is None: return
    current = _current(binding['source_root'])
    old = json.loads(binding['receipt'])
    if current['fingerprint'] != old['fingerprint'] or current['lineage'] != binding['lineage']:
        raise Denied('LEGACY_SOURCE_CHANGED_RECONCILE_REQUIRED')
    p = current['projects'][project]
    if current['global_reasons']: raise Denied(current['global_reasons'][0])
    if p['unresolved']: raise Denied('LEGACY_OPERATION_UNRESOLVED')
    if (p['v1_state'], p['v4_state']) != ('active', 'armed'):
        raise Denied('LEGACY_AUTHORITY_NOT_GRANTED')
    # A smaller certified-version allowance is not permission for three attempts.
    # Partial allowances require an explicit mapping, never silent expansion.
    if p['v4_authorized_max'] != 3:
        raise Denied('LEGACY_CERTIFIED_ALLOWANCE_REQUIRES_MAPPING')


def inherited_consumption(con, project):
    row = con.execute('SELECT consumed FROM legacy_bindings WHERE project=?', (project,)).fetchone()
    return row[0] if row else 0


def require_reconciliation(con, project, root):
    for row in con.execute('SELECT root,project FROM legacy_roots'):
        if (Path(root).is_relative_to(Path(row['root'])) or Path(row['root']).is_relative_to(Path(root))) and row['project'] != project:
            raise Denied('LEGACY_ROOT_ALREADY_BOUND')
    if con.execute('SELECT 1 FROM legacy_bindings WHERE project=?', (project,)).fetchone(): return
    for ancestor in (Path(root), *Path(root).parents):
        if (ancestor/PATHS['v1']).is_file(): raise Denied('LEGACY_RECONCILE_REQUIRED')


def reconcile(ledger, source_root):
    source_root = str(Path(source_root).resolve(strict=True))
    with ledger.transaction() as con:
        observed = _current(source_root)
        for p in PRODUCTS:
            info = observed['projects'][p]
            old = con.execute('SELECT * FROM legacy_bindings WHERE project=?', (p,)).fetchone()
            if old and (old['lineage'] != observed['lineage'] or info['consumed'] < old['consumed']):
                raise Denied('LEGACY_LINEAGE_OR_BUDGET_REGRESSION')
            existing = con.execute('SELECT root FROM projects WHERE id=?', (p,)).fetchone()
            if existing and not old and existing['root'] != info['root']: raise Denied('LEGACY_PROJECT_ID_CONFLICT')
            if con.execute("SELECT 1 FROM attempts WHERE project=? AND state NOT IN ('ACCEPTED','REJECTED','FAILED','CANCELLED')", (p,)).fetchone():
                raise Denied('LEGACY_RECONCILE_REQUIRES_IDLE_PROJECT')
            local = con.execute('SELECT count(*) FROM attempts WHERE project=?', (p,)).fetchone()[0]
            if local + info['consumed'] > 3: raise Denied('LEGACY_COMBINED_BUDGET_EXCEEDED')
            if not existing:
                con.execute('INSERT INTO projects(id,root) VALUES(?,?)', (p, info['root']))
            con.execute('INSERT OR IGNORE INTO legacy_roots VALUES(?,?)', (info['root'], p))
            if con.execute('SELECT project FROM legacy_roots WHERE root=?', (info['root'],)).fetchone()[0] != p:
                raise Denied('LEGACY_ROOT_ALREADY_BOUND')
            con.execute('INSERT OR REPLACE INTO legacy_bindings VALUES(?,?,?,?,?)',
                        (p, observed['lineage'], source_root, info['consumed'], canonical(observed)))
            con.execute('UPDATE projects SET active=0,approved=0 WHERE id=?', (p,))
        ledger._event(con, 'LEGACY_RECONCILED', {'lineage': observed['lineage'], 'fingerprint': observed['fingerprint'],
                      'consumed': {p: observed['projects'][p]['consumed'] for p in PRODUCTS}, 'authority_granted': False})
        return observed


def rebind(ledger, project, root):
    target = Path(root).resolve(strict=True)
    if not target.is_dir(): raise Denied('PROJECT_ROOT_NOT_DIRECTORY')
    target = os.path.normcase(str(target))
    with ledger.transaction() as con:
        if not con.execute('SELECT 1 FROM legacy_bindings WHERE project=?', (project,)).fetchone():
            raise Denied('LEGACY_BINDING_REQUIRED')
        if con.execute("SELECT 1 FROM attempts WHERE project=? AND state NOT IN ('ACCEPTED','REJECTED','FAILED','CANCELLED')", (project,)).fetchone():
            raise Denied('UNRESOLVED_ATTEMPT')
        owner = con.execute('SELECT project FROM legacy_roots WHERE root=?', (target,)).fetchone()
        if owner and owner[0] != project: raise Denied('LEGACY_ROOT_ALREADY_BOUND')
        require_reconciliation(con, project, target)
        con.execute('INSERT OR IGNORE INTO legacy_roots VALUES(?,?)', (target, project))
        con.execute('UPDATE projects SET root=?,active=0,approved=0 WHERE id=?', (target, project))
        ledger._event(con, 'LEGACY_ROOT_REBOUND', {'project': project, 'budget_preserved': True})
