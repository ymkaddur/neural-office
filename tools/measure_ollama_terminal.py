"""Measure one real PowerShell/ollama run on Windows. Uses installed local weights."""
import argparse
from datetime import datetime, timezone
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from neural_office.measurements import JobSampler, job_sample
from neural_office.ollama import local_metadata, select_model
from neural_office.windows_job import Job


PROMPT = ('Fuentes locales. PDF: Primera respuesta en 24 horas. JSON: response_sla_hours = 48. '
          'Compara las dos fuentes. Responde en una sola frase en español con el origen de cada '
          'cifra y di si coinciden.')
# Only data passes through the environment. The command never treats the prompt as code.
QUERY = ("$ErrorActionPreference = 'Stop'; "
         "if ($PSVersionTable.PSVersion -lt [version]'7.4') { "
         "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); $OutputEncoding = [Console]::OutputEncoding }; "
         "'' | & $env:NEURAL_BENCH_OLLAMA run $env:NEURAL_BENCH_MODEL $env:NEURAL_BENCH_PROMPT "
         "> $env:NEURAL_BENCH_OUTPUT; exit $LASTEXITCODE")


def launch(job, command, env):
    import win32api
    import win32con
    import win32process
    process, thread, pid, _ = win32process.CreateProcess(
        command[0], subprocess.list2cmdline(command), None, None, False,
        win32con.CREATE_SUSPENDED | subprocess.CREATE_NO_WINDOW | win32con.CREATE_UNICODE_ENVIRONMENT,
        env, str(ROOT), win32process.STARTUPINFO())
    try:
        if not job.dll.AssignProcessToJobObject(job.handle, int(process)):
            raise ctypes.WinError(ctypes.get_last_error())
        win32process.ResumeThread(thread)
        return process, pid
    except BaseException:
        win32api.TerminateProcess(process, 1)
        process.Close()
        raise
    finally:
        thread.Close()


def require_listener(pid, port):
    import psutil
    listeners = psutil.Process(pid).net_connections(kind='tcp')
    if not any(c.status == psutil.CONN_LISTEN and c.laddr.ip == '127.0.0.1'
               and c.laddr.port == port for c in listeners):
        raise ConnectionError('The private server does not own the listener')


def peak_cpu_cores(samples):
    # Compare the endpoints of rolling windows at least one second long.
    left, peaks = 0, []
    for right, end in enumerate(samples):
        while left + 1 < right and end['elapsed_ns'] - samples[left + 1]['elapsed_ns'] >= 1e9:
            left += 1
        start = samples[left]
        elapsed = (end['elapsed_ns'] - start['elapsed_ns']) / 1e9
        if elapsed >= 1:
            peaks.append((end['cpu_seconds'] - start['cpu_seconds']) / elapsed)
    return round(max(peaks), 3) if peaks else None


def measure(job, shell, env, output, port, server_pid, expected_digest, phase):
    import win32event
    import win32process
    require_listener(server_pid, port)
    loaded = local_metadata('/api/ps', port)['models']
    if ((phase == 'cold' and loaded)
            or (phase == 'warm' and [m['digest'] for m in loaded] != [expected_digest])):
        raise RuntimeError('Unexpected initial model residency')
    sampler = JobSampler(job, interval=0.1)
    sampler.start()
    try:
        proc, _ = launch(job, [shell, '-NoLogo', '-NonInteractive', '-NoProfile', '-Command', QUERY],
                         {**env, 'NEURAL_BENCH_OUTPUT': str(output)})
        try:
            if win32event.WaitForSingleObject(proc, 120_000) != win32event.WAIT_OBJECT_0:
                raise TimeoutError('Terminal did not finish in 120 s')
            code = win32process.GetExitCodeProcess(proc)
            if code:
                raise RuntimeError(f'Terminal exited with {code}')
        finally:
            proc.Close()
        finished_s = (time.perf_counter_ns() - sampler.started_ns) / 1e9
        cpu_at_exit = job_sample(job)['cpu_seconds']
        # Observe a real full second even if the client has already returned.
        # Wall time and CPU per task still end at terminal exit.
        if finished_s < 1.1:
            time.sleep(1.1 - finished_s)
    finally:
        stats = sampler.stop()
    require_listener(server_pid, port)
    models = local_metadata('/api/ps', port)['models']
    if [m['digest'] for m in models] != [expected_digest]:
        raise RuntimeError('Unexpected model digest after generation')
    raw_answer = output.read_bytes()
    encoding = 'utf-16' if raw_answer.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    answer = raw_answer.decode(encoding).strip()
    if not answer:
        raise RuntimeError('Terminal returned no answer')
    start = sampler.samples[0] if sampler.samples else None
    cpu_delta = round(cpu_at_exit - start['cpu_seconds'], 3) if stats['complete'] and start else None
    return dict(phase=phase, elapsed_s=round(finished_s, 3), observed_s=round(stats['elapsed_seconds'], 3),
                cpu_s=cpu_delta,
                peak_cpu_cores_1s=peak_cpu_cores(sampler.samples) if stats['complete'] else None,
                peak_ws_bytes=stats['sampled_peak_working_set_sum_bytes'],
                peak_private_bytes=stats['sampled_peak_private_commit_sum_bytes'],
                samples=stats['sample_count'], complete=stats['complete'],
                incomplete_samples=stats['incomplete_samples'], observation_errors=stats['observation_errors'],
                resident={k: models[0].get(k) for k in ('context_length', 'size', 'size_vram')},
                answer=answer, mentions_both_values=all(re.search(rf'\b{n}\b', answer) for n in [24, 48]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='qwen2.5:0.5b')
    parser.add_argument('--warm', type=int, choices=range(0, 21), default=3)
    parser.add_argument('--output', type=Path, help='Write a new JSON file after all runs succeed')
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('Windows, pywin32 and psutil are required')
    if args.output and (args.output.exists() or not args.output.parent.is_dir()):
        parser.error('output must be a new file under an existing directory')
    ollama, shell = shutil.which('ollama'), shutil.which('pwsh') or shutil.which('powershell')
    if not ollama or not shell:
        parser.error('Ollama and PowerShell must be installed')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'OLLAMA_HOST': f'127.0.0.1:{port}', 'OLLAMA_NO_CLOUD': '1',
           'OLLAMA_MAX_LOADED_MODELS': '1', 'OLLAMA_NUM_PARALLEL': '1', 'OLLAMA_CONTEXT_LENGTH': '4096',
           'OLLAMA_KEEP_ALIVE': '5m', 'NEURAL_BENCH_MODEL': args.model, 'NEURAL_BENCH_OLLAMA': ollama,
           'NEURAL_BENCH_PROMPT': PROMPT}
    with tempfile.TemporaryDirectory() as folder, Job('NeuralOffice-Terminal-' + uuid.uuid4().hex) as job:
        server, pid = launch(job, [ollama, 'serve'], env)
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    require_listener(pid, port)
                    tags = local_metadata('/api/tags', port)['models']
                    break
                except (ConnectionError, TimeoutError):
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.2)
            model = select_model(args.model, tags)
            version = local_metadata('/api/version', port)['version']
            rows = [measure(job, shell, env, Path(folder) / f'{i}.txt', port, pid,
                            model['model_digest'], 'cold' if i == 0 else 'warm') for i in range(1 + args.warm)]
        finally:
            server.Close()
    import psutil
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
        cpu_model = winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
    shell_version = subprocess.check_output(
        [shell, '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', '$PSVersionTable.PSVersion.ToString()'],
        text=True, timeout=10).strip()
    report = dict(schema=2, captured_utc=datetime.now(timezone.utc).isoformat(), kind='single_terminal_baseline',
                  system=platform.platform(), logical_cpus=os.cpu_count(), powershell=Path(shell).name,
                  powershell_version=shell_version, cpu_model=cpu_model, host_ram_bytes=psutil.virtual_memory().total,
                  ollama=version, model=args.model, model_digest=model['model_digest'], prompt=PROMPT,
                  prompt_sha256=hashlib.sha256(PROMPT.encode()).hexdigest(), sample_interval_s=0.1,
                  scope='private ready server, runner, PowerShell and CLI; OS file cache not purged',
                  runs=rows)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.output:
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(encoded)
    else:
        print(encoded)


if __name__ == '__main__':
    main()
