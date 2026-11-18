"""A bounded naming heuristic, checked separately against Edge's accessibility tree."""
import unittest

from neural_office.audit import audit_html


# Each document contains one text input. The expected text is the independent
# browser-side criterion. The static check only predicts empty versus nonempty.
CASES = [
    ('unresolved', '<input aria-labelledby="absent">', ''),
    ('empty explicit', '<label for="x">  </label><input id="x">', ''),
    ('forward', '<input aria-labelledby="n"><span id="n">Correo</span>', 'Correo'),
    ('partial list', '<b id="n">Cuenta</b><input aria-labelledby="absent n">', 'Cuenta'),
    ('empty ref', '<span id="n"></span><input aria-labelledby="n">', ''),
    ('native fallback', '<label for="x">Alias</label><input id="x" aria-labelledby="absent">', 'Alias'),
    ('direct fallback', '<input aria-labelledby="absent" aria-label="Aviso">', 'Aviso'),
    ('empty target fallback', '<span id="n"></span><input aria-labelledby="n" aria-label="Aviso">', 'Aviso'),
    ('implicit rich', '<label><b>Correo</b><input></label>', 'Correo'),
    ('implicit empty', '<label><input></label>', ''),
    ('explicit elsewhere', '<label for="other">Otro<input></label>', ''),
    ('duplicate first', '<span id="n"></span><span id="n">Otro</span><input aria-labelledby="n">', ''),
    ('image label', '<label><img alt="Correo"><input></label>', 'Correo'),
    ('script alone', '<label for="x"><script>0</script></label><input id="x">', ''),
    ('two sources', '<i id="a">Nombre</i><i id="b">legal</i><input aria-labelledby="a b">', 'Nombre legal'),
    ('hidden label child', '<label for="x"><span hidden>Correo</span></label><input id="x">', ''),
    ('aria-hidden label child', '<label for="x"><b aria-hidden="true">Correo</b></label><input id="x">', ''),
    ('css hidden nested image', '<label for="x"><img style="display: none" alt="Correo"></label><input id="x">', ''),
    ('visible label sibling', '<label for="x"><b hidden>Cuenta</b>Correo</label><input id="x">', 'Correo'),
    ('direct hidden reference', '<span hidden id="n"><b>Correo</b></span><input aria-labelledby="n">', 'Correo'),
    ('visible reference with hidden child', '<span id="n"><b hidden>Correo</b></span><input aria-labelledby="n">', ''),
    ('template id', '<template><b id="n">Correo</b></template><input aria-labelledby="n">', ''),
    ('hidden native label', '<label hidden for="x"><b>Correo</b></label><input id="x">', ''),
]


class NameCandidates(unittest.TestCase):
    def test_static_candidates(self):
        for name, html, expected in CASES:
            with self.subTest(name=name):
                flags = [f for f in audit_html(html.encode()) if f['code'] == 'CONTROL_LABEL_CANDIDATE']
                self.assertEqual(len(flags), int(not expected))

    def test_implicit_label_applies_to_first_eligible_control(self):
        html = '<label>Cuenta<input type="hidden"><input><input></label>'
        self.assertEqual([f['column'] for f in audit_html(html.encode()) if f['code'] == 'CONTROL_LABEL_CANDIDATE'],
                         [html.rindex('<input>') + 1])
