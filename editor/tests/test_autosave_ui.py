"""Automatic persistence across switching/close, without save confirmation dialogs."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path

from PIL import Image
import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PySide6.QtTest import QTest
from PySide6.QtGui import QCloseEvent
from cursor_studio.models import Frame
from cursor_studio.services.project import load_project, save_project
from cursor_studio.ui import main_window
from cursor_studio.ui.theme_launcher import ThemeLauncher

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def editor(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window,'ROOT',tmp_path)
    def unexpected(*args,**kwargs):raise AssertionError('Unexpected save confirmation or file picker')
    monkeypatch.setattr(QMessageBox,'question',unexpected)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',unexpected)
    window=main_window.MainWindow()
    yield window
    window.dirty=False;window.close()


def test_new_import_autosaves_after_edit_and_never_overwrites_another_project(editor,tmp_path):
    original=tmp_path/'source.png';Image.new('RGBA',(32,32),'red').save(original)
    original_bytes=original.read_bytes()
    existing=tmp_path/'projects/工程-未命名主题/theme.json'
    save_project(editor.theme,existing)
    old=existing.read_bytes()
    editor.set_frames([Frame(Image.open(original).convert('RGBA'),(3,4),173)])
    QTest.qWait(900)
    assert not editor.dirty and editor.project_path.is_file()
    assert editor.project_path.is_relative_to(tmp_path/'projects')
    assert editor.project_path!=existing
    restored=load_project(editor.project_path)
    assert restored.roles['Arrow'].frames[0].hotspot==(3,4)
    assert restored.roles['Arrow'].frames[0].duration_ms==173
    assert original.read_bytes()==original_bytes and existing.read_bytes()==old


def test_switch_flushes_pending_edits_to_existing_project_without_asking(editor,tmp_path):
    editor.set_frames([Frame(Image.new('RGBA',(32,32),'red'),(1,2),100)])
    editor.save();before=editor.project_path
    other=tmp_path/'另一个/theme.json';save_project(editor.theme,other)
    editor.set_hotspot(5,7)
    assert editor.dirty
    editor.open_source(other)
    assert load_project(before).roles['Arrow'].frames[0].hotspot==(5,7)
    assert editor.project_path==other and not editor.dirty
    assert not editor.autosave_timer.isActive()


def test_close_flushes_pending_new_project(editor):
    editor.set_frames([Frame(Image.new('RGBA',(32,32),'blue'),(2,3),100)])
    event=QCloseEvent();editor.closeEvent(event)
    assert event.isAccepted() and editor.project_path.is_file()
    assert not editor.dirty and not editor.autosave_timer.isActive()


def test_failed_save_blocks_switch_and_keeps_selector_and_edits(editor,tmp_path,monkeypatch):
    editor.set_frames([Frame(Image.new('RGBA',(32,32),'red'))])
    before=editor.theme
    editor.library_path='original selection'
    def denied(*a,**k):raise PermissionError('read-only project')
    monkeypatch.setattr(main_window,'save_project',denied)
    with pytest.raises(PermissionError):editor.open_source(tmp_path/'other')
    assert editor.theme is before and editor.dirty
    assert editor.project_path is None


def test_startup_is_real_standard_size_and_does_not_overwrite_source(editor,tmp_path):
    project=tmp_path/'例子/project/theme.json'
    theme=load_project(ROOT/'懒羊羊/project/theme.json')
    save_project(theme,project)
    before=project.read_bytes()
    editor.refresh_library();editor.open_startup()
    assert editor.output_size.currentData()==32
    assert editor.output_size.currentText()=='32 px（标准版）'
    assert all(role.size==32 for role in editor.theme.roles.values())
    assert editor.rendered[0].image.size==(32,32)
    assert project.read_bytes()==before and not editor.dirty
    editor.output_size.setCurrentIndex(editor.output_size.findData(128));editor.change_theme_size()
    editor.ask_discard()
    assert all(role.size==128 for role in load_project(project).roles.values())


def test_standalone_launcher_starts_standard_and_can_select_larger():
    app=QApplication.instance() or QApplication([])
    launcher=ThemeLauncher(ROOT/'懒羊羊/project/theme.json')
    try:
        assert launcher.size.currentData()==32
        assert '（标准版）' in launcher.size.currentText()
        assert launcher.preview_frames[0].image.size==(32,32)
        launcher.size.setCurrentIndex(launcher.size.findData(128))
        assert launcher.preview_frames[0].image.size==(128,128)
    finally:launcher.close()
