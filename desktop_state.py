"""Read whether our Windows desktop is interactive; never unlock or switch it."""
import ctypes
from ctypes import wintypes


class _SessionInfo(ctypes.Structure):
    _fields_ = [('session_id', wintypes.ULONG), ('state', ctypes.c_int),
                ('flags', wintypes.LONG), ('station', wintypes.WCHAR * 33),
                ('user', wintypes.WCHAR * 21), ('domain', wintypes.WCHAR * 18),
                ('logon', ctypes.c_longlong), ('connect', ctypes.c_longlong),
                ('disconnect', ctypes.c_longlong), ('last_input', ctypes.c_longlong),
                ('current', ctypes.c_longlong), ('incoming_bytes', wintypes.DWORD),
                ('outgoing_bytes', wintypes.DWORD), ('incoming_frames', wintypes.DWORD),
                ('outgoing_frames', wintypes.DWORD), ('incoming_compressed', wintypes.DWORD),
                ('outgoing_compressed', wintypes.DWORD)]


class _InfoEx(ctypes.Structure):
    _fields_ = [('level', wintypes.DWORD), ('data', _SessionInfo)]


def session_state():
    """Return Windows session state/lock flag, or None if it cannot be queried."""
    wts = ctypes.WinDLL('wtsapi32', use_last_error=True)
    wts.WTSQuerySessionInformationW.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.c_int,
                                               ctypes.POINTER(ctypes.c_void_p),
                                               ctypes.POINTER(wintypes.DWORD))
    wts.WTSFreeMemory.argtypes = (ctypes.c_void_p,)
    pointer, size = ctypes.c_void_p(), wintypes.DWORD()
    if not wts.WTSQuerySessionInformationW(None, 0xffffffff, 25, ctypes.byref(pointer),
                                          ctypes.byref(size)):  # WTSSessionInfoEx
        return None
    try:
        if size.value < ctypes.sizeof(_InfoEx):
            return None
        info = ctypes.cast(pointer, ctypes.POINTER(_InfoEx)).contents
        return (info.data.state, info.data.flags) if info.level == 1 else None
    finally:
        wts.WTSFreeMemory(pointer)


def desktop_available():
    """Fail closed for visuals on lock, secure desktop, or an inaccessible session."""
    # WTSActive=0, WTS_SESSIONSTATE_UNLOCK=1 on this supported Windows version.
    if session_state() != (0, 1):
        return False
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.OpenInputDesktop.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    user32.OpenInputDesktop.restype = wintypes.HANDLE
    user32.GetUserObjectInformationW.argtypes = (wintypes.HANDLE, ctypes.c_int,
                                                ctypes.c_void_p, wintypes.DWORD,
                                                ctypes.POINTER(wintypes.DWORD))
    user32.CloseDesktop.argtypes = (wintypes.HANDLE,)
    desktop = user32.OpenInputDesktop(0, False, 1)  # DESKTOP_READOBJECTS
    if not desktop:
        return False
    try:
        name = ctypes.create_unicode_buffer(256)
        needed = wintypes.DWORD()
        if not user32.GetUserObjectInformationW(desktop, 2, name, ctypes.sizeof(name),
                                                ctypes.byref(needed)):  # UOI_NAME
            return False
        return name.value.casefold() == 'default'
    finally:
        user32.CloseDesktop(desktop)
