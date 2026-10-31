"""Explicit size selection and apply surface; cancellation lives at repository root."""
import os
import sys
from pathlib import Path
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication,QDialog,QVBoxLayout,QLabel,QPushButton,QMessageBox,QComboBox,QHBoxLayout,QFileDialog
from cursor_studio.models import ROLES
from cursor_studio.services.project import load_project
from cursor_studio.services.export import validate_theme
from cursor_studio.services.application import apply_theme
from cursor_studio.services.sizing import STANDARD_SIZE, OUTPUT_SIZES, size_label
from .preview import pixmap,Scene
from .localization import install_chinese

class ThemeLauncher(QDialog):
    def __init__(self,project):
        super().__init__()
        install_chinese()
        self.project=Path(project).resolve();self.theme=load_project(self.project)
        for name in ['msyh.ttc','msyhbd.ttc']:
            p=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name
            if p.exists():QFontDatabase.addApplicationFont(str(p))
        self.home=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'CustomCursorStudio'
        self.setWindowTitle('调整大小并应用 · '+self.theme.name);self.resize(520,650)
        self.preview_frames=[];self.preview_index=0;self.applied_size=None
        self.preview_timer=QTimer(self);self.preview_timer.setSingleShot(True);self.preview_timer.timeout.connect(self.advance_preview)
        layout=QVBoxLayout(self);layout.setSpacing(10)
        title=QLabel(self.theme.name);title.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(title)
        self.icon=QLabel();self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter);self.icon.setFixedHeight(144);layout.addWidget(self.icon)
        row=QHBoxLayout();row.addWidget(QLabel('实际指针大小'))
        self.size=QComboBox()
        for n in OUTPUT_SIZES:self.size.addItem(size_label(n),n)
        self.size.currentIndexChanged.connect(self.update_size);row.addWidget(self.size);layout.addLayout(row)
        self.selection_status=QLabel();layout.addWidget(self.selection_status)
        hint=QLabel('选尺寸仅更新预览。要改变系统指针，请点击下方“应用所选大小”。');hint.setWordWrap(True);layout.addWidget(hint)
        self.scene=Scene();layout.addWidget(self.scene)
        self.size.setCurrentIndex(self.size.findData(STANDARD_SIZE));self.update_size()
        note=QLabel('点击应用后，将备份当前方案并切换全部 15 种系统指针。\n无需打开编辑器，无需管理员权限。');note.setWordWrap(True);layout.addWidget(note)
        for text,fn in [('应用所选大小',self.confirm_apply),('导出所选大小的主题 ZIP',self.export_selected),('关闭',self.close)]:
            b=QPushButton(text);b.clicked.connect(lambda checked=False,f=fn:self.safe(f));layout.addWidget(b)
        cancel_hint=QLabel('取消自定义：请运行项目根目录的“取消自定义光标.cmd”，恢复 Windows 默认白色指针。');cancel_hint.setWordWrap(True);layout.addWidget(cancel_hint)
        self.setStyleSheet('QWidget{font-family:"Microsoft YaHei";font-size:14px;background:#f5f3fa;color:#373045;} QPushButton{padding:10px;border:1px solid #cfc4e8;border-radius:8px;background:white;}')
    def safe(self,fn):
        try:fn()
        except Exception as exc:QMessageBox.warning(self,'操作未完成',str(exc))
    def selected_theme(self):
        from cursor_studio.services.sizing import resize_theme
        return resize_theme(self.theme,self.size.currentData())
    def update_size(self,*args):
        from cursor_studio.services.render import render_frames
        self.preview_timer.stop()
        t=self.selected_theme();self.preview_frames=render_frames(t,t.roles['Arrow']);self.preview_index=0
        self.show_preview_frame()
        selected=self.size.currentData()
        state='已应用' if selected==self.applied_size else '预览中 · 尚未应用'
        self.selection_status.setText(f'所选 {selected} px · {state}（显示大小还受系统 DPI 影响）')
    def show_preview_frame(self):
        frame=self.preview_frames[self.preview_index]
        self.icon.setPixmap(pixmap(frame.image));self.scene.set_frame(frame)
        if len(self.preview_frames)>1:self.preview_timer.start(max(1,round(frame.duration_ms)))
    def advance_preview(self):
        if self.preview_frames:
            self.preview_index=(self.preview_index+1)%len(self.preview_frames);self.show_preview_frame()
    def closeEvent(self,event):
        self.preview_timer.stop();super().closeEvent(event)
    def export_selected(self):
        from cursor_studio.services.export import export_theme
        path,_=QFileDialog.getSaveFileName(self,'导出所选大小',self.theme.name+'.zip','主题 (*.zip)')
        if path:
            overwrite=Path(path).exists()
            if overwrite and QMessageBox.question(self,'确认覆盖','替换已存在的 ZIP？')!=QMessageBox.StandardButton.Yes:return
            export_theme(self.selected_theme(),path,overwrite)
            QMessageBox.information(self,'导出完成',path)
    def confirm_apply(self):
        if QMessageBox.question(self,'确认应用系统指针',f'立即以 {self.size.currentData()} px 应用“{self.theme.name}”的 15 种系统指针？\n将先备份当前设置，失败自动尝试回滚。',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
            self.perform_apply()
    def perform_apply(self):
        theme=self.selected_theme()
        apply_theme(theme,self.home)
        self.applied_size=self.size.currentData();self.update_size()
        QMessageBox.information(self,'已应用',f'已应用 {self.applied_size} px 系统鼠标主题。取消请运行根目录“取消自定义光标.cmd”。')

def main():
    app=QApplication(sys.argv)
    try:w=ThemeLauncher(sys.argv[1]);w.show()
    except Exception as exc:QMessageBox.critical(None,'主题无法打开',str(exc));return 1
    return app.exec()

if __name__=='__main__':raise SystemExit(main())
