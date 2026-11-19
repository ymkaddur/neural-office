"""Real packaged desktop exercise through Windows accessibility APIs only.

No DevTools port, JavaScript evaluation, provider mocks or direct IPC calls.
Restricted to an isolated GitHub Windows runner; not an App Control workaround.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

from e2e_v55_native import (MODEL, MODEL_DIGEST, OLLAMA_SHA256, OLLAMA_VERSION,
                            EXPECTED_FINDINGS, Samples, http, native_picker,
                            prepare_ollama, readonly_counts, sha)

OBJECTIVE = 'Revisa las barreras de accesibilidad y prioriza los hallazgos del HTML sintético.'
SECOND = 'Revisa el mismo HTML sintético; esta ejecución se cancelará desde la interfaz.'
LABELS = ['Falta un título de documento no vacío', 'El documento no declara su idioma',
          'Una imagen no tiene atributo alt', 'Un control podría necesitar una etiqueta']


class TerminalDelivery(AssertionError):
    """The first authorized CI attempt has reached a state that cannot produce a report."""


def delivery_rendered(counts, names):
    if any(state in ('FAILED','REJECTED','CANCELLED','RECOVERY_REQUIRED') for state in counts['states']):
        raise TerminalDelivery('FIRST_DELIVERY_UNAVAILABLE:'+','.join(counts['states']))
    return counts['states'] == ['ACCEPTED'] and '4 hallazgos para revisar' in names()


def startup_tail(log):
    """Keep only known stage names, phases, counts and error categories from the synthetic run."""
    if not log.is_file():
        return []
    stages = {'BOOTSTRAP_SPAWN_BEGIN','BOOTSTRAP_LAUNCHED','BOOTSTRAP_EXITED','STARTUP_PROBE_BEGIN',
              'STARTUP_PHASE','STARTUP_RETRY','START_TIMEOUT','OWNED_BACKEND_READY','STARTUP_SUBPROCESS_FAILED'}
    categories = {'ConnectionRefusedError','TimeoutError','RemoteDisconnected','ConnectionResetError',
                  'TimeoutExpired','CalledProcessError'}
    with log.open('rb') as stream:
        stream.seek(0,2)
        stream.seek(max(0,stream.tell()-131072))
        lines = stream.read(131072).splitlines()
    rows = []
    for line in lines:
        if len(line)>2048 or not line.startswith(b'{'):
            continue
        try:
            entry = json.loads(line)
        except (UnicodeError, ValueError):
            continue
        if not isinstance(entry,dict) or not isinstance(entry.get('stage'),str) or entry['stage'] not in stages:
            continue
        row = {'stage':entry['stage']}
        if entry.get('phase') in ('metadata','listener_owner','model_identity'):
            row['phase'] = entry['phase']
        for field in ('probe','active_processes','returncode'):
            if type(entry.get(field)) is int:
                row[field] = entry[field]
        for field in ('error_type','last_error'):
            if isinstance(entry.get(field),str) and entry[field] in categories:
                row[field] = entry[field]
        rows.append(row)
    return rows[-12:]


def wait(test, timeout=45, description='condition'):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            value = test()
            if value:
                return value
        except TerminalDelivery:
            raise
        except Exception as error:
            # Preserve the last UIA error category without converting it to a pass.
            last = f'{type(error).__name__}: {error}'[:1000]
        time.sleep(.5)
    raise AssertionError(f'TIMEOUT:{description}:{last or "not observed"}')


def viewport_checks(geometry):
    area = geometry['monitor_work_area_px']
    client = geometry['client_rectangle_px']
    origin = geometry['client_origin_screen_px']
    client_screen = [origin[0] + client[0], origin[1] + client[1],
                     origin[0] + client[2], origin[1] + client[3]]
    def contained(rectangle):
        return rectangle is not None and area[0] <= rectangle[0] < rectangle[2] <= area[2] and \
            area[1] <= rectangle[1] < rectangle[3] <= area[3]
    # Maximized outer borders may exceed Work; content and the primary action may not.
    return {'client_screen_px': client_screen, 'client_within_work_area': contained(client_screen),
            'review_button_within_work_area': contained(geometry['review_button_rectangle_px'])}


class Screen:
    def __init__(self, host):
        from pywinauto import Application
        self.host = host
        self.window = Application(backend='uia').connect(process=host.pid).window(title_re='Neural Office.*')
        self.window.wait('visible', timeout=30)
        self.edit_receipts = []

    def names(self):
        return '\n'.join(control.element_info.name for control in self.window.descendants()
                         if control.is_visible() and control.element_info.name)

    def control(self, name, kind='Button', regex=False):
        selector = {'title_re' if regex else 'title': name, 'control_type': kind}
        control = self.window.child_window(**selector)
        control.wait('visible enabled', timeout=15)
        return control.wrapper_object()

    def button(self, name, regex=False):
        self.control(name, regex=regex).invoke()

    def objective(self, text):
        editor = self.control('Tu encargo al Director', 'Edit')
        receipt = {'requested_length': len(text), 'readings': [], 'matched': False}
        self.edit_receipts.append(receipt)
        began = time.monotonic_ns()
        editor.set_edit_text(text)
        def acknowledged():
            value = editor.get_value()
            receipt['readings'].append({'elapsed_ns': time.monotonic_ns() - began,
                                        'type': type(value).__name__,
                                        'length': len(value) if isinstance(value, str) else None,
                                        'sha256': hashlib.sha256(value.encode()).hexdigest() if isinstance(value, str) else None})
            receipt['matched'] = value == text
            return receipt['matched']
        # UIA sets cross-process state; equality remains mandatory after its ack.
        wait(acknowledged, timeout=5, description='exact objective readback after UIA SetValue')

    def tab(self, name):
        self.control(name, 'TabItem').select()

    def screenshot(self, path):
        self.window.set_focus()
        self.window.capture_as_image().save(path)

    def close(self):
        from pywinauto import Application
        import psutil
        identities = []
        for process in self.host.children(recursive=True):
            try:
                name = process.name().lower()
                if name.startswith('python') or name in ('ollama.exe', 'llama-server.exe'):
                    identities.append({'pid': process.pid, 'created': process.create_time(), 'name': name})
            except psutil.NoSuchProcess:
                continue  # This identity had already exited before capture.
        if not identities:
            raise AssertionError('NO_OWNED_CORE_OBSERVED_BEFORE_CLOSE')
        Application(backend='win32').connect(process=self.host.pid).window(title_re='Neural Office.*').close(wait_time=30)
        self.host.wait(timeout=30)
        def still_alive(identity):
            try:
                current = psutil.Process(identity['pid'])
                return current.create_time() == identity['created'] and current.is_running()
            except psutil.NoSuchProcess:
                return False
        # Read-only verification of captured identities; never kill a reused PID.
        wait(lambda: not any(still_alive(identity) for identity in identities), timeout=15,
             description='pre-close owned Python/Ollama identities exited')
        return {'scope': 'captured Python/Ollama descendants; WebView sharing not certified',
                'identities': identities, 'exited': True}

    def inventory(self):
        from pywinauto import Application
        result = []
        # Include an owned native picker if the failure occurred inside it.
        for window in Application(backend='uia').connect(process=self.host.pid).windows():
            result.append({'window': window.window_text()[:200], 'controls': [
                {'type': c.element_info.control_type, 'id': c.element_info.automation_id,
                 'name': c.element_info.name[:300], 'enabled': c.is_enabled(), 'visible': c.is_visible()}
                for c in window.descendants()][:400]})
        return result

    def geometry(self):
        import win32api
        import win32gui
        from ctypes import wintypes
        rectangle = self.window.rectangle()
        handle = self.window.handle
        work_area = win32api.GetMonitorInfo(win32api.MonitorFromWindow(handle))['Work']
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
        user32.SystemParametersInfoW.restype = wintypes.BOOL
        user32.GetDpiForWindow.argtypes = [wintypes.HWND]
        user32.GetDpiForWindow.restype = wintypes.UINT
        user32.IsZoomed.argtypes = [wintypes.HWND]
        user32.IsZoomed.restype = wintypes.BOOL
        primary = wintypes.RECT()
        if not user32.SystemParametersInfoW(48, 0, ctypes.byref(primary), 0):
            raise ctypes.WinError(ctypes.get_last_error())
        dpi = user32.GetDpiForWindow(handle)
        dwm = ctypes.WinDLL('dwmapi')
        dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        dwm.DwmGetWindowAttribute.restype = ctypes.c_long
        extended = wintypes.RECT()
        has_frame = dwm.DwmGetWindowAttribute(handle, 9, ctypes.byref(extended), ctypes.sizeof(extended)) == 0
        send = self.window.child_window(title_re='Revisar encargo.*', control_type='Button')
        if not send.exists(timeout=.1):
            send = self.window.child_window(title='Comprobar HTML', control_type='Button')
        send_rect = send.rectangle() if send.exists(timeout=.1) else None
        return {'window_rectangle_px': [rectangle.left, rectangle.top, rectangle.right, rectangle.bottom],
                'monitor_work_area_px': list(work_area),
                'primary_work_area_px': [primary.left, primary.top, primary.right, primary.bottom],
                'win32_window_rectangle_px': list(win32gui.GetWindowRect(handle)),
                'client_rectangle_px': list(win32gui.GetClientRect(handle)),
                'client_origin_screen_px': list(win32gui.ClientToScreen(handle, (0, 0))),
                'extended_frame_px': [extended.left, extended.top, extended.right, extended.bottom] if has_frame else None,
                'review_button_rectangle_px': [send_rect.left, send_rect.top, send_rect.right, send_rect.bottom] if send_rect else None,
                'dpi': dpi, 'scale_factor': dpi / 96 if dpi else None, 'maximized': bool(user32.IsZoomed(handle))}

    def maximize(self, enabled):
        from pywinauto import Application
        native = Application(backend='win32').connect(process=self.host.pid).window(title_re='Neural Office.*')
        native.maximize() if enabled else native.restore()
        wait(lambda: self.geometry()['maximized'] == enabled, timeout=5, description='native maximize/restore acknowledged')


def main():
    if os.name != 'nt' or os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_OS') != 'Windows':
        raise SystemExit('CI_ONLY: no local application-control bypass')
    import psutil
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--profile-work', action='store_true', help='Measure first and repeated static and one-role work in separate windows')
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    tools = Path(os.environ['NO_E2E_TOOLS']).resolve()
    work = Path(tempfile.mkdtemp(prefix='neural-office-uia-', dir=os.environ['RUNNER_TEMP']))
    state = work / 'state.sqlite3'; source = work / 'audit-sample.html'
    shutil.copyfile(root / 'examples/audit-sample.html', source)
    executable = root / 'desktop/src-tauri/target/release/neural-office-desktop.exe'
    evidence = {'schema': 1, 'commit': os.environ.get('GITHUB_SHA'), 'status': 'running',
                'test': 'real-packaged-windows-desktop-uia', 'model': MODEL,
                'source_sha256': sha(source), 'executable_sha256': sha(executable),
                'tools': json.loads((tools / 'tools.json').read_text(encoding='utf-8-sig')),
                'runner_elevated': bool(ctypes.windll.shell32.IsUserAnAdmin()),
                'runner_environment': {
                    'system': platform.system(), 'release': platform.release(), 'machine': platform.machine(),
                    'python': sys.version, 'logical_cpus': psutil.cpu_count(logical=True),
                    'physical_cpus': psutil.cpu_count(logical=False), 'total_ram_bytes': psutil.virtual_memory().total},
                'checks': [], 'limitations': [
                    'One synthetic HTML task and one cancellation; no semantic model quality claim.',
                    'Windows CI runner only, not a user-machine policy override or clean-machine installer test.',
                    'UI Automation is instrumentation, not a human usability or accessibility audit.',
                    'RSS may double-count shared pages; half-second samples are not absolute peaks or leak proof.',
                    'CPU fields sum counters of currently observed processes, not total lifetime CPU of the run.',
                    'The separate metadata server and test harness are outside the sampled application tree.']}
    checks = evidence['checks']; stage = 'prepare_tools'
    app = host = screen = metadata = sampler = None
    logs = []

    def sanitized(value):
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        for path, label in ((str(work), '<synthetic-work>'), (str(root), '<repository>'),
                            (str(tools), '<test-tools>'), (str(Path.home()), '<runner-home>'),
                            (sys.executable, '<test-python>')):
            text = text.replace(path, label).replace(path.replace('\\', '/'), label)
        return text

    try:
        ollama = prepare_ollama(tools)
        with socket.socket() as check:
            check.bind(('127.0.0.1', 11434))
        env = os.environ.copy()
        for name in ('TAURI_AUTOMATION', 'TAURI_WEBVIEW_AUTOMATION', 'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'):
            env.pop(name, None)  # Only this new child environment; no system setting changes.
        env.update({'PATH': str(ollama) + os.pathsep + env['PATH'],
                    'OLLAMA_HOST': '127.0.0.1:11434', 'OLLAMA_NO_CLOUD': '1',
                    'OLLAMA_MODELS': str(work / 'models'), 'NEURAL_OFFICE_ROOT': str(root),
                    'NEURAL_OFFICE_PYTHON': sys.executable, 'NEURAL_OFFICE_STATE': str(state)})
        def open_desktop():
            nonlocal app, host, screen
            app = subprocess.Popen([str(executable)], env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            host = psutil.Process(app.pid)
            screen = Screen(host)
            screen.edit_receipts = evidence.setdefault('input_acknowledgements', [])
            wait(lambda: re.search('Última conexión confirmada|Núcleo local conectado', screen.names()), description='native IPC ready')
            return app, host, screen

        stage = 'open_packaged_ui'
        app, host, screen = open_desktop()
        release = json.loads((root / 'desktop/src-tauri/tauri.conf.json').read_bytes())['version']
        evidence['window_title'] = screen.window.window_text()
        assert evidence['window_title'] == f'Neural Office · V{release}', 'WINDOW_RELEASE_MISMATCH'
        checks.append({'check': 'native-window-title-matches-release', 'verified': True})
        evidence['initial_geometry'] = screen.geometry()
        sampler = Samples(host)
        wait(lambda: '0 intentos · sin modelo' in screen.names(), description='model-free entry visible')
        screen.screenshot(output / '01-ready.png')
        sampler.phase = 'window_differential'
        before = evidence['initial_geometry']
        frame, area = before['win32_window_rectangle_px'], before['monitor_work_area_px']
        if before['maximized']:
            def fits_after_resize(label):
                observations = evidence.setdefault(label + '_readings', [])
                def acknowledged():
                    geometry = screen.geometry()
                    checks = viewport_checks(geometry)
                    observations.append({'geometry': geometry, 'checks': checks})
                    return geometry if checks['client_within_work_area'] and checks['review_button_within_work_area'] else None
                return wait(acknowledged, timeout=5, description=label + ' client and review action within work area')
            # Exercise Restore as a real user would; retain the initial state afterward.
            try:
                screen.maximize(False)
                evidence['restored_geometry'] = screen.geometry()
                screen.screenshot(output / '01-restored-contrast.png')
                evidence['restored_geometry'] = fits_after_resize('restored_geometry')
            finally:
                screen.maximize(True)
                evidence['remaximized_geometry'] = screen.geometry()
                screen.screenshot(output / '01-remaximized-contrast.png')
            evidence['remaximized_geometry'] = fits_after_resize('remaximized_geometry')
            evidence['window_differential'] = 'initial maximized -> restored content fits -> maximized content fits'
            checks.append({'check': 'normal-restore-and-remaximize-content-within-work-area', 'verified': True})
        elif frame[2] - frame[0] > area[2] - area[0] or frame[3] - frame[1] > area[3] - area[1]:
            screen.maximize(True)
            evidence['maximized_geometry'] = screen.geometry()
            screen.screenshot(output / '01-maximized-contrast.png')
            screen.maximize(False)
            evidence['restored_geometry'] = screen.geometry()
        else:
            evidence['window_differential'] = 'not needed: initial outer dimensions fit the work area'
        evidence['initial_viewport_checks'] = viewport_checks(before)
        assert evidence['initial_viewport_checks']['client_within_work_area'], 'INITIAL_CLIENT_OUTSIDE_WORK_AREA'
        assert evidence['initial_viewport_checks']['review_button_within_work_area'], 'INITIAL_REVIEW_ACTION_OUTSIDE_WORK_AREA'
        checks.append({'check': 'initial-native-client-and-review-action-within-work-area', 'verified': True})
        sampler.phase = 'idle_before'
        time.sleep(5)
        stage = 'native_static_review'; sampler.phase = 'prepare'
        screen.objective(OBJECTIVE)
        assert screen.control('Tu encargo al Director', 'Edit').get_value() == OBJECTIVE
        screen.button('Elegir archivo HTML')
        native_picker(host, source)
        wait(lambda: 'audit-sample.html' in screen.names(), description='captured source')
        from pywinauto import Application, keyboard
        import win32gui
        inspect = screen.control('Comprobar HTML')
        native_window = Application(backend='win32').connect(process=host.pid).window(handle=screen.window.handle)
        native_window.set_focus()
        focus_receipt = evidence['static_keyboard'] = {'readings': [], 'space_sends': 0}
        focus_started = time.monotonic_ns()

        def inspection_focused():
            foreground = win32gui.GetForegroundWindow() == native_window.handle
            if foreground and not inspect.has_keyboard_focus():
                inspect.set_focus()
            focused = inspect.has_keyboard_focus()
            focus_receipt['readings'].append({'elapsed_ns': time.monotonic_ns() - focus_started,
                'foreground': foreground, 'control_focused': focused, 'enabled': inspect.is_enabled()})
            return foreground and focused and focus_receipt['readings'][-1]['enabled']

        wait(inspection_focused, timeout=10, description='foreground and HTML check button has UIA keyboard focus')
        keyboard.send_keys('{SPACE}', turn_off_numlock=False)
        focus_receipt['space_sends'] += 1
        wait(lambda: '4 hallazgos para revisar' in screen.names(), description='keyboard static findings')
        region = screen.window.child_window(auto_id='static-workspace').rectangle()
        positions = [screen.control(label, 'Text').rectangle() for label in LABELS]
        assert all(region.top <= rect.top < rect.bottom <= region.bottom and
                   region.left <= rect.left < rect.right <= region.right for rect in positions), 'STATIC_FINDING_CLIPPED'
        assert readonly_counts(state) == {'attempts': 0, 'calls': 0, 'states': []}, 'STATIC_CONSUMED_WORK'
        assert not any(p.name().lower() in ('ollama.exe', 'llama-server.exe') for p in host.children(recursive=True))
        screen.screenshot(output / '01-static-result.png')
        checks.append({'check':'keyboard-static-review-four-visible-positions-without-ollama-or-consumption','verified':True})

        log = (work / 'metadata.log').open('wb'); logs.append(log)
        metadata = subprocess.Popen([str(ollama / 'ollama.exe'), 'serve'], env=env,
                                    stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        wait(lambda: http('GET', 'http://127.0.0.1:11434/api/version', timeout=5), description='metadata server')
        stage = 'pull_public_model'
        assert http('POST', 'http://127.0.0.1:11434/api/pull', {'name': MODEL, 'stream': False}, timeout=600).get('status') == 'success'
        models = http('GET', 'http://127.0.0.1:11434/api/tags')['models']
        assert len(models) == 1 and models[0]['name'] == MODEL and models[0]['digest'] == MODEL_DIGEST, 'MODEL_IDENTITY_CHANGED'
        evidence.update(model_digest=MODEL_DIGEST, ollama_version=OLLAMA_VERSION, ollama_archive_sha256=OLLAMA_SHA256)

        stage = 'native_source_and_approval'
        screen.button('Consultar al Director')
        wait(lambda: screen.control('Modelo local', 'ComboBox').selected_text() == MODEL, description='real model selected')
        checks.append({'check': 'packaged-ui-native-ipc-real-catalog-no-devtools', 'verified': True})
        assert 'audit-sample.html' in screen.names(), 'MODE_SWITCH_LOST_SOURCE'
        assisted_geometry = screen.geometry()
        assert viewport_checks(assisted_geometry)['review_button_within_work_area'], 'ASSISTED_ACTION_OFFSCREEN'
        assert screen.control('Tu encargo al Director','Edit').get_value() == OBJECTIVE, 'STATIC_REVIEW_LOST_OBJECTIVE'
        screen.button('Revisar encargo.*', regex=True)
        wait(lambda: 'el saldo pasará a 2 de 3' in screen.names() and 'Consumirá 1 intento' in screen.names(),
             description='visible approval with the projected balance')
        assert readonly_counts(state)['attempts'] == 0, 'PREVIEW_CONSUMED_ATTEMPT'
        screen.screenshot(output / '02-approval.png')
        checks.append({'check': 'native-file-picker-visible-approval-no-early-consumption', 'verified': True})
        stage = 'real_inference'; sampler.phase = 'work'; began = time.monotonic()
        screen.button('Autorizar y ejecutar.*', regex=True)
        wait(lambda: screen.window.child_window(title='Tu encargo', control_type='Text').exists(timeout=.1),
             description='exact post-reservation request label')
        assert readonly_counts(state)['attempts'] == 1, 'UI_REQUEST_WITHOUT_DURABLE_RESERVATION'
        before_capture = readonly_counts(state)
        screen.screenshot(output / '03-after-start.png')
        evidence['after_start_capture'] = {'counts_before': before_capture, 'counts_after': readonly_counts(state),
                                           'meaning': 'after authorization; not an atomic RUNNING snapshot'}
        wait(lambda: delivery_rendered(readonly_counts(state),screen.names), timeout=360, description='real report rendered')
        evidence['first_delivery_seconds'] = round(time.monotonic() - began, 3)
        sampler.phase = 'idle_after'
        content = screen.names()
        assert 'Entrega disponible' in content and all(label in content for label in LABELS), 'FINDINGS_NOT_RENDERED'
        assert readonly_counts(state) == {'attempts': 1, 'calls': 1, 'states': ['ACCEPTED']}, 'CALL_OR_QUOTA_MISMATCH'
        screen.screenshot(output / '04-result.png')
        stage = 'finding_guidance_disclosure'
        guidance = 'Añade un title descriptivo en head. Debe identificar el propósito de esta página.'
        rule = 'DOCUMENT_TITLE_MISSING'
        assert guidance not in screen.names() and rule not in screen.names(), 'GUIDANCE_NOT_COLLAPSED'
        # WebView2 exposes summary as a button without the Invoke pattern.
        # Use actual pointer input, then require the observable disclosure state.
        screen.control('Qué revisar: Falta un título de documento no vacío').click_input()
        wait(lambda: guidance in screen.names() and rule in screen.names(), description='selected guidance and rule visible')
        screen.screenshot(output / '04-finding-guidance.png')
        screen.control('Qué revisar: Falta un título de documento no vacío').click_input()
        wait(lambda: guidance not in screen.names() and rule not in screen.names() and all(label in screen.names() for label in LABELS),
             description='collapsed guidance restores overview of all four findings')
        assert readonly_counts(state) == {'attempts': 1, 'calls': 1, 'states': ['ACCEPTED']}, 'GUIDANCE_REEXECUTED_WORK'
        checks.append({'check': 'four-visible-findings-expand-collapse-real-guidance-without-new-work', 'verified': True})
        screen.tab('Evidencia y alcance')
        with closing(sqlite3.connect(state.as_uri() + '?mode=ro', uri=True)) as con:
            artifact, artifact_hash = con.execute('SELECT artifact,artifact_sha FROM attempts WHERE ordinal=1').fetchone()
        artifact = bytes(artifact); report = json.loads(artifact)
        expected_hashes = (artifact_hash, sha(source), MODEL_DIGEST)
        def evidence_exposed():
            content = screen.names()
            return all(value in content for value in expected_hashes)
        wait(evidence_exposed, timeout=15,
             description='evidence tab exposes all expected hashes after Select')
        assert hashlib.sha256(artifact).hexdigest() == artifact_hash, 'STORED_REPORT_HASH_CHANGED'
        assert [(f['code'], f['line'], f['column']) for f in report['findings']] == EXPECTED_FINDINGS, 'STATIC_ORACLE_MISMATCH'
        assert report['source_sha256'] == sha(source) and report['model_commentary_status'] == 'UNVERIFIED_ASSISTANCE'
        assert len(report['role_outputs']) == 1 and report['role_outputs'][0]['content'].strip(), 'MODEL_OUTPUT_MISSING'
        evidence['report_sha256'] = artifact_hash
        checks.append({'check': 'real-model-one-call-four-visible-findings-and-matching-visible-hashes', 'verified': True})
        time.sleep(5); sampler.finish(); evidence['resource_samples'] = sampler.rows
        stage = 'close_reopen'
        evidence['first_close_core_quiescence'] = screen.close()
        screen = None; host = None; app = None
        app, host, screen = open_desktop()
        screen.button(re.escape(OBJECTIVE) + '.*', regex=True)
        wait(lambda: '4 hallazgos para revisar' in screen.names(), description='persisted report visible')
        assert readonly_counts(state) == {'attempts': 1, 'calls': 1, 'states': ['ACCEPTED']}, 'REOPEN_REEXECUTED_WORK'
        assert '2 intentos disponibles' in screen.names(), 'REOPEN_LOST_BUDGET'
        screen.screenshot(output / '05-reopened.png')
        checks.append({'check': 'normal-close-owned-core-exit-reopen-without-new-attempt-or-call', 'verified': True})
        stage = 'cancel_second_attempt'
        screen.button('Nuevo encargo')
        screen.button('Consultar al Director')
        screen.objective(SECOND)
        screen.button('Elegir archivo HTML'); native_picker(host, source)
        wait(lambda: 'audit-sample.html' in screen.names(), description='second source captured')
        stage = 'history_preserves_unsent_draft'
        screen.button(re.escape(OBJECTIVE) + '.*', regex=True)
        wait(lambda: '4 hallazgos para revisar' in screen.names(), description='previous report opened from draft')
        screen.button('Volver al borrador')
        wait(lambda: screen.control('Tu encargo al Director', 'Edit').get_value() == SECOND,
             description='unsent draft survived history without rewriting it')
        assert 'audit-sample.html' in screen.names(), 'HISTORY_LOST_CAPTURED_SOURCE'
        assert readonly_counts(state) == {'attempts': 1, 'calls': 1, 'states': ['ACCEPTED']}, 'DRAFT_NAVIGATION_RESERVED_WORK'
        checks.append({'check': 'history-return-retains-exact-draft-and-source-without-reservation', 'verified': True})
        screen.screenshot(output / '05-draft-return.png')
        stage = 'cancel_second_attempt'
        screen.button('Revisar encargo.*', regex=True)
        wait(lambda: 'el saldo pasará a 1 de 3' in screen.names(), description='second visible approval with one left after reservation')
        screen.button('Autorizar y ejecutar.*', regex=True)
        screen.button('.*Detener trabajo', regex=True)
        wait(lambda: 'Encargo detenido' in screen.names(), timeout=90, description='confirmed cancellation')
        counts = readonly_counts(state)
        assert counts['attempts'] == 2 and counts['calls'] in (1, 2) and counts['states'] == ['ACCEPTED', 'CANCELLED'], 'CANCEL_CONTRACT'
        assert '1 intento disponible' in screen.names(), 'CANCEL_BUDGET_NOT_VISIBLE'
        assert 'Encargo detenido' in screen.control(re.escape(SECOND) + '.*', regex=True).window_text(), 'HISTORY_TERMINAL_STATE_STALE'
        def cancelled_delivery_header():
            delivery = screen.window.child_window(auto_id='connected-delivery').wrapper_object()
            labels = [control.element_info.name for control in delivery.descendants(control_type='Text')
                      if control.is_visible()]
            return 'Sin informe validado' in labels and 'Esperando informe' not in labels
        wait(cancelled_delivery_header, timeout=15, description='cancelled delivery section no longer promises a report')
        checks.append({'check': 'cancelled-delivery-header-terminal-without-report', 'verified': True})
        wait(lambda: not any(p.name().lower() in ('ollama.exe', 'llama-server.exe') for p in host.children(recursive=True)), description='backend stopped')
        screen.screenshot(output / '06-cancelled.png')
        evidence['final_counts'] = counts
        checks.append({'check': 'native-cancellation-history-quota-and-owned-backend-quiescence', 'verified': True})
        if args.profile_work:
            stage = 'measure_packaged_work'
            screen.close()
            screen = None
            evidence['work_profiles'] = []
            for arm in (0, 1):
                subprocess.run([sys.executable, '-B', '-m', 'tools.measure_v58_desktop',
                                '--executable', str(executable), '--expected-sha256', evidence['executable_sha256'],
                                '--version', release, '--arm', str(arm), '--output', str(work/'profiles')],
                               cwd=root, env=env, check=True, timeout=360)
                profile = json.loads((work/'profiles'/f'native-{arm}'/'result.json').read_bytes())
                assert profile['job_empty'] and profile['close']['exited'] and profile['exe_sha256'] == evidence['executable_sha256']
                for row in profile['rows']:
                    before, after = row['counts_before'], row['counts_after']
                    calls = after['calls'] - before['calls']
                    attempts = len(after['states']) - len(before['states'])
                    assert calls == attempts == arm
                    evidence['work_profiles'].append({'roles':arm, 'phase':row['phase'], 'attempts':attempts,
                                                      'calls':calls, **row['work']})
            checks.append({'check':'static-and-one-role-first-and-repeat-job-counters','verified':True})
        evidence['status'] = 'passed'
    except Exception as error:
        evidence['status'] = 'failed'
        evidence['failure'] = {'stage': stage, 'type': type(error).__name__, 'message': sanitized(str(error))[:8000]}
        if stage == 'real_inference' and state.is_file():
            try:
                evidence['failure']['durable_counts'] = readonly_counts(state)
                with closing(sqlite3.connect(state.as_uri()+'?mode=ro',uri=True)) as con:
                    first = con.execute('SELECT id FROM attempts ORDER BY rowid LIMIT 1').fetchone()
                if first and re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',first[0]):
                    evidence['failure']['startup_stages'] = startup_tail(work/'logs'/(first[0]+'.log'))
            except (OSError,sqlite3.Error) as diagnostic_error:
                evidence['failure']['diagnostic_error'] = type(diagnostic_error).__name__
        if screen:
            try:
                evidence['failure']['controls'] = json.loads(sanitized(screen.inventory()))
                screen.screenshot(output / 'failure.png')
            except Exception as capture_error:
                evidence['failure']['capture_error'] = type(capture_error).__name__
        raise
    finally:
        if sampler:
            sampler.finish(); evidence['resource_samples'] = sampler.rows
        if screen:
            try: screen.close()
            except Exception: pass
        for process in (app, metadata):
            if process and process.poll() is None:
                try:
                    for child in reversed(psutil.Process(process.pid).children(recursive=True)):
                        try: child.terminate()
                        except psutil.Error: pass
                    process.terminate(); process.wait(timeout=15)
                except (psutil.Error, subprocess.TimeoutExpired):
                    if process.poll() is None: process.kill()
        for log in logs: log.close()
        (output / 'verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'native_uia_e2e': evidence['status'], 'checks': len(checks), 'last_stage': stage}))


if __name__ == '__main__':
    main()
