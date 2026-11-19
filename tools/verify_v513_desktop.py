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
                wait(lambda: all('Incluir '+file in screen.names() for file in before),
                     description='five selected native files visible')
                screen.screenshot(out/'01-adjuntos.png')
                screen.button('Inspeccionar · 0 intentos')
                wait(lambda: 'Hay un plazo que no coincide' in screen.names(), description='local finding')
                screen.button(r'.*especificacion\.pdf.*Pág\. 2.*', regex=True)
                wait(lambda: 'Página 2 de especificacion.pdf' in screen.names(), description='rendered PDF page 2')
                screen.screenshot(out/'02-evidencia-pdf.png')
                screen.button(r'.*manifiesto\.json.*Línea 4.*', regex=True)
                wait(lambda: 'Campos del JSON' in screen.names() and 'response_sla_hours' in screen.names(),
                     description='JSON source line inspected')
                screen.screenshot(out/'03-evidencia-json.png')
                details = screen.control(r'Actividad de la inspección.*', regex=True)
                details.click_input()
                wait(lambda: 'Comparar el plazo de primera respuesta' in screen.names(), description='actual inspection steps')
                screen.screenshot(out/'04-actividad.png')
                screen.button('Ver adjuntos')
                screen.button(r'entrega\.zip.*Inventario del paquete.*', regex=True)
                screen.button(r'.*visual/\s*movil\.jpg.*', regex=True)
                wait(lambda: '360 × 720' in screen.names() and 'Inventario del paquete' in screen.names(),
                     description='real image decoded inside the ZIP')
                screen.button('Ampliar zoom')
                wait(lambda: '125 %' in screen.names(), description='image zoom applied')
                screen.screenshot(out/'05-paquete.png')
            except BaseException:
                screen.screenshot(out/'fallo.png')
                (out/'controles-al-fallar.txt').write_text(screen.names(), encoding='utf-8')
                raise
        record = frozen_report(folder, before)
        require(stored(folder) == ([],0,[]), 'local inspection consumed a model call or reservation')
        with window(exe, ROOT, folder, version) as (screen, host, _, _):
            screen.button(re.escape(OBJECTIVE)+'.*', regex=True)
            wait(lambda: 'Hay un plazo que no coincide' in screen.names(), description='report restored after restarting Tauri')
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
