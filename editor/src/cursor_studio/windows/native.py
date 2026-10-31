"""Native cursor load validation without changing any active system cursor."""
import ctypes
import os
from pathlib import Path


def validate_cursor_file(path: Path) -> bool:
    if os.name!='nt':
        raise OSError('原生光标加载验证仅支持 Windows')
    user32=ctypes.WinDLL('user32',use_last_error=True)
    # LR_LOADFROMFILE without LR_SHARED gives us an owned cursor handle.
    # LoadCursorFromFile can return shared handles that must not be destroyed.
    user32.LoadImageW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_int,ctypes.c_int,ctypes.c_uint]
    user32.LoadImageW.restype=ctypes.c_void_p
    user32.DestroyCursor.argtypes=[ctypes.c_void_p]
    user32.DestroyCursor.restype=ctypes.c_int
    handle=user32.LoadImageW(None,str(Path(path).resolve()),2,0,0,0x10)
    if not handle:
        raise OSError(ctypes.get_last_error(),f'Windows 无法加载光标：{path}')
    try:
        return True
    finally:
        if not user32.DestroyCursor(handle):
            raise OSError(ctypes.get_last_error(),'Windows 无法释放验证用光标句柄')
