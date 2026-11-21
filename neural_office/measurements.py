"""Read-only measurements of our Windows Job, never the user's other processes.

Working sets may count shared pages more than once. Private commit is not physical
RAM. Samples can miss short peaks. A failed observation is unknown, never zero.
"""
import ctypes
from ctypes import wintypes as w
import math
import os
import threading
import time

from .windows_job import Accounting, BASIC_ACCOUNTING, ExtendedLimits, EXTENDED_LIMIT


class MemoryCounters(ctypes.Structure):
    _fields_ = [('cb', w.DWORD), ('PageFaultCount', w.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
            'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
            'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]


def nonnegative(value):
    if type(value) is int:
        return value if 0 <= value <= 2**53 - 1 else None
    if type(value) is float and math.isfinite(value) and 0 <= value <= 2**53 - 1:
        return value
    return None


def generation_metrics(response):
    """No guessed zeros, durations or first-token latency from non-streaming data."""
    names = ('total_duration', 'load_duration', 'prompt_eval_count',
             'prompt_eval_cached_count', 'prompt_eval_duration', 'eval_count', 'eval_duration')
    result = {name: nonnegative(response.get(name)) if type(response.get(name)) is int else None for name in names}
    count, duration = result['eval_count'], result['eval_duration']
    result['generated_tokens_per_second'] = (
        count * 1e9 / duration if count is not None and duration is not None and duration > 0 else None)
    result['first_token_ms'] = None
    result['first_token_reason'] = 'non_streaming_backend'
    return result


def job_sample(job):
    if job.handle is None:
        raise RuntimeError('MEASUREMENT_JOB_CLOSED')
    accounting, limits = Accounting(), ExtendedLimits()
    for kind, info in ((BASIC_ACCOUNTING, accounting), (EXTENDED_LIMIT, limits)):
        if not job.dll.QueryInformationJobObject(job.handle, kind, ctypes.byref(info), ctypes.sizeof(info), None):
            raise ctypes.WinError(ctypes.get_last_error())
    # JobObjectBasicProcessIdList (3): capacity is increased on ERROR_MORE_DATA.
    capacity = 8
    while capacity <= 4096:
        class ProcessList(ctypes.Structure):
            _fields_ = [('assigned', w.DWORD), ('count', w.DWORD),
                        ('pids', ctypes.c_size_t * capacity)]
        processes = ProcessList()
        if job.dll.QueryInformationJobObject(job.handle, 3, ctypes.byref(processes), ctypes.sizeof(processes), None):
            break
        error = ctypes.get_last_error()
        if error != 234:
            raise ctypes.WinError(error)
        capacity *= 2
    else:
        raise RuntimeError('MEASUREMENT_PROCESS_LIMIT')
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(MemoryCounters), w.DWORD]
    psapi.GetProcessMemoryInfo.restype = w.BOOL
    job.dll.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    job.dll.OpenProcess.restype = w.HANDLE
    job.dll.IsProcessInJob.argtypes = [w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)]
    job.dll.IsProcessInJob.restype = w.BOOL
    working_set = private_commit = 0
    missing = 0
    for pid in processes.pids[:processes.count]:
        handle = job.dll.OpenProcess(0x1010, False, pid)
        if not handle:
            missing += 1
            continue
        try:
            belongs = w.BOOL()
            if not job.dll.IsProcessInJob(handle, job.handle, ctypes.byref(belongs)) or not belongs.value:
                missing += 1
                continue
            info = MemoryCounters(); info.cb = ctypes.sizeof(info)
            if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(info), info.cb):
                missing += 1
                continue
            working_set += info.WorkingSetSize
            private_commit += info.PrivateUsage
        finally:
            job.dll.CloseHandle(handle)
    return {
        'cpu_seconds': (accounting.TotalUserTime + accounting.TotalKernelTime) / 1e7,
        'active_processes': accounting.ActiveProcesses,
        'job_peak_commit_bytes': limits.PeakJobMemoryUsed,
        'working_set_sum_bytes': working_set if not missing else None,
        'private_commit_sum_bytes': private_commit if not missing else None,
        'unreadable_processes': missing,
    }


class JobSampler:
    def __init__(self, job, interval=0.5, reader=job_sample):
        if type(interval) not in (int, float) or not math.isfinite(interval) or not 0.05 <= interval <= 10:
            raise ValueError('MEASUREMENT_INTERVAL_INVALID')
        self.job, self.interval, self.reader = job, interval, reader
        self.samples, self.errors = [], []
        self.stop_event = threading.Event()
        self.thread = None
        self.started_ns = None
        self.initial_sample = None

    def sample(self):
        try:
            sample = self.reader(self.job)
            self.samples.append({'elapsed_ns': time.perf_counter_ns() - self.started_ns, **sample})
            return True
        except Exception as exc:
            self.errors.append(type(exc).__name__)
            return False

    def start(self):
        if self.thread is not None:
            raise RuntimeError('SAMPLER_ALREADY_STARTED')
        self.started_ns = time.perf_counter_ns()
        if self.sample():
            self.initial_sample = self.samples[-1]
        def observe():
            while not self.stop_event.wait(self.interval):
                self.sample()
        self.thread = threading.Thread(target=observe, name='neural-office-measurements', daemon=True)
        self.thread.start()

    def stop(self):
        if self.thread is None:
            raise RuntimeError('SAMPLER_NOT_STARTED')
        self.stop_event.set()
        self.thread.join(5)
        if self.thread.is_alive():
            raise RuntimeError('SAMPLER_TERMINATION_UNCONFIRMED')
        final_observed = self.sample()
        elapsed = (time.perf_counter_ns() - self.started_ns) / 1e9
        def peak(key):
            values = [s[key] for s in self.samples if s.get(key) is not None]
            return max(values) if values else None
        final = self.samples[-1] if final_observed else {}
        initial = self.initial_sample or {}
        cpu = final.get('cpu_seconds')
        initial_cpu = initial.get('cpu_seconds')
        average = None
        if initial_cpu is not None and cpu is not None and 0 <= initial_cpu <= cpu:
            observed_ns = final['elapsed_ns'] - initial['elapsed_ns']
            if observed_ns > 0:
                average = 100 * (cpu - initial_cpu) / (observed_ns / 1e9) / (os.cpu_count() or 1)
        return {
            'scope': 'owned_backend_job_only', 'interval_seconds': self.interval,
            'sample_count': len(self.samples), 'elapsed_seconds': elapsed,
            'cpu_seconds': cpu,
            'cpu_percent_machine_average': average,
            'sampled_peak_working_set_sum_bytes': peak('working_set_sum_bytes'),
            'sampled_peak_private_commit_sum_bytes': peak('private_commit_sum_bytes'),
            'job_peak_commit_bytes': peak('job_peak_commit_bytes'),
            'incomplete_samples': sum(s['unreadable_processes'] > 0 for s in self.samples),
            'observation_errors': self.errors,
            'complete': average is not None and not self.errors and all(s['unreadable_processes'] == 0 for s in self.samples),
            'system_gpu_usage': None,
        }
