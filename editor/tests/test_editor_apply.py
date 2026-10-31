"""End-to-end edited pixels through save/export/apply; OS mutation is mocked."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import zipfile

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QDialog, QComboBox, QDoubleSpinBox
from cursor_studio.ui import main_window
from cursor_studio.services.application import apply_theme
from cursor_studio.services.project import load_project, save_project
from cursor_studio.services.export import export_theme
from cursor_studio.services.sizing import resize_theme
from cursor_studio.services.render import render_frames
from cursor_studio.windows import schemes
from cursor_studio.io.cur import decode_cur
from cursor_studio.io.ani import decode_ani
from test_schemes import Registry

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('name', ['懒羊羊', '一二', '吹泡泡Dva', '月神天使'])
@pytest.mark.parametrize('size', [64,128])
def test_all_cases_save_export_and_apply_the_same_edited_pixels(tmp_path, monkeypatch, name, size):
    theme = resize_theme(load_project(ROOT/name/'project/theme.json'), size)
    theme.roles['Arrow'].opacity = .6
    theme.roles['Arrow'].frames[0].hotspot = (7,9)
    project = tmp_path/'project/theme.json'
    save_project(theme, project)
    restored = load_project(project)
    archive = export_theme(restored, tmp_path/'theme.zip')
    registry = Registry()
    monkeypatch.setattr(schemes, '_backend', lambda: registry)
    # Windows validates every actual exported file. Non-Windows CI skips only
    # this native check, never substitutes the binary codecs or render path.
    if os.name != 'nt':monkeypatch.setattr(schemes, '_validate_file', lambda _: True)
    backup = apply_theme(restored, tmp_path/'local')
    assert backup.is_file() and registry.runtime_size == size
    values = registry.snapshot()['cursors']['values']
    assert values['CursorBaseSize']['data'] == size
    with zipfile.ZipFile(archive) as zipped:
        for key, role in restored.roles.items():
            path = Path(values[key]['data'])
            assert path.is_file() and '.prepare-' not in str(path)
            assert path.read_bytes() == zipped.read(path.name)
            frames = (decode_ani if path.suffix == '.ani' else decode_cur)(path.read_bytes())
            expected = render_frames(restored, role)
            assert frames[0].image.size == (size,size)
            assert frames[0].hotspot == expected[0].hotspot
            assert frames[0].image.tobytes() == expected[0].image.tobytes()
    assert all(f.image.size == (256,256) for f in theme.roles['Arrow'].frames)


def test_editor_resizes_overrides_and_apply_requires_confirmation(monkeypatch):
    app=QApplication.instance() or QApplication([])
    w=main_window.MainWindow()
    w.open_source(ROOT/'懒羊羊')
    called=[]
    monkeypatch.setattr(main_window,'apply_theme',lambda theme:called.append(theme) or Path('backup.json'))
    monkeypatch.setattr(QMessageBox,'information',lambda *a,**k:None)
    try:
        w.output_size.setCurrentIndex(w.output_size.findData(128));w.change_theme_size()
        assert all(role.size==128 for role in w.theme.roles.values())
        assert w.rendered[0].image.size==(128,128)
        assert w.size.currentData()==128
        assert not called
        assert not any('AI' in b.text() for b in w.findChildren(QPushButton))
        monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.No)
        w.confirm_apply();assert not called
        monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.Yes)
        w.confirm_apply()
        assert len(called)==1 and called[0].roles['Arrow'].size==128
        assert w.apply_button.isEnabled() and '已启用' in w.status.text()
        # A per-role size reduction must rescale hotspots, not create an invalid
        # coordinate and silently prevent rendering/export.
        w.role.frames[0].hotspot=(100,100)
        w.size.setCurrentIndex(w.size.findData(32))
        assert w.role.frames[0].hotspot==(25,25)
        assert w.rendered[0].image.size==(32,32)
        assert w.output_size.currentData() is None
    finally:
        w.dirty=False;w.close()


def test_size_failure_restores_both_registry_and_original_runtime_size(tmp_path,monkeypatch):
    registry=Registry()
    registry.state['cursors']['values']['CursorBaseSize']={'type':4,'data':128}
    before=registry.snapshot()
    calls=[]
    def set_size(size):
        calls.append(size)
        if size==96:raise OSError('size rejected')
        registry.runtime_size=size
    registry.set_size=set_size
    monkeypatch.setattr(schemes,'_backend',lambda:registry)
    monkeypatch.setattr(schemes,'_validate_file',lambda _:True)
    # Bundled projects are editable and may already have a user-selected size.
    theme=resize_theme(load_project(ROOT/'懒羊羊/project/theme.json'),96)
    with pytest.raises(RuntimeError,match='已回滚'):
        apply_theme(theme,tmp_path)
    assert registry.snapshot()==before and registry.runtime_size==32
    assert calls==[96,32]


def test_metadata_changes_all_existing_role_overrides(monkeypatch):
    app=QApplication.instance() or QApplication([])
    w=main_window.MainWindow();w.open_source(ROOT/'一二')
    def accept_settings(dialog):
        combo=dialog.findChild(QComboBox)
        combo.setCurrentIndex(combo.findData(128))
        dialog.findChild(QDoubleSpinBox).setValue(120)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog,'exec',accept_settings)
    try:
        w.metadata()
        assert w.theme.canvas_size==128 and w.theme.scale==1.2
        assert all(role.size==128 and role.scale is None for role in w.theme.roles.values())
        assert w.output_size.currentData()==128 and w.rendered[0].image.size==(128,128)
    finally:w.dirty=False;w.close()
