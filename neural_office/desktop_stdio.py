"""Private newline-delimited JSON pipe owned by the desktop host, never HTTP.

The Rust host must reject host.source.capture from its webview proxy. Only a
completed native picker may synthesize that private operation on this pipe.
"""
import argparse
import sys

from .desktop_contract import MAX_MESSAGE_BYTES, valid
from .desktop_service import DesktopService, public_error
from .ledger import Denied, Ledger, canonical
from .ollama import json_unique

MAX_RESPONSE_BYTES = 2_097_152


def respond(service, raw):
    request_id = None
    try:
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_MESSAGE_BYTES:
            raise Denied('DESKTOP_MESSAGE_SIZE_OR_TYPE')
        message = json_unique(raw.decode('utf-8'))
        if type(message) is dict and valid('id', message.get('id')):
            request_id = message['id']
        if type(message) is dict and message.get('method') == 'host.source.capture':
            if (set(message) != {'version', 'id', 'method', 'params'}
                    or type(message['version']) is not int or message['version'] != 1
                    or request_id is None or type(message['params']) is not dict
                    or set(message['params']) != {'project_id', 'path'}
                    or type(message['params']['path']) is not str
                    or not 0 < len(message['params']['path']) <= 4096
                    or '\x00' in message['params']['path']):
                raise Denied('DESKTOP_HOST_CAPTURE_INVALID')
            result = service.host_capture(**message['params'])
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


def serve(service, reader, writer):
    try:
        while True:
            line = reader.readline(MAX_MESSAGE_BYTES + 2)
            if not line: return 0
            # Close instead of draining an unbounded attacker-controlled line.
            if not line.endswith(b'\n') or len(line)-1 > MAX_MESSAGE_BYTES:
                writer.write(canonical({'version': 1, 'id': None, 'ok': False, 'result': None,
                                        'error': {'code': 'DESKTOP_FRAME_SIZE_OR_TERMINATION'}}).encode('utf-8')+b'\n')
                writer.flush()
                return 2
            writer.write(respond(service, line[:-1])+b'\n')
            writer.flush()
    finally:
        service.close()


def main():
    parser = argparse.ArgumentParser(description='Private Neural Office desktop sidecar')
    parser.add_argument('--state', required=True, help='Native host chosen local ledger path')
    args = parser.parse_args()
    service = DesktopService(Ledger(args.state))
    return serve(service, sys.stdin.buffer, sys.stdout.buffer)


if __name__ == '__main__':
    raise SystemExit(main())
