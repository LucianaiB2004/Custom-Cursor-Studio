"""Independent regression checks for integration boundaries."""
from PIL import Image
from cursor_studio.models import Theme, Role, Frame, ROLES
from cursor_studio.services.export import export_theme
from cursor_studio.io.importers import safe_extract_reference
from cursor_studio.io.reference import import_reference
import os
import pytest

def test_exported_zip_can_be_opened_as_reference(tmp_path):
    theme=Theme(name='自制主题')
    for key in ROLES:
        theme.roles[key]=Role([Frame(Image.new('RGBA',(32,32),'red'),(2,3),100)],size=32)
    archive=export_theme(theme,tmp_path/'theme.zip')
    target=safe_extract_reference(archive,tmp_path/'unpacked')
    reopened=import_reference(target/'AutoSetup.inf')
    assert all(reopened.roles[k].frames for k in ROLES)
    assert reopened.roles['Arrow'].frames[0].hotspot==(2,3)

def test_failed_save_on_close_keeps_window_open(tmp_path,monkeypatch):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication,QMessageBox
    from PySide6.QtGui import QCloseEvent
    from cursor_studio.ui.main_window import MainWindow
    app=QApplication.instance() or QApplication([])
    w=MainWindow();w.show();app.processEvents()
    w.set_frames([Frame(Image.new('RGBA',(32,32)),(0,0),100)])
    w.role.frames[0].hotspot=(99,0)
    w.project_path=tmp_path/'cannot_save.json'
    monkeypatch.setattr(QMessageBox,'question',lambda *args,**kwargs:QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QMessageBox,'warning',lambda *args,**kwargs:QMessageBox.StandardButton.Ok)
    event=QCloseEvent()
    try:
        w.closeEvent(event)
        assert not event.isAccepted()
        assert w.dirty and w.isVisible()
        assert not w.project_path.exists()
    finally:w.dirty=False;w.close()

def test_import_sequence_stops_at_budget_before_decoding_more(tmp_path,monkeypatch):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication,QFileDialog
    import cursor_studio.ui.main_window as ui
    app=QApplication.instance() or QApplication([]);w=ui.MainWindow()
    files=[]
    for i in range(3):
        path=tmp_path/f'{i}.png';Image.new('RGBA',(3000,3000)).save(path);files.append(str(path))
    original=ui.import_media;seen=[]
    def tracked(path):
        seen.append(path)
        assert len(seen)<=2,'decoder was invoked after the sequence exceeded its aggregate budget'
        return original(path)
    monkeypatch.setattr(QFileDialog,'getOpenFileNames',lambda *args,**kwargs:(files,''))
    monkeypatch.setattr(ui,'import_media',tracked)
    try:
        with pytest.raises(ValueError):w.import_files()
        assert not w.role.frames
    finally:w.dirty=False;w.close()
