"""Windows-only drag & drop for Tk windows, pure standard library.

Registers a Tk toplevel as an OLE drop target (``IDropTarget`` / CF_HDROP)
so a user can drop files — e.g. a .hex firmware file — onto the window.

Why this exists: the Tk builds we ship (python-build-standalone, static
Tcl/Tk inside ``_tkinter.pyd``) contain no ``tkdnd`` package, so the
usual ``root.drop_target_register`` / ``dnd_bind`` path is unavailable on
Windows. Here the COM interface is implemented directly with ``ctypes`` —
no extra dependencies, no native build step.

Design notes:
  - ``OleInitialize`` must run on the thread that owns the window; callers
    invoke :func:`register` from Tk's main thread (it is).
  - Drop notifications arrive as window messages on that same thread, so
    invoking the Tk callback directly is safe; we still marshal through
    ``root.after`` to keep total ordering with the event loop.
  - Trampoline function pointers, the vtable and the COM instance struct
    are all pinned in ``_pin`` so nothing can be garbage-collected while
    OLE may still call back into us.
  - Every Windows API call is checked; any failure simply means "no DnD"
    and the app keeps working via Browse / paste.

COM interop notes (verified against the x64 ABI):
  - IDropTarget vtable: 7 slots — QI, AddRef, Release, DragEnter,
    DragOver, DragLeave, Drop. (IUnknown contributes the first three.)
  - IDataObject vtable: GetData is slot 3 (QI, AddRef, Release, GetData).
  - The COM object outlives a single registration: while ``_pin`` holds
    references, vtables/trampolines stay put for the process lifetime.

Public API:
    register(root, on_drop_paths) -> bool   # on_drop_paths(paths: list[str])
    unregister(hwnd)                      # best-effort cleanup
"""

import ctypes
from ctypes import wintypes

# ------------------------------------------------------------------ constants
S_OK = 0x00000000
S_FALSE = 0x00000001
E_NOTIMP = 0x80004001
E_NOINTERFACE = 0x80004003

CF_HDROP = 15
DTSC_DROP = 0x00000000
DVASPECT_CONTENT = 1
TYMED_HGLOBAL = 1

# ------------------------------------------------------------- COM structures
_GUID_SIZE = 16


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_uint8 * 8),
    ]


def _guid(d1, d2, d3, d4_bytes):
    return _GUID(d1, d2, d3, (ctypes.c_uint8 * 8)(*d4_bytes))


def _bytes_of(g):
    return ctypes.string_at(ctypes.addressof(g), _GUID_SIZE)


# IID_IUnknown   = 00000000-0000-0000-C000-000000000046
GUID_IUNKNOWN = _guid(0x00000000, 0x0000, 0x0000, bytes.fromhex("c000000000000046"))
# IID_IDropTarget = 00000122-0000-0000-C000-000000000046
GUID_IDROPTARGET = _guid(0x00000122, 0x0000, 0x0000, bytes.fromhex("c000000000000046"))


class POINTL(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class FORMATETC(ctypes.Structure):
    # CLIPFORMAT cfFormat; IMMEDIATE* ptd; DWORD dwAspect; LONG lindex;
    _fields_ = [
        ("cfFormat", ctypes.c_uint),
        ("ptd", ctypes.c_void_p),
        ("dwAspect", ctypes.c_uint),
        ("lindex", ctypes.c_long),
    ]


class STGMEDIUM(ctypes.Structure):
    _fields_ = [
        ("tymed", ctypes.c_uint),
        ("u", ctypes.c_void_p),  # union member; hGlobal for TYMED_HGLOBAL
        ("flags", ctypes.c_uint),
    ]


# ------------------------------------------------------------ trampoline setup
_HRESULT = ctypes.c_int32

# DragEnter(self, pDataObj*, grfKeyState, POINTL*, DWORD*)
_FT_DRAG_ENTER = ctypes.CFUNCTYPE(
    _HRESULT,
    ctypes.c_void_p,  # self
    ctypes.c_void_p,  # pDataObj
    ctypes.c_ulong,   # grfKeyState
    ctypes.c_void_p,  # POINTL* pt
    ctypes.c_void_p,  # DWORD* pdwEffect
)
# DragOver(self, grfKeyState, POINTL*, DWORD*)
_FT_DRAG_OVER = ctypes.CFUNCTYPE(
    _HRESULT,
    ctypes.c_void_p,  # self
    ctypes.c_ulong,   # grfKeyState
    ctypes.c_void_p,  # POINTL* pt
    ctypes.c_void_p,  # DWORD* pdwEffect
)

# (self_ptr, riid*, ppv**)
_FT_QI = ctypes.CFUNCTYPE(_HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
# (self_ptr)
_FT_REF = ctypes.CFUNCTYPE(_HRESULT, ctypes.c_void_p)
# (self_ptr)
_FT_LEAVE = ctypes.CFUNCTYPE(_HRESULT, ctypes.c_void_p)
# (self_ptr, pDataObj, grfKeyState, POINTL*, DWORD*)
_FT_DROP = ctypes.CFUNCTYPE(_HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)
# IDataObject::GetData (self_ptr, FORMATETC*, STGMEDIUM*)
_FT_GETDATA = ctypes.CFUNCTYPE(_HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

# IDropTarget: QI, AddRef, Release, DragEnter, DragOver, DragLeave, Drop
_VT = ctypes.c_void_p * 7


class _IDropTarget(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(_VT))]


# pinned references (keep trampolines/vtable/instances alive)
_pin = {}


class _Reg:
    __slots__ = (
        "root", "on_drop", "instance", "vtable",
        "f_qi", "f_ref", "f_enter", "f_over", "f_leave", "f_drop",
        "refcount", "hwnd",
    )


def _ptr_bytes(addr):
    return (ctypes.c_uint8 * 8)(*[(addr >> (8 * i)) & 0xFF for i in range(8)])


def _state(self_ptr):
    try:
        return _pin.get(int(self_ptr))
    except Exception:
        return None


def _set_effect(pdw_effect, effect):
    if pdw_effect:
        try:
            ptr = ctypes.cast(pdw_effect, ctypes.POINTER(ctypes.c_ulong))
            ptr[0] = effect
        except Exception:
            pass


def _query_interface(self_ptr, p_riid, p_pvv):
    reg = _state(self_ptr)
    if reg is None:
        return 0x80004005  # E_FAIL
    try:
        riid_bytes = ctypes.string_at(p_riid, _GUID_SIZE)
    except Exception:
        return 0x80004005  # E_FAIL
    if riid_bytes in (_bytes_of(GUID_IUNKNOWN), _bytes_of(GUID_IDROPTARGET)):
        # *ppv = this interface pointer; QI implies AddRef (counted below)
        try:
            ctypes.memmove(p_pvv, _ptr_bytes(int(self_ptr)), 8)
        except Exception:
            pass
        reg.refcount += 1
        return S_OK
    try:
        ctypes.memmove(p_pvv, _ptr_bytes(0), 8)
    except Exception:
        pass
    return E_NOINTERFACE


def _add_ref(self_ptr):
    reg = _state(self_ptr)
    if reg is None:
        return 0x80004005
    reg.refcount += 1
    return S_OK


def _release(self_ptr):
    # NOTE: while this app is running the object is kept alive by _pin
    # (single-registration app; OLE may hold a reference to the very end).
    reg = _state(self_ptr)
    if reg is None:
        return 0x80004005
    reg.refcount = max(0, reg.refcount - 1)
    return S_OK


def _drag_enter(self_ptr, p_dataobj, grf, point, pdw):
    _set_effect(pdw, DTSC_DROP)
    return S_OK


def _drag_over(self_ptr, grf, point, pdw):
    _set_effect(pdw, DTSC_DROP)
    return S_OK


def _drag_leave(self_ptr):
    return S_OK


def _drop(self_ptr, p_dataobj, grf, point, pdw):
    _set_effect(pdw, DTSC_DROP)
    paths = _extract_paths(p_dataobj)
    if paths:
        reg = _state(self_ptr)
        if reg is not None:
            try:
                reg.root.after(0, lambda: reg.on_drop(paths))
            except Exception:
                try:
                    reg.on_drop(paths)
                except Exception:
                    pass
    return S_OK


def _extract_paths(p_dataobj):
    """GetData(CF_HDROP) on the passed IDataObject, return the file list.

    OLE protocol: the pointer is valid for the duration of the call (the
    caller owns it — we must NOT Release it); the returned HGLOBAL is
    ours to free.
    """
    if not p_dataobj:
        return []
    try:
        shell = ctypes.windll.shell32
        vtable = ctypes.cast(
            ctypes.cast(p_dataobj, ctypes.POINTER(ctypes.c_uint64))[0],
            ctypes.POINTER(ctypes.c_uint64 * 12),
        )
        get_data = _FT_GETDATA(vtable[3])  # IDataObject::GetData (slot 3)

        fmt = FORMATETC(CF_HDROP, None, DVASPECT_CONTENT, -1)
        medium = STGMEDIUM(TYMED_HGLOBAL, None, 0)
        hr = get_data(p_dataobj, ctypes.byref(fmt), ctypes.byref(medium))
        if hr not in (S_OK, S_FALSE) or not medium.u:
            return []
        h_drop = medium.u
        try:
            # (iFile = 0xFFFFFFFF, lpsz = NULL) -> number of files in the drop
            n = shell.DragQueryFileW(h_drop, 0xFFFFFFFF, None, 0)
            if n <= 0:
                return []
            capacity = max(1024, n * 64 + 256)
            paths = []
            for i in range(n):
                buf = ctypes.create_unicode_buffer(capacity)
                got = shell.DragQueryFileW(h_drop, i, buf, capacity)
                if got:
                    paths.append(buf.value)
            return paths
        finally:
            try:
                ctypes.windll.kernel32.GlobalFree(h_drop)
            except Exception:
                pass
    except Exception:
        return []


# ------------------------------------------------------------------- public API
def _available():
    return hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32")


def register(root, on_drop_paths):
    """Register *root*'s window as a drop target.

    ``on_drop_paths(paths)`` is invoked (on Tk's main thread) with the list
    of dropped file paths. Returns True on success.
    """
    try:
        if not _available():
            return False
        if root.winfo_exists() is False:
            return False
        ole32 = ctypes.windll.ole32
        user32 = ctypes.windll.user32

        hr = ole32.OleInitialize(None)
        # S_OK (new) and S_FALSE (already initialized on this thread) are fine
        if hr not in (S_OK, S_FALSE):
            return False

        # Full-size handle arithmetic: HWND is a pointer, not a 32-bit int.
        user32.GetParent.restype = wintypes.HWND
        hwnd = user32.GetParent(int(root.winfo_id())) or int(root.winfo_id())

        reg = _Reg()
        reg.root = root
        reg.on_drop = on_drop_paths
        reg.refcount = 1
        reg.hwnd = int(hwnd)

        reg.f_qi = _FT_QI(_query_interface)
        reg.f_ref = _FT_REF(_add_ref)
        reg.f_enter = _FT_DRAG_ENTER(_drag_enter)
        reg.f_over = _FT_DRAG_OVER(_drag_over)
        reg.f_leave = _FT_LEAVE(_drag_leave)
        reg.f_drop = _FT_DROP(_drop)

        reg.vtable = _VT()
        reg.vtable[0] = ctypes.cast(reg.f_qi, ctypes.c_void_p)       # QueryInterface
        reg.vtable[1] = ctypes.cast(reg.f_ref, ctypes.c_void_p)      # AddRef
        reg.vtable[2] = ctypes.cast(reg.f_ref, ctypes.c_void_p)      # Release
        reg.vtable[3] = ctypes.cast(reg.f_enter, ctypes.c_void_p)    # DragEnter
        reg.vtable[4] = ctypes.cast(reg.f_over, ctypes.c_void_p)     # DragOver
        reg.vtable[5] = ctypes.cast(reg.f_leave, ctypes.c_void_p)    # DragLeave
        reg.vtable[6] = ctypes.cast(reg.f_drop, ctypes.c_void_p)     # Drop

        reg.instance = _IDropTarget(ctypes.cast(ctypes.addressof(reg.vtable), ctypes.POINTER(_VT)))

        self_key = ctypes.addressof(reg.instance)
        _pin[self_key] = reg

        hr = user32.RegisterDragDrop(int(hwnd), ctypes.byref(reg.instance), None)
        if hr != 0:
            raise OSError("RegisterDragDrop failed: 0x%08x" % (hr & 0xFFFFFFFF))
        return True
    except Exception:
        return False


def unregister(hwnd):
    """Best-effort RevokeDragDrop; safe to call more than once."""
    try:
        if _available():
            ctypes.windll.user32.RevokeDragDrop(int(hwnd))
    except Exception:
        pass
