"""Exercise a locally built Windows host over an isolated ledger and a fixture model.

The test owns both windows and the single sidecar it disconnects. The model
worker belongs to a second service so the same live attempt spans the outage.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from neural_office.desktop_service import DesktopService
from neural_office.ledger import Denied, Ledger
from test_v55_service import FixtureBackend, PROFILE


class TestModel(FixtureBackend):
    entered = threading.Event()
    release = threading.Event()
    fail_start = True
    invocations = 0
    invocation_lock = threading.Lock()

    def start(self):
        if type(self).fail_start:
            raise Denied('MODEL_METADATA_UNAVAILABLE')

    def infer(self, payload):
        with self.invocation_lock:
            type(self).invocations += 1
        self.entered.set()
        if not self.release.wait(150):
            raise RuntimeError('fixture barrier expired')
        return super().infer(payload)

    def request_stop(self):
        super().request_stop()
        self.release.set()


def wait_until(probe, description, seconds=20):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        result = probe()
        if result:
            return result
        time.sleep(.2)
    raise AssertionError(description)


def run(exe, dest, baseline, sdk=None, cycles=1):
    import psutil
    from pywinauto import Desktop

    dest.mkdir(parents=True, exist_ok=False)
    ledger_path = dest / 'office.sqlite3'
    source = dest / 'documento.html'
    source.write_text('<html lang="es"><title>Ejemplo</title></html>', encoding='utf-8')
    ledger = Ledger(ledger_path)
    owner = DesktopService(ledger, backend_factory=TestModel, model_discovery=lambda: [PROFILE.copy()])
    control = None
    record = {'mode': 'baseline' if baseline else 'candidate', 'fixture_model': True, 'observations': {}}
    record['host'] = 'webview2-development-adapter' if sdk else 'native-tauri-executable'
    out = record['observations']
    old_title = 'Revisar el archivo anterior de prueba'
    live_title = 'Revisar el documento activo de prueba'

    def start(title, key):
        selected = owner.host_capture('ejemplo', source)
        approval = owner.preview('ejemplo', selected['entry_token'], PROFILE['model_digest'], 1, title)
        return owner.start(approval['approval_token'], key, approval['expected_revision'])['id']

    def counts():
        with ledger.connection() as con:
            attempts = [(r['id'], r['ordinal'], r['request_key']) for r in con.execute(
                'SELECT id, ordinal, request_key FROM attempts WHERE project=? ORDER BY ordinal', ('ejemplo',))]
            calls = [(r['attempt'],r['seq']) for r in con.execute('SELECT attempt,seq FROM calls ORDER BY attempt,seq')]
        with TestModel.invocation_lock:
            invocations = TestModel.invocations
        return {'attempts': attempts, 'calls': calls, 'fixture_invocations': invocations,
                'charged': owner.snapshot()['projects'][0]['attempts_consumed']}

    def open_window():
        nonlocal control
        env = {**os.environ, 'NEURAL_OFFICE_PYTHON':sys._base_executable,
               'NEURAL_OFFICE_ROOT':str(ROOT), 'NEURAL_OFFICE_STATE':str(ledger_path),
               'WEBVIEW2_USER_DATA_FOLDER':str(dest/'webview')}
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 1
        command = [str(exe)]
        if sdk:
            env['NEURAL_OFFICE_TEST_WEBVIEW_SDK'] = str(sdk)
            command = [str(exe), '-NoProfile', '-NonInteractive', '-STA', '-File', str(ROOT/'tests'/'WebView2-V58TestHost.ps1')]
        with (dest/'host-runtime.log').open('ab') as log:
            control = subprocess.Popen(command, cwd=ROOT, env=env, startupinfo=startup,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        def host_window():
            if control.poll() is not None:
                raise RuntimeError(f'Test host exited with {control.returncode} before showing its window. See host-runtime.log.')
            return next((item.handle for item in Desktop(backend='win32').windows(process=control.pid)
                         if item.window_text().startswith('Neural Office')), None)
        handle = wait_until(host_window, 'No hay ventana visible para el PID del host', 35)
        win = Desktop(backend='uia').window(handle=handle)
        return win

    def close_window(win):
        nonlocal control
        if control and control.poll() is None:
            win.close()
            control.wait(timeout=25)
        control = None

    def names(win):
        return '\n'.join(c.element_info.name for c in win.descendants()
                         if c.is_visible() and c.element_info.name)

    def connected(text):
        return bool({'Núcleo local', 'Núcleo local conectado', 'Última conexión confirmada'}.intersection(text.splitlines()))

    def btn(win, regex):
        return win.child_window(title_re=regex,control_type='Button').wrapper_object()

    def select_evidence(win):
        win.child_window(title='Evidencia y alcance',control_type='TabItem').select()

    def local_sidecar():
        for p in psutil.Process(control.pid).children(recursive=False):
            args = p.cmdline()
            if ('neural_office.desktop_stdio' in args and '--state' in args
                    and Path(args[args.index('--state')+1]).resolve()==ledger_path.resolve()):
                return p
        return None

    win = None
    try:
        old_id=start(old_title,'previous-key')
        owner._worker.join(10)
        assert not owner._worker.is_alive() and owner.attempt(old_id)['state']=='FAILED'
        charge_before_target = counts()['charged']
        assert charge_before_target==1
        TestModel.fail_start=False
        live_id=start(live_title,'current-key')
        assert TestModel.entered.wait(10) and owner.attempt(live_id)['state']=='RUNNING'
        before=counts()
        assert before['charged']==2 and len(before['attempts'])==2 and len(before['calls'])==1 and before['fixture_invocations']==1
        record['target_attempt']=live_id
        record['history_attempt']=old_id
        out['before']=before
        out['target_reservation_cost']=before['charged']-charge_before_target
        assert out['target_reservation_cost']==1
        win=open_window()
        wait_until(lambda:connected(names(win)) and live_title in names(win),'No se mostró el intento vivo')
        select_evidence(win)
        wait_until(lambda:live_id in names(win),'El intento inicial no coincide')
        window_handle=win.handle
        out['initial_history_enabled']=btn(win,'.*'+old_title+'.*').is_enabled()
        if not (baseline or sdk):
            version=json.loads((ROOT/'desktop/src-tauri/tauri.conf.json').read_text(encoding='utf-8'))['version']
            assert win.wrapper_object().window_text()==f'Neural Office · V{version}'
            assert Path(psutil.Process(control.pid).exe()).samefile(exe)
            record['window_title']=win.wrapper_object().window_text()
        assert before['attempts']==[(old_id,1,'previous-key'),(live_id,2,'current-key')]
        assert before['calls'][0][0]==live_id
        out['cycles']=[]
        for cycle in range(1,cycles+1):
            child=wait_until(local_sidecar,'Sidecar de prueba no identificado')
            # Close only this isolated host's verified Python peer. The fixture owner lives in this test.
            old_peer=(child.pid, child.create_time())
            child.terminate()
            child.wait(timeout=10)
            broken=wait_until(lambda:(s if 'HOST_DISCONNECTED' in (s:=names(win)) else None),'Falta señal de pérdida del pipe',22)
            out['online_during_outage']=connected(broken)
            out['after_disconnect']=counts()
            if baseline:
                assert out['online_during_outage'] and not out['initial_history_enabled']
                btn(win,'^Actualizar$').invoke()
                wait_until(lambda:'HOST_DISCONNECTED' in names(win),'Falta rechazo de Actualizar')
                assert local_sidecar() is None
                out['same_window_reconnected']=False
                close_window(win)
                win=open_window()
                wait_until(lambda:connected(names(win)),'Reapertura sin conexión')
                select_evidence(win)
            else:
                assert not out['online_during_outage'] and out['initial_history_enabled']
                btn(win,'^Reconectar$').invoke()
                wait_until(lambda:connected(names(win)) and 'HOST_DISCONNECTED' not in names(win),'La conexión no se concilió',30)
                replacement = local_sidecar()
                assert replacement is not None and (replacement.pid,replacement.create_time())!=old_peer
                assert control.poll() is None and win.wrapper_object().element_info.process_id==control.pid
                assert win.handle==window_handle
                out['same_window_reconnected']=True
            wait_until(lambda:live_id in names(win),'Cambió el intento tras la reconexión')
            out['after_reconnect']=counts()
            assert before==out['after_disconnect']==out['after_reconnect']
            out['reconnection_cost']=out['after_reconnect']['charged']-before['charged']
            assert owner.attempt(live_id)['state']=='RUNNING'
            out['cycles'].append({'cycle':cycle,'target_attempt':live_id,'same_window':out['same_window_reconnected'],
                                  'replacement_peer_verified':not baseline,'disconnected_status_observed':not out['online_during_outage'],
                                  'during':out['after_disconnect'],'after':out['after_reconnect']})
        if not baseline:
            btn(win,'.*'+old_title+'.*').invoke()
            wait_until(lambda:'MODEL_METADATA_UNAVAILABLE' in names(win),'Falta diagnóstico persistido en historial')
            assert owner.attempt(live_id)['state']=='RUNNING'
            assert owner.attempt(old_id)['state']=='FAILED'
            visible_history=names(win)
            assert 'documento.html' in visible_history
            if 'Núcleo local' in visible_history.splitlines():
                assert btn(win,r'.*Detener trabajo.*ejemplo$').is_enabled()
            out['history_read_kept_charge']=counts()==before
            assert out['history_read_kept_charge']
            btn(win,'.*Volver al (trabajo|encargo) en curso.*').invoke()
            wait_until(lambda:live_title in names(win) and btn(win,'.*Detener trabajo.*').is_enabled(),'No volvió al intento vivo')
            btn(win,'.*Detener trabajo.*').invoke()
            wait_until(lambda:owner.attempt(live_id)['state']=='CANCELLED','La parada no llegó al intento activo')
            assert owner.attempt(old_id)['state']=='FAILED' and counts()==before
            out['confirmed_cancel_target']=live_id
            out['final_active_state']=owner.attempt(live_id)['state']
            out['final_history_state']=owner.attempt(old_id)['state']
            out['after_cancel']=counts()
        record['status']='passed'
    except Exception:
        if win is not None and control is not None and control.poll() is None:
            (dest/'last-view.txt').write_text(names(win),encoding='utf-8')
        raise
    finally:
        try:
            if control and control.poll() is None:
                if win is not None: close_window(win)
                else: control.terminate();control.wait(timeout=12)
        finally:
            TestModel.release.set()
            owner.close()
            (dest/'receipt.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--expect-baseline',action='store_true')
    parser.add_argument('--webview-sdk',type=Path,help='Test the production renderer and stdio using the signed Microsoft WinForms SDK and Windows PowerShell as host')
    parser.add_argument('--cycles',type=int,choices=(1,2),default=1,help='Reconnect this same attempt once or twice')
    args=parser.parse_args()
    if args.expect_baseline and args.cycles!=1:
        parser.error('the V5.7 baseline can only be recovered by reopening the window')
    if sys.platform!='win32' or not args.executable.is_file() or args.output.exists():
        parser.error('requires Windows, a local test host and a fresh output directory')
    if args.webview_sdk and (args.expect_baseline or not args.webview_sdk.is_dir()):
        parser.error('the development adapter requires a local SDK and a candidate run')
    run(args.executable.resolve(),args.output.resolve(),args.expect_baseline,args.webview_sdk.resolve() if args.webview_sdk else None,args.cycles)
