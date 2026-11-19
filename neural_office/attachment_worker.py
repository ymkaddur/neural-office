"""Dedicated decoder process. The parent gives it bounded bytes, never file paths."""
import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import sys


def constrain_memory():
    maximum = 384 * 1024 * 1024
    if os.name != 'nt':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (maximum, maximum))
        return
    class Basic(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong),
                    ('PerJobUserTimeLimit', ctypes.c_longlong), ('LimitFlags', w.DWORD),
                    ('MinimumWorkingSetSize', ctypes.c_size_t), ('MaximumWorkingSetSize', ctypes.c_size_t),
                    ('ActiveProcessLimit', w.DWORD), ('Affinity', ctypes.c_size_t),
                    ('PriorityClass', w.DWORD), ('SchedulingClass', w.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', Basic), ('IoInfo', ctypes.c_ulonglong * 6),
                    ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    kernel.SetInformationJobObject.restype = w.BOOL
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.AssignProcessToJobObject.restype = w.BOOL
    kernel.GetCurrentProcess.restype = w.HANDLE
    limits = Extended()
    limits.BasicLimitInformation.LimitFlags = 0x100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY
    limits.ProcessMemoryLimit = maximum
    job = kernel.CreateJobObjectW(None, None)
    if (not job or not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits))
            or not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess())):
        raise OSError('DECODER_CONTAINMENT_UNAVAILABLE')
    # The process keeps this kernel handle until exit; no untrusted code receives it.


def main():
    # The host launches this known script with Python -I. Only the packaged source
    # root and that interpreter's site packages participate in imports.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from neural_office.attachment_formats import MAX_FILE, read, result
    command = json.loads(sys.argv[1])
    expected_bytes = command.pop('captured_bytes')
    expected_sha = command.pop('captured_sha256')
    try:
        constrain_memory()
    except OSError:
        response = result(command['kind'], 'unavailable', 'Windows no pudo aplicar el límite de memoria del lector.')
    else:
        data = sys.stdin.buffer.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            response = result(command['kind'], 'limit', 'El adjunto supera el límite de lectura.')
        elif len(data) != expected_bytes or hashlib.sha256(data).hexdigest() != expected_sha:
            response = result(command['kind'], 'incomplete', 'El lector no recibió la captura íntegra. Vuelve a abrir el adjunto.')
        else:
            try:
                response = read(data=data, **command)
            except MemoryError:
                response = result(command['kind'], 'limit', 'El lector alcanzó su límite de memoria.')
    sys.stdout.buffer.write(json.dumps(response, ensure_ascii=True, allow_nan=False).encode('ascii'))


if __name__ == '__main__':
    main()
