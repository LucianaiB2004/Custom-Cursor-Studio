"""Windows live cursor-size cache, isolated from persistence and GUI policy.

The SPI action numbers 0x2028 (GET) and 0x2029 (SET) are UNDOCUMENTED Windows
behavior, not public SDK constants. Their calling convention is evidenced by:
https://bugzilla.mozilla.org/show_bug.cgi?id=1712669#c4
https://github.com/marco-kretz/win11-multi-dpi-cursor/blob/main/multi-dpi-cursor.wh.cpp

The GET was checked read-only on Windows 11 build 26200. Other Windows versions
or future updates may reject these actions. Failure must be surfaced, never
silently replaced by a registry value or a default size. Tests do not call SET.

set_size() changes the running session only (flags=0). Its caller MUST obtain UI
confirmation, capture get_size() before the transaction, manage persistent
registry values/backups, and restore the captured runtime size on failure.
Importing this module never reads or changes system settings.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os

_GET_SIZE = 0x2028
_SET_SIZE = 0x2029


def _api():
    if os.name != 'nt':
        raise OSError('系统指针大小设置仅支持 Windows。')
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    spi = user32.SystemParametersInfoW
    spi.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
    spi.restype = wintypes.BOOL
    return spi


def _last_error():
    return ctypes.get_last_error()


def _clear_error():
    if hasattr(ctypes, 'set_last_error'):
        ctypes.set_last_error(0)


def _native_error(action):
    code = _last_error()
    detail = ctypes.FormatError(code).strip() if hasattr(ctypes, 'FormatError') and code else 'Windows 未提供额外错误说明'
    error = OSError(code, f'Windows 实时指针大小接口 0x{action:04X} 失败（Win32={code}）：{detail}。'
                    '该接口未公开，当前 Windows 版本可能不支持，未将注册表值视为实际生效。')
    error.winerror = code
    return error


def get_size() -> int:
    """Read the running session's base size, without registry writes or fallback."""
    api = _api()
    value = wintypes.DWORD()
    _clear_error()
    if not api(_GET_SIZE, 0, ctypes.byref(value), 0):
        raise _native_error(_GET_SIZE)
    if not 16 <= value.value <= 256:
        raise OSError(f'Windows 返回的实时指针大小 {value.value} 超出支持范围16–256，未采用默认替代。')
    return int(value.value)


def set_size(size: int) -> None:
    """Set runtime size after explicit confirmation; caller owns backup/rollback.

    pvParam carries the integer VALUE as a pointer-sized number, not a pointer
    to a DWORD. flags=0 avoids making persistent profile changes outside the
    caller's registry transaction. Read-back mismatch is an application failure.
    """
    if type(size) is not int or not 16 <= size <= 256:
        raise ValueError('系统指针大小必须是16–256之间的整数。')
    api = _api()
    _clear_error()
    if not api(_SET_SIZE, 0, ctypes.c_void_p(size), 0):
        raise _native_error(_SET_SIZE)
    actual = get_size()
    if actual != size:
        raise OSError(f'实时指针大小回读不一致：请求 {size} px，Windows 实际为 {actual} px。')
