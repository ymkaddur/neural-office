"""Capture one explicitly selected local file, locking writes on Windows."""
import ctypes
from ctypes import wintypes as w
import os
from pathlib import Path
from .ledger import Denied


def local_path(value, reason='NETWORK_INPUT_EXCLUDED'):
    """Reject explicit UNC/device namespaces without touching the filesystem.

    This lexical gate does not certify mapped drives or junction destinations.
    Callers must retain their resolved-path and opened-handle checks.
    """
    path=Path(value)
    if str(path).startswith('\\\\'): raise Denied(reason)
    return path


def capture_html(file,root):
    if os.name!='nt': raise Denied('V52_FILE_CAPTURE_REQUIRES_WINDOWS')
    import msvcrt
    root=local_path(root)
    candidate=local_path(file)
    root=root.resolve(strict=True)
    candidate=candidate.resolve(strict=True)
    if not candidate.is_relative_to(root) or candidate.suffix.lower() not in ('.html','.htm'):
        raise Denied('INPUT_OUTSIDE_ROOT_OR_UNSUPPORTED')
    if str(candidate).startswith('\\\\'): raise Denied('NETWORK_INPUT_EXCLUDED')
    dll=ctypes.WinDLL('kernel32',use_last_error=True)
    dll.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,ctypes.c_void_p,w.DWORD,w.DWORD,w.HANDLE]
    dll.CreateFileW.restype=w.HANDLE
    dll.GetFinalPathNameByHandleW.argtypes=[w.HANDLE,w.LPWSTR,w.DWORD,w.DWORD]
    dll.GetFinalPathNameByHandleW.restype=w.DWORD
    dll.CloseHandle.argtypes=[w.HANDLE];dll.CloseHandle.restype=w.BOOL
    # FILE_SHARE_READ excludes existing/future writers and deletion while held.
    handle=dll.CreateFileW(str(candidate),0x80000000,1,None,3,0x80,None)
    if handle==ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
    try:
        buffer=ctypes.create_unicode_buffer(32768)
        length=dll.GetFinalPathNameByHandleW(handle,buffer,len(buffer),0)
        if not length or length>=len(buffer): raise Denied('INPUT_FINAL_PATH_UNKNOWN')
        actual=buffer.value
        if actual.startswith('\\\\?\\'): actual=actual[4:]
        if not Path(actual).is_relative_to(root) or os.path.normcase(actual)!=os.path.normcase(str(candidate)):
            raise Denied('INPUT_IDENTITY_CHANGED')
        fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
        handle=None
        with os.fdopen(fd,'rb') as source:
            size=os.fstat(source.fileno()).st_size
            if not 0<size<=262144: raise Denied('SNAPSHOT_SIZE')
            data=source.read(262145)
            if len(data)!=size: raise Denied('INPUT_CHANGED_DURING_CAPTURE')
        data.decode('utf-8-sig',errors='strict')
        return data
    finally:
        if handle is not None: dll.CloseHandle(handle)
