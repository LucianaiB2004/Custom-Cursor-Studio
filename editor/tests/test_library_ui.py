import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PIL import Image
from PySide6.QtWidgets import QApplication
from cursor_studio.ui import main_window

def test_library_opens_project_and_refreshes_new_folder(tmp_path,monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window,'ROOT',tmp_path)
    w = main_window.MainWindow()
    assert w.library.count()==1
    folder = tmp_path/'后来加入'
    folder.mkdir()
    Image.new('RGBA',(32,32),'red').save(folder/'Arrow.png')
    w.refresh_library()
    assert w.library.count()==2
    w.library.setCurrentIndex(1)
    w.open_library_selection()
    assert w.theme.name=='后来加入' and len(w.role.frames)==1
    assert w.project_path is None and w.dirty
    assert '14' in w.status.text()
    w.dirty=False;w.close()

def test_startup_and_folder_import_can_open_bundled_projects():
    app = QApplication.instance() or QApplication([])
    w = main_window.MainWindow()
    w.open_startup()
    assert all(role.frames for role in w.theme.roles.values())
    w.dirty=False
    w.open_source(main_window.ROOT/'懒羊羊')
    assert w.project_path==main_window.ROOT/'懒羊羊/project/theme.json'
    assert not w.dirty
    w.open_source(main_window.ROOT/'月神天使')
    assert w.project_path==main_window.ROOT/'月神天使/project/theme.json'
    w.open_source(main_window.ROOT/'月神天使/AutoSetup.inf')
    assert w.project_path is None and w.dirty
    w.dirty=False;w.close()

def test_hd_projects_editable_original_reference_files_protected():
    import pytest
    app=QApplication.instance() or QApplication([])
    w=main_window.MainWindow()
    w.protect(main_window.ROOT/'月神天使/project/theme.json')
    with pytest.raises(ValueError,match='原始参考'):
        w.protect(main_window.ROOT/'月神天使/AutoSetup.inf')
    w.close()

def test_cancel_or_failed_import_keeps_theme_and_selector(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    w=main_window.MainWindow()
    w.open_source(main_window.ROOT/'懒羊羊')
    before=w.library.currentData();theme=w.theme
    monkeypatch.setattr(w,'ask_discard',lambda:False)
    w.library.setCurrentIndex(w.library.findData(str(main_window.ROOT/'一二')))
    w.open_library_selection()
    assert w.theme is theme and w.library.currentData()==before
    monkeypatch.setattr(w,'ask_discard',lambda:True)
    from cursor_studio.models import Frame
    from cursor_studio.io.ani import encode_ani
    import pytest
    (tmp_path/'Arrow.ani').write_bytes(encode_ani([Frame(Image.new('RGBA',(32,32)),(0,0),70000)]))
    with pytest.raises(ValueError):w.open_source(tmp_path)
    assert w.theme is theme and w.library.currentData()==before
    w.dirty=False;w.close()
