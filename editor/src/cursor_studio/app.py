import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from cursor_studio.ui.main_window import MainWindow

def main():
    app=QApplication(sys.argv)
    app.setApplicationName('Custom Cursor Studio');app.setOrganizationName('CursorStudio')
    window=MainWindow();window.show()
    path=Path(sys.argv[1]) if len(sys.argv)>1 else None
    QTimer.singleShot(0,lambda:window.safe(lambda:window.open_startup(path)))
    return app.exec()

if __name__=='__main__':raise SystemExit(main())
