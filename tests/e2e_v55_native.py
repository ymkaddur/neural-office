"""CI-only real Windows desktop test; no renderer/IPC/model mocks.

The harness uses W3C WebDriver for the packaged WebView and UI Automation for
the host-owned file dialog. Its inputs, ledger and model cache are disposable.
It must not be used to work around a user's application-control policy.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile

MODEL = 'qwen2.5:0.5b'
MODEL_DIGEST = 'a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67'
OLLAMA_VERSION = '0.40.16'
OLLAMA_SHA256 = '50fcf5ad54277f2fa5d173ebfc93bcb017adbc0c9ef2314daabc96ca9e6aa64e'
EXPECTED_FINDINGS = [
    ('DOCUMENT_TITLE_MISSING', 1, 1), ('HTML_LANGUAGE_MISSING', 2, 1),
    ('IMAGE_ALT_MISSING', 6, 3), ('CONTROL_LABEL_CANDIDATE', 7, 3),
]
ELEMENT = 'element-6066-11e4-a52e-4f735466cecf'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def http(method, url, data=None, timeout=90):
    if not url.startswith(('http://127.0.0.1:4444/', 'http://127.0.0.1:11434/')):
        raise ValueError('TEST_CONTROL_ENDPOINT_NOT_LOCAL')
    raw = None if data is None else json.dumps(data).encode()
    request = urllib.request.Request(url, raw, {'Content-Type': 'application/json'}, method=method)
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=timeout) as response:
            body = response.read(24 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as error:
        try:
            value = json.loads(error.read(65536)).get('value', {})
            code, message = value.get('error', ''), value.get('message', '')
        except (ValueError, AttributeError):
            code, message = '', ''
        # A status alone concealed the cause of the first native-session failure.
        # Keep bounded diagnostic detail; main sanitizes this CI-only evidence.
        raise RuntimeError(f'HTTP_{error.code}:{code}:{message[:8000]}') from None
    if len(body) > 24 * 1024 * 1024:
        raise RuntimeError('TEST_RESPONSE_TOO_LARGE')
    return json.loads(body)


def wait(test, timeout=45, description='condition'):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            result = test()
            if result:
                return result
        except (OSError, RuntimeError, KeyError) as error:
            last = type(error).__name__
        time.sleep(.2)
    raise AssertionError(f'TIMEOUT:{description}:{last or "not observed"}')


class Driver:
    def __init__(self, executable):
        value = http('POST', 'http://127.0.0.1:4444/session', {
            'capabilities': {'alwaysMatch': {'tauri:options': {'application': str(executable)}}}
        })['value']
        self.session = value['sessionId']

    def call(self, method, route, data=None):
        return http(method, f'http://127.0.0.1:4444/session/{self.session}{route}', data)['value']

    def script(self, code, *args):
        return self.call('POST', '/execute/sync', {'script': code, 'args': list(args)})

    def find(self, selector):
        return self.call('POST', '/element', {'using': 'css selector', 'value': selector})[ELEMENT]

    def click(self, selector):
        self.call('POST', f'/element/{self.find(selector)}/click', {})

    def type(self, selector, text):
        self.call('POST', f'/element/{self.find(selector)}/value', {'text': text})

    def screenshot(self, path):
        Path(path).write_bytes(base64.b64decode(self.call('GET', '/screenshot'), validate=True))

    def body(self):
        return self.script('return document.body.innerText')

    def close_session(self):
        try:
            self.call('DELETE', '')
        except (RuntimeError, OSError):
            pass  # The native WM_CLOSE can already have destroyed this session.


class Samples:
    """Observed process-tree RSS/private commit and CPU; shared pages may repeat."""
    def __init__(self, host):
        self.host = host
        self.phase = 'idle_before'
        self.rows = []
        self.stop = threading.Event()
        self.worker = threading.Thread(target=self.run, daemon=True)
        self.worker.start()

    def run(self):
        import psutil
        while not self.stop.is_set():
            groups = {}
            unreadable = 0
            try:
                processes = [self.host, *self.host.children(recursive=True)]
            except psutil.Error:
                self.rows.append({'monotonic_ns': time.monotonic_ns(), 'phase': self.phase,
                                  'groups': {}, 'unreadable_processes': 1, 'complete': False})
                break
            for process in processes:
                try:
                    name = process.name().lower()
                    group = ('host' if process.pid == self.host.pid else 'webview' if 'msedgewebview2' in name
                             else 'python' if name.startswith('python') else 'model_backend'
                             if name in ('ollama.exe', 'llama-server.exe') else 'other_child')
                    memory, cpu = process.memory_info(), process.cpu_times()
                    item = groups.setdefault(group, {'processes': 0, 'rss_bytes': 0,
                                                     'private_bytes': 0, 'cpu_seconds': 0.0})
                    item['processes'] += 1
                    item['rss_bytes'] += memory.rss
                    item['private_bytes'] += memory.private
                    item['cpu_seconds'] += cpu.user + cpu.system
                except (psutil.Error, AttributeError):
                    unreadable += 1
                    continue
            self.rows.append({'monotonic_ns': time.monotonic_ns(), 'phase': self.phase,
                              'groups': groups, 'unreadable_processes': unreadable,
                              'complete': unreadable == 0})
            self.stop.wait(.5)

    def finish(self):
        self.stop.set()
        self.worker.join(5)


def prepare_ollama(tools):
    archive = tools / 'ollama.zip'
    urllib.request.urlretrieve(
        f'https://github.com/ollama/ollama/releases/download/v{OLLAMA_VERSION}/ollama-windows-amd64.zip', archive)
    if sha(archive) != OLLAMA_SHA256:
        raise AssertionError('OLLAMA_ARCHIVE_HASH_CHANGED')
    root = tools / 'ollama'
    root.mkdir()
    # The pinned distribution places CPU backends directly in lib/ollama.
    # GPU subdirectories and the tray application are deliberately not loaded.
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            name = PurePosixPath(entry.filename.replace('\\', '/'))
            if name.is_absolute() or '..' in name.parts or ':' in entry.filename:
                raise AssertionError('UNSAFE_ARCHIVE_ENTRY')
            if entry.is_dir():
                continue
            if name.as_posix() == 'ollama.exe' or name.parent.as_posix() == 'lib/ollama':
                target = root.joinpath(*name.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(entry) as source, target.open('wb') as output:
                    shutil.copyfileobj(source, output)
    if not (root / 'ollama.exe').is_file() or not list((root / 'lib/ollama').glob('ggml-cpu-*.dll')):
        raise AssertionError('PINNED_CPU_DISTRIBUTION_LAYOUT_CHANGED')
    return root


def readonly_counts(state):
    with closing(sqlite3.connect(state.as_uri() + '?mode=ro', uri=True)) as con:
        return {'attempts': con.execute('SELECT count(*) FROM attempts').fetchone()[0],
                'calls': con.execute('SELECT count(*) FROM calls').fetchone()[0],
                'states': [row[0] for row in con.execute('SELECT state FROM attempts ORDER BY ordinal')]}


def native_picker(host, source):
    from pywinauto import Application
    dialog = Application(backend='uia').connect(process=host.pid).window(title='Elegir HTML para revisar')
    dialog.wait('visible', timeout=20)
    # File name is the native IFileDialog edit (1001), not an injected JS path.
    field = dialog.child_window(auto_id='1001', control_type='Edit')
    field.wait('enabled', timeout=10)
    field.set_edit_text(str(source))
    dialog.child_window(auto_id='1', control_type='Button').invoke()
    dialog.wait_not('visible', timeout=20)


def graceful_close(host):
    from pywinauto import Application
    Application(backend='win32').connect(process=host.pid).window(title_re='Neural Office.*').close()
    host.wait(timeout=30)


def main():
    if os.name != 'nt' or os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_OS') != 'Windows':
        raise SystemExit('CI_ONLY: this test never bypasses local application-control policies')
    import psutil
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    tools = Path(os.environ['NO_E2E_TOOLS']).resolve()
    work = Path(tempfile.mkdtemp(prefix='neural-office-native-', dir=os.environ['RUNNER_TEMP']))
    state = work / 'state.sqlite3'
    source = work / 'audit-sample.html'
    shutil.copyfile(root / 'examples/audit-sample.html', source)
    executable = root / 'desktop/src-tauri/target/release/neural-office-desktop.exe'
    evidence = {'schema': 1, 'commit': os.environ.get('GITHUB_SHA'), 'status': 'running',
                'test': 'real-packaged-windows-desktop', 'model': MODEL,
                'source_sha256': sha(source), 'executable_sha256': sha(executable),
                'tools': json.loads((tools / 'tools.json').read_text(encoding='utf-8-sig')),
                'checks': [], 'limitations': [
                    'One synthetic HTML task and one cancellation; no semantic model quality claim.',
                    'Windows GitHub runner only; does not override a user machine application-control policy.',
                    'RSS sums may double-count shared pages; sampling is not a peak or leak proof.',
                    'Metadata server and test drivers are excluded from app resource samples.',
                    'Native dialog automation is not a human usability or accessibility audit.']}
    steps = evidence['checks']
    driver = host = sampler = metadata = driver_process = None
    logs = []
    def sanitized(text):
        for path, label in ((str(work), '<synthetic-work>'), (str(root), '<repository>'),
                            (str(tools), '<test-tools>'), (str(Path.home()), '<runner-home>'),
                            (sys.executable, '<test-python>')):
            text = text.replace(path, label).replace(path.replace('\\', '/'), label)
        return text

    stage = 'prepare_tools'
    try:
        ollama_root = prepare_ollama(tools)
        for port in (11434, 4444, 4445):
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', port))  # Never take over an existing service.
        env = os.environ.copy()
        env.update({'PATH': str(ollama_root) + os.pathsep + env['PATH'],
                    'OLLAMA_HOST': '127.0.0.1:11434', 'OLLAMA_NO_CLOUD': '1',
                    'OLLAMA_MODELS': str(work / 'models'), 'NEURAL_OFFICE_ROOT': str(root),
                    'NEURAL_OFFICE_PYTHON': sys.executable, 'NEURAL_OFFICE_STATE': str(state)})
        log = (work / 'metadata.log').open('wb'); logs.append(log)
        metadata = subprocess.Popen([str(ollama_root / 'ollama.exe'), 'serve'], env=env,
                                    stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        wait(lambda: http('GET', 'http://127.0.0.1:11434/api/version', timeout=5), description='metadata server')
        stage = 'pull_public_model'
        pulled = http('POST', 'http://127.0.0.1:11434/api/pull', {'name': MODEL, 'stream': False}, timeout=600)
        assert pulled.get('status') == 'success', 'MODEL_PULL_FAILED'
        models = http('GET', 'http://127.0.0.1:11434/api/tags')['models']
        assert len(models) == 1 and models[0]['name'] == MODEL, 'UNEXPECTED_MODEL_CATALOG'
        assert models[0]['digest'] == MODEL_DIGEST, 'PUBLIC_MODEL_TAG_CHANGED'
        evidence['model_digest'] = models[0]['digest']
        evidence['ollama_version'] = OLLAMA_VERSION
        evidence['ollama_archive_sha256'] = OLLAMA_SHA256
        driver_log = (work / 'driver.log').open('wb'); logs.append(driver_log)
        driver_path = Path.home() / '.cargo/bin/tauri-driver.exe'
        driver_process = subprocess.Popen([str(driver_path), '--native-driver', str(tools / 'edge/msedgedriver.exe')],
                                          env=env, stdout=driver_log, stderr=driver_log,
                                          creationflags=subprocess.CREATE_NO_WINDOW)
        wait(lambda: http('GET', 'http://127.0.0.1:4444/status', timeout=5), description='webdriver server')

        def open_desktop():
            current = Driver(executable)
            def find_host():
                return next((p for p in psutil.Process(driver_process.pid).children(recursive=True)
                             if p.name().lower() == executable.name.lower()), None)
            owned = wait(find_host, description='owned desktop process')
            wait(lambda: 'Núcleo local conectado' in current.body(), description='native IPC ready')
            url = current.call('GET', '/url')
            assert url.startswith(('http://tauri.localhost/', 'https://tauri.localhost/', 'tauri://localhost/')), 'DEV_SERVER_USED'
            assert current.script('return !!window.__TAURI_INTERNALS__'), 'NATIVE_HOST_MISSING'
            return current, owned

        stage = 'open_packaged_ui'
        driver, host = open_desktop()
        sampler = Samples(host)
        wait(lambda: MODEL in driver.script('return document.querySelector("#connected-model").innerText'), description='real model in UI')
        driver.screenshot(output / '01-ready.png')
        time.sleep(5)  # Explicitly measured idle window, not synchronization for a race.
        steps.append({'check': 'packaged-assets-native-ipc-model-catalog', 'verified': True})
        stage = 'native_source_and_approval'
        sampler.phase = 'prepare'
        driver.type('#connected-objective', 'Revisa las barreras de accesibilidad y prioriza los hallazgos del HTML sintético.')
        driver.click('.source-picker')
        native_picker(host, source)
        wait(lambda: 'audit-sample.html' in driver.script('return document.querySelector(".source-picker").innerText'), description='captured source')
        driver.click('.connected-send-row button[type=submit]')
        wait(lambda: driver.script('return document.querySelector("dialog").open'), description='approval dialog')
        assert 'Consumirá 1 intento' in driver.body(), 'APPROVAL_BUDGET_MISSING'
        assert readonly_counts(state)['attempts'] == 0, 'PREVIEW_CONSUMED_ATTEMPT'
        driver.screenshot(output / '02-approval.png')
        steps.append({'check': 'native-file-picker-and-zero-consumption-before-approval', 'verified': True})
        stage = 'real_inference'
        sampler.phase = 'work'
        began = time.monotonic()
        driver.click('.approval-actions .solid-button')
        wait(lambda: driver.script('return !!document.querySelector(".connected-work-status")'), description='reserved attempt')
        driver.screenshot(output / '03-running.png')
        wait(lambda: driver.script('return !!document.querySelector(".connected-report")'), timeout=360, description='real report rendered')
        evidence['first_delivery_seconds'] = round(time.monotonic() - began, 3)
        sampler.phase = 'idle_after'
        assert 'Entrega disponible' in driver.body(), 'REPORT_NOT_ACCEPTED'
        assert readonly_counts(state) == {'attempts': 1, 'calls': 1, 'states': ['ACCEPTED']}, 'REAL_CALL_OR_QUOTA_MISMATCH'
        driver.screenshot(output / '04-result.png')
        driver.click('#tab-evidence')
        driver.click('.connected-evidence details summary')
        report_text = driver.script('return document.querySelector(".connected-evidence pre").textContent')
        report = json.loads(report_text)
        actual = [(f['code'], f['line'], f['column']) for f in report['findings']]
        assert actual == EXPECTED_FINDINGS, 'INDEPENDENT_STATIC_ORACLE_MISMATCH'
        assert report['source_sha256'] == sha(source), 'SOURCE_CHANGED'
        assert report['model_commentary_status'] == 'UNVERIFIED_ASSISTANCE', 'MODEL_CLAIM_UNBOUNDED'
        assert len(report['role_outputs']) == 1 and report['role_outputs'][0]['content'].strip(), 'MODEL_OUTPUT_MISSING'
        evidence['report_sha256'] = hashlib.sha256(report_text.encode()).hexdigest()
        with closing(sqlite3.connect(state.as_uri() + '?mode=ro', uri=True)) as con:
            stored_hash = con.execute('SELECT artifact_sha FROM attempts WHERE ordinal=1').fetchone()[0]
        assert evidence['report_sha256'] == stored_hash, 'DISPLAYED_REPORT_HASH_CHANGED'
        steps.append({'check': 'real-ollama-one-call-four-static-findings-report-hash', 'verified': True})
        time.sleep(5)
        stage = 'close_reopen'
        sampler.finish()
        evidence['resource_samples'] = sampler.rows
        graceful_close(host); driver.close_session(); driver = None; host = None
        driver, host = open_desktop()
        driver.click('.connected-history button')
        wait(lambda: driver.script('return !!document.querySelector(".connected-report")'), description='persisted report after reopen')
        assert readonly_counts(state) == {'attempts': 1, 'calls': 1, 'states': ['ACCEPTED']}, 'REOPEN_REEXECUTED_WORK'
        assert '1 de 3 intentos' in driver.body(), 'REOPEN_LOST_BUDGET'
        driver.screenshot(output / '05-reopened.png')
        steps.append({'check': 'native-close-reopen-preserves-report-attempt-and-call-count', 'verified': True})
        stage = 'cancel_second_attempt'
        driver.click('.new-task')
        driver.type('#connected-objective', 'Revisa el mismo HTML sintético; esta ejecución se cancelará desde la interfaz.')
        driver.click('.source-picker'); native_picker(host, source)
        wait(lambda: 'audit-sample.html' in driver.script('return document.querySelector(".source-picker").innerText'), description='second captured source')
        driver.click('.connected-send-row button[type=submit]')
        wait(lambda: driver.script('return document.querySelector("dialog").open'), description='second approval')
        driver.click('.approval-actions .solid-button')
        wait(lambda: driver.script('return !!document.querySelector(".stop-button:not(:disabled)")'), description='cancellable work')
        driver.click('.stop-button')
        wait(lambda: 'Encargo detenido' in driver.script('return document.querySelector(".connected-work-status")?.innerText || ""'), timeout=90, description='confirmed cancellation')
        counts = readonly_counts(state)
        assert counts['attempts'] == 2 and counts['states'] == ['ACCEPTED', 'CANCELLED'], 'CANCELLATION_QUOTA_OR_STATE_CHANGED'
        assert 'Encargo detenido' in driver.script('return document.querySelector(".connected-history").innerText'), 'HISTORY_TERMINAL_STATE_STALE'
        wait(lambda: not any(p.name().lower() in ('ollama.exe', 'llama-server.exe') for p in host.children(recursive=True)), description='owned backend stopped')
        driver.screenshot(output / '06-cancelled.png')
        evidence['final_counts'] = counts
        steps.append({'check': 'native-cancel-confirmation-history-quota-and-backend-quiescence', 'verified': True})
        evidence['status'] = 'passed'
    except Exception as error:
        evidence['status'] = 'failed'
        evidence['failure'] = {'stage': stage, 'type': type(error).__name__,
                               'message': sanitized(str(error))[:8000]}
        if driver_process and driver_process.poll() is None:
            try:
                evidence['failure']['owned_driver_processes'] = [
                    {'name': child.name(), 'running': child.is_running()}
                    for child in psutil.Process(driver_process.pid).children(recursive=True)]
            except psutil.Error:
                evidence['failure']['owned_process_inventory'] = 'unavailable'
        if driver:
            try:
                driver.screenshot(output / 'failure.png')
            except Exception:
                pass
        raise
    finally:
        if sampler:
            sampler.finish()
            evidence['resource_samples'] = sampler.rows
        if host:
            try:
                graceful_close(host)
            except Exception:
                pass
        if driver:
            driver.close_session()
        # Only process identities created by this harness and their descendants.
        for owned in (driver_process, metadata):
            if owned and owned.poll() is None:
                try:
                    tree = psutil.Process(owned.pid).children(recursive=True)
                    for child in reversed(tree):
                        try: child.terminate()
                        except psutil.Error: pass
                    owned.terminate(); owned.wait(timeout=15)
                except (psutil.Error, subprocess.TimeoutExpired):
                    if owned.poll() is None: owned.kill()
        for log in logs:
            log.close()
        if evidence['status'] == 'failed':
            driver_log_path = work / 'driver.log'
            if driver_log_path.is_file():
                with driver_log_path.open('rb') as diagnostic:
                    diagnostic.seek(max(0, driver_log_path.stat().st_size - 32768))
                    tail = diagnostic.read().decode('utf-8', errors='replace')
                (output / 'driver-diagnostic.txt').write_text(sanitized(tail), encoding='utf-8')
        (output / 'verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'native_e2e': evidence['status'], 'checks': len(steps), 'last_stage': stage}))


if __name__ == '__main__':
    main()
