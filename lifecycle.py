"""Windows singleton helpers shared by the watcher and its supervisor."""
import ctypes
from ctypes import wintypes

WORKER_MUTEX = 'Local\\CodexAutoRetryV1'
SUPERVISOR_MUTEX = 'Local\\CodexAutoRetrySupervisorV1'


def acquire_mutex(name=WORKER_MUTEX):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    handle = kernel.CreateMutexW(None, False, name)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        close_mutex(handle)
        return None
    return handle


def close_mutex(handle):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle(handle)


def mutex_exists(name=WORKER_MUTEX):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenMutexW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.OpenMutexW.restype = wintypes.HANDLE
    handle = kernel.OpenMutexW(0x00100000, False, name)
    if handle:
        close_mutex(handle)
        return True
    error = ctypes.get_last_error()
    if error == 2:
        return False
    raise ctypes.WinError(error)
