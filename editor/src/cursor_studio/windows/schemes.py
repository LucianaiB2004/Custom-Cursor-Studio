"""Explicitly invoked HKCU-only cursor transactions.

Callers MUST obtain an affirmative UI confirmation before apply/restore. Importing
this module never accesses the registry. The backend boundary makes transactions
testable without changing a developer's desktop.
"""
from __future__ import annotations

import base64
import copy
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import uuid

from cursor_studio.models import ROLES

_KEYS = {"cursors": r"Control Panel\Cursors", "schemes": r"Control Panel\Cursors\Schemes"}
_MAX_BACKUP = 2 * 1024 * 1024


def _validate_file(path: Path) -> bool:
    from cursor_studio.windows.native import validate_cursor_file
    return validate_cursor_file(path)


class _WindowsRegistry:
    def __init__(self):
        if os.name != "nt":
            raise OSError("应用和恢复系统指针仅支持 Windows。")
        import winreg
        self.reg = winreg

    def snapshot(self):
        result = {}
        for label, key in _KEYS.items():
            try:
                with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER, key, 0, self.reg.KEY_READ) as handle:
                    values = {}
                    for index in range(self.reg.QueryInfoKey(handle)[1]):
                        name, value, kind = self.reg.EnumValue(handle, index)
                        values[name] = {"type": kind, "data": value}
                    result[label] = {"exists": True, "values": values}
            except FileNotFoundError:
                result[label] = {"exists": False, "values": {}}
        return result

    def check_write(self):
        # Opening a handle requests rights; it does not create a key or value.
        access = self.reg.KEY_QUERY_VALUE | self.reg.KEY_SET_VALUE | self.reg.KEY_CREATE_SUB_KEY
        for key in _KEYS.values():
            candidate = key
            while True:
                try:
                    with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER, candidate, 0, access):
                        break
                except FileNotFoundError:
                    if "\\" not in candidate:
                        raise PermissionError("无法访问当前用户的指针注册表父键。")
                    candidate = candidate.rsplit("\\", 1)[0]

    def replace(self, snapshot):
        # Restore the exact set of values including removing values absent at
        # backup time. Work child-first for deletion of previously absent keys.
        for label in ("cursors", "schemes"):
            record = snapshot[label]
            if not record["exists"]:
                continue
            with self.reg.CreateKeyEx(self.reg.HKEY_CURRENT_USER, _KEYS[label], 0,
                                      self.reg.KEY_QUERY_VALUE | self.reg.KEY_SET_VALUE) as handle:
                existing = [self.reg.EnumValue(handle, i)[0]
                            for i in range(self.reg.QueryInfoKey(handle)[1])]
                for name in existing:
                    if name not in record["values"]:
                        self.reg.DeleteValue(handle, name)
                for name, value in record["values"].items():
                    self.reg.SetValueEx(handle, name, 0, value["type"], value["data"])
                self.reg.FlushKey(handle)
        for label in ("schemes", "cursors"):
            if snapshot[label]["exists"]:
                continue
            try:
                with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER, _KEYS[label], 0,
                                      self.reg.KEY_QUERY_VALUE | self.reg.KEY_SET_VALUE) as handle:
                    names = [self.reg.EnumValue(handle, i)[0]
                             for i in range(self.reg.QueryInfoKey(handle)[1])]
                    # Do not delete unknown subkeys recursively.
                    if self.reg.QueryInfoKey(handle)[0]:
                        raise OSError("指针键出现未备份的子键，已停止删除以保护数据。")
                    for name in names:
                        self.reg.DeleteValue(handle, name)
                self.reg.DeleteKey(self.reg.HKEY_CURRENT_USER, _KEYS[label])
            except FileNotFoundError:
                pass

    def refresh(self):
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        spi = user32.SystemParametersInfoW
        spi.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
        spi.restype = wintypes.BOOL
        # Microsoft: SPI_SETCURSORS requires uiParam=0 and pvParam=NULL.
        if not spi(0x0057, 0, None, 0x02):
            raise ctypes.WinError(ctypes.get_last_error())

    def get_size(self):
        from .pointer_size import get_size
        return get_size()

    def set_size(self, size):
        from .pointer_size import set_size
        set_size(size)


def _backend():
    return _WindowsRegistry()


def _encode_snapshot(snapshot):
    encoded = copy.deepcopy(snapshot)
    for section in encoded.values():
        for value in section["values"].values():
            if isinstance(value["data"], bytes):
                value["data"] = {"base64": base64.b64encode(value["data"]).decode("ascii")}
    return encoded


def _decode_snapshot(raw):
    if not isinstance(raw, dict) or set(raw) != set(_KEYS):
        raise ValueError("备份仅允许固定的当前用户指针键。")
    result = copy.deepcopy(raw)
    for label, section in result.items():
        if not isinstance(section, dict) or set(section) != {"exists", "values"}:
            raise ValueError("备份键结构无效。")
        if type(section["exists"]) is not bool or not isinstance(section["values"], dict):
            raise ValueError("备份键格式无效。")
        values = section["values"]
        if len(values) > 1000 or (not section["exists"] and values):
            raise ValueError("备份键的值数量或存在状态无效。")
        lowered = set()
        for name, entry in values.items():
            if not isinstance(name, str) or len(name) > 16383 or "\x00" in name or name.casefold() in lowered:
                raise ValueError("备份值名称无效或重复。")
            lowered.add(name.casefold())
            if not isinstance(entry, dict) or set(entry) != {"type", "data"}:
                raise ValueError("备份值结构无效。")
            kind, data = entry["type"], entry["data"]
            if type(kind) is not int or not 0 <= kind <= 11:
                raise ValueError("备份注册表类型无效。")
            if kind in (1, 2):
                valid = isinstance(data, str) and "\x00" not in data and len(data) <= 32767
            elif kind in (4, 11):
                valid = type(data) is int and 0 <= data < (1 << (32 if kind == 4 else 64))
            elif kind == 7:
                valid = isinstance(data, list) and len(data) <= 1000 and all(
                    isinstance(x, str) and "\x00" not in x and len(x) <= 32767 for x in data)
            elif kind == 0 and data is None:
                valid = True
            else:
                valid = isinstance(data, dict) and set(data) == {"base64"} and isinstance(data["base64"], str)
                if valid:
                    try:
                        entry["data"] = base64.b64decode(data["base64"], validate=True)
                    except (ValueError, TypeError) as error:
                        raise ValueError("备份二进制值无效。") from error
            if not valid:
                raise ValueError("备份注册表值与类型不匹配。")
    if result["schemes"]["exists"] and not result["cursors"]["exists"]:
        raise ValueError("备份父键不存在而子键存在。")
    return result


def _write_backup(snapshot, directory: Path, runtime_size=None) -> Path:
    # Validate before writing, including values produced by the actual registry.
    encoded = _encode_snapshot(snapshot)
    _decode_snapshot(encoded)
    payload = json.dumps({"format": "cursor-studio-backup", "version": 1,
                          "created_utc": datetime.now(timezone.utc).isoformat(),
                          "snapshot": encoded, "runtime_size": runtime_size}, ensure_ascii=False, indent=2).encode("utf-8")
    if len(payload) > _MAX_BACKUP:
        raise ValueError("指针备份超过 2 MiB，操作已取消。")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    name = "cursors-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8] + ".json"
    target = directory / name
    fd, temporary = tempfile.mkstemp(prefix=".backup-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target


def backup_current(backup_dir: Path) -> Path:
    """Read and back up all cursor/installed-scheme values; no registry writes."""
    backend = _backend()
    return _write_backup(backend.snapshot(), Path(backup_dir), backend.get_size())


def list_backups(directory: Path) -> list[Path]:
    return sorted((p for p in Path(directory).glob("cursors-*.json") if p.is_file()), reverse=True)


def _read_backup(path: Path, with_size=False):
    path = Path(path)
    if path.stat().st_size > _MAX_BACKUP:
        raise ValueError("备份文件超过 2 MiB。")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as error:
        raise ValueError("无法读取指针备份 JSON。") from error
    if not isinstance(raw, dict) or raw.get("format") != "cursor-studio-backup" or raw.get("version") != 1:
        raise ValueError("不支持的指针备份格式。")
    snapshot = _decode_snapshot(raw.get("snapshot"))
    size = raw.get('runtime_size')
    if size is not None and (type(size) is not int or not 16 <= size <= 256):
        raise ValueError('备份的系统实际尺寸无效。')
    if with_size:
        if size is None:
            entry = snapshot['cursors']['values'].get('CursorBaseSize', {})
            size = entry.get('data') if entry.get('type') == 4 else None
            if size is not None and (type(size) is not int or not 16 <= size <= 256):
                raise ValueError('旧备份中的系统尺寸无效。')
        return snapshot, size
    return snapshot


def _transaction(backend, wanted, original, size=None, original_size=None):
    try:
        backend.replace(wanted)
        if size is not None:backend.set_size(size)
        backend.refresh()
        if size is not None and backend.get_size() != size:
            raise OSError('Windows 运行时指针尺寸未生效，已停止报告成功。')
        if backend.snapshot() != wanted:
            raise OSError("应用后的注册表回读不一致。")
    except Exception as error:
        try:
            backend.replace(original)
            if original_size is not None:backend.set_size(original_size)
            backend.refresh()
            if original_size is not None and backend.get_size() != original_size:
                raise OSError('回滚后的运行时指针尺寸不一致。')
            if backend.snapshot() != original:
                raise OSError("回滚后的注册表回读不一致。")
        except Exception as rollback_error:
            raise RuntimeError(f"操作失败：{error}；自动回滚也失败：{rollback_error}。请使用已保存的备份恢复。") from error
        raise RuntimeError(f"操作失败，已回滚原方案：{error}") from error


def _set_value(values, name, kind, data):
    # winreg preserves the spelling of an existing value but compares names
    # case-insensitively. Model that when preparing the expected read-back.
    existing = next((key for key in values if key.casefold() == name.casefold()), name)
    values[existing] = {"type": kind, "data": data}


def restore_backup(path: Path) -> None:
    """Restore an explicit user-selected backup; confirmation is the caller's job."""
    wanted, size = _read_backup(Path(path), with_size=True)
    backend = _backend()
    backend.check_write()
    original = backend.snapshot()
    original_size = backend.get_size()
    _write_backup(original, Path(path).parent, original_size)
    _transaction(backend, wanted, original, size, original_size)


def apply_files(mapping: dict[str, Path], name: str, backup_dir: Path, size: int | None = None) -> Path:
    """Apply 15 persistent local files, returning the pre-change backup path.

    Files must remain at these paths after this call. No asset is copied, no
    elevation is requested, and no imported INF/script is ever executed.
    """
    if set(mapping) != set(ROLES):
        raise ValueError("应用需要完整且准确的 15 种角色映射。")
    if size is not None and (type(size) is not int or not 16 <= size <= 256):
        raise ValueError("系统指针尺寸必须是16–256之间的整数。")
    if not isinstance(name, str) or not name.strip() or len(name) > 128 or any(c in name for c in '\x00\r\n'):
        raise ValueError("方案名称必须为 1–128 个字符且不包含控制字符。")
    paths = {}
    for role in ROLES:
        path = Path(mapping[role]).resolve(strict=True)
        if not path.is_file() or path.suffix.lower() not in {".cur", ".ani"} or "," in str(path):
            raise ValueError("指针路径必须为有效 CUR/ANI 文件且不能包含逗号。")
        if not _validate_file(path):
            raise ValueError(f"Windows 无法加载指针：{role}")
        paths[role] = str(path)
    backend = _backend()
    backend.check_write()
    original = backend.snapshot()
    original_size = backend.get_size()
    backup = _write_backup(original, Path(backup_dir), original_size)
    wanted = copy.deepcopy(original)
    wanted["cursors"]["exists"] = True
    wanted["schemes"]["exists"] = True
    for role, path in paths.items():
        _set_value(wanted["cursors"]["values"], role, 2, path)
    _set_value(wanted["cursors"]["values"], "", 1, name)
    _set_value(wanted["cursors"]["values"], "Scheme Source", 4, 1)
    if size is not None:
        # Windows selects/scales cursor images using the system base size. Merely
        # exporting a larger CUR/ANI leaves a 32 px desktop cursor unchanged.
        # Microsoft's winget-dsc MousePointer resource uses this same HKCU value.
        _set_value(wanted["cursors"]["values"], "CursorBaseSize", 4, size)
    _set_value(wanted["schemes"]["values"], name, 1, ",".join(paths[key] for key in ROLES))
    _transaction(backend, wanted, original, size, original_size)
    return backup
