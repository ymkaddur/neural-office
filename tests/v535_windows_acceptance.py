"""Exercise the published GUI only through Windows accessibility and its real file picker."""
from contextlib import closing, contextmanager
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT))
from examples.multiformat.build_example import pdf_bytes
from neural_office.windows_job import Job
from tools.measure_v58_desktop import NativeWindow, choose_files
from tools.package_windows_pilot import HOST
from neural_office.measurements import job_cpu_seconds
from tools.measure_v5352_polished import completed_calls, repair_checks
from tools.measure_v5352_team import CASES, capture, grade
from e2e_v55_native import MODEL, MODEL_DIGEST, OLLAMA_VERSION, http, native_picker, prepare_ollama, readonly_counts, sha
from e2e_v55_native_uia import wait


VERSION = '5.35.2'
PDF = 'especificacion.pdf'
JSON = 'manifiesto.json'
COMPARE = 'Compara el plazo de primera respuesta.'
LITERAL = 'Busca «Primera respuesta» en especificacion.pdf.'
ASK = 'Según la especificación, ¿en cuántas horas llega la primera respuesta? Contesta con la cifra y su unidad.'
TEXT_ONLY = 'Guarda este encargo de prueba sin adjuntar documentos.'
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
    if objective == TEXT_ONLY:
        verify(not hashes and not refs and 'team' not in record and finding['rule'] == 'text_brief',
               'A written turn gained files, roles, or citations')
    elif objective == COMPARE:
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


def window_titles(screen):
    import win32gui
    expected = 'Neural Office · V' + VERSION
    host_title = win32gui.GetWindowText(screen.window.handle)
    documents = [item.element_info.name for item in screen.window.descendants(control_type='Document') if item.is_visible()]
    verify(host_title == expected, 'Unexpected Win32 title: ' + host_title)
    verify(documents == [expected], 'Unexpected WebView2 document titles: ' + repr(documents))
    return {'title': host_title, 'webview2_document_title': documents[0]}


@contextmanager
def desktop(exe, work, out, phase):
    import psutil
    from pywinauto import Desktop
    package = Path(os.environ['NO_PILOT_DIR']).resolve(strict=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith('NEURAL_OFFICE_') and k != 'PYTHONPATH'}
    env['WEBVIEW2_USER_DATA_FOLDER'] = str(work / 'webview')
    command = ['pwsh', '-NoProfile', '-NonInteractive', '-File', str(package / 'Start-NeuralOffice-Desktop.ps1'),
               '-Python', sys.executable, '-State', str(work / 'office.sqlite3')]
    started = time.monotonic()
    with Job('Local\\NeuralOfficePilot_' + uuid4().hex) as job:
        log = work / (phase + '-launcher.txt')
        with log.open('wb') as stream:
            code = job.start(command, env=env, log=stream).wait(timeout=45)
        message = log.read_text(encoding='utf-8-sig', errors='replace')
        verify(code == 0, 'Packaged launcher failed: ' + message[-600:])
        # A console-less starter can return no stdout on Windows. Identify the actual
        # window by its owner and the executable in this run's isolated package.
        def packaged_window():
            for window in Desktop(backend='win32').windows():
                if window.window_text() != 'Neural Office · V' + VERSION:
                    continue
                process = psutil.Process(window.process_id())
                if Path(process.exe()).samefile(exe):
                    return window.handle, process
            return None

        hwnd, host = wait(packaged_window, description='packaged host window')
        verify(Path(host.cwd()).samefile(package), 'Host outside the package')
        inherited = host.environ()
        verify(Path(inherited['NEURAL_OFFICE_ROOT']).samefile(package), 'Core outside the package')
        verify(Path(inherited['NEURAL_OFFICE_STATE']) == work / 'office.sqlite3', 'Unexpected state file')
        screen = NativeWindow(host, hwnd)
        process_handle = job.dll.OpenProcess(0x1000, False, host.pid)
        verify(bool(process_handle), 'Unable to verify packaged process membership')
        try:
            member = wintypes.BOOL()
            verify(job.dll.IsProcessInJob(process_handle, job.handle, ctypes.byref(member)) and member.value,
                   'The packaged host is outside the measured Windows job')
        finally:
            job.dll.CloseHandle(process_handle)
        screen.process_job = job
        try:
            wait(screen.core_ready, description='packaged core connected to WebView2')
            yield screen, host, time.monotonic() - started
        except Exception:
            screen.screenshot(out / (phase + '-fallo.png'))
            (out / (phase + '-controles.txt')).write_text(screen.names(visible_only=False), encoding='utf-8')
            raise
        finally:
            screen.close()
            wait(lambda: job.active() == 0, description='packaged desktop and its children closed')


def local(exe, work, state, out, receipt):
    work.mkdir()
    files = fixtures(work / 'entrega de prueba')
    hashes = {p.name: sha(p) for p in files}
    with desktop(exe, work, out, 'local') as (screen, host, ready):
        verify(screen.control('Instrucción para el Director', 'Edit').is_visible(), 'Missing composer')
        receipt.update(window_titles(screen), ready_seconds=round(ready, 2), pid=host.pid)
        screen.screenshot(out / '01-ventana.png')
        edit(screen, TEXT_ONLY)
        wait(lambda: screen.control(SEND, regex=True).is_enabled(), description='can send a written turn without a file')
        screen.button(SEND, regex=True)
        wait(lambda: 'Encargo guardado en este hilo' in screen.names(), description='the written turn has a visible receipt')
        receipt['written_turn'] = inspect_report(state, TEXT_ONLY, {})
        verify(readonly_counts(state) == {'states': [], 'calls': 0, 'attempts': 0}, 'A written turn charged work')
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
    distribution = prepare_ollama(tools, destination=work / 'ollama-distribution')
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


def resize_to_minimum(screen):
    import win32con
    import win32gui
    if screen.geometry()['maximized']:
        screen.maximize(False)
    geom = screen.geometry()
    handle = screen.window.handle
    left, top, right, bottom = win32gui.GetWindowRect(handle)
    _, _, old_width, old_height = win32gui.GetClientRect(handle)
    width, height = (round(size * geom['dpi'] / 96) for size in (760, 540))
    x, y = geom['monitor_work_area_px'][:2]
    win32gui.SetWindowPos(handle, 0, x + 8, y + 8, width + right - left - old_width,
                          height + bottom - top - old_height, win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
    wait(lambda: win32gui.GetClientRect(handle)[2:] == (width, height), description='minimum native client size')


def open_permission(screen, state):
    screen.button('Consultar al modelo')
    wait(lambda: screen.control('Modelo local', 'ComboBox').selected_text() == MODEL, description='real model in catalog')
    screen.button('Revisar permiso')
    wait(lambda: 'Autorizar una consulta' in screen.names(), description='visible approval before charging')
    verify(ASK in screen.names(visible_only=False) and PDF_QUOTE in screen.names(visible_only=False),
           'Approval lacks request or excerpt')
    verify(readonly_counts(state)['attempts'] == 0, 'Opening permission charged a reservation')


def check_first_frame(screen, screenshot):
    from pywinauto import Desktop
    # Observe without focusing, scrolling, invoking, or bringing the button into view.
    button = screen.control(r'^Autorizar y ejecutar.*', regex=True)
    dialog = screen.control('Autorizar una consulta', 'Window')
    screen.window.capture_as_image().save(screenshot)
    geom = screen.geometry()
    x, y = geom['client_origin_screen_px']
    width, height = geom['client_rectangle_px'][2:]
    rect = button.rectangle()
    bounds = [rect.left, rect.top, rect.right, rect.bottom]
    frame = dialog.rectangle()
    for area in ([x, y, x + width, y + height], geom['monitor_work_area_px'], [frame.left, frame.top, frame.right, frame.bottom]):
        verify(area[0] <= rect.left < rect.right <= area[2] and area[1] <= rect.top < rect.bottom <= area[3],
               f'Button outside the visible area: {bounds} / {area}')
    verify(rect.width() >= 70 and rect.height() >= 24 and button.is_enabled(), 'Inactive or clipped action')
    center = ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
    points = [center] + [(px, py) for px in (rect.left + 6, rect.right - 7) for py in (rect.top + 6, rect.bottom - 7)]
    desktop_ui = Desktop(backend='uia')
    for point in points:
        hit = desktop_ui.from_point(*point)
        ancestor = hit
        while ancestor is not None and ancestor != button and ancestor != dialog:
            ancestor = ancestor.parent()
        verify(ancestor == button, f'Point {point} hits {hit.element_info.name!r} instead of the action')
    return {'client_px': [width, height], 'button_screen_px': bounds, 'hit_points': points}


def model(exe, work, state, out, receipt):
    from pywinauto import keyboard, mouse
    from pywinauto.uia_defines import IUIA
    baseline = json.loads((out / 'local.json').read_bytes())
    verify(baseline['status'] == 'passed' and baseline['exe_sha256'] == sha(exe), 'Different app or failed baseline')
    with real_model(work), desktop(exe, work, out, 'modelo') as (screen, host, ready):
        wait(lambda: DETAIL in screen.names(), description='native restart reopened the named-source answer')
        receipt.update(window_titles(screen))
        edit(screen, ASK)
        open_permission(screen, state)
        receipt['initial_permission'] = check_first_frame(screen, out / '05-permiso.png')
        focus = lambda: IUIA().iuia.GetFocusedElement().CurrentName
        wait(lambda: focus() == 'Cerrar revisión', description='initial focus on the close button')
        keyboard.send_keys('{TAB}')
        wait(lambda: focus() == 'Detalles del permiso', description='scope and excerpts reachable by keyboard')
        keyboard.send_keys('+{TAB}')
        wait(lambda: focus() == 'Cerrar revisión', description='reverse keyboard navigation')
        keyboard.send_keys('{ESC}')
        wait(lambda: focus() == 'Consultar al modelo' and 'Autorizar una consulta' not in screen.names(),
             description='Escape returns focus to the thread')
        verify(readonly_counts(state)['attempts'] == 0, 'Dismissing the first permission charged work')
        receipt['escape_before_reservation'] = True
        resize_to_minimum(screen)
        open_permission(screen, state)
        receipt['minimum_permission'] = check_first_frame(screen, out / '05-permiso-minimo.png')
        mouse.click(coords=receipt['minimum_permission']['hit_points'][0])
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


def team_permission(screen, host, source, objective):
    from pywinauto import keyboard
    import win32gui
    screen.objective(objective)
    screen.button('Elegir archivo HTML')
    native_picker(host, source)
    wait(lambda: source.name in screen.names(), description='seven-role source captured')
    screen.button('Consultar al Director')
    wait(lambda: screen.control('Modelo local','ComboBox').selected_text() == MODEL, description='selected local model')
    screen.disclosure('Perfil acotado', True)
    selector = screen.control('Roles secuenciales','ComboBox')
    screen.window.set_focus()
    selector.set_focus()
    wait(lambda: win32gui.GetForegroundWindow()==screen.window.handle and selector.has_keyboard_focus(),
         timeout=5, description='team selector owns keyboard focus')
    keyboard.send_keys('{END}{TAB}', turn_off_numlock=False)
    wait(lambda: selector.selected_text()=='7 · Equipo completo', description='seven roles selected by keyboard')
    screen.reveal_button(r'^Revisar encargo.*', regex=True).invoke()
    permission = screen.control('Este es el encargo.', 'Window')
    def permission_matches():
        labels = words(' '.join(node.element_info.name for node in permission.descendants(control_type='Text')))
        return objective in labels and source.name in labels and '7 llamadas secuenciales' in labels
    wait(permission_matches, description='exact team objective, source and seven calls in the permission dialog')


def warm_turn(screen, host, work, state, out, previous_runtime, case, already_charged):
    source = work / ('imagen-y-formulario.html' if case == 'abierto' else 'formulario.html')
    raw, objective = CASES[case]
    source.write_bytes(raw)
    screen.reveal_button(r'^Preparar otro encargo.*', regex=True).invoke()
    team_permission(screen, host, source, objective)
    verify(readonly_counts(state)['attempts']==already_charged, 'Warm preview charged before consent')
    before = job_cpu_seconds(screen.process_job)
    screen.button(r'^Autorizar y ejecutar.*', regex=True)
    def accepted_repair():
        with database(state) as db:
            row = db.execute('SELECT id,state FROM attempts WHERE objective=?',(objective,)).fetchone()
        return row if row and row['state'] in ('ACCEPTED','FAILED','REJECTED','CANCELLED','RECOVERY_REQUIRED') else None
    accepted_turn = wait(accepted_repair, timeout=420, description='warm team accepted in the same project')
    verify(accepted_turn['state']=='ACCEPTED', 'Warm team failed')
    if case == 'abierto':
        screen.control('Recomendaciones del modelo local','Text')
    else:
        wait(lambda: 'Comentarios del modelo' in screen.names(visible_only=False),description='citation report rendered')
        screen.disclosure('Comentarios del modelo', True)
    goal, model_digest, calls = completed_calls(state, accepted_turn['id'])
    verify(goal==objective and model_digest==MODEL_DIGEST and all(c['runtime']==previous_runtime and c['resident']
           and c['reused'] for c in calls), 'The second approval did not use the same already-loaded private model')
    answer = calls[-1]['answer']
    checks = repair_checks(answer) if case == 'abierto' else grade(case, answer)
    verify(all(checks.values()), 'Incomplete literal integrated answer: '+answer)
    expected = list(json.loads(answer).values()) if case == 'abierto' else [json.loads(answer)]
    def displayed():
        names = words(screen.names(visible_only=False))
        return all(text in names for text in expected)
    wait(displayed,description='the exact model answer in the native document')
    cpu = job_cpu_seconds(screen.process_job) - before
    screen.screenshot(out/('08-director-reparaciones.png' if case == 'abierto' else '09-director-formulario.png'))
    return dict(cpu_s=cpu,attempt=accepted_turn['id'],model_digest=model_digest,source_sha256=sha(source),
                checks=checks,answer=answer,calls=calls,visible_in_report=True)


def team(exe, work, state, out, receipt):
    from neural_office.runner import ROLES
    work.mkdir()
    source = work / 'prueba-equipo.html'
    browser_check = receipt['phase'] == 'team-browser'
    if browser_check:
        source.write_bytes(b'<html lang="es">\n<title>Demo</title>\n<body>\n  <img src="primera.jpg">\n'
                           b'  <img src="decorativa.jpg" alt="">\n  <img src="ultima.jpg">\n</body></html>')
        objective = 'Indica el código y todas las líneas de la imagen sin descripción. Añade cómo contrastarlas en el navegador.'
        positions = [(4,3),(6,3)]
    else:
        source.write_bytes(b'<html lang="es"><title>Prueba</title>\n<img src="foto.png">\n</html>')
        objective = 'Indica el código y la línea de la imagen sin descripción.'
        positions = [(2,1)]
    with real_model(work), desktop(exe, work, out, 'equipo') as (screen, host, _):
        receipt.update(window_titles(screen))
        screen.open_html()
        team_permission(screen, host, source, objective)
        verify(readonly_counts(state)['attempts']==0, 'Early team reservation')
        screen.button(r'^Autorizar y ejecutar.*', regex=True)
        def terminal():
            states = readonly_counts(state)['states']
            return states if any(s in ('ACCEPTED','REJECTED','CANCELLED','FAILED','RECOVERY_REQUIRED') for s in states) else None
        verify(wait(terminal, timeout=450, description='seven-role terminal receipt') == ['ACCEPTED'],
               'The team did not deliver')
        with database(state) as db:
            attempt, = db.execute('SELECT id,objective,profile,snapshot_sha,artifact FROM attempts').fetchall()
            rows = db.execute('SELECT role,state,payload_sha,response FROM calls WHERE attempt=? ORDER BY seq',
                              (attempt['id'],)).fetchall()
        verify(attempt['objective']==objective and attempt['snapshot_sha']==sha(source), 'Team source or goal changed')
        verify(json.loads(attempt['profile']).get('execution_policy')=='local-team-v1', 'Team approval used another policy')
        verify([r['role'] for r in rows]==list(ROLES) and len({r['payload_sha'] for r in rows})==7, 'Role chain changed')
        receipt['calls'] = []
        for row in rows:
            response = json.loads(row['response'])
            stats = response['_neural_office_execution']
            verify(row['state']=='DONE' and response['done'] and stats['model_digest']==MODEL_DIGEST
                   and stats['owned_job'] and stats['eval_count']>0 and response['message']['content'].strip(),
                   'Missing model output or execution receipt')
            receipt['calls'].append({'role':row['role'],'request':row['payload_sha'],'tokens':stats['eval_count'],
                                     'mode':stats['mode'],'size_vram':stats['size_vram'],
                                     'model_identity_check':stats['model_identity_check']})
        artifact = json.loads(attempt['artifact'])
        receipt['integrator_answer'] = json.loads(rows[-1]['response'])['message']['content']
        receipt['model_digest'] = MODEL_DIGEST
        expected = [{'code':'IMAGE_ALT_MISSING','line':line,'column':column} for line,column in positions]
        verify(artifact['requested_rule']=='IMAGE_ALT_MISSING' and artifact['findings']==expected, 'Incorrect delivered location')
        answer = json.loads(receipt['integrator_answer'])
        if browser_check:
            verify(answer.startswith('IMAGE_ALT_MISSING, líneas 4, 6. ') and 'dom' in answer.casefold()
                   and 'accesibilidad' in answer.casefold(), 'The real team omitted a source location or the browser check')
        else:
            verify(answer=='IMAGE_ALT_MISSING, línea 2, columna 1', 'The actual model cited a different location')
        wait(lambda: 'Comentarios del modelo' in screen.names(visible_only=False), description='team report rendered')
        screen.disclosure('Comentarios del modelo', True)
        displayed = ' '.join(receipt['integrator_answer'].split())
        wait(lambda: displayed in ' '.join(screen.names(visible_only=False).split()),
             description='actual integrator answer in the expanded native report')
        receipt['integrator_in_expanded_report'] = True
        screen.screenshot(out/('08-equipo-navegador.png' if browser_check else '07-equipo.png'))
        receipt.update(objective=objective, source_sha256=sha(source), findings=artifact['findings'])
        if not browser_check:
            first = completed_calls(state, attempt['id'])[2]
            verify(not any(c['reused'] or c['resident'] for c in first), 'Cold setup was already a warm team')
            for charged,(key,case) in enumerate((('warm_repair','abierto'),('warm_control','control')),start=1):
                receipt[key] = warm_turn(screen,host,work,state,out,first[0]['runtime'],case,charged)
            for key,case in (('warm_repair','abierto'),('warm_control','control')):
                turn = receipt[key]
                reference = capture(ROOT,'warm',case,out/('warm-powershell-'+case+'.json'),boundaries_only=True)
                verify(reference['model_loaded_before_query'] and reference['digest']==turn['model_digest']
                       and reference['source_sha256']==turn['source_sha256'], 'Incomparable native PowerShell reference')
                turn['terminal_cpu_s'] = reference['query_cpu_s']
                turn['ratio'] = turn['cpu_s'] / reference['query_cpu_s']
                turn['within_1_3'] = turn['ratio'] <= 1.3
        receipt['status'] = 'passed'


def main():
    if sys.platform != 'win32' or os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_OS') != 'Windows':
        raise SystemExit('This acceptance test requires an isolated Windows Actions runner')
    phase, = sys.argv[1:]
    functions = {'local': local, 'model': model, 'team': team, 'team-browser': team}
    out = ROOT / 'v535-package-evidence'
    out.mkdir(exist_ok=True)
    work = Path(os.environ['RUNNER_TEMP']) / ('v535-native-' + (phase if phase in ('team','team-browser') else 'office'))
    package = Path(os.environ['NO_PILOT_DIR']).resolve(strict=True)
    verify(not package.is_relative_to(ROOT), 'Package test must run outside the checkout')
    exe = (package / HOST).resolve(strict=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    verify((package / 'SOURCE_COMMIT').read_text(encoding='ascii').strip() == commit, 'Unexpected package source')
    verify(sha(exe) == sha(ROOT / HOST), 'Packaged host differs from compiled executable')
    if phase == 'local':
        manifest = dict(line.split('  ', 1)[::-1] for line in (package / 'SHA256SUMS').read_text(encoding='utf-8').splitlines())
        actual = {p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*') if p.is_file() and p != package / 'SHA256SUMS'}
        verify(actual == manifest, 'The clean extraction differs from the package manifest')
    receipt = {'phase': phase, 'status': 'failed', 'product_commit': commit, 'test_commit': os.environ['GITHUB_SHA'],
               'run_id': os.environ['GITHUB_RUN_ID'], 'version': VERSION, 'exe_sha256': sha(exe), 'packaged_launcher': True,
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
