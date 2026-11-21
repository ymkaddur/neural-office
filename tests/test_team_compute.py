import os
import socket
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from neural_office.ledger import Denied
from neural_office.ollama import OwnedOllama, inference_options, listener_pids, review_profile
from neural_office.runner import prompt


MODEL = {'mode':'ollama-owned', 'model':'test', 'model_digest':'a'*64, 'num_gpu':0}
SOURCE = b'<html lang="es"><title>Test</title>\n<img src="x">\n</html>'


class TeamCompute(unittest.TestCase):
    def test_new_team_enables_local_acceleration_without_changing_admitted_profiles(self):
        for profile in (review_profile(MODEL, 1), review_profile(MODEL, 3), {**MODEL, 'roles':7}):
            self.assertEqual(inference_options(profile), {'num_gpu':0,'num_ctx':8192,'num_predict':128,'temperature':0})
        team = review_profile(MODEL, 7)
        self.assertEqual(inference_options(team), {'num_gpu':-1,'num_thread':1,'num_ctx':8192,'num_predict':128,'temperature':0})
        for change in ({'roles':3}, {'mode':'fixture'}, {'analysis_scope':'text'}, {'num_gpu':0}):
            with self.subTest(change=change), self.assertRaisesRegex(Denied, 'MODEL_PROFILE_MISMATCH'):
                inference_options({**team, **change})
        self.assertNotIn('execution_policy', MODEL)

    def test_citation_choices_follow_the_actual_source_and_leave_an_absence_option(self):
        row = dict(profile=review_profile(MODEL, 7), objective='Indica el código y la línea de la imagen sin descripción.',
                   snapshot=SOURCE, outputs=[])
        first = prompt(row, 'researcher')
        shifted = prompt({**row, 'snapshot': b'\n\n'+SOURCE}, 'researcher')
        self.assertIn('IMAGE_ALT_MISSING: línea 2, columna 1.', first['format']['enum'])
        self.assertIn('IMAGE_ALT_MISSING: línea 4, columna 1.', shifted['format']['enum'])
        self.assertIn('La comprobación no registró IMAGE_ALT_MISSING.', shifted['format']['enum'])
        self.assertNotIn('format', prompt({**row, 'objective':'Recomienda un plan de revisión.'}, 'integrator'))
        self.assertNotIn('format', prompt({**row, 'profile':{**MODEL,'roles':7}}, 'researcher'))

    @unittest.skipUnless(os.name == 'nt', 'Windows listener ownership')
    def test_live_windows_table_does_not_admit_an_unrelated_listener(self):
        with tempfile.TemporaryDirectory() as tmp, socket.socket() as listener:
            listener.bind(('127.0.0.1',0))
            listener.listen()
            port = listener.getsockname()[1]
            self.assertEqual(listener_pids(port), {os.getpid()})
            backend = OwnedOllama('Local\\NeuralTeamTest_'+uuid.uuid4().hex, MODEL, Path(tmp)/'test.log')
            try:
                backend.port = port
                with self.assertRaisesRegex(Denied,'BACKEND_NOT_OWNED_BY_OFFICE'):
                    backend._assert_owned_listener()
                for identities, expected in [(set(),'OWNER_UNKNOWN'), ({1,2},'AMBIGUOUS')]:
                    with mock.patch('neural_office.ollama.listener_pids',return_value=identities):
                        with self.assertRaisesRegex(Denied,expected):
                            backend._assert_owned_listener()
            finally:
                backend.close()
