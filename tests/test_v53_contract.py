import json
import unittest
from neural_office.desktop_contract import decode_command, MAX_MESSAGE_BYTES, MAX_SAFE_INTEGER
from neural_office.ledger import Denied


class DesktopContract(unittest.TestCase):
    def request(self, method, params, **extra):
        return json.dumps({'version': 1, 'id': 'request-1', 'method': method, 'params': params, **extra}).encode()

    def test_preview_validates_shape_but_has_no_dispatcher(self):
        message = self.request('attempt.preview', {'project_id': 'example', 'entry_token': 'opaque',
            'model_digest': 'a' * 64, 'roles': 3, 'objective': 'Review the supplied example.'})
        self.assertEqual(decode_command(message)['params']['roles'], 3)

    def test_transport_and_authority_fields_cannot_be_smuggled(self):
        for message in (self.request('describe', {}, authorized=True),
                        self.request('describe', {'shell': 'powershell'}),
                        self.request('shell.execute', {}),
                        self.request('attempt.start', {'approval_token': 'x', 'idempotency_key': 'k',
                                                      'expected_revision': 0, 'budget': 999})):
            with self.assertRaises(Denied): decode_command(message)

    def test_revision_boundaries_and_bool_are_distinct(self):
        for after in (-1, True, 0.5, MAX_SAFE_INTEGER + 1, '0'):
            with self.assertRaises(Denied): decode_command(self.request('events.read', {'after': after, 'limit': 1}))
        for after in (0, MAX_SAFE_INTEGER):
            self.assertEqual(decode_command(self.request('events.read', {'after': after, 'limit': 200}))['params']['after'], after)
        for limit in (0, 201, True):
            with self.assertRaises(Denied): decode_command(self.request('events.read', {'after': 0, 'limit': limit}))

    def test_duplicate_keys_nan_bad_utf8_and_oversize_are_rejected(self):
        for raw in (b'{"version":1,"version":1}', b'{"x":NaN}', b'\xff', b'x'*(MAX_MESSAGE_BYTES+1), b'[]'):
            with self.assertRaises(Denied): decode_command(raw)

    def test_paths_are_not_opaque_file_grants(self):
        for token in ('C:/private/file', '../parent', '', 'x'*65):
            with self.assertRaises(Denied): decode_command(self.request('attempt.start', {
                'approval_token': token, 'idempotency_key': 'k', 'expected_revision': 0}))

    def test_cancel_does_not_depend_on_a_stale_ui_revision(self):
        self.assertEqual(decode_command(self.request('attempt.cancel', {'attempt_id': 'a'}))['method'], 'attempt.cancel')

    def test_objective_limits_include_whitespace(self):
        params = {'project_id': 'example', 'entry_token': 'opaque', 'model_digest': 'a'*64, 'roles': 1}
        for objective in (' ', '\x00', 'x' + ' '*2000, '\ud800'):
            with self.assertRaises(Denied):
                decode_command(self.request('attempt.preview', {**params, 'objective': objective}))
        self.assertEqual(len(decode_command(self.request('attempt.preview', {**params, 'objective': 'x'*2000}))['params']['objective']), 2000)


if __name__ == '__main__': unittest.main()
