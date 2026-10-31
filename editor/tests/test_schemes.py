import copy
import json
from pathlib import Path

import pytest

from cursor_studio.models import ROLES
from cursor_studio.windows import schemes


class Registry:
    def __init__(self):
        self.state = {
            "cursors": {"exists": True, "values": {
                "": {"type": 1, "data": "原方案"},
                "Arrow": {"type": 2, "data": "%SystemRoot%\\Cursors\\arrow.cur"},
                "custom": {"type": 3, "data": b"\x00\xff"},
                "multi": {"type": 7, "data": ["甲", "乙"]},
            }},
            "schemes": {"exists": False, "values": {}},
        }
        self.refreshes = 0
        self.fail_refresh_once = False
        self.permission = True
        self.runtime_size = 32

    def get_size(self):
        return self.runtime_size

    def set_size(self, size):
        self.runtime_size = size

    def snapshot(self):
        return copy.deepcopy(self.state)

    def check_write(self):
        if not self.permission:
            raise PermissionError("write denied")

    def replace(self, snapshot):
        self.state = copy.deepcopy(snapshot)

    def refresh(self):
        self.refreshes += 1
        if self.fail_refresh_once:
            self.fail_refresh_once = False
            raise OSError("SPI_SETCURSORS failed")


@pytest.fixture
def registry(monkeypatch):
    registry = Registry()
    monkeypatch.setattr(schemes, "_backend", lambda: registry)
    monkeypatch.setattr(schemes, "_validate_file", lambda _: True)
    return registry


def files(tmp_path):
    result = {}
    for role in ROLES:
        path = tmp_path / (role + ".cur")
        path.write_bytes(b"test-only validated by fixture")
        result[role] = path
    return result


def test_backup_preserves_binary_types_and_absent_key(tmp_path, registry):
    path = schemes.backup_current(tmp_path)
    original = registry.snapshot()
    registry.state["cursors"]["values"]["Arrow"] = {"type": 1, "data": "changed"}
    registry.state["cursors"]["values"]["added"] = {"type": 4, "data": 1}
    schemes.restore_backup(path)
    assert registry.state == original
    assert registry.refreshes == 1
    assert len(schemes.list_backups(tmp_path)) == 2


def test_backup_preserves_empty_reg_none_value(tmp_path, registry):
    registry.state["cursors"]["values"]["empty"] = {"type": 0, "data": None}
    path = schemes.backup_current(tmp_path)
    registry.state["cursors"]["values"].pop("empty")
    schemes.restore_backup(path)
    assert registry.state["cursors"]["values"]["empty"] == {"type": 0, "data": None}


def test_apply_persists_backup_before_mutation_and_maps_all_roles(tmp_path, registry):
    original = registry.snapshot()
    original_replace = registry.replace
    def checked_replace(snapshot):
        assert schemes.list_backups(tmp_path / "backups")
        original_replace(snapshot)
    registry.replace = checked_replace
    mapping = files(tmp_path)
    backup = schemes.apply_files(mapping, "我的指针", tmp_path / "backups")
    assert backup.is_file()
    assert registry.state["cursors"]["values"]["Scheme Source"] == {"type": 4, "data": 1}
    for key, path in mapping.items():
        assert registry.state["cursors"]["values"][key] == {"type": 2, "data": str(path.resolve())}
    schemes.restore_backup(backup)
    assert registry.state == original


def test_failed_refresh_rolls_back_every_value(tmp_path, registry):
    original = registry.snapshot()
    registry.fail_refresh_once = True
    with pytest.raises(RuntimeError, match="已回滚"):
        schemes.apply_files(files(tmp_path), "new", tmp_path / "backups")
    assert registry.state == original
    assert registry.refreshes == 2


def test_denied_permissions_make_no_backup_or_changes(tmp_path, registry):
    original = registry.snapshot()
    registry.permission = False
    with pytest.raises(PermissionError):
        schemes.apply_files(files(tmp_path), "new", tmp_path / "backups")
    assert registry.state == original
    assert not (tmp_path / "backups").exists()


def test_reject_missing_roles_before_any_mutation(tmp_path, registry):
    with pytest.raises(ValueError, match="15"):
        schemes.apply_files({}, "new", tmp_path)
    assert registry.refreshes == 0


def test_reject_arbitrary_registry_path_and_bad_value_type(tmp_path, registry):
    path = schemes.backup_current(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["snapshot"]["HKLM\\Software\\bad"] = {}
    path.write_text(json.dumps(payload), encoding="utf-8")
    original = registry.snapshot()
    with pytest.raises(ValueError):
        schemes.restore_backup(path)
    assert registry.state == original
    assert registry.refreshes == 0


def test_native_validation_failure_cannot_apply(tmp_path, registry, monkeypatch):
    monkeypatch.setattr(schemes, "_validate_file", lambda _: False)
    with pytest.raises(ValueError, match="加载"):
        schemes.apply_files(files(tmp_path), "new", tmp_path / "backups")
    assert registry.refreshes == 0
    assert not (tmp_path / "backups").exists()


def test_case_insensitive_registry_names_do_not_create_duplicate_values(tmp_path, registry):
    values = registry.state["cursors"]["values"]
    values["arrow"] = values.pop("Arrow")
    mapping = files(tmp_path)
    schemes.apply_files(mapping, "new", tmp_path / "backups")
    values = registry.state["cursors"]["values"]
    assert "Arrow" not in values
    assert values["arrow"]["data"] == str(mapping["Arrow"].resolve())


def test_failed_rollback_reports_failure_and_retains_backup(tmp_path, registry):
    def always_fail():
        raise OSError("refresh broken")
    registry.refresh = always_fail
    with pytest.raises(RuntimeError, match="自动回滚也失败"):
        schemes.apply_files(files(tmp_path), "new", tmp_path / "backups")
    assert len(schemes.list_backups(tmp_path / "backups")) == 1


@pytest.mark.parametrize("kind,data", [(4, -1), (4, "1"), (2, 1), (7, ["ok", 123]), (99, "bad")])
def test_restore_rejects_wrong_registry_data_types(tmp_path, registry, kind, data):
    path = schemes.backup_current(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["snapshot"]["cursors"]["values"]["malformed"] = {"type": kind, "data": data}
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        schemes.restore_backup(path)
    assert registry.refreshes == 0
