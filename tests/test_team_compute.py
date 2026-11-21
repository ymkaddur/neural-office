import hashlib
import json
import os
import re
import socket
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from neural_office import excerpt_review
from neural_office.ledger import Denied
from neural_office.ollama import OwnedOllama, _team_model_files, inference_options, listener_pids, review_profile
from neural_office.runner import prompt


MODEL = {'mode':'ollama-owned', 'model':'test', 'model_digest':'a'*64, 'num_gpu':0}
SOURCE = b'<html lang="es"><title>Test</title>\n<img src="x">\n</html>'


class TeamCompute(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows model store')
    def test_catalog_attested_tag_and_config_are_both_rechecked_on_each_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            tag=root/'manifests-v2'/'ollama.com'/'library'/'example'/'latest'
            config=b'{"model_format":"gguf"}'
            config_sha=hashlib.sha256(config).hexdigest()
            blob=root/'blobs'/('sha256-'+config_sha)
            blob.parent.mkdir()
            blob.write_bytes(config)
            tag.parent.mkdir(parents=True)
            manifest=json.dumps({'schemaVersion':2,'mediaType':'application/vnd.docker.distribution.manifest.v2+json',
                                 'config':{'digest':'sha256:'+config_sha}}).encode()
            tag.write_bytes(manifest)
            profile=review_profile({**MODEL,'model':'example:latest','model_digest':hashlib.sha256(manifest).hexdigest()},7)
            with mock.patch('neural_office.ollama.local_metadata') as catalog:
                backend=OwnedOllama('Local\\NeuralTag_'+uuid.uuid4().hex,profile,root/'run.log')
                try:
                    backend._model_root=root
                    backend._model_files=_team_model_files(root,profile,'0.40.16')
                    self.assertEqual(len(backend._model_files),2)
                    backend.check_model()
                    for file, content in ((tag,manifest),(blob,config)):
                        file.write_bytes(content+b' ')
                        with self.assertRaisesRegex(Denied,'MODEL_DIGEST_CHANGED'):
                            backend.check_model()
                        with mock.patch('neural_office.ollama.http.client.HTTPConnection') as network:
                            with self.assertRaisesRegex(Denied,'MODEL_DIGEST_CHANGED'):
                                backend.infer({})
                            network.assert_not_called()
                        with self.assertRaisesRegex(Denied,'MODEL_DIGEST_CHANGED'):
                            _team_model_files(root,profile,'0.40.16')
                        file.write_bytes(content)
                    with (mock.patch.object(backend,'_assert_owned_listener'),
                          mock.patch('neural_office.ollama.http.client.HTTPConnection') as network):
                        response=network.return_value.getresponse.return_value
                        response.status=200
                        def finish_while_retagged(_):
                            tag.write_bytes(manifest+b' ')
                            return b'{"done":true}'
                        response.read.side_effect=finish_while_retagged
                        with self.assertRaisesRegex(Denied,'MODEL_DIGEST_CHANGED'):
                            backend.infer({'model':profile['model'],'options':inference_options(profile)})
                        self.assertEqual(backend.telemetry,[])
                    tag.unlink()
                    with self.assertRaisesRegex(Denied,'MODEL_IDENTITY_UNAVAILABLE'):
                        backend.check_model()
                    catalog.assert_not_called()
                finally:
                    backend.close()
            self.assertEqual(_team_model_files(root,profile,'unknown'),())
            self.assertEqual(_team_model_files(root,profile,'0.40.16'),())
            self.assertEqual(_team_model_files(root,{**profile,'model':'org/example:latest'},'0.40.16'),())

    def test_new_team_enables_local_acceleration_without_changing_admitted_profiles(self):
        for profile in (review_profile(MODEL, 1), review_profile(MODEL, 3), {**MODEL, 'roles':7}):
            self.assertEqual(inference_options(profile), {'num_gpu':0,'num_ctx':8192,'num_predict':128,'temperature':0})
        team = review_profile(MODEL, 7)
        self.assertEqual(inference_options(team), {'num_gpu':-1,'num_thread':1,'num_ctx':8192,'num_predict':128,'temperature':0})
        for change in ({'roles':3}, {'mode':'fixture'}, {'analysis_scope':'text'}, {'num_gpu':0}):
            with self.subTest(change=change), self.assertRaisesRegex(Denied, 'MODEL_PROFILE_MISMATCH'):
                inference_options({**team, **change})
        self.assertNotIn('execution_policy', MODEL)

    def test_verified_citation_follows_the_actual_source_and_grammar_does_not_supply_the_answer(self):
        row = dict(profile=review_profile(MODEL, 7), objective='Indica el código y la línea de la imagen sin descripción.',
                   snapshot=SOURCE, outputs=[])
        first = prompt(row, 'researcher')
        shifted = prompt({**row, 'snapshot': b'\n\n'+SOURCE}, 'researcher')
        self.assertIn('IMAGE_ALT_MISSING, línea 2, columna 1', first['messages'][-1]['content'])
        self.assertIn('IMAGE_ALT_MISSING, línea 4, columna 1', shifted['messages'][-1]['content'])
        citation=prompt(row,'integrator')
        self.assertEqual(citation['format'], prompt({**row,'snapshot':b'\n\n'+SOURCE},'integrator')['format'])
        shape=citation['format']['pattern']
        self.assertTrue(re.fullmatch(shape,'CONTROL_LABEL_CANDIDATE, línea 92, columna 15'))
        self.assertTrue(re.fullmatch(shape,'IMAGE_ALT_MISSING, línea 2, columna 1'))
        self.assertIsNone(re.fullmatch(shape,'OBSOLETURA, línea 2, columna 1'))
        self.assertNotIn('format', prompt({**row,'objective':row['objective']+' Además, explica cómo corregirla.'},'integrator'))
        self.assertNotIn('format', prompt({**row,'objective':row['objective']+' Incluye un ejemplo.'},'integrator'))
        self.assertNotIn('format', prompt({**row,'objective':row['objective'][:-1]+' y el título.'},'integrator'))
        self.assertNotIn('format', prompt({**row,'snapshot':SOURCE.replace(b'<img src="x">', b'')},'integrator'))
        self.assertNotIn('format', prompt({**row, 'objective':'Recomienda un plan de revisión.'}, 'integrator'))
        self.assertNotIn('format', prompt({**row, 'profile':{**MODEL,'roles':7}}, 'researcher'))

    def test_open_questions_keep_original_mandates_and_complete_prior_responses(self):
        from neural_office.runner import ROLES
        row = dict(profile=review_profile(MODEL,7), snapshot=SOURCE, objective='Revisa la imagen de la página.',
                   outputs=[dict(role='verifier',content='Comentario del revisor.',content_sha='a'*64)])
        for role in ROLES:
            with self.subTest(role=role):
                current = prompt(row,role)
                prior = prompt({**row,'profile':{**MODEL,'roles':7}},role)
                self.assertEqual(current['messages'],prior['messages'])
                self.assertNotIn('format',current)

    def test_unit_contract_depends_on_authorized_fragment_and_explicit_request(self):
        goal = '¿Cuántas horas dura? Devuelve la cifra y su unidad.'
        for number in ('31', '67', '2,5'):
            fragments = [{'name':'manual.pdf', 'quote':f'Primera respuesta en {number} horas.'}]
            self.assertTrue(excerpt_review.hour_answer_requested(goal,fragments))
            self.assertFalse(excerpt_review.hour_answer_requested(goal,fragments*2))
            self.assertFalse(excerpt_review.hour_answer_requested('Resume el documento.',fragments))
            snapshot = json.dumps({'scope':excerpt_review.SCOPE,'fragments':fragments}).encode()
            profile = {**MODEL,'roles':1,'analysis_scope':excerpt_review.SCOPE}
            row = dict(profile=profile, objective=goal, snapshot=snapshot, outputs=[])
            self.assertNotIn('format', prompt(row,'director'))
            shape = prompt({**row,'profile':{**profile,'answer_format':'hour-quantity-v1'}},'director')['format']
            self.assertNotIn(number, shape['pattern'])
        self.assertFalse(excerpt_review.hour_answer_requested(goal,[{'quote':'De 12 horas a 18 horas.'}]))

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
