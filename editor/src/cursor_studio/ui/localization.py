"""Translate Qt's built-in dialogs and buttons using its bundled language pack."""
from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtWidgets import QApplication


def install_chinese():
    app = QApplication.instance()
    if app is None or hasattr(app, '_cursor_chinese'):
        return
    translator = QTranslator(app)
    if translator.load('qtbase_zh_CN', QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
        app._cursor_chinese = translator
