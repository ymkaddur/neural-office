"""Native Windows UI Automation, isolated synthetic state and Job Object counters.

Run with python -B -m tools.verify_v510_desktop. The old binary and core are a pair.
"""
import argparse
from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile
import threading
import time
import uuid

from neural_office.ledger import Ledger
from neural_office.windows_job import Job
from tools.measure_v58 import ROOT, point, require
from tools.measure_v58_desktop import NativeWindow, choose_source, launch, saved
from tools.summarize_v58 import interval
from e2e_v55_native_uia import wait


EDGE_HTML = ('<html lang="es">\r<head><title> </title></head>\r<body><svg><title>Marca</title></svg>'
             '\r  <img>\r<label for="c"><span hidden>Correo</span></label><input id="c">'
             '\r<span hidden id="n">Nombre</span><input aria-labelledby="n"></body></html>').encode()
PROFILE = {'roles': 1, 'mode': 'fixture', 'model': 'synthetic', 'model_digest': 'a'*64}
ARCHIVE = 'Revisión anterior guardada'
ACTIVE = 'Revisión pendiente de parada'


@contextmanager
def window(exe, core, folder, version, *, failure_dir=None):
    from pywinauto import Desktop
    with Job('Local\\NeuralOffice510_'+uuid.uuid4().hex) as job:
        start = time.perf_counter()
        host = launch(exe, folder, job, core_root=core)
        title = f'Neural Office · V{version}'
        hwnd = wait(lambda: next((w.handle for w in Desktop(backend='win32').windows(process=host.pid)
                                  if w.window_text()==title), None), description='versioned Windows host')
        screen = NativeWindow(host, hwnd)
        wait(screen.core_ready, description='confirmed local core')
        ready = time.perf_counter()-start
        try:
            yield screen, host, job, ready
        except Exception as error:
            if failure_dir is not None:
                try:
                    screen.screenshot(failure_dir/(folder.name+'-fallo.png'))
                    (failure_dir/(folder.name+'-controles.txt')).write_text(screen.names(visible_only=False),encoding='utf-8')
                except Exception as capture_error:
                    error.add_note('Native failure capture: '+type(capture_error).__name__)
            raise
        finally:
            screen.close()
            wait(lambda: job.active()==0, description='owned desktop tree closed')


def measure(job, action):
    samples, errors = [], []
    stopped = threading.Event()
    def sample():
        while not stopped.wait(.1):
            try:
                samples.append(point(job))
            except OSError as error:
                errors.append(type(error).__name__)
    thread = threading.Thread(target=sample)
    begin = point(job)
    thread.start()
    try:
        action()
        end = point(job)
    finally:
        stopped.set()
        thread.join()
    require(not errors,'incomplete Job Object sampler')
    return interval(begin,end,samples)


def visual_pass(exe, core, folder, name, out, order):
    version = json.loads((core/'desktop/src-tauri/tauri.conf.json').read_bytes())['version']
    source = folder/'audit-sample.html'
    source.write_bytes((core/'examples/audit-sample.html').read_bytes())
    rows = []
    with window(exe,core,folder,version) as (screen,host,job,ready):
        if name=='mineral':
            screen.button('Comparar con paleta mineral V5.9')
            screen.control('Activar variante grafito')
        elif name=='graphite':
            screen.control('Comparar con paleta mineral V5.9')
        before = measure(job, lambda: time.sleep(3))
        geometry = screen.geometry()
        for iteration in range(2):
            if iteration:
                screen.button('Quitar fuente del borrador')
            choose_source(screen,host,source)
            wait(lambda: source.name in screen.names(), description='same source captured')
            require('4 hallazgos para revisar' not in screen.names(),'result still present before check')
            action=screen.control('Comprobar HTML')
            def check():
                action.invoke()
                wait(lambda:'4 hallazgos para revisar' in screen.names(),description='all four findings rendered')
            rows.append(measure(job,check))
            require(saved(folder/'office.sqlite3')=={'states':[],'calls':0},'static charged work')
        if order==0:
            screen.screenshot(out/(name+'.png'))
        return {'variant':name,'round':order+1,'launch_to_ready_s':ready,'idle':before,
                'first':rows[0],'repeat':rows[1],'client_px':geometry['client_rectangle_px'],'dpi':geometry['dpi'],
                'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}


def timeout_core(folder, original_root=ROOT):
    """One failed quota read in a private test peer. The application has no fault switch."""
    package=folder/'peer'/'neural_office'
    package.mkdir(parents=True)
    original=original_root/'neural_office'
    (package/'__init__.py').write_text('__path__.append('+repr(str(original))+')\n',encoding='utf-8')
    script = """import runpy
from pathlib import Path
from .desktop_service import DesktopService
from .ledger import Denied
snapshot = DesktopService.snapshot
marker = Path(__file__).parents[2] / 'once'
def quota(self, *args, **kwargs):
    if marker.is_file():
        marker.unlink()
        raise Denied('HOST_RESPONSE_TIMEOUT')
    return snapshot(self, *args, **kwargs)
DesktopService.snapshot = quota
runpy.run_path(SOURCE, run_name='neural_office.native_test_entry')['main']()
"""
    code=script.replace('SOURCE',repr(str(original/'desktop_stdio.py')))
    compile(code,'desktop_stdio.py','exec')
    (package/'desktop_stdio.py').write_text(code,encoding='utf-8')
    return package.parent


def visible_edge_findings(screen):
    expected = ('3 hallazgos para revisar', 'Falta un título de documento no vacío',
                'Una imagen no tiene atributo alt', 'Un control podría necesitar una etiqueta',
                'Línea 1 · columna 1', 'Línea 4 · columna 3', 'Línea 5 · columna 50')
    frames = []
    start = time.monotonic()

    def complete():
        names = screen.names()
        missing = [i for i, label in enumerate(expected) if label not in names]
        if not frames or frames[-1]['missing'] != missing:
            frames.append({'ms': round((time.monotonic()-start)*1000), 'missing': missing})
        return not missing

    try:
        wait(complete, description='all three native findings and all source positions visible')
    except AssertionError:
        print('Native findings visibility:', frames, flush=True)
        raise
    return frames


def incident(exe,folder,fail_snapshot=False,evidence_dir=None):
    db = folder/'office.sqlite3'
    ledger = Ledger(db)
    ledger.initialize()
    ledger.register('Revision',folder)
    ids=[]
    for i, objective in enumerate(('Primera revisión guardada',ARCHIVE,ACTIVE)):
        attempt=ledger.reserve('Revision',objective,EDGE_HTML,PROFILE,'revision-'+str(i),admit=True)
        ids.append(attempt)
        if i<2:
            require(ledger.cancel(attempt)=='CANCELLED','history preparation')
    source=folder/'bordes.html'
    source.write_bytes(EDGE_HTML)
    before=saved(db)
    require(dict(before['states'])[ids[-1]]=='QUEUED','live identity not queued')
    core=timeout_core(folder) if fail_snapshot else ROOT
    with window(exe,core,folder,json.loads((ROOT/'desktop/src-tauri/tauri.conf.json').read_bytes())['version'],failure_dir=evidence_dir) as (screen,host,_,_ready):
        screen.button(ARCHIVE+'.*',regex=True)
        wait(lambda:'Consultando el historial' in screen.names(),description='viewing other attempt')
        if fail_snapshot:
            (folder/'once').touch(exist_ok=False)
            # A second authorized client stops this synthetic queued attempt. The renderer
            # can learn its terminal state only from polling, before its failed balance read.
            require(ledger.cancel(ids[-1])=='CANCELLED','external terminal control')
        else:
            screen.button('.*Detener trabajo',regex=True)
        wait(lambda:dict(saved(db)['states'])[ids[-1]]=='CANCELLED',description='durable stop of active identity')
        screen.button('Volver al último encargo')
        if fail_snapshot:
            names=wait(lambda:(text if 'Cuota pendiente de actualizar' in (text:=screen.names()) and 'HOST_RESPONSE_TIMEOUT' in text else None),
                       description='one failed read affects only quota after confirmed stop')
            require(ACTIVE in names and 'Encargo detenido' in names and 'Detener trabajo' not in names,'terminal status lost')
            screen.button('Reconectar')
        wait(lambda:'0 intentos disponibles' in screen.names() and 'Sin informe validado' in screen.names(),
             description='terminal current attempt and budget')
        screen.new_html()
        choose_source(screen,host,source)
        screen.button('Comprobar HTML')
        try:
            frames = visible_edge_findings(screen)
        except AssertionError:
            if evidence_dir is not None:
                screen.screenshot(evidence_dir/('findings-balance-fault.png' if fail_snapshot else 'findings-stop.png'))
            raise
        screen.button('Consultar al Director')
        wait(lambda:'3 intentos consumidos' in screen.names(),description='explicit exhausted budget')
        button=screen.window.child_window(title_re='Revisar encargo.*',control_type='Button')
        require(button.exists() and not button.is_enabled(),'exhausted approval enabled')
        require('APPROVAL_CHANGED' not in screen.names(),'quota shown as changed scope')
    after=saved(db)
    with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as con:
        stops=con.execute("SELECT count(*) FROM events WHERE kind='CANCELLATION_REQUESTED' AND json_extract(payload,'$.attempt')=?", (ids[-1],)).fetchone()[0]
    require(stops==1 and after=={'states':[(i,'CANCELLED') for i in ids],'calls':0},'identity, calls or budget changed')
    return {'seeded_attempts':3,'final_attempts':3,'target_stop_receipts':stops,'model_calls':0,'forced_balance_timeout':fail_snapshot,
            'native_static_findings':3,'image_line':4,'image_column':3,'finding_visibility_frames':frames}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--baseline-exe',type=Path,required=True)
    parser.add_argument('--baseline-core',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    exe,base,old=args.exe.resolve(strict=True),args.baseline_exe.resolve(strict=True),args.baseline_core.resolve(strict=True)
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    require(sys.platform=='win32' and (old/'neural_office/desktop_stdio.py').is_file(),'Windows and reference core required')
    import psutil
    result={'platform':platform.platform(),'logical_cpus':psutil.cpu_count(),'ram_bytes':psutil.virtual_memory().total,
            'exe_hashes':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in [('reference',base),('candidate',exe)]},'rows':[]}
    with tempfile.TemporaryDirectory(prefix='neural-office-510-') as tmp:
        folder=Path(tmp)
        cases=folder/'incident';cases.mkdir()
        result['incident']=incident(exe,cases,evidence_dir=out)
        fault=folder/'fault';fault.mkdir()
        result['balance_fault']=incident(exe,fault,fail_snapshot=True,evidence_dir=out)
        for index,variants in enumerate((('reference','graphite','mineral'),('mineral','graphite','reference'))):
            for name in variants:
                case=folder/(name+str(index));case.mkdir()
                print('Visual comparison',index+1,name,flush=True)
                result['rows'].append(visual_pass(base if name=='reference' else exe,old if name=='reference' else ROOT,case,name,out,index))
    require(len({(tuple(row['client_px']),row['dpi'],row['source_sha256']) for row in result['rows']})==1,
            'different viewport, DPI or source')
    (out/'metrics.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Compared six fresh windows and twelve static checks. All incident assertions passed.')


if __name__=='__main__':
    main()
