from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QCursor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

def pixmap(image):
    image = image.convert('RGBA')
    raw = image.tobytes()
    return QPixmap.fromImage(QImage(raw, image.width, image.height, image.width*4,
                                    QImage.Format.Format_RGBA8888).copy())

class Preview(QWidget):
    hotspotChanged = Signal(int, int)
    paintPixel = Signal(int, int, bool)
    strokeStarted = Signal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(250, 250)
        self.frame = None
        self.zoom = 4
        self.background = '棋盘'
        self.tool = '热点'
        self.rect = QRectF()
        self.setMouseTracking(True)
        self.setAccessibleName('光标编辑画布，可拖动热点')

    def set_frame(self, frame):
        self.frame = frame
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.contentsRect(), QColor('#f0f2f7'))
        if self.frame is None:
            p.setPen(QColor('#6b7280'))
            p.drawText(self.contentsRect(), Qt.AlignmentFlag.AlignCenter,
                       '从一张图片开始\n\n导入素材，或打开参考主题\n在这里调整画面与点击热点')
            return
        im = self.frame.image
        zoom = min(self.zoom, (self.width()-40)/im.width, (self.height()-60)/im.height)
        w, h = im.width*zoom, im.height*zoom
        self.rect = QRectF((self.width()-w)/2, (self.height()-h)/2-8, w, h)
        bg = '#ffffff' if self.background == '浅色' else '#232733'
        p.fillRect(self.rect, QColor(bg))
        if self.background == '棋盘':
            p.save(); p.setClipRect(self.rect)
            for y in range(0, int(h)+12, 12):
                for x in range(0, int(w)+12, 12):
                    p.fillRect(QRectF(self.rect.x()+x,self.rect.y()+y,12,12),
                               QColor('#e1e4ec' if (x//12+y//12)%2 else '#ffffff'))
            p.restore()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.drawPixmap(self.rect, pixmap(im), QRectF(0,0,im.width,im.height))
        p.setPen(QPen(QColor('#c5cad7'),1)); p.drawRect(self.rect)
        hx, hy = self.frame.hotspot
        x, y = self.rect.x()+(hx+.5)*zoom, self.rect.y()+(hy+.5)*zoom
        for color,width in [('#ffffff',3),('#e4476b',1)]:
            p.setPen(QPen(QColor(color),width))
            p.drawLine(int(x-10),int(y),int(x+10),int(y))
            p.drawLine(int(x),int(y-10),int(x),int(y+10))
        p.setPen(QColor('#737b8c'))
        p.drawText(QRectF(0,self.height()-27,self.width(),24), Qt.AlignmentFlag.AlignCenter,
                   f'{im.width} × {im.height} px   ·   热点 {hx}, {hy}   ·   显示 {zoom*100:.0f}%')

    def _position(self,event):
        if self.frame and self.rect.contains(event.position()):
            x=int((event.position().x()-self.rect.x())/self.rect.width()*self.frame.image.width)
            y=int((event.position().y()-self.rect.y())/self.rect.height()*self.frame.image.height)
            if self.tool == '热点': self.hotspotChanged.emit(x,y)
            else: self.paintPixel.emit(x,y,self.tool=='橡皮')

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.strokeStarted.emit(); self._position(event)

    def mouseMoveEvent(self,event):
        if event.buttons() & Qt.MouseButton.LeftButton: self._position(event)

class Scene(QWidget):
    """A real Qt cursor restricted to this widget, with no global cursor changes."""
    def __init__(self):
        super().__init__(); self.setMinimumHeight(125)
        self.setMouseTracking(True)
        self.setToolTip('把鼠标移到此区域，体验实际大小和热点；只影响本窗口')

    def set_frame(self,frame):
        if frame:
            self.setCursor(QCursor(pixmap(frame.image),*frame.hotspot))
        else: self.unsetCursor()

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#ffffff'))
        p.drawRoundedRect(self.contentsRect().adjusted(1,1,-1,-1),12,12)
        p.setPen(QColor('#788196')); p.drawText(18,25,'场景试用 · 将鼠标移入这里')
        p.setBrush(QColor('#edeafd'));p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(18,44,104,34,7,7)
        p.setPen(QColor('#6854ca'));p.drawText(36,66,'示例按钮')
        p.setPen(QColor('#9ba4b5'));p.drawRect(142,44,max(30,self.width()-164),34)
        p.setPen(QColor('#6c7486'));p.drawText(152,66,'文本输入区域 |')
        p.drawText(18,106,'链接文字    ┃    窗口边缘    ┃    拖拽区域')
