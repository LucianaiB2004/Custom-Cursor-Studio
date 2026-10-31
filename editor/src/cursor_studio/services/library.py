"""Discover local theme folders and import them without executing package contents."""
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from cursor_studio.models import Theme, Role, ROLES
from cursor_studio.io.importers import import_media, safe_extract_reference
from cursor_studio.io.reference import import_reference
from .project import load_project
from .render import validate_role

MEDIA = {'.cur','.ani','.png','.jpg','.jpeg','.gif','.apng','.svg'}
ALIASES = {name.casefold().replace(' ',''): key for key, name in ROLES.items()}
ALIASES.update({key.casefold(): key for key in ROLES})
ALIASES.update({'沿对角线调整大小1':'SizeNWSE','沿对角线调整大小2':'SizeNESW'})
IGNORED = {'editor','skills','cursor-theme-creator','archives','references','src','tests','scripts','docs','evidence','build','dist'}

@dataclass(frozen=True)
class ThemeEntry:
    folder: Path
    kind: str

def _children(folder):
    entries = []
    for entry in folder.iterdir():
        if len(entries) >= 2048:
            raise ValueError('主题目录条目超过2048，请拆分文件夹')
        entries.append(entry)
    return entries

def _kind(folder):
    if (folder/'project/theme.json').is_file() or (folder/'theme.json').is_file(): return '工程'
    if (folder/'theme-map.json').is_file(): return '映射主题'
    entries = _children(folder)
    if any(p.suffix.casefold()=='.inf' for p in entries if p.is_file()): return 'INF主题'
    if (folder/'Windows主题').is_dir(): return '资源主题'
    if any(p.stem.casefold().replace(' ','') in ALIASES and
           (p.is_dir() or p.suffix.casefold() in MEDIA) for p in entries): return '素材主题'
    return None

def discover_themes(root):
    root = Path(root).resolve()
    result = []
    for folder in _children(root):
        if folder.name.startswith('.') or folder.name.casefold() in IGNORED or not folder.is_dir(): continue
        # No recursion into user-supplied junctions or symlinks outside the library.
        if folder.is_symlink() or folder.resolve().parent != root: continue
        candidates = _children(folder) if folder.name=='projects' else [folder]
        for candidate in candidates:
            if not candidate.is_dir() or candidate.is_symlink() or not candidate.resolve().is_relative_to(root): continue
            try: kind = _kind(candidate)
            except (OSError,ValueError): continue
            if kind: result.append(ThemeEntry(candidate.resolve(),kind))
    return sorted(result,key=lambda item:item.folder.name.casefold())

def _safe_file(folder, relative):
    if not isinstance(relative,str) or not relative or '\\' in relative or ':' in relative or PureWindowsPath(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('主题素材路径必须是文件夹内的安全相对路径')
    target = (folder/relative).resolve()
    if not target.is_relative_to(folder) or not target.is_file(): raise ValueError('主题素材路径不存在或超出文件夹')
    if target.suffix.casefold() not in MEDIA: raise ValueError('主题包含不支持的素材格式')
    return target

def _from_mapping(folder, mapping, name):
    if not isinstance(name,str) or not name or len(name)>128: raise ValueError('主题名称无效')
    if not isinstance(mapping,dict) or not mapping or set(mapping)-set(ROLES): raise ValueError('主题角色映射无效或含未知角色')
    theme = Theme(name=name)
    total = 0
    for key, paths in mapping.items():
        if not isinstance(paths,list): paths = [paths]
        frames = []; role_pixels = 0
        for relative in paths:
            incoming = import_media(_safe_file(folder,relative))
            frames.extend(incoming)
            pixels = sum(f.image.width*f.image.height for f in incoming)
            total += pixels; role_pixels += pixels
            if len(frames)>256 or role_pixels>16*1024*1024 or total>64*1024*1024: raise ValueError('主题超过256帧/角色、16M像素/角色或64M总像素限制')
        if not frames: raise ValueError(f'{key} 没有可导入的素材帧')
        theme.roles[key] = Role(frames=frames,size=min(256,max(max(f.image.size) for f in frames)))
    return theme

def open_theme_source(source):
    """Return (theme, existing_project_path_or_None). Imports always save as new projects."""
    theme, project = _read_theme_source(source)
    for role in theme.roles.values(): validate_role(theme,role)
    if sum(f.image.width*f.image.height for role in theme.roles.values() for f in role.frames)>64*1024*1024:
        raise ValueError('主题素材超过64M总像素限制')
    return theme,project

def _read_theme_source(source):
    source = Path(source).resolve()
    if source.is_file():
        ext = source.suffix.casefold()
        if ext=='.json' and source.name!='theme-map.json': return load_project(source),source
        if source.name=='theme-map.json': return open_theme_source(source.parent)
        if ext=='.inf': return import_reference(source),None
        if ext=='.zip':
            with tempfile.TemporaryDirectory(prefix='cursor-library-') as tmp:
                safe_extract_reference(source,Path(tmp))
                infs = list(Path(tmp).rglob('*.inf'))
                if len(infs)!=1: raise ValueError('参考ZIP必须包含且只包含一份INF映射')
                return import_reference(infs[0]),None
        raise ValueError('请选择工程JSON、INF、ZIP或主题文件夹；单张素材请使用“导入素材”')
    if not source.is_dir(): raise ValueError('无法识别主题：文件夹不存在')
    for relative in ['project/theme.json','theme.json']:
        path = source/relative
        if path.is_file(): return load_project(path),path
    manifest = source/'theme-map.json'
    if manifest.is_file():
        if manifest.stat().st_size>1024*1024: raise ValueError('主题映射文件超过1 MiB')
        doc = json.loads(manifest.read_text('utf-8-sig'))
        if not isinstance(doc,dict): raise ValueError('主题映射必须是JSON对象')
        return _from_mapping(source,doc.get('roles'),doc.get('name',source.name)),None
    entries = _children(source)
    if any(p.suffix.casefold()=='.inf' for p in entries if p.is_file()): return import_reference(source),None
    if (source/'Windows主题').is_dir(): return open_theme_source(source/'Windows主题')
    mapping = {}
    for path in sorted(entries,key=lambda p:p.name.casefold()):
        key = ALIASES.get(path.stem.casefold().replace(' ',''))
        if not key: continue
        if path.is_dir():
            paths = [p.relative_to(source).as_posix() for p in sorted(_children(path)) if p.is_file() and p.suffix.casefold() in MEDIA]
        elif path.suffix.casefold() in MEDIA: paths = [path.name]
        else: continue
        if key in mapping: raise ValueError(f'{key} 存在重复素材映射，请保留一个文件或一个帧序列文件夹')
        mapping[key] = paths
    if not mapping: raise ValueError('无法识别主题：需要theme.json、theme-map.json、INF或按Arrow/正常选择等状态命名的素材')
    return _from_mapping(source,mapping,source.name),None
