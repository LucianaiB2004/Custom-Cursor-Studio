import copy
import json
import os
import tempfile
import time
from pathlib import Path
from PIL import Image
from PySide6.QtCore import Qt, QTimer, QSize, QThread, Signal
from PySide6.QtGui import QColor, QIcon, QAction, QKeySequence, QFontDatabase
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QListWidget, QListWidgetItem, QSplitter,
    QScrollArea, QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox, QSlider,
    QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QTextEdit, QColorDialog,
    QInputDialog, QProgressDialog)
from cursor_studio.models import Frame, Role, Theme, ROLES
from cursor_studio.paths import WORKSPACE_ROOT,EDITOR_ROOT
from cursor_studio.io.importers import import_media
from cursor_studio.services.project import save_project, atomic_write
from cursor_studio.services.render import render_frames
from cursor_studio.services.export import validate_theme, export_theme
from cursor_studio.services.library import discover_themes, open_theme_source
from cursor_studio.services.sizing import resize_theme, STANDARD_SIZE, OUTPUT_SIZES, size_label
from cursor_studio.services.autosave import reserve_project_path
from cursor_studio.services.application import apply_theme
from .preview import Preview, Scene, pixmap
from .localization import install_chinese

ROOT = WORKSPACE_ROOT
FILTER = '光标素材 (*.png *.jpg *.jpeg *.gif *.apng *.svg *.cur *.ani)'

class ExportWorker(QThread):
    succeeded = Signal(str)
    failed = Signal(str)
    def __init__(self, theme, path, overwrite):
        super().__init__(); self.theme=copy.deepcopy(theme); self.path=path; self.overwrite=overwrite
    def run(self):
        try: self.succeeded.emit(str(export_theme(self.theme,self.path,self.overwrite)))
        except Exception as exc: self.failed.emit(str(exc))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        install_chinese()
        for font in ['msyh.ttc','msyhbd.ttc']:
            path=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/font
            if path.exists():QFontDatabase.addApplicationFont(str(path))
        self.theme=Theme(canvas_size=STANDARD_SIZE); self.project_path=None; self.dirty=False; self.loading=False;self.library_path=None
        self.autosave_path=None
        self.autosave_timer=QTimer(self);self.autosave_timer.setSingleShot(True)
        self.autosave_timer.timeout.connect(self.autosave_background)
        self.frame_index=0; self.rendered=[]; self.playing=False; self.deadline=0
        self.history=[]; self.brush_color=QColor('#9468df'); self.worker=None
        self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.advance)
        self.setWindowTitle('Custom Cursor Studio · 自定义鼠标指针'); self.resize(1280,820)
        self.setMinimumSize(1000,680)
        host=QWidget(); self.setCentralWidget(host); layout=QVBoxLayout(host);layout.setContentsMargins(16,12,16,10);layout.setSpacing(10)
        top=QHBoxLayout(); brand=QLabel('Cursor Studio');brand.setObjectName('brand');top.addWidget(brand)
        self.name=QLineEdit(self.theme.name);self.name.setMaximumWidth(200);self.name.setAccessibleName('主题名称');top.addWidget(self.name,1)
        self.name.textEdited.connect(self.rename_theme)
        for text, fn in [('新建',self.new_project),('打开',self.open_project),('另存为',self.save_as),('导入素材',self.import_files),('导出 ZIP',self.export_zip)]:
            b=self.button(text,fn);top.addWidget(b)
            if text=='导出 ZIP':b.setObjectName('primary')
        self.apply_button=self.button('启用当前主题',self.confirm_apply)
        self.apply_button.setObjectName('primary');top.addWidget(self.apply_button)
        layout.addLayout(top)
        secondary=QHBoxLayout()
        secondary.addWidget(QLabel('本地主题'))
        self.library=QComboBox();self.library.setMinimumWidth(170);self.library.setMaximumWidth(280)
        self.library.setToolTip('自动发现项目根目录和 projects 下的主题文件夹；选择后打开编辑')
        self.library.activated.connect(lambda *_:self.safe(self.open_library_selection));secondary.addWidget(self.library)
        for text,fn in [('刷新',self.refresh_library),('导入文件夹',self.folder_dialog),('导入 INF / ZIP',self.reference_dialog),('主题设置',self.metadata)]:
            secondary.addWidget(self.button(text,fn))
        secondary.addStretch()
        secondary.addWidget(QLabel('整套尺寸'))
        self.output_size=QComboBox();self.output_size.addItem('各状态独立',None)
        for n in OUTPUT_SIZES:self.output_size.addItem(size_label(n),n)
        self.output_size.setToolTip('改变全部15种状态的输出尺寸，同时按比例调整热点；保存、导出和启用均使用此尺寸。')
        self.output_size.activated.connect(lambda *_:self.safe(self.change_theme_size));secondary.addWidget(self.output_size)
        secondary.addWidget(self.button('备份记录',self.backups))
        layout.addLayout(secondary)
        splitter=QSplitter();layout.addWidget(splitter,1)
        left=QWidget();ll=QVBoxLayout(left);ll.setContentsMargins(0,0,0,0)
        self.role_heading=QLabel('系统指针  ·  0 / 15');self.role_heading.setObjectName('heading');ll.addWidget(self.role_heading)
        self.roles=QListWidget();self.roles.setIconSize(QSize(32,32));self.roles.setMinimumWidth(180);self.roles.setMaximumWidth(250);ll.addWidget(self.roles)
        for key,name in ROLES.items():
            item=QListWidgetItem(name);item.setData(Qt.ItemDataRole.UserRole,key);item.setSizeHint(QSize(180,43));self.roles.addItem(item)
        ll.addWidget(self.button('用当前角色补齐缺失项…',self.confirm_copy))
        splitter.addWidget(left)
        middle=QWidget();ml=QVBoxLayout(middle);ml.setContentsMargins(10,0,10,0);ml.setSpacing(9)
        titlebar=QHBoxLayout();self.current_title=QLabel('正常选择');self.current_title.setObjectName('heading');titlebar.addWidget(self.current_title);titlebar.addStretch()
        self.background=QComboBox();self.background.addItems(['棋盘','浅色','深色']);self.background.currentTextChanged.connect(self.background_changed);titlebar.addWidget(self.background)
        self.zoom=QComboBox();self.zoom.addItems(['查看 100%','查看 200%','查看 400%','查看 800%']);self.zoom.setToolTip('仅放大编辑画面，不改变导出或系统指针大小；实际大小请用“整套尺寸”。');self.zoom.setCurrentIndex(2);self.zoom.currentIndexChanged.connect(self.zoom_changed);titlebar.addWidget(self.zoom);ml.addLayout(titlebar)
        self.preview=Preview();ml.addWidget(self.preview,1)
        self.preview.hotspotChanged.connect(self.set_hotspot)
        self.preview.strokeStarted.connect(self.start_stroke);self.preview.paintPixel.connect(self.paint_pixel)
        controls=QHBoxLayout()
        controls.addWidget(self.button('<',lambda:self.select_frame(self.frame_index-1)))
        self.play=self.button('播放',self.toggle_play);controls.addWidget(self.play)
        controls.addWidget(self.button('>',lambda:self.select_frame(self.frame_index+1)))
        self.frame_label=QLabel('尚未导入');controls.addWidget(self.frame_label);controls.addStretch()
        self.tool=QComboBox();self.tool.addItems(['热点','画笔','橡皮']);self.tool.currentTextChanged.connect(self.tool_changed);controls.addWidget(self.tool)
        controls.addWidget(self.button('颜色',self.pick_color));controls.addWidget(self.button('撤销',self.undo));ml.addLayout(controls)
        self.scene=Scene();ml.addWidget(self.scene);splitter.addWidget(middle)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setMinimumWidth(270);scroll.setMaximumWidth(340)
        right=QWidget();rl=QVBoxLayout(right);rl.setContentsMargins(12,4,8,8);rl.setSpacing(9)
        heading=QLabel('当前状态属性');heading.setObjectName('heading');rl.addWidget(heading)
        self.source_info=QLabel('导入图片或逐帧绘制');self.source_info.setWordWrap(True);rl.addWidget(self.source_info)
        form=QFormLayout();form.setHorizontalSpacing(8)
        self.size=QComboBox();self.size.addItem('跟随主题',None)
        for n in [32,48,64,96,128,256]:self.size.addItem(f'{n} × {n}',n)
        form.addRow('画布尺寸',self.size)
        self.scale=QDoubleSpinBox();self.scale.setRange(0,800);self.scale.setSuffix(' %');self.scale.setSpecialValueText('跟随主题');self.scale.setDecimals(0);form.addRow('素材缩放',self.scale)
        self.interpolation=QComboBox();self.interpolation.addItems(['像素 · 无插值','高清 · 平滑']);form.addRow('缩放方式',self.interpolation)
        self.fit=QComboBox();self.fit.addItems(['完整显示','铺满并裁切']);form.addRow('适配方式',self.fit)
        self.align=QComboBox();self.align.addItems(['居中','左上','右上','左下','右下']);form.addRow('对齐',self.align)
        self.opacity=QSpinBox();self.opacity.setRange(0,100);self.opacity.setSuffix(' %');form.addRow('不透明度',self.opacity)
        hot=QHBoxLayout();self.hot_x=QSpinBox();self.hot_y=QSpinBox()
        for label,spin in [('X',self.hot_x),('Y',self.hot_y)]:hot.addWidget(QLabel(label));spin.setRange(0,255);hot.addWidget(spin)
        form.addRow('点击热点',hot);rl.addLayout(form)
        hint=QLabel('红色十字是实际点击位置。缩放或裁切后请校准热点。');hint.setWordWrap(True);hint.setObjectName('muted');rl.addWidget(hint)
        rl.addWidget(self.button('将热点应用到全部帧',self.hotspot_all))
        rl.addWidget(QLabel('动画帧  ·  按所列顺序循环'))
        self.frames=QListWidget();self.frames.setIconSize(QSize(28,28));self.frames.setMinimumHeight(120);self.frames.setMaximumHeight(210);rl.addWidget(self.frames)
        actions=QHBoxLayout()
        for text,fn in [('+',lambda:self.import_files(True)),('−',self.delete_frame),('↑',lambda:self.move_frame(-1)),('↓',lambda:self.move_frame(1))]:actions.addWidget(self.button(text,fn))
        rl.addLayout(actions)
        times=QFormLayout();self.duration=QDoubleSpinBox();self.duration.setRange(1,60000);self.duration.setDecimals(3);self.duration.setSuffix(' ms');times.addRow('当前帧时长',self.duration);rl.addLayout(times)
        rl.addWidget(self.button('将时长应用到全部帧',self.duration_all))
        rl.addWidget(self.button('新建透明帧',self.blank_frame));rl.addWidget(self.button('导出当前 CUR / ANI',self.export_current));rl.addStretch()
        scroll.setWidget(right);splitter.addWidget(scroll);splitter.setSizes([210,680,300]);splitter.setCollapsible(0,False);splitter.setCollapsible(1,False);splitter.setCollapsible(2,False)
        self.status=QLabel('就绪 · 离线处理，素材不会上传');layout.addWidget(self.status)
        self.roles.currentRowChanged.connect(self.role_changed);self.frames.currentRowChanged.connect(self.select_frame)
        for widget in [self.size,self.interpolation,self.fit,self.align]:widget.currentIndexChanged.connect(self.properties_changed)
        for widget in [self.scale,self.opacity]:widget.valueChanged.connect(self.properties_changed)
        self.hot_x.valueChanged.connect(self.hotspot_input);self.hot_y.valueChanged.connect(self.hotspot_input);self.duration.valueChanged.connect(self.duration_changed)
        self.roles.setCurrentRow(0)
        self.setStyleSheet('''
QMainWindow,QWidget { font-family: "Microsoft YaHei"; font-size: 12px; color:#30374a; }
QMainWindow { background:#f4f5f9; } QLabel#brand { font-size:19px;font-weight:700;color:#5c4bb4; }
QLabel#heading { font-size:15px; font-weight:600; padding:5px 0; } QLabel#muted {color:#7c8493;font-size:11px;}
QPushButton {background:#fff;border:1px solid #dce0e9;border-radius:7px;padding:7px 10px;}
QPushButton:hover {background:#eeebfc;border-color:#aea0e0;} QPushButton:pressed {background:#ded6f7;}
QPushButton#primary {background:#7761ce;color:white;border-color:#7761ce;font-weight:600;}
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QTextEdit {background:#fff;border:1px solid #dce0e9;border-radius:5px;padding:5px;}
QListWidget {background:white;border:1px solid #e0e3eb;border-radius:9px;outline:none;}
QListWidget::item {padding:3px 5px;border-radius:5px;} QListWidget::item:selected {background:#eae5fa;color:#57419e;}
QScrollArea {border:0;background:transparent;} QSplitter::handle {background:#e2e5ec;}
''')
        for shortcut,fn in [('Ctrl+S',self.save),('Ctrl+O',self.open_project),('Ctrl+N',self.new_project),('Ctrl+Z',self.undo)]:
            action=QAction(self);action.setShortcut(QKeySequence(shortcut));action.triggered.connect(lambda checked=False,f=fn:self.safe(f));self.addAction(action)
        self.refresh_library()

    def button(self,text,fn):
        b=QPushButton(text);b.clicked.connect(lambda checked=False:self.safe(fn));return b
    def safe(self,fn):
        try:return fn()
        except Exception as exc:
            QMessageBox.warning(self,'操作未完成',str(exc));self.status.setText(f'操作未完成：{exc}')
    @property
    def key(self):
        return list(ROLES)[max(0,self.roles.currentRow())]
    @property
    def role(self):return self.theme.roles[self.key]
    def mark(self):
        self.dirty=True;self.setWindowTitle(f'{self.theme.name} * · Custom Cursor Studio')
        self.autosave_timer.start(700)
    def autosave_background(self):
        if not self.dirty:return
        try:self.save()
        except Exception as exc:
            self.status.setText(f'自动保存未完成：{exc} · 更改仍在编辑器中，请修正后重试')
    def snapshot(self):
        self.history.append((self.key,copy.deepcopy(self.role)))
        if len(self.history)>12:self.history.pop(0)
    def undo(self):
        if self.history:
            key,role=self.history.pop();self.theme.roles[key]=role
            self.roles.setCurrentRow(list(ROLES).index(key));self.role_changed();self.mark()
    def rename_theme(self,text):self.theme.name=text;self.mark()
    def ask_discard(self):
        # Switching is already the user's decision. Flush silently; a failure
        # raises and keeps this project open instead of discarding edited data.
        if self.dirty:self.save()
        return True
    def closeEvent(self,event):
        event.ignore()
        if self.worker and self.worker.isRunning():event.ignore();return
        try:
            if self.ask_discard():self.autosave_timer.stop();self.stop_play();event.accept()
        except Exception as exc:
            QMessageBox.warning(self,'保存失败，窗口已保留',str(exc))
    def new_project(self):
        if self.ask_discard():self.load_theme(Theme(canvas_size=STANDARD_SIZE))
    def load_theme(self,theme,path=None):
        self.autosave_timer.stop();self.autosave_path=None
        self.stop_play();self.theme=theme;self.project_path=path;self.history=[];self.dirty=False
        self.library_path=None;self.library.setCurrentIndex(0)
        self.name.setText(theme.name);self.roles.setCurrentRow(0);self.role_changed();self.update_roles()
        self.setWindowTitle(f'{theme.name} · Custom Cursor Studio')
        self.sync_output_size()
    def sync_output_size(self):
        sizes={r.size or self.theme.canvas_size for r in self.theme.roles.values()}
        value=next(iter(sizes)) if len(sizes)==1 else None
        index=self.output_size.findData(value)
        if index<0:self.output_size.addItem(f'{value} px',value);index=self.output_size.count()-1
        self.output_size.setCurrentIndex(index)
    def change_theme_size(self):
        size=self.output_size.currentData()
        if size is None:return
        selected=resize_theme(self.theme,size)
        self.stop_play();self.theme=selected;self.history=[];self.role_changed();self.mark()
        self.status.setText(f'整套15种状态已改为 {size} px · 热点已按比例调整 · 点击“启用当前主题”后改变系统指针')
    def confirm_apply(self):
        problems=validate_theme(self.theme)
        if problems:raise ValueError('\n'.join(problems))
        size=self.theme.roles['Arrow'].size or self.theme.canvas_size
        if QMessageBox.question(self,'确认启用系统指针',f'启用“{self.theme.name}”的全部15种状态？\n系统基础尺寸：{size} px；使用当前编辑后的图像、热点和动画。\n先备份当前方案，失败尝试回滚。无需先保存或导出。',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        self.stop_play();self.apply_button.setEnabled(False)
        try:
            backup=apply_theme(copy.deepcopy(self.theme))
        finally:self.apply_button.setEnabled(True)
        self.status.setText(f'已启用：{self.theme.name} · {size} px · 备份：{backup}')
        QMessageBox.information(self,'启用完成',f'当前编辑的主题已启用。\n基础尺寸：{size} px\n备份：{backup}\n取消自定义请运行根目录“取消自定义光标.cmd”。')
    def open_project(self):
        if not self.ask_discard():return
        path,_=QFileDialog.getOpenFileName(self,'打开工程','','Cursor Studio 工程 (*.json)')
        if path:self.open_source(Path(path),check_discard=False)
    def refresh_library(self):
        selected=self.library_path
        entries=discover_themes(ROOT)
        self.library.blockSignals(True);self.library.clear();self.library.addItem('选择主题文件夹…',None)
        for entry in entries:self.library.addItem(f'{entry.folder.name} · {entry.kind}',str(entry.folder))
        index=self.library.findData(selected) if selected else 0
        self.library.setCurrentIndex(max(0,index));self.library.blockSignals(False)
        self.status.setText(f'已发现 {len(entries)} 个本地主题 · 新增文件夹后点击刷新，也可导入外部文件夹')
    def open_library_selection(self):
        path=self.library.currentData()
        if path:self.open_source(Path(path))
    def open_startup(self,path=None):
        if path is not None:opened=self.open_source(Path(path))
        elif self.library.count()>1:
            self.library.setCurrentIndex(1);self.open_library_selection();opened=True
        else:
            self.status.setText('新建空白工程 · 32 px（标准版） · 修改会自动保存');return
        if opened:
            # Each launch begins with a real standard-size rendering, not just
            # a changed combo label. Do not overwrite source projects on launch.
            self.theme=resize_theme(self.theme,STANDARD_SIZE);self.history=[];self.role_changed()
            self.status.setText('已载入主题 · 32 px（标准版） · 修改会自动保存，可随时切换整套尺寸')
        return opened
    def folder_dialog(self):
        path=QFileDialog.getExistingDirectory(self,'选择主题或素材文件夹',str(ROOT))
        if path:self.open_source(Path(path))
    def open_source(self,path,check_discard=True):
        def restore_selection():self.library.setCurrentIndex(max(0,self.library.findData(self.library_path)))
        if check_discard:
            try:
                if not self.ask_discard():restore_selection();return False
            except Exception:
                restore_selection();raise
        try:theme,project=open_theme_source(path)
        except Exception:
            restore_selection();raise
        self.load_theme(theme,project)
        if project is None:self.mark()
        missing=sum(not role.frames for role in theme.roles.values())
        suffix=f' · 缺少 {missing} 种状态，请补齐后导出' if missing else ' · 15 种状态完整'
        self.status.setText(('已打开工程：' if project else '已导入主题（保存为独立工程）：')+str(path)+suffix)
        folder=project.parent.parent if project and project.parent.name=='project' else (project.parent if project else Path(path))
        self.library_path=str(folder.resolve());index=self.library.findData(self.library_path)
        self.library.setCurrentIndex(max(0,index))
        return True
    def protect(self,path):
        p=Path(path).resolve()
        for root in [EDITOR_ROOT/'references',EDITOR_ROOT/'archives']:
            if p.is_relative_to(root.resolve()):raise ValueError('参考主题目录只读，请选择自己的工程或导出目录')
        baseline=EDITOR_ROOT/'evidence/reference-locations.json'
        if baseline.is_file():
            originals=json.loads(baseline.read_text('utf-8'))
            if p in {(ROOT/relative).resolve() for relative in originals.values()}:
                raise ValueError('原始参考资源只读，请保存为独立工程或文件')
        if p in {(ROOT/'吹泡泡Dva.zip').resolve(),(ROOT/'月神天使.zip').resolve()}:
            raise ValueError('不能覆盖原始主题压缩包')
    def overwrite(self,path):
        self.protect(path)
        if not Path(path).exists():return False
        if QMessageBox.question(self,'覆盖文件',f'目标已存在：\n{path}\n确认替换？',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return None
        return True
    def save(self):
        self.autosave_timer.stop()
        path=self.project_path or self.autosave_path
        if path is None:
            self.autosave_path=reserve_project_path(ROOT,self.theme.name)
            path=self.autosave_path
        self.protect(path)
        save_project(self.theme,path,overwrite=Path(path).exists())
        self.project_path=Path(path);self.dirty=False
        self.setWindowTitle(f'{self.theme.name} · Custom Cursor Studio')
        self.status.setText(f'已自动保存：{path}')
        return True
    def save_as(self):
        path=self.project_path
        text,_=QFileDialog.getSaveFileName(self,'另存工程（建议单独文件夹）',str(path or ROOT/'projects'/'我的主题'/'theme.json'),'工程 (*.json)')
        if not text:return False
        path=Path(text)
        if path.suffix.lower()!='.json':path=path.with_suffix('.json')
        overwrite=self.overwrite(path)
        if overwrite is None:return False
        self.protect(path);save_project(self.theme,path,overwrite=overwrite);self.project_path=path;self.dirty=False
        self.autosave_timer.stop();self.autosave_path=None
        self.setWindowTitle(f'{self.theme.name} · Custom Cursor Studio');self.status.setText(f'已保存工程和本地素材：{path}');return True
    def reference_dialog(self):
        path,_=QFileDialog.getOpenFileName(self,'选择参考 INF 或 ZIP',str(ROOT),'参考主题 (*.inf *.zip)')
        if path:self.open_reference(Path(path))
    def open_reference(self,path):
        return self.open_source(Path(path))
    def set_frames(self,frames,append=False):
        self.snapshot()
        if append:self.role.frames.extend(frames)
        else:
            edge=max(max(f.image.size) for f in frames)
            self.theme.roles[self.key]=Role(frames=frames,size=min(edge,256))
        self.frame_index=0;self.role_changed();self.mark()
    def import_files(self,append=False):
        paths,_=QFileDialog.getOpenFileNames(self,'导入图片 / 动画（多选为图片序列，按文件名排序）','',FILTER)
        if paths:
            frames=[]
            pixels=sum(f.image.width*f.image.height for f in self.role.frames) if append else 0
            existing=len(self.role.frames) if append else 0
            for path in sorted(paths,key=lambda s:s.casefold()):
                incoming=import_media(path)
                pixels+=sum(f.image.width*f.image.height for f in incoming)
                if pixels>16_777_216 or len(frames)+len(incoming)+existing>256:
                    raise ValueError('累计素材超过 256 帧或 16M 像素限制')
                frames.extend(incoming)
            if len(frames)+ (len(self.role.frames) if append else 0)>256:raise ValueError('最多导入 256 帧')
            if sum(f.image.width*f.image.height for f in frames)>16_777_216:raise ValueError('素材总像素超过 16M，请先缩小图片')
            self.set_frames(frames,append);self.status.setText(f'已导入 {len(frames)} 帧 · 请校准热点')
    def blank_frame(self):
        size=self.role.size or self.theme.canvas_size
        self.set_frames([Frame(Image.new('RGBA',(size,size)))],append=True)
    def update_roles(self):
        done=0
        for i,(key,name) in enumerate(ROLES.items()):
            r=self.theme.roles[key];item=self.roles.item(i)
            if r.frames:
                done+=1;item.setIcon(QIcon(pixmap(r.frames[0].image)))
                item.setText(f'{name} · {"动态" if len(r.frames)>1 else "静态"}')
            else:item.setIcon(QIcon());item.setText(f'{name}   待补齐')
        self.role_heading.setText(f'系统指针  ·  {done} / 15')
        self.sync_output_size()
    def role_changed(self,*args):
        self.stop_play();self.frame_index=min(self.frame_index,max(0,len(self.role.frames)-1));self.loading=True
        self.current_title.setText(f'{ROLES[self.key]}  ·  {self.key}')
        index=self.size.findData(self.role.size)
        if index<0:self.size.addItem(f'{self.role.size} × {self.role.size}',self.role.size);index=self.size.count()-1
        self.size.setCurrentIndex(index);self.scale.setValue(0 if self.role.scale is None else self.role.scale*100)
        self.interpolation.setCurrentIndex(0 if self.role.interpolation=='nearest' else 1)
        self.fit.setCurrentIndex(0 if self.role.fit=='contain' else 1)
        self.align.setCurrentIndex(['center','top-left','top-right','bottom-left','bottom-right'].index(self.role.alignment))
        self.opacity.setValue(round(self.role.opacity*100));self.loading=False
        self.refresh_frames();self.refresh_render();self.update_roles()
    def refresh_frames(self):
        self.loading=True;self.frames.clear()
        for i,f in enumerate(self.role.frames):
            item=QListWidgetItem(QIcon(pixmap(f.image)),f'{i+1:02d}    {f.duration_ms:g} ms');self.frames.addItem(item)
        self.frames.setCurrentRow(self.frame_index);self.loading=False
    def refresh_render(self):
        try:
            self.rendered=render_frames(self.theme,self.role)
            self.status.setText(f'{ROLES[self.key]} · {len(self.role.frames)} 帧 · 仅本地编辑，未改变系统指针')
        except ValueError as exc:
            self.rendered=[];self.status.setText(f'校验：{exc}，请调整右侧属性')
        self.show_frame()
    def show_frame(self):
        frame=self.rendered[self.frame_index] if self.frame_index<len(self.rendered) else None
        self.preview.set_frame(frame);self.scene.set_frame(frame)
        self.loading=True
        if self.role.frames:
            raw=self.role.frames[self.frame_index];self.hot_x.setValue(raw.hotspot[0]);self.hot_y.setValue(raw.hotspot[1]);self.duration.setValue(raw.duration_ms)
            self.source_info.setText(f'源素材 {raw.image.width} × {raw.image.height} px\n输出 {self.role.size or self.theme.canvas_size} px · {len(self.role.frames)} 帧')
            self.frame_label.setText(f'{self.frame_index+1} / {len(self.role.frames)}')
            self.frames.setCurrentRow(self.frame_index)
        else:self.frame_label.setText('尚未导入');self.source_info.setText('导入图片或新建透明帧')
        self.loading=False
    def select_frame(self,index):
        if self.loading or not self.role.frames:return
        self.stop_play();self.frame_index=index%len(self.role.frames);self.show_frame()
    def properties_changed(self,*args):
        if self.loading:return
        self.stop_play();self.snapshot();r=self.role
        old_size=r.size or self.theme.canvas_size
        r.size=self.size.currentData();new_size=r.size or self.theme.canvas_size
        if new_size!=old_size:
            for frame in r.frames:frame.hotspot=tuple(min(new_size-1,round(v*new_size/old_size)) for v in frame.hotspot)
        r.scale=self.scale.value()/100 if self.scale.value() else None
        r.interpolation=['nearest','smooth'][self.interpolation.currentIndex()]
        r.fit=['contain','cover'][self.fit.currentIndex()];r.alignment=['center','top-left','top-right','bottom-left','bottom-right'][self.align.currentIndex()]
        r.opacity=self.opacity.value()/100;self.refresh_render();self.sync_output_size();self.mark()
    def set_hotspot(self,x,y):
        if not self.role.frames:return
        self.role.frames[self.frame_index].hotspot=(x,y);self.refresh_render();self.mark()
    def hotspot_input(self,*args):
        if not self.loading:self.set_hotspot(self.hot_x.value(),self.hot_y.value())
    def hotspot_all(self):
        if self.role.frames:
            self.snapshot();spot=self.role.frames[self.frame_index].hotspot
            for f in self.role.frames:f.hotspot=spot
            self.refresh_render();self.mark()
    def duration_changed(self,value):
        if not self.loading and self.role.frames:
            self.stop_play();self.role.frames[self.frame_index].duration_ms=value;self.refresh_frames();self.refresh_render();self.mark()
    def duration_all(self):
        self.snapshot()
        for f in self.role.frames:f.duration_ms=self.duration.value()
        self.refresh_frames();self.refresh_render();self.mark()
    def move_frame(self,direction):
        i=self.frame_index;j=i+direction
        if 0<=j<len(self.role.frames):
            self.stop_play();self.snapshot();self.role.frames[i],self.role.frames[j]=self.role.frames[j],self.role.frames[i]
            self.frame_index=j;self.refresh_frames();self.refresh_render();self.mark()
    def delete_frame(self):
        if self.role.frames:
            self.stop_play();self.snapshot();self.role.frames.pop(self.frame_index);self.frame_index=max(0,self.frame_index-1);self.role_changed();self.mark()
    def toggle_play(self):
        if self.playing:self.stop_play();return
        if len(self.rendered)<2:return
        self.playing=True;self.play.setText('暂停')
        self.deadline=time.monotonic()+self.rendered[self.frame_index].duration_ms/1000
        self.timer.start(max(1,round(self.rendered[self.frame_index].duration_ms)))
    def stop_play(self):
        self.timer.stop();self.playing=False
        if hasattr(self,'play'):self.play.setText('播放')
    def advance(self):
        if not self.playing or not self.rendered:return
        now=time.monotonic()
        # Precise single-shot deadlines preserve individual delays without accumulated drift.
        while now>=self.deadline:
            self.frame_index=(self.frame_index+1)%len(self.rendered)
            self.deadline+=self.rendered[self.frame_index].duration_ms/1000
        self.show_frame();self.timer.start(max(1,round((self.deadline-now)*1000)))
    def background_changed(self,value):self.preview.background=value;self.preview.update()
    def zoom_changed(self,index):self.preview.zoom=[1,2,4,8][index];self.preview.update()
    def tool_changed(self,text):
        self.preview.tool=text
        if text!='热点':self.status.setText('画笔会将当前角色效果合并到画布，可撤销；透明帧可直接绘制')
    def pick_color(self):
        color=QColorDialog.getColor(self.brush_color,self,'画笔颜色',QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():self.brush_color=color
    def start_stroke(self):
        self.stop_play();self.snapshot()
        if self.preview.tool!='热点' and self.rendered:
            # Bake ALL frames together so transforms cannot change the appearance of other frames.
            self.role.frames=copy.deepcopy(self.rendered);self.role.scale=1.;self.role.opacity=1.;self.role.fit='contain';self.role.alignment='center'
            self.role_changed()
    def paint_pixel(self,x,y,erase):
        if self.role.frames:
            f=self.role.frames[self.frame_index]
            if 0<=x<f.image.width and 0<=y<f.image.height:
                f.image.putpixel((x,y),(0,0,0,0) if erase else self.brush_color.getRgb());self.refresh_render();self.mark()
    def copy_to_missing(self):
        if not self.role.frames:raise ValueError('当前角色没有素材')
        for key,r in self.theme.roles.items():
            if not r.frames:self.theme.roles[key]=copy.deepcopy(self.role)
        self.update_roles();self.mark()
    def confirm_copy(self):
        if QMessageBox.question(self,'明确选择默认替代',f'将“{ROLES[self.key]}”的素材、帧、热点和尺寸复制到所有缺失角色？\n不会替换已完成角色。')==QMessageBox.StandardButton.Yes:self.copy_to_missing()
    def metadata(self):
        dialog=QDialog(self);dialog.setWindowTitle('主题设置');form=QFormLayout(dialog)
        author=QLineEdit(self.theme.author);desc=QTextEdit(self.theme.description);desc.setMaximumHeight(110)
        size=QComboBox()
        for n in [32,48,64,96,128,256]:size.addItem(str(n),n)
        if size.findData(self.theme.canvas_size)<0:size.addItem(str(self.theme.canvas_size),self.theme.canvas_size)
        size.setCurrentIndex(size.findData(self.theme.canvas_size));scale=QDoubleSpinBox();scale.setRange(1,800);scale.setValue(self.theme.scale*100);scale.setSuffix(' %')
        form.addRow('作者',author);form.addRow('描述',desc);form.addRow('整套画布',size);form.addRow('整套素材缩放',scale)
        form.addRow(QLabel('作用于全部15种状态，覆盖独立尺寸与缩放；热点随画布尺寸调整。'))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        if dialog.exec():
            selected=resize_theme(self.theme,size.currentData())
            selected.author=author.text();selected.description=desc.toPlainText();selected.scale=scale.value()/100
            for role in selected.roles.values():role.scale=None
            self.theme=selected;self.history=[];self.role_changed();self.mark()
    def export_current(self):
        from cursor_studio.io.cur import encode_cur,decode_cur
        from cursor_studio.io.ani import encode_ani,decode_ani
        from cursor_studio.windows.native import validate_cursor_file
        frames=render_frames(self.theme,self.role)
        if not frames:raise ValueError('请先导入素材')
        animated=len(frames)>1;ext='.ani' if animated else '.cur'
        path,_=QFileDialog.getSaveFileName(self,'导出当前角色',str(ROOT/'exports'/(self.key+ext)),f'Windows 光标 (*{ext})')
        if not path:return
        path=Path(path).with_suffix(ext);overwrite=self.overwrite(path)
        if overwrite is None:return
        data=(encode_ani if animated else encode_cur)(frames);(decode_ani if animated else decode_cur)(data)
        with tempfile.TemporaryDirectory() as tmp:
            test=Path(tmp)/('test'+ext);test.write_bytes(data)
            if os.name=='nt':validate_cursor_file(test)
        atomic_write(path,data,overwrite);self.status.setText(f'已导出并验证：{path}'+(' · ANI 时长量化为 1/60 秒' if animated else ''))
    def export_zip(self):
        problems=validate_theme(self.theme)
        if problems:raise ValueError('\n'.join(problems))
        path,_=QFileDialog.getSaveFileName(self,'导出完整主题 ZIP',str(ROOT/'exports'/'我的主题.zip'),'主题 ZIP (*.zip)')
        if not path:return
        path=Path(path).with_suffix('.zip');overwrite=self.overwrite(path)
        if overwrite is None:return
        self.stop_play();self.progress=QProgressDialog('正在生成 15 个光标、验证 Windows 加载并打包…',None,0,0,self)
        self.progress.setWindowModality(Qt.WindowModality.ApplicationModal);self.progress.setMinimumDuration(0);self.progress.show()
        self.worker=ExportWorker(self.theme,path,overwrite)
        self.worker.succeeded.connect(self.export_done);self.worker.failed.connect(self.export_failed);self.worker.start()
    def export_done(self,path):
        self.progress.close();self.status.setText(f'完整主题已导出：{path}')
        QMessageBox.information(self,'导出完成',f'15 个光标、AutoSetup.inf 和安装教程已打包：\n{path}\n\n未安装或切换系统方案。ANI 时长按 1/60 秒量化。')
    def export_failed(self,message):self.progress.close();QMessageBox.warning(self,'导出失败',message)
    def backups(self):
        from cursor_studio.windows.schemes import backup_current,list_backups,restore_backup
        directory=Path(os.environ.get('LOCALAPPDATA',str(ROOT)))/'CustomCursorStudio'/'backups'
        dialog=QDialog(self);dialog.setWindowTitle('当前用户指针方案 · 备份与恢复');dialog.resize(560,330);layout=QVBoxLayout(dialog)
        label=QLabel('备份只读取当前用户设置。恢复会覆盖指针设置，并自动另存恢复前的状态。');label.setWordWrap(True);layout.addWidget(label)
        listing=QListWidget();layout.addWidget(listing)
        def reload():
            listing.clear()
            for path in list_backups(directory):
                item=QListWidgetItem(path.name);item.setData(Qt.ItemDataRole.UserRole,str(path));listing.addItem(item)
        def backup():
            path=backup_current(directory);reload();self.status.setText(f'已备份：{path}')
        def restore():
            item=listing.currentItem()
            if not item:raise ValueError('请选择一条备份记录')
            if QMessageBox.question(dialog,'确认恢复系统指针',f'将恢复 {item.text()} 的全部指针设置。\n确认立即修改当前用户的系统指针？',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
                restore_backup(Path(item.data(Qt.ItemDataRole.UserRole)));reload();QMessageBox.information(dialog,'恢复完成','已恢复并刷新系统指针设置')
        row=QHBoxLayout();row.addWidget(self.button('备份当前方案',backup));row.addWidget(self.button('恢复选中备份…',restore));layout.addLayout(row);reload();dialog.exec()
