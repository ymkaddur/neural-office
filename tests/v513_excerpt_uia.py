"""Native UIA regression for consent, selected excerpts, one reservation and one owned call."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from examples.multiformat.build_example import example_files
from neural_office.ledger import canonical
from neural_office.runner import prompt


PROJECT = 'Portal de extractos'
OBJECTIVE = 'Compara los dos plazos. Indica qué dato debe confirmar la persona responsable.'
SCOPE = 'local-inspection-excerpts-v1'
SOURCE_PDF = 'especificacion.pdf'
SOURCE_JSON = 'manifiesto.json'
PDF_QUOTE = 'Primera respuesta en 24 horas.'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_only(path):
    connection = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    return closing(connection)


def counts(state):
    with read_only(state) as db:
        # One read transaction keeps the attempt and call counts at the same snapshot.
        db.execute('BEGIN')
        project = db.execute('SELECT state FROM attempts WHERE project=? ORDER BY ordinal', (PROJECT,)).fetchall()
        local_calls = db.execute('SELECT COUNT(*) FROM calls c JOIN attempts a ON a.id=c.attempt WHERE a.project=?',
                                 (PROJECT,)).fetchone()[0]
        total = db.execute('SELECT (SELECT COUNT(*) FROM attempts),(SELECT COUNT(*) FROM calls)').fetchone()
        return {'states': [row[0] for row in project], 'calls': local_calls,
                'global_attempts': total[0], 'global_calls': total[1]}


def static_oracle(state, inputs):
    with read_only(state.with_name(state.name+'.attachments.sqlite3')) as db:
        row, = db.execute('SELECT id,payload,payload_sha FROM reports WHERE project=? AND thread=?',
                          (PROJECT, 'main')).fetchall()
        captured = {item['name']: (item['id'], item['sha256']) for item in
                    db.execute('SELECT id,name,sha256 FROM captures WHERE project=? AND thread=?',(PROJECT,'main'))}
    assert {p.name:sha(p.read_bytes()) for p in inputs} == {name:data[1] for name,data in captured.items()}
    assert sha(row['payload'].encode()) == row['payload_sha']
    record = json.loads(row['payload'])
    assert (record['id'],record['objective'],record['reservations'],record['model_calls']) == (row['id'],OBJECTIVE,0,0)
    finding, = [item for item in record['findings'] if item['rule']=='first_response_hours']
    assert finding['status']=='mismatch' and len(finding['sources'])==2
    # Values, locators and text were defined by the synthetic documents, independently of the model.
    pdf = {'name':SOURCE_PDF,'quote':PDF_QUOTE,'page':2,'value':24,'unit':'h'}
    manifest = next(p for p in inputs if p.name==SOURCE_JSON).read_text(encoding='utf-8')
    line = manifest.splitlines()[3]
    assert json.loads(manifest)['response_sla_hours']==48 and 'response_sla_hours' in line
    field = {'name':SOURCE_JSON,'quote':'48','line':4,'column':line.index('48')+1,
             'pointer':'/response_sla_hours','value':48,'unit':'h'}
    for expected, observed in zip((pdf,field),finding['sources']):
        expected['attachment_id'],expected['sha256']=captured[expected['name']]
        assert all(observed.get(key)==value for key,value in expected.items())
    return row['id'], [pdf,field]


def accepted_receipt(state, model, model_digest, inspection, fragments):
    with read_only(state) as db:
        db.execute('BEGIN')
        row, = db.execute('SELECT * FROM attempts WHERE project=?',(PROJECT,)).fetchall()
        call, = db.execute('SELECT role,state,payload_sha FROM calls WHERE attempt=?',(row['id'],)).fetchall()
        answer, = db.execute('SELECT role,content,content_sha FROM outputs WHERE attempt=?',(row['id'],)).fetchall()
    profile=json.loads(row['profile'])
    assert (row['state'],row['ordinal'],row['objective'],profile['model'],profile['model_digest'],
            profile['mode'],profile['roles']) == ('ACCEPTED',1,OBJECTIVE,model,model_digest,'ollama-owned',1)
    snapshot=bytes(row['snapshot'])
    assert json.loads(snapshot)=={'scope':SCOPE,'project_id':PROJECT,'thread_id':'main',
                                  'inspection_id':inspection,'fragments':fragments}
    assert profile['analysis_scope']==SCOPE and profile['inspection_id']==inspection and profile['thread_id']=='main'
    assembled=prompt({'snapshot':snapshot,'profile':profile,'objective':OBJECTIVE,'outputs':[]},'director')
    body=canonical(assembled).encode()
    material=json.loads(assembled['messages'][1]['content'])
    assert (set(material)=={'role','objective','scope','authorized_fragments'} and
            material['authorized_fragments']==fragments and material['role']=='director' and
            material['objective']==OBJECTIVE and len(assembled['messages'])==2 and 'tools' not in assembled)
    assert (call['role'],call['state'],call['payload_sha'])==('director','DONE',sha(body))
    raw=bytes(row['artifact'])
    assert sha(raw)==row['artifact_sha'] and sha(snapshot)==row['snapshot_sha']
    report=json.loads(raw)
    assert (report['scope'],report['source_sha256'],report['inspection_id'],report['thread_id'])==(
        SCOPE,sha(snapshot),inspection,'main')
    assert report['authorized_fragments']==fragments and report['findings']==[]
    assert report['model_commentary_status']=='UNVERIFIED_ASSISTANCE' and report['role_outputs']==[dict(answer)]
    assert answer['role']=='director' and answer['content'].strip() and sha(answer['content'].encode())==answer['content_sha']
    verdict=json.loads(row['verdict'])
    assert verdict['passed'] and verdict['artifact_sha256']==sha(raw) and all(verdict['checks'].values())
    return {'id':row['id'],'source_sha256':sha(snapshot),'report_sha256':sha(raw),'input_sha256':sha(body),
            'input_bytes':len(body),'answer_sha256':answer['content_sha'],'model':model,'model_digest':model_digest,
            'inspection_id':inspection,'project':PROJECT,'thread':'main','fragments':fragments},answer['content']


def run_excerpt_ui(screen, host, state, work, output, model, model_digest, evidence):
    """Run inside the already-provisioned CI Windows instance. Only UI actions can mutate it."""
    from e2e_v55_native_uia import wait
    from tools.measure_v58_desktop import choose_files
    from neural_office.desktop_service import MAX_MODELS
    from pywinauto import keyboard
    import win32gui

    track=evidence['excerpt_ui']={'surface':'Windows UI Automation, native multi-file picker, owned Ollama',
                                  'project':PROJECT,'checkpoints':{},'stage':'setup'}
    starting=counts(state)
    assert starting['states']==[] and starting['calls']==0,'EXCERPT_PROJECT_NOT_FRESH'
    track['checkpoints']['before']=starting
    folder=work/'extractos sinteticos'
    assert not folder.exists(),'EXCERPT_INPUT_DIRECTORY_ALREADY_USED'
    inputs=example_files(folder)
    hashes={p.name:sha(p.read_bytes()) for p in inputs}
    try:
        if 'Instrucción para el Director' not in screen.names().splitlines():
            screen.button('Volver al hilo' if 'Volver al hilo' in screen.names().splitlines() else 'Nuevo hilo')
        screen.button('Crear otro proyecto')
        project=screen.control('Nombre del proyecto','Edit')
        project.set_edit_text(PROJECT)
        wait(lambda:project.get_value()==PROJECT,description='new excerpt project name acknowledged')
        screen.button('Abrir proyecto')
        wait(lambda:PROJECT in screen.names() and 'Instrucción para el Director' in screen.names().splitlines(),
             description='new project is the active thread')
        editor=screen.control('Instrucción para el Director','Edit')
        editor.set_edit_text(OBJECTIVE)
        wait(lambda:editor.get_value()==OBJECTIVE,description='excerpt objective read back')
        track['stage']='native_picker_and_free_inspection'
        choose_files(screen,host,inputs,title='Adjuntar archivos al hilo',button='Adjuntar archivos')
        wait(lambda:{'Incluir '+name for name in hashes}<=set(screen.names(visible_only=False).splitlines()),
             description='all five user-selected sources represented')
        screen.button('Inspeccionar · 0 intentos')
        wait(lambda:'Hay un plazo que no coincide' in screen.names(),description='discrepancy before any inference')
        inspection,fragments=static_oracle(state,inputs)
        assert counts(state)==starting
        track.update(inputs_sha256=hashes,inspection_id=inspection)

        def review_permission():
            screen.button('Consultar al modelo')
            select=screen.control('Modelo local','ComboBox')
            if select.selected_text()!=model:
                screen.window.set_focus()
                select.set_focus()
                def key(stroke):
                    wait(lambda:select.has_keyboard_focus() and win32gui.GetForegroundWindow()==screen.window.handle,
                         timeout=4,description='owned combobox holds Windows keyboard focus')
                    keyboard.send_keys(stroke,turn_off_numlock=False)
                # The installed catalog can contain several models. Walk the collapsed HTML
                # select using ordinary Windows input, and inspect every change through UIA.
                key('{HOME}')
                for _ in range(MAX_MODELS):
                    current=select.selected_text()
                    if current==model:
                        break
                    key('{DOWN}')
                    wait(lambda:select.selected_text()!=current,timeout=3,description='installed-model selection advanced')
            wait(lambda:select.selected_text()==model,description='installed model choice acknowledged')
            screen.button('Revisar permiso')
            wait(lambda:screen.approval_shows_balance(2),description='fresh project 3 to 2 displayed')
            dialog=screen.window.child_window(title='Este es el encargo.',control_type='Window').wrapper_object()
            fields=[node.element_info.name for node in dialog.descendants(control_type='Text')]
            visible=' '.join(' '.join(fields).split())
            assert all(s in visible for s in (PROJECT,OBJECTIVE,model,'Extractos de la entrega','Hasta 1 llamada',
                                             'Fragmentos que recibirá el modelo',SOURCE_PDF,SOURCE_JSON,PDF_QUOTE))
            assert '48' in fields and not any(p.name in visible for p in inputs if p.name not in (SOURCE_PDF,SOURCE_JSON))

        track['stage']='dismiss_permission'
        review_permission()
        assert counts(state)==starting
        screen.screenshot(output/'07-extractos-permiso.png')
        screen.reveal_button('Volver al encargo').invoke()
        wait(lambda:'Este es el encargo.' not in screen.names().splitlines() and 'Consultar al modelo' in screen.names(),
             description='dismissed permission returns to captured report')
        track['checkpoints']['dismissed']=counts(state)
        assert track['checkpoints']['dismissed']==starting
        track['stage']='fresh_permission_and_model_delivery'
        review_permission()
        assert counts(state)==starting
        began=time.monotonic()
        screen.reveal_button('Autorizar y ejecutar.*',regex=True).invoke()
        def completed():
            observed=counts(state)
            if observed['states'] and observed['states'][-1] in ('ACCEPTED','CANCELLED','REJECTED','FAILED','RECOVERY_REQUIRED'):
                return observed
            return None
        final=wait(completed,timeout=340,description='excerpt attempt reached an authoritative terminal/recovery state')
        track['authorization_to_terminal_seconds']=round(time.monotonic()-began,3)
        track['checkpoints']['delivered']=final
        assert final=={'states':['ACCEPTED'],'calls':1,'global_attempts':starting['global_attempts']+1,
                       'global_calls':starting['global_calls']+1},'EXCERPT_DELIVERY_OR_CHARGE_MISMATCH'
        receipt,answer=accepted_receipt(state,model,model_digest,inspection,fragments)
        track['receipt']=receipt
        track['stage']='visible_reply_and_receipts'
        screen.tab('Informe')
        wait(lambda:'Comentario sobre la entrega' in screen.names() and
             ' '.join(answer.split()) in ' '.join(screen.names(visible_only=False).split()),
             description='exact returned commentary on report tab')
        wait(lambda:'2 intentos disponibles' in screen.names(),description='selected project balance after one charge')
        screen.disclosure('Fuentes que recibió el modelo',expanded=True)
        wait(lambda:all(f['quote'] in screen.names(visible_only=False).splitlines() for f in fragments),
             description='same two excerpts displayed with the response')
        screen.screenshot(output/'08-extractos-entrega.png')
        screen.tab('Actividad')
        def activity_receipt():
            # WebView exposes count and noun as distinct text nodes.
            content=' '.join(screen.names().split())
            return all(value in content for value in ('Respuesta registrada',model,'1 llamada autorizada'))
        wait(activity_receipt,description='one completed Director call on activity tab')
        screen.tab('Evidencia y alcance')
        wait(lambda:all(receipt[k] in screen.names(visible_only=False) for k in
                        ('id','model_digest','source_sha256','report_sha256')),description='visible receipt fingerprints match SQLite')
        screen.screenshot(output/'09-extractos-recibo.png')
        assert static_oracle(state,inputs)==(inspection,fragments) and {p.name:sha(p.read_bytes()) for p in inputs}==hashes
        assert counts(state)==final,'READING_EXCERPT_EVIDENCE_CHARGED_AGAIN'
        track.update(stage='passed',authorization_to_evidence_seconds=round(time.monotonic()-began,3))
    except Exception:
        track['last_counts']=counts(state)
        raise
