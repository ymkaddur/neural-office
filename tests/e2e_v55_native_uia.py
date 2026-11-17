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


def wait(test, timeout=45, description='condition'):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            value = test()
            if value:
                return value
        except Exception as error:
            # Preserve the last UIA error category without converting it to a pass.
            last = f'{type(error).__name__}: {error}'[:1000]
        time.sleep(.5)
    raise AssertionError(f'TIMEOUT:{description}:{last or "not observed"}')


class Screen:
    def __init__(self, host):
        from pywinauto import Application
        self.host = host
        self.window = Application(backend='uia').connect(process=host.pid).window(title_re='Neural Office.*')
        self.window.wait('visible', timeout=30)

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
        editor.set_edit_text(text)
        assert editor.get_value() == text, 'EDIT_VALUE_NOT_ACCEPTED'

    def tab(self, name):
        self.control(name, 'TabItem').select()

    def screenshot(self, path):
        self.window.set_focus()
        self.window.capture_as_image().save(path)

    def close(self):
        from pywinauto import Application
        Application(backend='win32').connect(process=self.host.pid).window(title_re='Neural Office.*').close(wait_time=30)
        self.host.wait(timeout=30)

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


def main():
    if os.name != 'nt' or os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_OS') != 'Windows':
        raise SystemExit('CI_ONLY: no local application-control bypass')
    import psutil
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
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
        log = (work / 'metadata.log').open('wb'); logs.append(log)
        metadata = subprocess.Popen([str(ollama / 'ollama.exe'), 'serve'], env=env,
                                    stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        wait(lambda: http('GET', 'http://127.0.0.1:11434/api/version', timeout=5), description='metadata server')
        stage = 'pull_public_model'
        assert http('POST', 'http://127.0.0.1:11434/api/pull', {'name': MODEL, 'stream': False}, timeout=600).get('status') == 'success'
        models = http('GET', 'http://127.0.0.1:11434/api/tags')['models']
        assert len(models) == 1 and models[0]['name'] == MODEL and models[0]['digest'] == MODEL_DIGEST, 'MODEL_IDENTITY_CHANGED'
        evidence.update(model_digest=MODEL_DIGEST, ollama_version=OLLAMA_VERSION, ollama_archive_sha256=OLLAMA_SHA256)

        def open_desktop():
            nonlocal app, host, screen
            app = subprocess.Popen([str(executable)], env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            host = psutil.Process(app.pid)
            screen = Screen(host)
            wait(lambda: 'Núcleo local conectado' in screen.names(), description='native IPC ready')
            return app, host, screen

        stage = 'open_packaged_ui'
        app, host, screen = open_desktop()
        sampler = Samples(host)
        wait(lambda: screen.control('Modelo local', 'ComboBox').selected_text() == MODEL, description='real model selected')
        screen.screenshot(output / '01-ready.png')
        time.sleep(5)
        checks.append({'check': 'packaged-ui-native-ipc-real-catalog-no-devtools', 'verified': True})
        stage = 'native_source_and_approval'; sampler.phase = 'prepare'
        screen.objective(OBJECTIVE)
        screen.button('Elegir archivo HTML')
        native_picker(host, source)
        wait(lambda: 'audit-sample.html' in screen.names(), description='captured source')
        screen.button('Revisar encargo.*', regex=True)
        wait(lambda: 'Consumirá 1 intento' in screen.names(), description='visible approval')
        assert readonly_counts(state)['attempts'] == 0, 'PREVIEW_CONSUMED_ATTEMPT'
        screen.screenshot(output / '02-approval.png')
        checks.append({'check': 'native-file-picker-visible-approval-no-early-consumption', 'verified': True})
        stage = 'real_inference'; sampler.phase = 'work'; began = time.monotonic()
        screen.button('Autorizar y ejecutar.*', regex=True)
        wait(lambda: 'Tu encargo' in screen.names(), description='reserved attempt')
        screen.screenshot(output / '03-running.png')
        wait(lambda: '4 hallazgos para revisar' in screen.names(), timeout=360, description='real report rendered')
        evidence['first_delivery_seconds'] = round(time.monotonic() - began, 3)
        sampler.phase = 'idle_after'
        content = screen.names()
        assert 'Entrega disponible' in content and all(label in content for label in LABELS), 'FINDINGS_NOT_RENDERED'
        assert readonly_counts(state) == {'attempts': 1, 'calls': 1, 'states': ['ACCEPTED']}, 'CALL_OR_QUOTA_MISMATCH'
        screen.screenshot(output / '04-result.png')
        screen.tab('Evidencia y alcance')
        with closing(sqlite3.connect(state.as_uri() + '?mode=ro', uri=True)) as con:
            artifact, artifact_hash = con.execute('SELECT artifact,artifact_sha FROM attempts WHERE ordinal=1').fetchone()
        artifact = bytes(artifact); report = json.loads(artifact)
        content = screen.names()
        assert artifact_hash in content and sha(source) in content and MODEL_DIGEST in content, 'VISIBLE_EVIDENCE_HASH_MISSING'
        assert hashlib.sha256(artifact).hexdigest() == artifact_hash, 'STORED_REPORT_HASH_CHANGED'
        assert [(f['code'], f['line'], f['column']) for f in report['findings']] == EXPECTED_FINDINGS, 'STATIC_ORACLE_MISMATCH'
        assert report['source_sha256'] == sha(source) and report['model_commentary_status'] == 'UNVERIFIED_ASSISTANCE'
        assert len(report['role_outputs']) == 1 and report['role_outputs'][0]['content'].strip(), 'MODEL_OUTPUT_MISSING'
        evidence['report_sha256'] = artifact_hash
        checks.append({'check': 'real-model-one-call-four-visible-findings-and-matching-visible-hashes', 'verified': True})
        time.sleep(5); sampler.finish(); evidence['resource_samples'] = sampler.rows
        stage = 'close_reopen'
        screen.close(); screen = None; host = None; app = None
        app, host, screen = open_desktop()
        screen.button(re.escape(OBJECTIVE) + '.*', regex=True)
        wait(lambda: '4 hallazgos para revisar' in screen.names(), description='persisted report visible')
        assert readonly_counts(state) == {'attempts': 1, 'calls': 1, 'states': ['ACCEPTED']}, 'REOPEN_REEXECUTED_WORK'
        assert '1 de 3 intentos' in screen.names(), 'REOPEN_LOST_BUDGET'
        screen.screenshot(output / '05-reopened.png')
        checks.append({'check': 'normal-window-close-reopen-without-new-attempt-or-call', 'verified': True})
        stage = 'cancel_second_attempt'
        screen.button('Nuevo encargo')
        screen.objective(SECOND)
        screen.button('Elegir archivo HTML'); native_picker(host, source)
        wait(lambda: 'audit-sample.html' in screen.names(), description='second source captured')
        screen.button('Revisar encargo.*', regex=True)
        wait(lambda: 'Consumirá 1 intento' in screen.names(), description='second visible approval')
        screen.button('Autorizar y ejecutar.*', regex=True)
        screen.button('.*Detener trabajo', regex=True)
        wait(lambda: 'Encargo detenido' in screen.names(), timeout=90, description='confirmed cancellation')
        counts = readonly_counts(state)
        assert counts['attempts'] == 2 and counts['calls'] in (1, 2) and counts['states'] == ['ACCEPTED', 'CANCELLED'], 'CANCEL_CONTRACT'
        assert '2 de 3 intentos' in screen.names(), 'CANCEL_BUDGET_NOT_VISIBLE'
        assert 'Encargo detenido' in screen.control(re.escape(SECOND) + '.*', regex=True).window_text(), 'HISTORY_TERMINAL_STATE_STALE'
        wait(lambda: not any(p.name().lower() in ('ollama.exe', 'llama-server.exe') for p in host.children(recursive=True)), description='backend stopped')
        screen.screenshot(output / '06-cancelled.png')
        evidence['final_counts'] = counts
        checks.append({'check': 'native-cancellation-history-quota-and-owned-backend-quiescence', 'verified': True})
        evidence['status'] = 'passed'
    except Exception as error:
        evidence['status'] = 'failed'
        evidence['failure'] = {'stage': stage, 'type': type(error).__name__, 'message': sanitized(str(error))[:8000]}
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
