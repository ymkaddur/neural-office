"""Windows job ownership. Only trusted bootstrap code runs before self-assignment."""
import ctypes
from functools import cache
from ctypes import wintypes as w
import os
import subprocess
import sys
import time

KILL_ON_CLOSE=0x2000
EXTENDED_LIMIT=9
BASIC_ACCOUNTING=1
ALL_ACCESS=0x1F003F


class BasicLimits(ctypes.Structure):
    _fields_=[('PerProcessUserTimeLimit',ctypes.c_int64),('PerJobUserTimeLimit',ctypes.c_int64),
              ('LimitFlags',w.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),
              ('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',w.DWORD),
              ('Affinity',ctypes.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]


class IOCounts(ctypes.Structure):
    _fields_=[(n,ctypes.c_uint64) for n in ('ReadOperationCount','WriteOperationCount','OtherOperationCount',
                                         'ReadTransferCount','WriteTransferCount','OtherTransferCount')]


class ExtendedLimits(ctypes.Structure):
    _fields_=[('BasicLimitInformation',BasicLimits),('IoInfo',IOCounts),
              ('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),
              ('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]


class Accounting(ctypes.Structure):
    _fields_=[(n,ctypes.c_int64) for n in ('TotalUserTime','TotalKernelTime','ThisPeriodTotalUserTime','ThisPeriodTotalKernelTime')]+[
        ('TotalPageFaultCount',w.DWORD),('TotalProcesses',w.DWORD),('ActiveProcesses',w.DWORD),('TotalTerminatedProcesses',w.DWORD)]


@cache
def kernel():
    if os.name!='nt': raise RuntimeError('V52_OWNED_BACKEND_REQUIRES_WINDOWS')
    dll=ctypes.WinDLL('kernel32',use_last_error=True)
    signatures={
        'CreateJobObjectW':([ctypes.c_void_p,w.LPCWSTR],w.HANDLE),
        'OpenJobObjectW':([w.DWORD,w.BOOL,w.LPCWSTR],w.HANDLE),
        'SetInformationJobObject':([w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD],w.BOOL),
        'QueryInformationJobObject':([w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p],w.BOOL),
        'AssignProcessToJobObject':([w.HANDLE,w.HANDLE],w.BOOL),
        'IsProcessInJob':([w.HANDLE,w.HANDLE,ctypes.POINTER(w.BOOL)],w.BOOL),
        'OpenProcess':([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),
        'TerminateJobObject':([w.HANDLE,w.UINT],w.BOOL),
        'CloseHandle':([w.HANDLE],w.BOOL), 'GetCurrentProcess':([],w.HANDLE)}
    for name,(args,result) in signatures.items():
        fn=getattr(dll,name); fn.argtypes=args; fn.restype=result
    return dll


class Job:
    def __init__(self,name,existing=False,*,memory_bytes=None,cpu_seconds=None):
        if any(value is not None and (type(value) is not int or value <= 0) for value in (memory_bytes,cpu_seconds)):
            raise ValueError('JOB_LIMIT_INVALID')
        if existing and (memory_bytes is not None or cpu_seconds is not None):
            raise ValueError('JOB_LIMIT_ALREADY_CONFIGURED')
        self.dll=kernel(); self.name=name; self.handle=None; self.process=None
        if existing:
            handle=self.dll.OpenJobObjectW(ALL_ACCESS,False,name)
            if not handle:
                error=ctypes.get_last_error()
                if error==2: return
                raise ctypes.WinError(error)
        else:
            handle=self.dll.CreateJobObjectW(None,name)
            if not handle: raise ctypes.WinError(ctypes.get_last_error())
            if ctypes.get_last_error()==183:
                self.dll.CloseHandle(handle); raise RuntimeError('JOB_NAME_COLLISION')
            limits=ExtendedLimits(); limits.BasicLimitInformation.LimitFlags=KILL_ON_CLOSE
            if memory_bytes is not None:
                limits.BasicLimitInformation.LimitFlags |= 0x200  # JOB_OBJECT_LIMIT_JOB_MEMORY
                limits.JobMemoryLimit = memory_bytes
            if cpu_seconds is not None:
                limits.BasicLimitInformation.LimitFlags |= 0x4  # JOB_OBJECT_LIMIT_JOB_TIME
                limits.BasicLimitInformation.PerJobUserTimeLimit = cpu_seconds * 10_000_000
            if not self.dll.SetInformationJobObject(handle,EXTENDED_LIMIT,ctypes.byref(limits),ctypes.sizeof(limits)):
                error=ctypes.get_last_error(); self.dll.CloseHandle(handle); raise ctypes.WinError(error)
        self.handle=handle

    def contains_current_process(self):
        if self.handle is None:
            return False
        member = w.BOOL()
        if not self.dll.IsProcessInJob(self.dll.GetCurrentProcess(),self.handle,ctypes.byref(member)):
            raise ctypes.WinError(ctypes.get_last_error())
        return bool(member.value)

    def start(self,command,env=None,log=None):
        if self.handle is None or self.process is not None: raise RuntimeError('JOB_STATE')
        self.process=subprocess.Popen([sys.executable,'-B',__file__,'--join',self.name,*command],
            env=env,stdin=subprocess.DEVNULL,stdout=log or subprocess.DEVNULL,
            stderr=log or subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        return self.process

    def active(self):
        if self.handle is None: return 0
        info=Accounting()
        if not self.dll.QueryInformationJobObject(self.handle,BASIC_ACCOUNTING,ctypes.byref(info),ctypes.sizeof(info),None):
            raise ctypes.WinError(ctypes.get_last_error())
        return info.ActiveProcesses

    def terminate(self,timeout=10):
        if self.handle is None: return
        if not self.dll.TerminateJobObject(self.handle,1): raise ctypes.WinError(ctypes.get_last_error())
        deadline=time.monotonic()+timeout
        # Also stop an unassigned bootstrap; it cannot launch the backend before joining.
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=timeout)
        while self.active():
            if time.monotonic()>=deadline: raise TimeoutError('JOB_TERMINATION_UNCONFIRMED')
            time.sleep(.02)

    def close(self):
        if self.handle is not None:
            self.dll.CloseHandle(self.handle); self.handle=None

    def __enter__(self): return self

    def __exit__(self,*args):
        try: self.terminate()
        finally: self.close()


def join_and_run(name,command):
    dll=kernel()
    handle=dll.OpenJobObjectW(ALL_ACCESS,False,name)
    if not handle: raise RuntimeError('OWNER_JOB_UNAVAILABLE')
    try:
        if not dll.AssignProcessToJobObject(handle,dll.GetCurrentProcess()):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        dll.CloseHandle(handle)
    # No job handle is inherited. Owner death closes the last owner handle,
    # terminating this bootstrap and every descendant in the job.
    return subprocess.call(command,creationflags=subprocess.CREATE_NO_WINDOW)


if __name__=='__main__':
    if len(sys.argv)<5 or sys.argv[1]!='--join': raise SystemExit(2)
    raise SystemExit(join_and_run(sys.argv[2],sys.argv[3:]))
