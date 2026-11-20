"""Verify V5.12 through a packaged Windows host, native controls and an isolated ledger."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import runpy
import socket
import sqlite3
import sys
import tempfile
import threading
import time

from neural_office.desktop_contract import decode_command
from neural_office.desktop_service import DesktopService
from neural_office.ledger import Denied, Ledger
from neural_office.runner import run
from tools.measure_v58 import ROOT, require
from tools.verify_v510_desktop import choose_source, incident, wait, window

A, B = 'Proyecto-A', 'Proyecto-B'
PROFILE = {'mode': 'fixture', 'model': 'modelo de prueba', 'model_digest': 'a' * 64, 'roles': 1}
ARCHIVED = 'Revisar el formulario archivado'
LIVE = 'Revisar las etiquetas del formulario actual'


class FixtureModel:
    def __init__(self, *_):
        self.stopped = threading.Event()

    def start(self):
        pass

    def infer(self, _):
        return {'done': True, 'message': {'content': 'Comentario sintético para la lectura del informe.'}}

    def request_stop(self):
        self.stopped.set()

    def terminate(self):
        self.stopped.set()

    def close(self):
        pass


class WaitingModel(FixtureModel):
    def infer(self, _):
        if not self.stopped.wait(150):
            raise RuntimeError('test backend exceeded its lifetime')
        raise Denied('CANCELLED')


def test_peer(folder, mode):
    """Private sidecar for this test only. Production gets no new RPC or fault flag."""
    def hold(marker, release):
        (folder/marker).touch()
        deadline = time.monotonic() + 75
        while not (folder/release).exists():
            if time.monotonic() >= deadline:
                raise RuntimeError('The observer did not release the fixture.')
            time.sleep(.025)

    def catalog():
        if mode == 'slow':
            hold('catalog-held', 'release-catalog')
        return [] if mode in ('empty', 'slow') else [PROFILE]

    class Peer(DesktopService):
        def dispatch(self, raw):
            command = decode_command(raw)
            method = command['method']
            if mode == 'control' and method == 'report.read' and not (folder/'fault-seen').exists():
                require(command['params']['attempt_id'] == archived, 'wrong report fault target')
                super().dispatch(raw)  # The accepted report and requested bytes must exist.
                hold('fault-seen', 'release-read')
                raise Denied('HOST_RESPONSE_TIMEOUT')
            if mode == 'control' and method == 'attempt.get' and command['params']['attempt_id'] == live:
                if (folder/'fault-seen').exists() and not (folder/'release-read').exists():
                    hold('poll-held', 'release-read')
            return super().dispatch(raw)

    ledger = Ledger(folder/'office.sqlite3')
    service = Peer(ledger, backend_factory=WaitingModel, model_discovery=catalog)
    if mode == 'control':
        archived = (folder/'archived-id').read_text(encoding='ascii')
        source = service.host_capture(A, folder/A/'documento-a.html')
        preview = service.preview(A, source['entry_token'], PROFILE['model_digest'], 1, LIVE)
        live = service.start(preview['approval_token'], 'live-control', preview['expected_revision'])['id']
    serve = runpy.run_path(str(ROOT/'neural_office/desktop_stdio.py'), run_name='neural_office.test_stdio')['serve']
    return serve(service, sys.stdin.buffer, sys.stdout.buffer)


def private_core(folder, mode):
    package = folder/'peer'/'neural_office'
    package.mkdir(parents=True)
    original = ROOT/'neural_office'
    init = (original/'__init__.py').read_text(encoding='utf-8')
    (package/'__init__.py').write_text(init + f'\n__path__.append({str(original)!r})\n', encoding='utf-8')
    code = (f'import sys\nfrom pathlib import Path\nsys.path.append({str(ROOT)!r})\n'
            'from tools.verify_v512_desktop import test_peer\n'
            f'raise SystemExit(test_peer(Path({str(folder)!r}), {mode!r}))\n')
    compile(code, 'desktop_stdio.py', 'exec')
    (package/'desktop_stdio.py').write_text(code, encoding='utf-8')
    return package.parent


def stored(folder):
    with closing(sqlite3.connect((folder/'office.sqlite3').as_uri()+'?mode=ro', uri=True)) as db:
        attempts = db.execute('SELECT project,id,state FROM attempts ORDER BY project,ordinal').fetchall()
        calls = db.execute('SELECT count(*) FROM calls').fetchone()[0]
        stops = db.execute("SELECT json_extract(payload,'$.attempt') FROM events WHERE kind='CANCELLATION_REQUESTED' ORDER BY seq").fetchall()
        return attempts, calls, [s[0] for s in stops]


def inspect_without_model(exe, folder, version, mode):
    core = ROOT if mode == 'offline' else private_core(folder, mode)
    if mode == 'offline':
        with socket.socket() as sock:
            sock.settimeout(2)
            require(sock.connect_ex(('127.0.0.1', 11434)) != 0, 'real offline check requires an unused Ollama port')
    sample = (ROOT/'examples/audit-sample.html').read_bytes()
    with window(exe, core, folder, version) as (screen, host, _, _ready):
        for number in range(1 if mode == 'slow' else 2):
            if number:
                screen.button('Crear otro proyecto')
            source = folder/str(number)/'audit-sample.html'
            source.parent.mkdir()
            source.write_bytes(sample)
            choose_source(screen, host, source)
            wait(lambda: source.name in screen.names(), description='source was captured')
            screen.button('Consultar al Director')
            diagnostic = 'MODEL_METADATA_UNAVAILABLE' if mode=='offline' else 'Modelo local para la consulta'
            if mode=='slow':
                wait(lambda: (folder/'catalog-held').is_file(), description='catalogue barrier entered')
            else:
                wait(lambda: diagnostic in screen.names(), description='explicit model catalog outcome')
            require('4 hallazgos para revisar' not in screen.names(), 'stale result before static check')
            try:
                # The optional model guide can push the free action below the fold.
                screen.reveal_button('Comprobar HTML').invoke()
                wait(lambda: all(label in screen.names(visible_only=False) for label in ('4 hallazgos para revisar','Línea 7 · columna 3')),
                     description='static results and source position before catalogue release')
            finally:
                if mode=='slow':
                    (folder/'release-catalog').touch()
            require(stored(folder) == ([], 0, []), 'free check consumed work')
            require(not any(p.name().lower() == 'ollama.exe' for p in host.children(recursive=True)), 'a model was launched')
    return {'projects_checked': number + 1, 'findings_per_file': 4, 'attempts': 0, 'model_calls': 0,
            'catalogue': mode}


def selected_balance(screen, project, remaining):
    group = screen.window.child_window(auto_id='project-balance', control_type='Group').wrapper_object()
    texts = [child.element_info.name for child in group.descendants(control_type='Text') if child.is_visible()]
    return group.element_info.name == 'Saldo del proyecto ' + project and remaining in texts


def two_projects(exe, folder, version, out):
    sample = (ROOT/'examples/audit-sample.html').read_bytes()
    for project, name in [(A,'documento-a.html'),(B,'documento-b.html')]:
        (folder/project).mkdir()
        (folder/project/name).write_bytes(sample)
    ledger = Ledger(folder/'office.sqlite3')
    ledger.initialize()
    ledger.register(B, folder/B)
    first = ledger.reserve(B, 'Primer encargo del historial', sample, PROFILE, 'old-one', admit=True)
    require(ledger.cancel(first) == 'CANCELLED', 'could not seed the archived debit')
    archived = ledger.reserve(B, ARCHIVED, sample, PROFILE, 'old-two', admit=True, source_name='documento-b.html')
    require(run(ledger, archived, 1, FixtureModel) == 'ACCEPTED', 'could not seed a verified report')
    (folder/'archived-id').write_text(archived, encoding='ascii')
    core = private_core(folder, 'control')
    with window(exe, core, folder, version) as (screen, host, _, _ready):
        wait(lambda: selected_balance(screen,A,'2 intentos disponibles'), description='active project balance')
        wait(lambda: 'En curso' in screen.names() and 'documento-a.html' in screen.names(),
             description='active role, source and running call in the default activity view')
        screen.screenshot(out/'actividad.png')
        receipt = 'Llamada autorizada'
        require(receipt not in screen.names(visible_only=False), 'job receipts must start collapsed')
        activity = screen.reveal_button(r'(?s).*Actividad del encargo.*', regex=True)
        screen.press_space(activity)
        wait(lambda: all(text in screen.names(visible_only=False) for text in ('Intento reservado', 'Llamada autorizada')),
             description='recorded reservation and admitted model call on the active project')
        screen.screenshot(out/'actividad-detalle.png')
        screen.press_space(activity)
        wait(lambda: receipt not in screen.names(visible_only=False),
             description='closing job activity also removes the receipt from the accessibility tree')
        before, calls, old_stops = stored(folder)
        active, = [row[1] for row in before if row[0] == A and row[2] == 'RUNNING']
        require(len(before) == 3 and calls == 2, 'three seeded charges and two real call receipts expected')
        screen.button(B+'.*', regex=True)
        wait(lambda: selected_balance(screen,B,'1 intento disponible'), description='history project balance')
        controls = screen.window.child_window(title='Control del trabajo en curso')
        stop = controls.child_window(title_re=r'.*Detener trabajo.*' + A + '$', control_type='Button')
        require(stop.exists() and stop.is_enabled(), 'Stop lost its active project identity')
        screen.button(ARCHIVED+'.*', regex=True)
        try:
            wait(lambda: (folder/'fault-seen').is_file() and (folder/'poll-held').is_file(),
                 description='archive B and active poll A are both retained')
            stop = screen.control(r'.*Detener trabajo.*' + A + '$', regex=True)
            stop.invoke()
            wait(lambda: stored(folder)[2] == old_stops + [active], timeout=6,
                 description='independent ledger observed A stop while both readers are held')
        finally:
            (folder/'release-read').touch()
        wait(lambda: any(row == (A,active,'CANCELLED') for row in stored(folder)[0]), description='durable stop on A')
        draft = screen.control('Preparar otro encargo.*', regex=True)
        require(draft.window_text().endswith(B), 'new draft not bound to archived project')
        screen.button('Reintentar lectura del informe')
        wait(lambda: '4 hallazgos para revisar' in screen.names(), description='retry retrieved the same accepted report')
        screen.button('Preparar otro encargo.*', regex=True)
        choose_source(screen, host, folder/B/'documento-b.html')
        wait(lambda: 'documento-b.html' in screen.names() and selected_balance(screen,B,'1 intento disponible'),
             description='B draft accepts its own source')
        after, final_calls, stops = stored(folder)
        require(after == [(A,active,'CANCELLED'),(B,first,'CANCELLED'),(B,archived,'ACCEPTED')], 'wrong durable outcome')
        require(calls == final_calls and stops == old_stops + [active], 'duplicate work or wrong cancellation')
    return {'A_remaining': 2, 'B_remaining': 1, 'attempts_before': len(before), 'attempts_after': len(after),
            'admitted_calls_before': calls, 'admitted_calls_after': final_calls, 'new_stop_receipts_for_A': 1,
            'archived_report_retrieved': True, 'draft_reopened_in_B': True, 'stop_enabled_before_next_active_read': True,
            'admitted_call_and_reservation_disclosed': True, 'stop_committed_before_both_reads_released': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    exe = args.exe.resolve(strict=True)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    version = json.loads((ROOT/'desktop/src-tauri/tauri.conf.json').read_bytes())['version']
    result = {'version': version, 'exe_sha256': hashlib.sha256(exe.read_bytes()).hexdigest()}
    with tempfile.TemporaryDirectory(prefix='neural-v512-') as temp:
        for name in ('offline','empty','slow','control'):
            folder = Path(temp)/name
            folder.mkdir()
            print('Checking', name, flush=True)
            result[name] = (two_projects(exe,folder,version,out) if name == 'control' else
                            inspect_without_model(exe,folder,version,name))
        for name,fail_balance in [('historical_stop',False),('failed_balance_refresh',True)]:
            folder = Path(temp)/name
            folder.mkdir()
            result[name] = incident(exe,folder,fail_snapshot=fail_balance,evidence_dir=out)
    (out/'verification.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
