"""Time verified desktop reads of one completed synthetic attempt, without inference."""
import argparse
import ctypes
import json
import math
from pathlib import Path
import statistics
import sys
from time import perf_counter_ns, process_time_ns
from unittest.mock import patch


def peak_working_set():
    if sys.platform != 'win32':
        return None
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('peak', 'current', 'pool_peak', 'pool',
                                                  'nonpaged_peak', 'nonpaged', 'pagefile', 'pagefile_peak')]
    data = Counters()
    data.size = ctypes.sizeof(data)
    current = ctypes.windll.kernel32.GetCurrentProcess
    current.restype = wintypes.HANDLE
    read = ctypes.windll.psapi.GetProcessMemoryInfo
    read.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    if not read(current(), ctypes.byref(data), data.size):
        raise ctypes.WinError()
    return data.peak


def measure(checkout, count):
    sys.path[:0] = [str(checkout), str(checkout/'tests')]
    from test_v55_service import DesktopServiceTests
    from neural_office import continuity
    fixture = DesktopServiceTests()
    try:
        fixture.setUp()
        item = fixture.start(fixture.preview())
        fixture.finish()
        def read():
            row = fixture.service.attempt(item['id'])
            if row['id'] != item['id'] or row['state'] != 'ACCEPTED' or not row['report_available']:
                raise ValueError('The benchmark requires the same accepted attempt')
        with patch.object(continuity, 'signature', wraps=continuity.signature) as checked:
            read()
        for _ in range(3):
            read()
        samples = []
        cpu_start = process_time_ns()
        for _ in range(count):
            start = perf_counter_ns()
            read()
            samples.append((perf_counter_ns()-start)/1e6)
        cpu_ms = (process_time_ns()-cpu_start)/1e6
        return dict(reads=count, continuity_checks=checked.call_count,
                    median_ms=round(statistics.median(samples),3),
                    p95_ms=round(sorted(samples)[math.ceil(.95*count)-1],3),
                    process_cpu_ms=round(cpu_ms,3), process_peak_working_set_bytes=peak_working_set())
    finally:
        fixture.doCleanups()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--reads', type=int, default=60)
    args = parser.parse_args()
    if not 1 <= args.reads <= 10000:
        parser.error('--reads must be between 1 and 10000')
    print(json.dumps(measure(args.checkout.resolve(strict=True), args.reads)))
