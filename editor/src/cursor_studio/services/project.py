"""Content-addressed assets and atomic JSON project commits."""
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path, PureWindowsPath
from PIL import Image
from cursor_studio.models import Frame, Role, Theme, ROLES
from .render import number, validate_role, MAX_PIXELS, MAX_FRAMES

def atomic_write(path, data, overwrite=False):
    path=Path(path)
    if path.exists() and not overwrite:raise FileExistsError(f'文件已存在：{path}')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.cursor-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        if overwrite:os.replace(name,path)
        else:
            # Windows rename fails if the destination exists; hard-link gives the same
            # no-clobber guarantee on POSIX without a check-then-replace race.
            if os.name=='nt':os.rename(name,path)
            else:os.link(name,path);os.unlink(name)
    finally:
        if os.path.exists(name):os.unlink(name)

def _text(value,label,limit):
    if not isinstance(value,str) or len(value)>limit:raise ValueError(f'{label}格式错误或过长')
    return value

def _validate(theme):
    _text(theme.name,'主题名',128);_text(theme.author,'作者',256);_text(theme.description,'描述',10000)
    number(theme.canvas_size,1,256,'画布尺寸',True);number(theme.scale,.01,8,'缩放')
    if set(theme.roles)!=set(ROLES):raise ValueError('工程必须包含全部 15 种角色键')
    pixels=0;rendered_pixels=0
    for role in theme.roles.values():
        size,_=validate_role(theme,role)
        rendered_pixels+=size*size*len(role.frames)
        pixels+=sum(f.image.width*f.image.height for f in role.frames)
    if max(pixels,rendered_pixels)>MAX_PIXELS*4:raise ValueError('工程总素材或输出像素量过大')

def save_project(theme,path,overwrite=False):
    path=Path(path).resolve()
    if path.exists() and not overwrite:raise FileExistsError(f'工程已存在：{path}')
    _validate(theme)
    doc={'format':'custom-cursor-studio','version':1,'name':theme.name,'author':theme.author,'description':theme.description,'canvas_size':theme.canvas_size,'scale':theme.scale,'roles':{}}
    assets=path.parent/'assets'
    if assets.exists() and (assets.is_symlink() or assets.resolve().parent!=path.parent):raise ValueError('素材目录不能是外部链接')
    for key,role in theme.roles.items():
        record={k:getattr(role,k) for k in ('size','scale','interpolation','alignment','fit','opacity')};record['frames']=[]
        for frame in role.frames:
            buff=io.BytesIO();frame.image.convert('RGBA').save(buff,format='PNG');data=buff.getvalue()
            filename=hashlib.sha256(data).hexdigest()+'.png'; target=assets/filename
            if target.exists():
                if target.is_symlink() or target.read_bytes()!=data:raise ValueError('素材内容冲突或链接无效')
            else:atomic_write(target,data)
            record['frames'].append({'asset':f'assets/{filename}','hotspot':list(frame.hotspot),'duration_ms':frame.duration_ms})
        doc['roles'][key]=record
    atomic_write(path,json.dumps(doc,ensure_ascii=False,indent=2).encode('utf-8'),overwrite)
    return path

def _asset(root,relative):
    if not isinstance(relative,str) or not relative or '\\' in relative or ':' in relative or PureWindowsPath(relative).drive or Path(relative).is_absolute() or '..' in Path(relative).parts:raise ValueError('素材路径必须是工程内的安全相对路径')
    path=(root/relative).resolve()
    if not path.is_relative_to(root):raise ValueError('素材路径越过工程目录')
    if not path.is_file() or path.stat().st_size>64*1024*1024:raise ValueError('素材不存在或过大')
    return path

def load_project(path):
    path=Path(path).resolve()
    if path.stat().st_size>8*1024*1024:raise ValueError('工程描述过大')
    try:
        d=json.loads(path.read_text('utf-8'))
        if not isinstance(d,dict) or d.get('format')!='custom-cursor-studio' or d.get('version')!=1:raise ValueError('不支持的工程格式或版本')
        theme=Theme(name=d['name'],author=d['author'],description=d['description'],canvas_size=d['canvas_size'],scale=d['scale'])
        if not isinstance(d['roles'],dict) or set(d['roles'])!=set(ROLES):raise ValueError('角色映射不完整或包含未知角色')
        pixels=0
        for key,record in d['roles'].items():
            if not isinstance(record,dict) or not isinstance(record.get('frames'),list) or len(record['frames'])>MAX_FRAMES:raise ValueError('角色数据或帧数无效')
            role=Role(**{k:record[k] for k in ('size','scale','interpolation','alignment','fit','opacity')})
            for f in record['frames']:
                source=_asset(path.parent,f['asset'])
                with Image.open(source) as im:
                    if im.format!='PNG' or min(im.size)<1 or max(im.size)>4096:raise ValueError('工程素材必须是尺寸受限的 PNG')
                    pixels+=im.width*im.height
                    if pixels>MAX_PIXELS*4:raise ValueError('工程素材像素总量过大')
                    image=im.convert('RGBA')
                role.frames.append(Frame(image,tuple(f['hotspot']),f['duration_ms']))
            theme.roles[key]=role
        _validate(theme)
        return theme
    except (KeyError,TypeError,OverflowError,AttributeError) as exc:raise ValueError('工程描述字段缺失或格式错误') from exc
