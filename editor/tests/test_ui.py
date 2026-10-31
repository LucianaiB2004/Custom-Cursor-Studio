import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from cursor_studio.models import Frame
from cursor_studio.ui.main_window import MainWindow

def window():
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.show(); app.processEvents()
    return app, w

def test_hotspot_and_reorder_and_delete():
    app, w = window()
    w.set_frames([Frame(Image.new('RGBA',(32,32),'red'),(2,3),50), Frame(Image.new('RGBA',(32,32),'blue'),(4,5),150)])
    w.hot_x.setValue(7)
    assert w.role.frames[0].hotspot == (7,3)
    w.move_frame(1)
    assert [f.duration_ms for f in w.role.frames] == [150,50]
    w.delete_frame()
    assert len(w.role.frames) == 1
    w.dirty=False; w.close()

def test_preview_uses_per_frame_duration():
    app, w = window()
    w.set_frames([Frame(Image.new('RGBA',(32,32),'red'),(0,0),40),Frame(Image.new('RGBA',(32,32),'blue'),(0,0),400)])
    w.toggle_play()
    QTest.qWait(90)
    assert w.frame_index == 1
    QTest.qWait(100)
    assert w.frame_index == 1
    w.toggle_play(); assert not w.timer.isActive()
    w.dirty=False; w.close()

def test_missing_role_explicit_copy_and_size():
    app, w = window()
    w.set_frames([Frame(Image.new('RGBA',(32,32),'red'),(0,0),100)])
    w.copy_to_missing()
    assert all(r.frames for r in w.theme.roles.values())
    w.role.frames[0].hotspot=(5,6)
    assert w.theme.roles['Hand'].frames[0].hotspot == (0,0)
    w.resize(1000,680); app.processEvents()
    assert w.preview.width() >= 250
    w.dirty=False; w.close()
