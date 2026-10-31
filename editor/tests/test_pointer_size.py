"""Only the read-only GET smoke test calls Windows; SET tests use an API fake."""
import ctypes
import os
from ctypes import wintypes

import pytest

from cursor_studio.windows import pointer_size


class NativeSize:
    def __init__(self, size=32):
        self.size = size
        self.calls = []
        self.fail = None
        self.ignore_set = False

    def __call__(self, action, param, value, flags):
        self.calls.append((action, param, value, flags))
        if action == self.fail:
            return False
        if action == 0x2028:
            ctypes.cast(value, ctypes.POINTER(wintypes.DWORD)).contents.value = self.size
        elif action == 0x2029:
            assert isinstance(value, ctypes.c_void_p)
            if not self.ignore_set:
                self.size = value.value
        else:
            raise AssertionError('Unexpected native mutation')
        return True


@pytest.fixture
def native(monkeypatch):
    api = NativeSize()
    monkeypatch.setattr(pointer_size, '_api', lambda: api)
    monkeypatch.setattr(pointer_size, '_last_error', lambda: 87)
    return api


def test_reads_runtime_cache_without_registry_or_writes(native):
    assert pointer_size.get_size() == 32
    assert [call[0] for call in native.calls] == [0x2028]
    assert native.calls[0][1] == native.calls[0][3] == 0


def test_set_updates_live_size_without_persisting_and_reads_back(native):
    pointer_size.set_size(128)
    assert native.size == 128
    assert [call[0] for call in native.calls] == [0x2029, 0x2028]
    assert native.calls[0][1] == native.calls[0][3] == 0
    assert native.calls[0][2].value == 128


@pytest.mark.parametrize('value', [True, False, 0, 15, 257, 96.0, '96', None])
def test_invalid_sizes_never_reach_native_api(native, value):
    with pytest.raises(ValueError):
        pointer_size.set_size(value)
    assert not native.calls


@pytest.mark.parametrize('action', [0x2028, 0x2029])
def test_unsupported_action_reports_win32_error_without_fallback(native, action):
    native.fail = action
    with pytest.raises(OSError, match='Win32=87'):
        (pointer_size.get_size if action == 0x2028 else lambda: pointer_size.set_size(96))()
    assert len(native.calls) == 1


def test_success_return_without_actual_change_is_not_success(native):
    native.ignore_set = True
    with pytest.raises(OSError, match='96.*32'):
        pointer_size.set_size(96)


@pytest.mark.parametrize('value', [0, 99999])
def test_invalid_runtime_value_is_not_replaced_by_default(native, value):
    native.size = value
    with pytest.raises(OSError, match='范围'):
        pointer_size.get_size()


@pytest.mark.skipif(os.name != 'nt', reason='Windows read-only API probe')
def test_real_windows_get_is_read_only():
    assert 16 <= pointer_size.get_size() <= 256
