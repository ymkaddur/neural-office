"""Exercise the installed Tauri test host, native picker and unmodified local readers on Windows."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile

from examples.multiformat.build_example import example_files
from tools.measure_v58 import ROOT, require
from tools.measure_v58_desktop import choose_files
from tools.verify_v510_desktop import wait, window
from tools.verify_v512_desktop import stored


OBJECTIVE = 'Comprueba el plazo de primera respuesta en la entrega seleccionada.'
ANSWER = '24 h en la especificación, 48 h en la entrega'


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_report(folder, names):
    path = folder/'office.sqlite3.attachments.sqlite3'
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as db:
        captured = dict(db.execute('SELECT name,sha256 FROM captures'))
        require(captured == names, 'native selection and original file fingerprints differ')
        report, = db.execute('SELECT payload FROM reports').fetchall()
    record = json.loads(report[0])
    require(record['objective'] == OBJECTIVE and record['reservations'] == record['model_calls'] == 0,
            'local report scope or cost changed')
    finding, = [f for f in record['findings'] if f['rule'] == 'first_response_hours']
    expected = {'pdf': (2,None,None,24), 'json': (None,4,'/response_sla_hours',48)}
    require(finding['status'] == 'mismatch', 'the discrepancy was not recorded')
    for reference in finding['sources']:
        observed = tuple(reference.get(k) for k in ('page','line','pointer','value'))
        require(observed == expected.pop(reference['kind']), 'wrong source coordinates or hours')
        require(reference['sha256'] == names[reference['name']], 'citation points at another source')
    require(not expected and len(record['steps']) >= 6, 'receipt or citation missing')
    return record


def run(exe, out):
    version = json.loads((ROOT/'desktop/src-tauri/tauri.conf.json').read_bytes())['version']
    with tempfile.TemporaryDirectory(prefix='noffice-native-v513-') as work:
        folder = Path(work)
        inputs = example_files(folder/'entrega para revisar')
        before = {path.name:fingerprint(path) for path in inputs}
        require(len(before) == 5, 'the sample must have five inputs')
        with window(exe, ROOT, folder, version) as (screen, host, _, ready):
            try:
                editor = screen.control('Instrucción para el Director', 'Edit')
                editor.set_edit_text(OBJECTIVE)
                wait(lambda: editor.get_value() == OBJECTIVE, description='objective read back via UI Automation')
                choose_files(screen, host, inputs, title='Adjuntar archivos al hilo', button='Adjuntar archivos')
                expected_names = {'Incluir '+file for file in before}
                wait(lambda: expected_names.issubset(screen.names(visible_only=False).splitlines()),
                     description='five native files in the attachment inspector')
                screen.screenshot(out/'01-adjuntos.png')
                screen.press_space(screen.reveal_button('Inspector'))
                screen.button(r'^(?:↑\s*)?Enviar\s*·\s*0 intentos$', regex=True)
                wait(lambda: ANSWER in screen.names(), description='both expected values in the Director answer')
                screen.reveal_button(r'(?s).*especificacion\.pdf.*Pág\. 2.*', regex=True).invoke()
                wait(lambda: 'Página 2 de especificacion.pdf' in screen.names(), description='rendered PDF page 2')
                screen.screenshot(out/'02-evidencia-pdf.png')
                screen.reveal_button(r'(?s).*manifiesto\.json.*Línea 4.*', regex=True).invoke()
                wait(lambda: 'Campos del JSON' in screen.names(visible_only=False)
                     and re.search(r'"response_sla_hours"\s*:\s*48\b', screen.names()),
                     description='the visible fourth line contains the actual JSON field and value')
                screen.screenshot(out/'03-evidencia-json.png')
                receipt = 'Comparar el plazo de primera respuesta'
                require(receipt not in screen.names(visible_only=False), 'local activity must start collapsed')
                activity = screen.reveal_button(r'(?s).*Actividad de la inspección.*', regex=True)
                screen.press_space(activity)
                # The comparison is the sixth receipt and can start below the
                # thread viewport. Its text enters the UIA tree on expansion.
                wait(lambda: receipt in screen.names(visible_only=False),
                     description='final comparison receipt exposed to accessibility')
                screen.screenshot(out/'04-actividad.png')
                screen.press_space(activity)
                wait(lambda: receipt not in screen.names(visible_only=False),
                     description='closing activity also removes receipt from the accessibility tree')
                screen.button('Ver adjuntos')
                screen.reveal_button(r'(?s)entrega\.zip.*Inventario del paquete.*', regex=True).invoke()
                screen.reveal_button('visual/movil.jpg').invoke()
                wait(lambda: screen.window.child_window(title='visual/movil.jpg', control_type='Image').is_visible()
                     and re.search(r'\b360\s*×\s*720\b', screen.names()) and 'entrega.zip · Inventario' in screen.names(),
                     description='real image decoded inside the ZIP')
                screen.button('Ampliar zoom')
                wait(lambda: re.search(r'\b125\s*%', screen.names()), description='image zoom applied')
                screen.screenshot(out/'05-paquete.png')
            except BaseException:
                screen.screenshot(out/'fallo.png')
                (out/'controles-al-fallar.txt').write_text(screen.names(), encoding='utf-8')
                raise
        record = frozen_report(folder, before)
        require(stored(folder) == ([],0,[]), 'local inspection consumed a model call or reservation')
        with window(exe, ROOT, folder, version) as (screen, host, _, _):
            wait(lambda: ANSWER in screen.names(), description='report restored after restarting Tauri')
        require(frozen_report(folder,before)['id'] == record['id'], 'report identity changed on restart')
        require(stored(folder) == ([],0,[]), 'reopen admitted unexpected work')
        require({path.name:fingerprint(path) for path in inputs} == before, 'source files changed')
        return {'version':version, 'exe_sha256':fingerprint(exe), 'ui':'Windows UI Automation and native multi-file picker',
                'sidecar':'production Python with isolated Windows desktop ledger', 'time_to_ready_seconds':round(ready,3),
                'inputs_sha256':before, 'report_id':record['id'], 'receipt_count':len(record['steps']),
                'verified':['five attachments','PDF page 2 at 24 h','JSON line 4 at 48 h','actual steps',
                            'ZIP image 360x720 at 125%','same report after host restart'],
                'attempts':0, 'model_calls':0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=False)
    verified = run(args.exe.resolve(strict=True), target)
    (target/'verification.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(verified, ensure_ascii=True))
