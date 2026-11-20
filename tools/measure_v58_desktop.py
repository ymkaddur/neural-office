"""Measure a known Windows test host using UI Automation and an isolated ledger.

Run as a module with the native UI-test dependencies installed. No provider is installed or downloaded.
"""
import argparse
from contextlib import closing
import ctypes
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

from neural_office.diagnostics import write_json
from neural_office.ledger import digest
from neural_office.ollama import local_metadata, select_model
from neural_office.windows_job import Job
from tools.measure_v58 import ROOT, point, require, specification
from tools.summarize_v58 import interval

sys.path.insert(0,str(ROOT/'tests'))
from e2e_v55_native import Samples
from e2e_v55_native_uia import Screen, wait

EXPECTED_EXE='89bbcb48778df2ab82ab81d392a6152558b9c5a2a1fdfee8c288bac3393aaee3'
RESULT='4 hallazgos para revisar'


class NativeWindow(Screen):
    def __init__(self,host,hwnd):
        from pywinauto import Desktop
        self.host=host
        self.window=Desktop(backend='uia').window(handle=hwnd)
        self.edit_receipts=[]


def launch(executable, folder, job, *, core_root=ROOT):
    import psutil
    import win32api
    import win32con
    import win32process
    env={**os.environ,'NEURAL_OFFICE_PYTHON':sys.executable,'NEURAL_OFFICE_ROOT':str(core_root),
         'NEURAL_OFFICE_STATE':str(folder/'office.sqlite3'),'WEBVIEW2_USER_DATA_FOLDER':str(folder/'webview')}
    startup=win32process.STARTUPINFO()
    startup.dwFlags=win32con.STARTF_USESHOWWINDOW
    startup.wShowWindow=win32con.SW_SHOWNOACTIVATE
    process,thread,pid,_=win32process.CreateProcess(str(executable),subprocess.list2cmdline([str(executable)]),
        None,None,False,win32con.CREATE_SUSPENDED | win32con.CREATE_UNICODE_ENVIRONMENT,
        env,str(core_root),startup)
    try:
        if not job.dll.AssignProcessToJobObject(job.handle,int(process)):
            error=ctypes.get_last_error()
            win32api.TerminateProcess(process,1)
            raise ctypes.WinError(error)
        host=psutil.Process(pid)
        require(Path(host.exe()).samefile(executable),'native process identity')
        win32process.ResumeThread(thread)
        return host
    finally:
        thread.Close()
        process.Close()


def saved(db):
    with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as con:
        return {'states':list(con.execute('SELECT id,state FROM attempts ORDER BY ordinal')),
                'calls':con.execute("SELECT count(*) FROM calls WHERE state='DONE'").fetchone()[0]}


def choose_source(screen,host,source):
    """Resolve the dialog by its native handle, including when its accessibility provider runs out of process."""
    screen.open_html()
    choose_files(screen,host,[source],title='Elegir HTML para revisar',button_id='static-picker')


def choose_files(screen,host,paths,*,title,button=None,button_id=None):
    from pywinauto import Desktop
    import win32gui
    import win32process
    def dialogs():
        match=[]
        def visit(hwnd,_):
            if (win32gui.IsWindowVisible(hwnd) and win32process.GetWindowThreadProcessId(hwnd)[1]==host.pid
                    and win32gui.GetWindowText(hwnd)==title):
                match.append(hwnd)
        win32gui.EnumWindows(visit,None)
        return match
    require(not dialogs(),'test picker already open')
    if button_id is None:
        screen.button(button,regex=True)
    else:
        picker=screen.window.child_window(auto_id=button_id,control_type='Button')
        picker.wait('visible enabled',timeout=15)
        picker.wrapper_object().invoke()
    handles=wait(dialogs,timeout=18,description='owned native file dialog')
    require(len(handles)==1,'ambiguous owned file dialog')
    dialog=Desktop(backend='uia').window(handle=handles[0])
    field=dialog.child_window(auto_id='1148',control_type='Edit')
    field.wait('visible enabled',timeout=8)
    require(paths and all(Path(path).is_absolute() and Path(path).is_file() for path in paths),
            'synthetic selection must contain existing absolute files')
    selection=str(paths[0]) if len(paths)==1 else ' '.join('"'+str(path)+'"' for path in paths)
    field.set_edit_text(selection)
    require(field.get_value()==selection,'file dialog did not acknowledge the selected filenames')
    import win32con
    ok=win32gui.GetDlgItem(handles[0],win32con.IDOK)
    require(ok and win32gui.IsChild(handles[0],ok) and win32gui.IsWindowEnabled(ok)
            and win32gui.GetClassName(ok).lower()=='button','native dialog confirmation control')
    require(win32gui.GetWindowText(ok).replace('&','').casefold() in ('abrir','open'),'native dialog action')
    win32gui.PostMessage(ok,win32con.BM_CLICK,0,0)
    wait(lambda:not dialogs(),timeout=15,description='owned picker acknowledged selection')


def focused_widget(screen,control):
    """Find the focused control's input widget inside our isolated WebView2 process tree."""
    import win32gui, win32process
    control.set_focus()
    wait(control.has_keyboard_focus,timeout=3,description='scoped accessibility focus')
    owner={screen.host.pid,*[p.pid for p in screen.host.children(recursive=True)]}
    widgets=[]
    def child(hwnd,_):
        if (win32gui.GetClassName(hwnd)=='Chrome_WidgetWin_1'
                and win32process.GetWindowThreadProcessId(hwnd)[1] in owner and win32gui.IsWindowVisible(hwnd)):
            widgets.append(hwnd)
    win32gui.EnumChildWindows(screen.window.handle,child,None)
    require(len(widgets)==1 and win32gui.IsChild(screen.window.handle,widgets[0]),'ambiguous WebView input window')
    return widgets[0]


def webview_key(widget,key):
    import win32api, win32con, win32gui
    extended=key in (win32con.VK_DOWN,win32con.VK_HOME)
    keydata=1 | (win32api.MapVirtualKey(key,0)<<16) | (int(extended)<<24)
    win32gui.PostMessage(widget,win32con.WM_KEYDOWN,key,keydata)
    win32gui.PostMessage(widget,win32con.WM_KEYUP,key,keydata | 0xc0000000)


def choose_option(screen,combo,label,choices):
    import win32con, win32gui
    value=combo.iface_value
    wait(lambda:value.CurrentValue in choices,timeout=12,description='options populated')
    if value.CurrentValue==label:
        return
    widget=focused_widget(screen,combo)
    # Chromium HTML selects expose type-ahead on their input widget even when
    # the OS serves the transient popup from a different accessibility root.
    for char in (label[0] if label[0].isdigit() else label):
        win32gui.PostMessage(widget,win32con.WM_CHAR,ord(char),1)
        time.sleep(.025)
    wait(lambda:value.CurrentValue==label,timeout=4,description='requested option selected')


def setup_form(screen, host, source, arm, spec):
    choose_source(screen,host,source)
    wait(lambda:source.name in screen.names(),description='source captured')
    if arm:
        if 'Consultar al Director' in screen.names():
            screen.button('Consultar al Director')
        combo=screen.control('Modelo local','ComboBox')
        choose_option(screen,combo,spec['model'],{m['name'] for m in local_metadata()['models']})
        if arm==3:
            from pywinauto.uia_defines import NoPatternInterfaceError
            summary=screen.control('Perfil acotado.*',regex=True)
            try:
                disclosure=summary.iface_expand_collapse
            except NoPatternInterfaceError:
                selector=screen.window.child_window(title='Roles secuenciales',control_type='ComboBox')
                if not selector.exists(timeout=.2) or not selector.is_visible():
                    import win32con
                    webview_key(focused_widget(screen,summary),win32con.VK_RETURN)
            else:
                if disclosure.CurrentExpandCollapseState==0:  # UIA ExpandCollapseState_Collapsed
                    disclosure.Expand()
            roles=screen.control('Roles secuenciales','ComboBox')
            choose_option(screen,roles,'3 · Director, revisor e integrador',
                          {'1 · Director','3 · Director, revisor e integrador','7 · Equipo completo'})
        screen.objective(spec['objective'])
        screen.button('Revisar encargo.*',regex=True)
        wait(lambda:'Consumirá 1 intento' in screen.names(),description='approval is visible')
        content=' '.join(screen.names().split())
        has_roles=f'Hasta {arm} llamada' in content
        has_model=spec['model'] in content
        if not(has_roles and has_model):
            scope=content.partition('Trabajo')[2].partition('Presupuesto')[0]
            print('approval evidence:',{'model_matches':has_model,'role_text':scope[:180]},flush=True)
        require(has_roles and has_model,'approval scope')
        return screen.control('Autorizar y ejecutar.*',regex=True)
    return screen.control('Comprobar HTML')


def measure(exe, parent, arm, spec, *, version='5.8.0'):
    from pywinauto import Desktop
    import win32con
    import win32gui
    folder=parent/f'native-{arm}'
    folder.mkdir()
    source=folder/'audit-sample.html'
    source.write_bytes((ROOT/'examples/audit-sample.html').read_bytes())
    samples=[]
    errors=[]
    finished=threading.Event()
    job=Job('Local\\NeuralOffice58Window_'+uuid.uuid4().hex)
    def observe():
        while not finished.is_set():
            try:
                samples.append(point(job))
            except OSError as exc:
                errors.append(type(exc).__name__)
            finished.wait(.1)
    watcher=threading.Thread(target=observe)
    screen=None
    hwnd=None
    groups=None
    result={'arm':arm,'exe_sha256':digest(exe.read_bytes()),'rows':[]}
    try:
        watcher.start()
        start=time.perf_counter_ns()
        host=launch(exe,folder,job)
        title='Neural Office · V'+version
        hwnd=wait(lambda:next((w.handle for w in Desktop(backend='win32').windows(process=host.pid)
                               if w.window_text()==title),None),timeout=35,description='native window')
        screen=NativeWindow(host,hwnd)
        wait(screen.core_ready, description='local session connected')
        screen.open_html()
        wait(lambda:screen.window.child_window(auto_id='static-picker').is_enabled(),description='idle HTML session ready')
        require(win32gui.GetWindowText(hwnd)==title,'native window title')
        result['launch_to_ready_s']=(time.perf_counter_ns()-start)/1e9
        print('native',arm,'ready',flush=True)
        groups=Samples(host)
        before_idle=point(job)
        time.sleep(3)
        after_idle=point(job)
        result['idle']=interval(before_idle,after_idle,list(samples))
        result['idle_bounds']=[before_idle,after_idle]
        for index,phase in enumerate(('cold','repeat')):
            print('native',arm,phase,'form',flush=True)
            if index and arm:
                screen.new_html()
            elif index:
                screen.button('Quitar fuente del borrador')
            action=setup_form(screen,host,source,arm,spec)
            require(RESULT not in screen.names(),'stale result visible before measurement')
            counts=saved(folder/'office.sqlite3')
            groups.phase=phase
            begin=point(job)
            action.invoke()
            wait(lambda: RESULT in screen.names() and (not arm or 'Entrega disponible' in screen.names()),
                 timeout=240,description='new delivery visible')
            end=point(job)
            groups.phase='settled'
            total=saved(folder/'office.sqlite3')
            require(total['calls']-counts['calls']==arm and len(total['states'])-len(counts['states'])==int(bool(arm))
                    and all(state=='ACCEPTED' for _,state in total['states']), 'native quota or completion')
            metrics=interval(begin,end,list(samples))
            result['rows'].append({'phase':phase,'counts_before':counts,'counts_after':total,
                                   'begin':begin,'end':end,'work':metrics})
            print('native',arm,phase,round(metrics['wall_s'],3),flush=True)
        result['close']=screen.close()
        screen=None
        wait(lambda:job.active()==0,timeout=20,description='native process tree completed')
        result['job_empty']=True
    finally:
        try:
            if screen is not None and hwnd and job.active() and win32gui.IsWindow(hwnd):
                win32gui.PostMessage(hwnd,win32con.WM_CLOSE,0,0)
        finally:
            if groups:
                groups.finish()
            finished.set()
            watcher.join(5)
            try:
                job.terminate()
            finally:
                job.close()
                write_json(folder/'sampled.json',{'tree':samples,'grouped':groups.rows if groups else [],
                           'observation_errors':errors})
                write_json(folder/'result.json',result)
    require(not errors and not watcher.is_alive(),'incomplete observer')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--arm',type=int,choices=(0,1,3),required=True)
    p.add_argument('--version',default='5.8.0',help='Version expected in the native window title')
    p.add_argument('--expected-sha256',default=EXPECTED_EXE,help='Verified SHA-256 of the intended executable')
    a=p.parse_args()
    exe=a.executable.resolve(strict=True)
    require(sys.platform=='win32' and digest(exe.read_bytes())==a.expected_sha256.lower(),'wrong platform or executable')
    spec=specification()
    if a.arm:
        require(select_model(spec['model'],local_metadata()['models'])['model_digest']==spec['digest'],'unexpected weights')
    output=a.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    measure(exe,output,a.arm,spec,version=a.version)
