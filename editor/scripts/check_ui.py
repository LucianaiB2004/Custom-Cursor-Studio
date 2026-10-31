"""Render actual Qt widgets at acceptance sizes, without system cursor changes."""
import os
import sys
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from cursor_studio.ui.main_window import MainWindow, ROOT
from cursor_studio.paths import EDITOR_ROOT
app=QApplication([])
w=MainWindow()
w.open_startup(ROOT/'月神天使')
w.show()
for width,height in [(1280,820),(1000,680)]:
    w.resize(width,height);app.processEvents()
    w.grab().save(str(EDITOR_ROOT/'evidence'/f'editor-{width}.png'))
w.dirty=False;w.close()
