"""Private newline-delimited JSON pipe owned by the desktop host, never HTTP.

The Rust host must reject host.source.capture from its webview proxy. Only a
completed native picker may synthesize that private operation on this pipe.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import sys
import threading

from .desktop_contract import MAX_MESSAGE_BYTES, valid
from .desktop_service import DesktopService, public_error
from .ledger import Denied, Ledger, canonical
from .ollama import json_unique

MAX_RESPONSE_BYTES = 2_097_152
READ_METHODS = frozenset({
    'projects.list', 'snapshot.get', 'project.history', 'attempt.lookup', 'attempt.get',
    'events.read', 'attempt.events', 'report.get', 'report.read', 'source.check',
})
ATTACHMENT_METHODS = frozenset({
    'host.attachments.capture', 'attachments.list', 'attachments.inspect', 'attachments.view',
    'attachments.history', 'attachments.search', 'attachments.threads', 'attachments.report', 'attachments.preview', 'attachments.decide',
})


def _error(request_id, code):
    return canonical({'version': 1, 'id': request_id, 'ok': False, 'result': None,
                      'error': {'code': code}}).encode('utf-8')


def _path_parameter(path):
    if type(path) is not str or not 0 < len(path) <= 4096 or '\x00' in path:
        return False
    try:
        path.encode('utf-8')
    except UnicodeEncodeError:
        return False
    return True


def respond(service, raw, message=None):
    request_id = None
    try:
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_MESSAGE_BYTES:
            raise Denied('DESKTOP_MESSAGE_SIZE_OR_TYPE')
        if message is None:
            message = json_unique(raw.decode('utf-8'))
        if type(message) is dict and valid('id', message.get('id')):
            request_id = message['id']
        if type(message) is dict and message.get('method') in ('host.source.capture', 'host.attachments.capture'):
            if (set(message) != {'version', 'id', 'method', 'params'}
                    or type(message['version']) is not int or message['version'] != 1
                    or request_id is None or type(message['params']) is not dict
                    or not valid('project', message['params'].get('project_id'))):
                raise Denied('DESKTOP_HOST_CAPTURE_INVALID')
            params = message['params']
            if message['method'] == 'host.source.capture':
                if set(params) != {'project_id', 'path'} or not _path_parameter(params['path']):
                    raise Denied('DESKTOP_HOST_CAPTURE_INVALID')
                result = service.host_capture(**params)
            else:
                if (set(params) != {'project_id', 'thread_id', 'paths'} or not valid('id', params['thread_id'])
                        or type(params['paths']) is not list or not 1 <= len(params['paths']) <= 8
                        or not all(_path_parameter(path) for path in params['paths'])):
                    raise Denied('DESKTOP_HOST_CAPTURE_INVALID')
                result = service.host_attachments_capture(**params)
        else:
            result = service.dispatch(raw)
        response = {'version': 1, 'id': request_id, 'ok': True, 'result': result, 'error': None}
    except (Exception, RecursionError) as error:
        response = {'version': 1, 'id': request_id, 'ok': False, 'result': None,
                    'error': {'code': public_error(error)}}
    try:
        encoded = canonical(response).encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError):
        encoded = canonical({'version': 1, 'id': request_id, 'ok': False, 'result': None,
                             'error': {'code': 'DESKTOP_RESPONSE_INVALID'}}).encode('utf-8')
    if len(encoded) > MAX_RESPONSE_BYTES:
        encoded = canonical({'version': 1, 'id': request_id, 'ok': False, 'result': None,
                             'error': {'code': 'DESKTOP_RESPONSE_SIZE'}}).encode('utf-8')
    return encoded


class _Lane:
    """Limit all admitted work, including calls waiting for a worker."""
    def __init__(self, stack, name, workers, capacity):
        self.pool = stack.enter_context(ThreadPoolExecutor(max_workers=workers, thread_name_prefix=name))
        self.available = threading.BoundedSemaphore(capacity)

    def submit(self, work, *args):
        if not self.available.acquire(blocking=False):
            return False

        def run():
            try:
                work(*args)
            finally:
                self.available.release()
        self.pool.submit(run)
        return True


def serve(service, reader, writer):
    output = threading.Lock()
    broken = threading.Event()

    def send(packet):
        with output:
            if broken.is_set():
                return
            try:
                writer.write(packet + b'\n')
                writer.flush()
            except OSError:
                broken.set()

    def answer(raw, message):
        send(respond(service, raw, message))

    code = 0
    try:
        with ExitStack() as stack:
            reads = _Lane(stack, 'office-read', workers=2, capacity=4)
            catalog = _Lane(stack, 'office-metadata', workers=1, capacity=1)
            attachments = _Lane(stack, 'office-attachments', workers=1, capacity=2)
            lanes = dict.fromkeys(READ_METHODS, reads)
            lanes.update(dict.fromkeys(('models.list', 'attempt.preview'), catalog))
            lanes.update(dict.fromkeys(ATTACHMENT_METHODS, attachments))
            try:
                while not broken.is_set():
                    line = reader.readline(MAX_MESSAGE_BYTES + 2)
                    if not line:
                        break
                    if not line.endswith(b'\n') or len(line)-1 > MAX_MESSAGE_BYTES:
                        send(_error(None, 'DESKTOP_FRAME_SIZE_OR_TERMINATION'))
                        code = 2
                        break
                    raw = line[:-1]
                    try:
                        message = json_unique(raw.decode('utf-8'))
                    except (ValueError, UnicodeError, RecursionError):
                        message = None
                    method = message.get('method') if type(message) is dict else None
                    lane = lanes.get(method) if type(method) is str else None
                    if lane is None:
                        # Durable reservations, stop and recovery share input order.
                        answer(raw, message)
                    elif not lane.submit(answer, raw, message):
                        key = message.get('id')
                        send(_error(key if valid('id', key) else None, 'HOST_BUSY'))
            finally:
                # All mutations of the model lease ran on this thread. Revoke
                # it before waiting for an admitted slow observer on EOF.
                service.stop_owned()
    finally:
        service.close()
    return 1 if broken.is_set() else code


def main():
    parser = argparse.ArgumentParser(description='Private Neural Office desktop sidecar')
    parser.add_argument('--state', required=True, help='Native host chosen local ledger path')
    args = parser.parse_args()
    service = DesktopService(Ledger(args.state))
    return serve(service, sys.stdin.buffer, sys.stdout.buffer)


if __name__ == '__main__':
    raise SystemExit(main())
