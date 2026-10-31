import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PySide6.QtWidgets import QApplication,QMessageBox,QPushButton
from cursor_studio.ui.theme_launcher import ThemeLauncher

def test_cancel_apply_does_not_touch_system(monkeypatch):
    app=QApplication.instance() or QApplication([])
    w=ThemeLauncher(Path('懒羊羊/project/theme.json'))
    called=[]
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.No)
    monkeypatch.setattr(w,'perform_apply',lambda:called.append(True))
    w.confirm_apply()
    assert called==[]
    w.close()

def test_launcher_opens_without_editor():
    app=QApplication.instance() or QApplication([])
    w=ThemeLauncher(Path('一二/project/theme.json'))
    assert w.theme.name.startswith('一二')
    assert w.width()<900
    w.close()

def test_size_selection_changes_local_cursor_but_waits_for_apply(monkeypatch):
    app=QApplication.instance() or QApplication([])
    w=ThemeLauncher(Path('懒羊羊/project/theme.json'))
    applied=[]
    monkeypatch.setattr(w,'perform_apply',lambda:applied.append(True))
    for size in [64,96,128]:
        w.size.setCurrentIndex(w.size.findData(size))
        assert w.icon.pixmap().width()==size
        assert w.scene.cursor().pixmap().width()==size
        assert '尚未应用' in w.selection_status.text()
    assert not applied
    assert not any('恢复' in button.text() for button in w.findChildren(QPushButton))
    assert not hasattr(w,'confirm_restore')
    w.close()
