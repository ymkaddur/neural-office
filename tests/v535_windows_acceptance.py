"""Exercise the published GUI only through Windows accessibility and its real file picker."""
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys

ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT))
from examples.multiformat.build_example import pdf_bytes
from tools.measure_v58_desktop import choose_files
from tools.verify_v510_desktop import window
from e2e_v55_native import MODEL, MODEL_DIGEST, OLLAMA_VERSION, http, prepare_ollama, readonly_counts, sha
from e2e_v55_native_uia import wait


VERSION = '5.35.1'
PDF = 'especificacion.pdf'
JSON = 'manifiesto.json'
COMPARE = 'Compara el plazo de primera respuesta.'
LITERAL = 'Busca «Primera respuesta» en especificacion.pdf.'
ASK = 'Según la especificación, ¿en cuántas horas llega la primera respuesta? Contesta con la cifra y su unidad.'
PDF_QUOTE = 'Primera respuesta en 31 horas.'
TITLE = '31 h en la especificación, 57 h en la entrega'
DETAIL = '«Primera respuesta» aparece en el texto recuperado de especificacion.pdf.'
SEND = r'^(?:↑\s*)?Enviar\s*·\s*0 intentos$'


def verify(condition, message):
    if not condition:
        raise AssertionError(message)


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def fixtures(folder):
    folder.mkdir()
    pdf = folder / PDF
    pdf.write_bytes(pdf_bytes([['Portal de pruebas', 'Especificacion'], ['Plazo de soporte', PDF_QUOTE]]))
    manifest = folder / JSON
    manifest.write_text('{\n  "servicio": "soporte",\n  "comentario": "Primera respuesta en 57 horas.",\n'
                        '  "response_sla_hours": 57\n}\n', encoding='utf-8')
    return [manifest, pdf]


def database(path):
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    db.execute('BEGIN')
    return closing(db)


def inspect_report(state, objective, hashes):
    with database(state.with_name(state.name + '.attachments.sqlite3')) as db:
        captures = {r['name']: r['sha256'] for r in db.execute('SELECT name,sha256 FROM captures')}
        verify(captures == hashes, 'The captured bytes differ from the two files selected in the dialog')
        reports = [r for r in db.execute('SELECT id,payload,payload_sha FROM reports')
                   if json.loads(r['payload'])['objective'] == objective]
    verify(len(reports) == 1, 'The exact request must have a single durable result')
    saved = reports[0]
    verify(hashlib.sha256(saved['payload'].encode()).hexdigest() == saved['payload_sha'], 'Report digest')
    record = json.loads(saved['payload'])
    verify(record['id'] == saved['id'] and record['reservations'] == record['model_calls'] == 0, 'Local cost or identity')
    verify({a['name']: a['sha256'] for a in record['attachments']} == hashes, 'Report attachment identity')
    finding, = record['findings']
    refs = {r['name']: r for r in finding['sources']}
    verify(all(ref['sha256'] == hashes[name] for name, ref in refs.items()), 'Citation belongs to different bytes')
    if objective == COMPARE:
        verify(finding['rule'] == 'first_response_hours' and finding['status'] == 'mismatch', 'Wrong comparison')
        verify(set(refs) == {PDF, JSON} and refs[PDF]['page'] == 2 and refs[PDF]['value'] == 31, 'PDF locator or hours')
        verify(refs[JSON]['line'] == 4 and refs[JSON]['pointer'] == '/response_sla_hours' and refs[JSON]['value'] == 57,
               'Manifest locator or hours')
    else:
        verify(objective == LITERAL and finding['rule'] == 'literal' and finding['status'] == 'observed',
               'Wrong rule for named source')
        verify(set(refs) == {PDF} and refs[PDF]['page'] == 2 and refs[PDF]['quote'] == PDF_QUOTE,
               'The Director used the wrong file for the named request')
    return {'id': record['id'], 'objective': objective, 'rule': finding['rule'], 'sources': list(refs.values()),
            'model_calls': record['model_calls'], 'reservations': record['reservations']}


def edit(screen, text):
    field = screen.control('Instrucción para el Director', 'Edit')
    field.set_edit_text(text)
    wait(lambda: field.get_value() == text, description='the composer acknowledges the exact new objective')


def words(text):
    # WebView2 exposes interpolated React numbers and their adjacent labels as separate UIA text nodes.
    return ' '.join(text.split())


@contextmanager
def desktop(exe, work, out, phase):
    with window(exe, ROOT, work, VERSION) as (screen, host, job, ready):
        try:
            verify(Path(host.exe()).samefile(exe), 'Different live executable')
            yield screen, host, ready
        except Exception:
            screen.screenshot(out / (phase + '-fallo.png'))
            (out / (phase + '-controles.txt')).write_text(screen.names(visible_only=False), encoding='utf-8')
            raise


def local(exe, work, state, out, receipt):
    work.mkdir()
    files = fixtures(work / 'entrega de prueba')
    hashes = {p.name: sha(p) for p in files}
    with desktop(exe, work, out, 'local') as (screen, host, ready):
        import win32gui
        title = win32gui.GetWindowText(screen.window.handle)
        verify(title == 'Neural Office · V' + VERSION, 'Window title differs from the release')
        verify(screen.control('Instrucción para el Director', 'Edit').is_visible(), 'Missing composer')
        receipt.update(title=title, ready_seconds=round(ready, 2), pid=host.pid)
        screen.screenshot(out / '01-ventana.png')
        choose_files(screen, host, files, title='Adjuntar archivos al hilo', button='^Adjuntar archivos$')
        wanted = {'Incluir ' + p.name for p in files}
        wait(lambda: wanted <= set(screen.names(visible_only=False).splitlines()), description='two native selections in inspector')
        for label in wanted:
            verify(screen.control(label, 'CheckBox').get_toggle_state() == 1, 'Attachment is not selected: ' + label)
        screen.screenshot(out / '02-adjuntos.png')
        receipt.update(picker_dialogs=1, selected_files=hashes)
        inspector = screen.reveal_button('Inspector')
        screen.press_space(inspector)
        wait(lambda: not wanted.intersection(screen.names(visible_only=False).splitlines()),
             description='closing the inspector returns the thread to its full width')
        receipt['answers'] = []
        for index, (question, answer) in enumerate(((COMPARE, TITLE), (LITERAL, DETAIL)), 3):
            verify(answer not in screen.names(), 'Answer visible before sending the request')
            edit(screen, question)
            screen.button(SEND, regex=True)
            wait(lambda: answer in screen.names(), description='visible Director answer: ' + answer)
            wait(lambda: 'Comprobación local · 0 llamadas al modelo' in words(screen.names()),
                 description='zero-model disclosure next to the Director')
            saved = inspect_report(state, question, hashes)
            receipt['answers'].append({**saved, 'visible_answer': answer})
            screen.screenshot(out / (str(index).zfill(2) + '-director.png'))
        verify(readonly_counts(state) == {'states': [], 'calls': 0, 'attempts': 0}, 'Free inspection charged work')
    verify({p.name: sha(p) for p in files} == hashes, 'The app modified the original attachments')
    receipt['status'] = 'passed'


@contextmanager
def real_model(work):
    tools = Path(os.environ['NO_E2E_TOOLS'])
    distribution = prepare_ollama(tools)
    with socket.socket() as unused:
        unused.bind(('127.0.0.1', 11434))
    os.environ.update(PATH=str(distribution) + os.pathsep + os.environ['PATH'], OLLAMA_HOST='127.0.0.1:11434',
                      OLLAMA_MODELS=str(work / 'models'), OLLAMA_NO_CLOUD='1')
    with subprocess.Popen([str(distribution / 'ollama.exe'), 'serve'], stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          creationflags=subprocess.CREATE_NO_WINDOW) as server:
        try:
            wait(lambda: http('GET', 'http://127.0.0.1:11434/api/version', timeout=3).get('version') == OLLAMA_VERSION,
                 description='pinned local Ollama ready')
            pull = http('POST', 'http://127.0.0.1:11434/api/pull', {'name': MODEL, 'stream': False}, timeout=600)
            verify(pull.get('status') == 'success', 'Model download did not complete')
            catalog = http('GET', 'http://127.0.0.1:11434/api/tags')['models']
            verify([(m['name'], m['digest']) for m in catalog] == [(MODEL, MODEL_DIGEST)], 'Model digest changed')
            yield
        finally:
            server.terminate()
            server.wait(timeout=20)


def accepted(state, inspection):
    with database(state) as db:
        attempt, = db.execute('SELECT id,state,objective,profile,snapshot FROM attempts').fetchall()
        call, = db.execute('SELECT attempt,role,state FROM calls').fetchall()
        output, = db.execute('SELECT attempt,role,content,content_sha FROM outputs').fetchall()
    profile = json.loads(attempt['profile'])
    verify(attempt['state'] == 'ACCEPTED' and attempt['objective'] == ASK and profile['mode'] == 'ollama-owned'
           and profile['model_digest'] == MODEL_DIGEST, 'Unaccepted or substituted model call')
    snapshot = json.loads(attempt['snapshot'])
    fragment, = snapshot['fragments']
    verify(snapshot['inspection_id'] == inspection and fragment['name'] == PDF and fragment['page'] == 2
           and fragment['quote'] == PDF_QUOTE, 'Model received a different source or inspection')
    verify(call['attempt'] == output['attempt'] == attempt['id'] and call['role'] == output['role'] == 'director'
           and call['state'] == 'DONE', 'The Director did not finish exactly one call')
    answer = output['content'].strip()
    verify(bool(answer) and hashlib.sha256(output['content'].encode()).hexdigest() == output['content_sha'],
           'Empty or mismatched model output')
    return {'answer': answer, 'answer_sha256': output['content_sha'], 'attempt_id': attempt['id'],
            'inspection_id': inspection, 'fragment': fragment, 'model': MODEL, 'model_digest': MODEL_DIGEST,
            'mode': profile['mode'], 'state': attempt['state']}


def model(exe, work, state, out, receipt):
    baseline = json.loads((out / 'local.json').read_bytes())
    verify(baseline['status'] == 'passed' and baseline['exe_sha256'] == sha(exe), 'Different app or failed baseline')
    with real_model(work), desktop(exe, work, out, 'modelo') as (screen, host, ready):
        wait(lambda: DETAIL in screen.names(), description='native restart reopened the named-source answer')
        edit(screen, ASK)
        screen.button('Consultar al modelo')
        wait(lambda: screen.control('Modelo local', 'ComboBox').selected_text() == MODEL, description='real model in catalog')
        screen.button('Revisar permiso')
        wait(lambda: 'Autorizar una consulta' in screen.names(), description='visible approval before charging')
        verify(ASK in screen.names() and PDF_QUOTE in screen.names(), 'Approval lacks request or excerpt')
        verify(readonly_counts(state)['attempts'] == 0, 'Opening permission charged a reservation')
        screen.screenshot(out / '05-permiso.png')
        screen.button(r'^Autorizar y ejecutar.*', regex=True)
        terminal = {'ACCEPTED', 'FAILED', 'CANCELLED', 'REJECTED', 'RECOVERY_REQUIRED'}
        def final_state():
            counts = readonly_counts(state)
            return counts if any(s in terminal for s in counts['states']) else None
        final = wait(final_state, timeout=340, description='owned inference completed')
        receipt['counts'] = final
        verify(final == {'states': ['ACCEPTED'], 'attempts': 1, 'calls': 1}, 'Director attempt outcome: ' + str(final))
        response = accepted(state, baseline['answers'][-1]['id'])
        receipt.update(response)
        answer = ' '.join(response['answer'].split())
        wait(lambda: answer in ' '.join(screen.names(visible_only=False).split()), description='exact answer in the thread')
        # The receipt button follows the answer in the thread. Focusing it scrolls this part into view.
        screen.reveal_button('Ver recibo de la consulta')
        wait(lambda: answer in ' '.join(screen.names().split()), description='visible model output after scrolling')
        screen.screenshot(out / '06-respuesta-modelo.png')
        receipt['answer_in_native_ui'] = True
        receipt['matches_expected_hours'] = bool(re.search(r'\b(?:31|treinta y (?:una|un))\s*(?:h(?:oras?|rs?)?|hours?)\b',
                                                          answer, flags=re.I)) and not re.search(r'\b57\b', answer)
    verify(receipt['matches_expected_hours'], 'The real model answer did not give the requested 31 hours')
    receipt['status'] = 'passed'


def main():
    if sys.platform != 'win32' or os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_OS') != 'Windows':
        raise SystemExit('This acceptance test requires an isolated Windows Actions runner')
    phase, = sys.argv[1:]
    functions = {'local': local, 'model': model}
    out = ROOT.parent / 'evidence'
    out.mkdir(exist_ok=True)
    work = Path(os.environ['RUNNER_TEMP']) / 'v535-native-office'
    exe = (ROOT / 'desktop/src-tauri/target/release/neural-office-desktop.exe').resolve(strict=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    verify(commit == os.environ['PRODUCT_SHA'], 'Application differs from pinned source')
    receipt = {'phase': phase, 'status': 'failed', 'product_commit': commit, 'test_commit': os.environ['GITHUB_SHA'],
               'run_id': os.environ['GITHUB_RUN_ID'], 'version': VERSION, 'exe_sha256': sha(exe),
               'webview2': json.loads((Path(os.environ['NO_E2E_TOOLS']) / 'tools.json').read_text(encoding='utf-8-sig'))}
    try:
        functions[phase](exe, work, work / 'office.sqlite3', out, receipt)
    except Exception as error:
        receipt['error'] = str(error)
        raise
    finally:
        save(out / (phase + '.json'), receipt)
        print(json.dumps(receipt, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
