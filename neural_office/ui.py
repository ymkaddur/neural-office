"""Small local desktop UI. All worker communication returns through a queue."""
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
import uuid

from .__main__ import snapshot_file
from . import __version__
from .files import local_path
from .ledger import canonical
from .ollama import local_metadata,review_profile,select_model
from .runner import run

FINDING_NAMES={
    'HTML_LANGUAGE_MISSING':'Falta el idioma del documento',
    'HTML_ELEMENT_MISSING':'No se encontró el elemento HTML',
    'DOCUMENT_TITLE_MISSING':'Falta un título con contenido',
    'IMAGE_ALT_MISSING':'Imagen sin atributo alt',
    'CONTROL_LABEL_CANDIDATE':'Control que requiere revisar su etiqueta'}
STATE_NAMES={'ACCEPTED':'Informe estático verificado; comentarios sin certificar',
             'CANCELLED':'Cancelado; el intento sigue contabilizado',
             'FAILED':'Intento fallido; el presupuesto se conserva',
             'REJECTED':'El informe no superó la comprobación',
             'RECOVERY_REQUIRED':'Terminación sin confirmar; se mantiene el bloqueo'}


def report_text(raw):
    report=json.loads(raw)
    lines=['COMPROBACIONES ESTÁTICAS',
           'Resultado limitado al HTML seleccionado. No certifica accesibilidad ni seguridad.','']
    for finding in report['findings']:
        lines.append(f"• Línea {finding['line']}, columna {finding['column']}: {FINDING_NAMES[finding['code']]}")
    if not report['findings']: lines.append('No se detectaron los defectos cubiertos por estas comprobaciones.')
    lines.extend(['','COMENTARIOS DEL MODELO — REQUIEREN REVISIÓN HUMANA'])
    for item in report['role_outputs']: lines.extend(['',item['role'].capitalize()+':',item['content']])
    return '\n'.join(lines)


def show(ledger):
    ledger.initialize()
    window=tk.Tk(); window.title(f'Neural Office {__version__} — piloto local'); window.geometry('850x650')
    events=queue.Queue(); active={'attempt':None,'working':False,'cancel_requested':False}
    models=[]
    frame=ttk.Frame(window,padding=18); frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Auditoría HTML local',font=('Segoe UI',18,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Modelo local · cuatro comprobaciones estáticas de HTML · comentarios del modelo sin certificar',wraplength=800).pack(anchor='w',pady=(4,15))
    model=tk.StringVar(); chosen_file=tk.StringVar(); project=tk.StringVar(value='mi-auditoria'); roles=tk.StringVar(value='7')
    ttk.Label(frame,text='Modelo local instalado').pack(anchor='w')
    model_box=ttk.Combobox(frame,textvariable=model,state='readonly'); model_box.pack(fill='x')
    ttk.Label(frame,text='Proyecto (identidad persistente; máximo tres intentos)').pack(anchor='w',pady=(10,0))
    ttk.Entry(frame,textvariable=project).pack(fill='x')
    ttk.Label(frame,text='Archivo HTML').pack(anchor='w',pady=(10,0))
    ttk.Entry(frame,textvariable=chosen_file,state='readonly').pack(fill='x')
    files=ttk.Frame(frame);files.pack(fill='x',pady=5)
    ttk.Button(files,text='Elegir HTML…',command=lambda:chosen_file.set(filedialog.askopenfilename(filetypes=[('HTML','*.html *.htm')]) or chosen_file.get())).pack(side='left')
    ttk.Button(files,text='Usar ejemplo',command=lambda:chosen_file.set(str(Path(__file__).resolve().parent.parent/'examples'/'audit-sample.html'))).pack(side='left',padx=8)
    ttk.Label(frame,text='Roles').pack(anchor='w')
    ttk.Combobox(frame,textvariable=roles,values=['1','3','7'],state='readonly',width=8).pack(anchor='w')
    status=tk.StringVar(value='Preparando modelos…'); ttk.Label(frame,textvariable=status,wraplength=800).pack(anchor='w',pady=10)
    output=tk.Text(frame,wrap='word',height=14); output.pack(fill='both',expand=True)
    def log(text): output.insert('end',text+'\n'); output.see('end')
    def load_models():
        try: events.put(('models',local_metadata()['models']))
        except Exception as exc: events.put(('error','No se pudo consultar Ollama. Instala/inicia Ollama y descarga un modelo local. '+str(exc)))
    def work(values):
        try:
            file=local_path(values['file']); root=file.resolve().parent
            profile=review_profile(select_model(values['model'],models), values['roles'])
            source=snapshot_file(file,root)
            ledger.register(values['project'],root)
            attempt=ledger.reserve(values['project'],'Audit the selected HTML snapshot and explain the observed static findings.',source,profile,uuid.uuid4().hex,admit=True)
            events.put(('attempt',attempt))
            final=run(ledger,attempt,values['roles'],progress=lambda role,state:events.put(('progress',role+': '+state)))
            row=ledger.attempt(attempt)
            events.put(('result',(final,bytes(row['artifact']).decode('utf-8') if row['artifact'] else 'Sin artefacto aceptado.')))
        except Exception as exc: events.put(('error',str(exc)))
        finally: events.put(('idle',None))
    def start():
        if active['working']: return
        if not model.get() or not chosen_file.get(): messagebox.showinfo('Falta selección','Selecciona un modelo y un archivo HTML.'); return
        active['working']=True; active['attempt']=None; active['cancel_requested']=False
        start_button.configure(state='disabled')
        values={'file':chosen_file.get(),'model':model.get(),'project':project.get(),'roles':int(roles.get())}
        threading.Thread(target=work,args=(values,),daemon=True).start()
    def cancel():
        if not active['working']: return
        active['cancel_requested']=True
        status.set('Parada solicitada — esperando terminación comprobada')
        if active['attempt']:
            state=ledger.cancel(active['attempt']); status.set(state+' — esperando terminación comprobada')
    buttons=ttk.Frame(frame); buttons.pack(fill='x',pady=10)
    start_button=ttk.Button(buttons,text='Autorizar y auditar',command=start); start_button.pack(side='left')
    ttk.Button(buttons,text='Detener',command=cancel).pack(side='left',padx=8)
    def display_status():
        try:
            state=ledger.status()
            if not state['projects']:log('No hay proyectos registrados todavía.')
            for item in state['projects']:
                log(f"{item['id']}: {item['attempts_consumed']}/3 intentos; {item['verified_versions']} informes verificados; "+('activo' if item['active'] else 'aparcado'))
        except Exception as exc:log('No se pudo leer el estado: '+str(exc))
    ttk.Button(buttons,text='Ver presupuesto',command=display_status).pack(side='left',padx=8)
    def display_last_report():
        try:
            candidates=[a for a in ledger.status()['attempts'] if a['project']==project.get()]
            for item in reversed(candidates):
                saved=ledger.attempt(item['id'])
                if saved['artifact'] is not None:
                    log(report_text(bytes(saved['artifact']).decode('utf-8')))
                    status.set(STATE_NAMES.get(saved['state'],saved['state']));return
            log('Este proyecto todavía no tiene un informe guardado.')
        except Exception as exc:log('No se pudo leer el informe: '+str(exc))
    ttk.Button(buttons,text='Ver último informe',command=display_last_report).pack(side='left',padx=8)
    def poll():
        nonlocal models
        try:
            while True:
                kind,data=events.get_nowait()
                if kind=='models':
                    models=data; model_box['values']=[m['name'] for m in models]
                    if models: model.set(models[0]['name'])
                    status.set('Listo. El botón autoriza un intento del proyecto seleccionado.')
                elif kind=='attempt':
                    active['attempt']=data; log('Intento: '+data)
                    if active['cancel_requested']: cancel()
                elif kind=='progress': status.set(data); log(data)
                elif kind=='result':
                    status.set(STATE_NAMES.get(data[0],data[0]))
                    log(report_text(data[1]) if data[1].startswith('{') else data[1])
                    display_status()
                elif kind=='error': status.set('Requiere atención'); log(data)
                elif kind=='idle': active['working']=False; start_button.configure(state='normal')
        except queue.Empty: pass
        window.after(100,poll)
    def close():
        if active['working']:
            cancel(); status.set('Deteniendo. Cierra cuando termine la operación.'); return
        window.destroy()
    window.protocol('WM_DELETE_WINDOW',close)
    threading.Thread(target=load_models,daemon=True).start(); poll(); window.mainloop()
