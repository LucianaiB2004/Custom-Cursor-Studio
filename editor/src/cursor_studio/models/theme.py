from dataclasses import dataclass, field
from PIL import Image

ROLES = {
    "Arrow": "正常选择", "Help": "帮助选择", "AppStarting": "后台运行",
    "Wait": "忙", "Crosshair": "精确选择", "IBeam": "文本选择",
    "NWPen": "手写", "No": "不可用", "SizeNS": "垂直调整大小",
    "SizeWE": "水平调整大小", "SizeNWSE": "斜向调整 1", "SizeNESW": "斜向调整 2",
    "SizeAll": "移动", "UpArrow": "候选", "Hand": "链接选择",
}

@dataclass
class Frame:
    image: Image.Image
    hotspot: tuple[int, int] = (0, 0)
    duration_ms: float = 100.0

@dataclass
class Role:
    frames: list[Frame] = field(default_factory=list)
    size: int | None = None
    scale: float | None = None
    interpolation: str = "nearest"
    alignment: str = "center"
    fit: str = "contain"
    opacity: float = 1.0

@dataclass
class Theme:
    name: str = "未命名主题"
    author: str = ""
    description: str = ""
    canvas_size: int = 64
    scale: float = 1.0
    roles: dict[str, Role] = field(default_factory=lambda: {key: Role() for key in ROLES})
