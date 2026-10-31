"""Launcher transaction review: never writes the real Windows registry."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from cursor_studio.ui import theme_launcher
from cursor_studio.windows import schemes
from test_schemes import Registry


def test_launcher_applies_selected_size_and_preserves_backend_backup(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    registry = Registry()
    monkeypatch.setattr(schemes, "_backend", lambda: registry)
    monkeypatch.setattr(schemes, "_validate_file", lambda path: True)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    launcher = theme_launcher.ThemeLauncher(Path("懒羊羊/project/theme.json"))
    launcher.home = tmp_path

    try:
        launcher.size.setCurrentIndex(launcher.size.findData(128))
        launcher.perform_apply()
        values=registry.snapshot()['cursors']['values']
        assert values['CursorBaseSize']['data']==128
        assert launcher.applied_size==128
        assert '已应用' in launcher.selection_status.text()
        assert list((tmp_path/'backups').glob('*.json'))
        assert not (tmp_path/'last-application.json').exists()
    finally:
        launcher.close()
