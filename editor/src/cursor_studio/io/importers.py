"""Bounded offline imports. SVG is a deliberately small static safe subset."""
import io
import math
import re
import stat
import warnings
import zipfile
from pathlib import Path, PurePosixPath
from PIL import Image, UnidentifiedImageError
from defusedxml import ElementTree
from cursor_studio.models import Frame

MAX_FILE = 64 * 1024 * 1024
MAX_FRAMES = 256
MAX_PIXELS = 16 * 1024 * 1024
MAX_TOTAL_PIXELS = 32 * 1024 * 1024

def _svg(data: bytes) -> list[Frame]:
    if len(data) > 2 * 1024 * 1024:
        raise ValueError('SVG 超过 2 MB 限制')
    root = ElementTree.fromstring(data)
    allowed = {'svg', 'g', 'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon',
               'defs', 'linearGradient', 'radialGradient', 'stop', 'title', 'desc'}
    nodes = list(root.iter())
    if len(nodes) > 5000 or root.tag.split('}')[-1] != 'svg':
        raise ValueError('SVG 节点过多或根节点无效')
    for node in nodes:
        if node.tag.split('}')[-1] not in allowed:
            raise ValueError('SVG 仅支持静态形状和渐变；不支持脚本、动画、图片、文本或引用元素')
        for key, val in node.attrib.items():
            key = key.split('}')[-1].lower()
            if key.startswith('on') or key in {'href', 'src', 'style', 'base'}:
                raise ValueError('SVG 包含不允许的事件、外部引用或内联样式')
            if re.search(r'url\s*\(', val, re.I) and not re.fullmatch(r'url\(#[\w-]+\)', val):
                raise ValueError('SVG 外部资源被禁止')
            if len(val) > 100000:
                raise ValueError('SVG 属性过长')
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    renderer = QSvgRenderer(QByteArray(data))
    if not renderer.isValid():
        raise ValueError('SVG 无法栅格化')
    size = renderer.defaultSize()
    w, h = size.width(), size.height()
    if not 1 <= w <= 4096 or not 1 <= h <= 4096:
        raise ValueError('SVG 尺寸须在 1–4096 像素之间')
    factor = min(1, 256 / max(w, h))
    w, h = max(1, round(w*factor)), max(1, round(h*factor))
    image = QImage(w, h, QImage.Format.Format_RGBA8888)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    pixels = bytes(image.constBits())
    return [Frame(Image.frombytes('RGBA', (w, h), pixels, 'raw', 'RGBA', image.bytesPerLine()))]

def import_media(path: Path | str) -> list[Frame]:
    path = Path(path)
    if path.stat().st_size > MAX_FILE:
        raise ValueError('素材文件超过 64 MB 限制')
    ext = path.suffix.lower()
    try:
        if ext == '.cur':
            from .cur import decode_cur
            # CUR entries are alternate resolutions, never animation frames.
            choices = decode_cur(path.read_bytes())
            return [max(choices, key=lambda f: f.image.width * f.image.height)]
        if ext == '.ani':
            from .ani import decode_ani
            return decode_ani(path.read_bytes())
        if ext == '.svg':
            return _svg(path.read_bytes())
        if ext not in {'.png', '.jpg', '.jpeg', '.gif', '.apng'}:
            raise ValueError('不支持此格式。请选择 PNG、JPG、GIF、APNG、SVG、CUR 或 ANI')
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(path) as source:
                w, h = source.size
                count = getattr(source, 'n_frames', 1)
                if max(w,h) > 4096 or w*h > MAX_PIXELS or count > MAX_FRAMES or w*h*count > MAX_TOTAL_PIXELS:
                    raise ValueError('素材尺寸、帧数或解码内存超过安全限制（4096 边长 / 256 帧 / 总计 32M 像素）')
                frames = []
                start = 1 if source.info.get('default_image', False) else 0
                for i in range(start, count):
                    source.seek(i)
                    duration = float(source.info.get('duration', 100))
                    if not math.isfinite(duration) or not 0 < duration <= 60000:
                        raise ValueError(f'第 {i+1} 帧时长无效，须大于 0 且不超过 60000 ms')
                    frames.append(Frame(source.convert('RGBA').copy(), (0, 0), duration))
                if not frames:
                    raise ValueError('素材没有有效动画帧')
                return frames
    except (OSError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError,
            Image.DecompressionBombWarning, ElementTree.ParseError) as exc:
        raise ValueError(f'素材损坏或无法读取：{exc}') from exc

def safe_extract_reference(path: Path, destination: Path) -> Path:
    """Validate ALL entries before extraction. Only inert theme resources are allowed."""
    path, destination = Path(path), Path(destination)
    if path.stat().st_size > MAX_FILE:
        raise ValueError('主题 ZIP 超过 64 MB')
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 256 or sum(i.file_size for i in entries) > 128 * 1024 * 1024:
            raise ValueError('ZIP 文件数量或解压大小超出限制')
        checked = []
        names = set()
        for info in entries:
            name = info.filename
            if not (info.flag_bits & 0x800):
                try: name = name.encode('cp437').decode('gbk')
                except (UnicodeError, LookupError): pass
            parts = PurePosixPath(name).parts
            if '\\' in name or ':' in name or name.startswith('/') or '..' in parts or not parts:
                raise ValueError('ZIP 包含危险路径')
            if any(p.rstrip(' .') != p or p.split('.')[0].upper() in
                   {'CON','PRN','AUX','NUL', *[f'COM{i}' for i in range(10)], *[f'LPT{i}' for i in range(10)]} for p in parts):
                raise ValueError('ZIP 包含 Windows 特殊文件名')
            if stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1:
                raise ValueError('ZIP 不允许符号链接或加密条目')
            if info.file_size > MAX_FILE or (info.file_size > 1024*1024 and info.file_size/max(info.compress_size, 1) > 200):
                raise ValueError('ZIP 疑似压缩炸弹')
            key = name.rstrip('/').casefold()
            if key in names: raise ValueError('ZIP 包含重复路径')
            names.add(key)
            if not info.is_dir() and Path(name).suffix.lower() not in {'.cur', '.ani', '.inf', '.txt', '.md', '.svg', '.png', '.jpg'}:
                raise ValueError('主题包包含不支持的文件（不导入可执行文件或脚本）')
            target = destination.joinpath(*parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError('ZIP 路径越界')
            if target.exists(): raise ValueError('解压路径已存在，拒绝覆盖')
            checked.append((info, target))
        for info, target in checked:
            if info.is_dir(): target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as out:
                    out.write(archive.read(info))
    return destination
