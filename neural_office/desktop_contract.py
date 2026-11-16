"""V5.3 protocol-shape reference. Validation grants NO permission and executes nothing.

There is no desktop transport or command dispatcher in this release. Opaque grants,
authorization, idempotency and durable event replay must be enforced by the future
host/controller described in docs/V5_3_DESKTOP_CONTRACT.md.
"""
import re

from .ledger import Denied
from .ollama import json_unique

MAX_MESSAGE_BYTES = 16_384
MAX_SAFE_INTEGER = 2**53 - 1
METHODS = {
    'describe': {}, 'models.list': {}, 'projects.list': {},
    'source.pick': {'project_id': 'id'},
    'attempt.preview': {'project_id': 'id', 'entry_token': 'id', 'model_digest': 'digest',
                        'roles': 'roles', 'objective': 'objective'},
    'attempt.start': {'approval_token': 'id', 'idempotency_key': 'id', 'expected_revision': 'revision'},
    'attempt.cancel': {'attempt_id': 'id'},
    'attempt.recover': {'attempt_id': 'id', 'expected_revision': 'revision'},
    'attempt.get': {'attempt_id': 'id'}, 'report.get': {'attempt_id': 'id'},
    'events.read': {'after': 'revision', 'limit': 'limit'},
}


def valid(kind, value):
    if kind == 'id':
        return type(value) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value) is not None
    if kind == 'digest':
        return type(value) is str and re.fullmatch(r'[a-f0-9]{64}', value) is not None
    if kind == 'objective':
        if type(value) is not str or not 1 <= len(value) <= 2000 or not value.strip() or '\x00' in value:
            return False
        try: value.encode('utf-8')
        except UnicodeError: return False
        return True
    if kind == 'roles': return type(value) is int and value in (1, 3, 7)
    if kind == 'revision': return type(value) is int and 0 <= value <= MAX_SAFE_INTEGER
    if kind == 'limit': return type(value) is int and 1 <= value <= 200
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
