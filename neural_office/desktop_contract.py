"""Bounded desktop command shapes; permission is enforced by DesktopService.

The native host owns file selection. Its private capture operation deliberately
does not appear in this webview command allowlist.
"""
import re

from .ledger import Denied
from .ollama import json_unique

MAX_MESSAGE_BYTES = 16_384
MAX_SAFE_INTEGER = 2**53 - 1
METHODS = {
    'describe': {}, 'models.list': {}, 'projects.list': {},
    'project.history': {'project_id': 'project'},
    'snapshot.get': {'project_after': 'revision', 'attempt_after': 'revision', 'limit': 'limit'},
    'source.pick': {'project_id': 'project'},
    'library.list': {'project_id': 'project'},
    'library.for_draft': {'project_id': 'project', 'entry_id': 'id', 'expected_revision': 'revision'},
    'library.copy_to_draft': {'session_id': 'id', 'project_id': 'project', 'thread_id': 'id', 'entry_id': 'id',
                              'expected_revision': 'revision', 'active_revision': 'revision',
                              'draft_revision': 'revision', 'edit_id': 'id'},
    'library.history': {'project_id': 'project', 'entry_id': 'id'},
    'library.change': {'project_id': 'project', 'thread_id': 'id', 'report_id': 'id', 'entry_id': 'id',
                       'kind': 'library_kind', 'title': 'objective', 'body': 'inspection_objective',
                       'operation': 'library_op', 'expected_revision': 'revision'},
    'attachments.pick': {'project_id': 'project', 'thread_id': 'id'},
    'attachments.list': {'project_id': 'project', 'thread_id': 'id'},
    'attachments.cancel': {'project_id': 'project', 'thread_id': 'id'},
    'attachments.threads': {'project_id': 'project'},
    'attachments.inspect': {'project_id': 'project', 'thread_id': 'id',
                            'attachment_ids': 'capture_ids', 'objective': 'inspection_objective'},
    'attachments.view': {'project_id': 'project', 'thread_id': 'id', 'capture_id': 'id',
                         'page': 'page', 'member': 'member'},
    'attachments.history': {'project_id': 'project', 'thread_id': 'id'},
    'attachments.search': {'project_id': 'project', 'query': 'objective'},
    'attachments.search.page': {'project_id': 'project', 'query': 'objective', 'before': 'search_cursor'},
    'attachments.scope': {'project_id': 'project', 'thread_id':'id', 'report_id':'id'},
    'attachments.report': {'project_id': 'project', 'thread_id': 'id', 'report_id': 'id'},
    'attachments.activity': {'project_id':'project','thread_id':'id'},
    'attachments.decide': {'project_id': 'project', 'thread_id': 'id', 'report_id': 'id', 'choice':'decision', 'expected_revision':'revision'},
    'attachments.preview': {'project_id': 'project', 'thread_id': 'id', 'report_id': 'id',
                            'model_digest': 'digest', 'objective': 'objective'},
    'source.check': {'project_id': 'project', 'entry_token': 'id', 'offset': 'revision'},
    'attempt.preview': {'project_id': 'project', 'entry_token': 'id', 'model_digest': 'digest',
                        'roles': 'roles', 'objective': 'objective'},
    'attempt.start': {'approval_token': 'id', 'idempotency_key': 'id', 'expected_revision': 'revision'},
    'attempt.cancel': {'attempt_id': 'id'},
    'attempt.recover': {'attempt_id': 'id', 'expected_revision': 'revision'},
    'attempt.get': {'attempt_id': 'id'}, 'report.get': {'attempt_id': 'id'},
    'attempt.lookup': {'project_id': 'project', 'idempotency_key': 'id'},
    'report.read': {'attempt_id': 'id', 'offset': 'revision', 'limit': 'chunk'},
    'events.read': {'after': 'revision', 'limit': 'limit'},
    'attempt.events': {'attempt_id': 'id', 'before': 'revision', 'limit': 'limit'},
    'draft.get': {'session_id': 'id', 'project_id': 'project', 'thread_id': 'id'},
    'draft.put': {'session_id': 'id', 'project_id': 'project', 'thread_id': 'id',
                  'expected_revision': 'revision', 'edit_id': 'id', 'after_edit': 'id', 'text': 'draft'},
}


def valid(kind, value):
    if kind == 'search_cursor':
        return type(value) is str and (value == '' or re.fullmatch(r'[a-f0-9]{32}', value) is not None)
    if kind == 'draft':
        if type(value) is not str or '\x00' in value: return False
        try: return len(value.encode('utf-8')) <= 12_000
        except UnicodeError: return False
    if kind == 'library_kind':
        return value in ('memory', 'skill') if type(value) is str else False
    if kind == 'library_op':
        return value in ('create', 'edit', 'propose', 'accept', 'discard', 'retire') if type(value) is str else False
    if kind == 'decision': return type(value) is str and value in ('pdf','json','defer')
    if kind == 'project':
        # Existing ledger identifiers are user text, not opaque capability IDs.
        if type(value) is not str or not 1 <= len(value) <= 80: return False
        try: value.encode('utf-8')
        except UnicodeError: return False
        return True
    if kind == 'id':
        return type(value) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value) is not None
    if kind == 'digest':
        return type(value) is str and re.fullmatch(r'[a-f0-9]{64}', value) is not None
    if kind == 'capture_ids':
        return (type(value) is list and len(value) <= 8
                and all(valid('id', item) for item in value) and len(set(value)) == len(value))
    if kind == 'page': return type(value) is int and 1 <= value <= 10000
    if kind == 'member':
        if type(value) is not str or len(value) > 512 or '\x00' in value: return False
        try: value.encode('utf-8')
        except UnicodeError: return False
        return True
    if kind == 'inspection_objective' and value == '': return True
    if kind in ('objective', 'inspection_objective'):
        if type(value) is not str or not 1 <= len(value) <= 2000 or not value.strip() or '\x00' in value:
            return False
        try: value.encode('utf-8')
        except UnicodeError: return False
        return True
    if kind == 'roles': return type(value) is int and value in (1, 3, 7)
    if kind == 'revision': return type(value) is int and 0 <= value <= MAX_SAFE_INTEGER
    if kind == 'limit': return type(value) is int and 1 <= value <= 200
    if kind == 'chunk': return type(value) is int and 1 <= value <= 65_536
    return False


def decode_command(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_MESSAGE_BYTES:
        raise Denied('DESKTOP_MESSAGE_SIZE_OR_TYPE')
    try:
        message = json_unique(raw.decode('utf-8'))
    except (ValueError, UnicodeError, RecursionError):
        raise Denied('DESKTOP_MESSAGE_INVALID_JSON') from None
    if type(message) is not dict or set(message) != {'version', 'id', 'method', 'params'}:
        raise Denied('DESKTOP_MESSAGE_FIELDS')
    if type(message['version']) is not int or message['version'] != 1:
        raise Denied('DESKTOP_VERSION_UNSUPPORTED')
    if not valid('id', message['id']): raise Denied('DESKTOP_REQUEST_ID_INVALID')
    method = message['method']
    if type(method) is not str or method not in METHODS:
        raise Denied('DESKTOP_METHOD_UNSUPPORTED')
    params, expected = message['params'], METHODS[method]
    if type(params) is not dict or set(params) != set(expected):
        raise Denied('DESKTOP_PARAMETER_FIELDS')
    if not all(valid(kind, params[key]) for key, kind in expected.items()):
        raise Denied('DESKTOP_PARAMETER_INVALID')
    return message
