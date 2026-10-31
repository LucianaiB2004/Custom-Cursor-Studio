"""Offline creation of a new complete cursor theme; never changes the desktop."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import zipfile
from PIL import Image,ImageColor

from cursor_studio.models import Theme,Role,Frame,ROLES
from cursor_studio.services.project import save_project,load_project
from cursor_studio.services.render import render_frames
from cursor_studio.services.sizing import resize_theme
from cursor_studio.services.export import export_theme
from cursor_studio.io.cur import decode_cur
from cursor_studio.io.ani import decode_ani

from cursor_studio.paths import EDITOR_ROOT,WORKSPACE_ROOT
from .glyphs import glyph


def _validate_name(name):
    if not isinstance(name,str) or not name.strip() or len(name)>128 or name.rstrip(' .')!=name:
        raise ValueError('主题名须为1～128字符，且不能以空格或句点结尾')
    if re.search(r'[<>:"/\\|?*\x00-\x1f]',name) or name in {'.','..'}:
        raise ValueError('主题名包含Windows文件名不允许的字符')
    if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(10)],*[f'LPT{i}' for i in range(10)]}:
        raise ValueError('主题名不能使用Windows保留设备名')


def _read_artwork(path):
    if not path.is_file() or path.stat().st_size>64*1024*1024:
        raise ValueError('素材不存在或超过64 MiB')
    with Image.open(path) as source:
        if source.format!='PNG' or getattr(source,'n_frames',1)!=1:
            raise ValueError('创作入口需要静态透明PNG母版；动画请在编辑器中逐帧配置')
        if min(source.size)<256 or max(source.size)>4096:
            raise ValueError('母版边长应为256～4096像素，建议使用1024以上的原生高清画稿')
        art=source.convert('RGBA')
    low,high=art.getextrema()[3]
    if low!=0 or high==0: raise ValueError('母版需要真实透明背景及可见角色，不能是全透明或不透明背景图片')
    return art


def _make_theme(name,art,color):
    cropped=art.crop(art.getchannel('A').getbbox())
    cropped.thumbnail((224,224),Image.Resampling.LANCZOS)
    theme=Theme(name=name,author='Custom Cursor Studio',canvas_size=96,
                description='由用户本地透明素材制作；保留256px编辑素材，输出64/96/128px。轻浮动与忙碌环为布局动画，不是自动表情逐帧生成。')
    for key in ROLES:
        count=8 if key in ('Wait','AppStarting') else (4 if key in ('Arrow','Hand') else 1)
        frames=[]
        for step in range(count):
            image=Image.new('RGBA',(256,256))
            dy=[0,-2,-4,-2][step%4] if count>1 else 0
            image.alpha_composite(cropped,(256-cropped.width-3,256-cropped.height-3+dy))
            symbol,hotspot=glyph(key,step,color)
            image.alpha_composite(symbol)
            duration=120 if count==8 else ([400,120,120,240][step] if count==4 else 100)
            frames.append(Frame(image,tuple(round(v*96/256) for v in hotspot),duration))
        theme.roles[key]=Role(frames=frames,size=96,interpolation='smooth')
    return theme


def _entrypoints(folder,output):
    if output.parent==WORKSPACE_ROOT:
        scripts=r'%~dp0..\editor\scripts'
    else:
        # External output can be used locally with the original workspace; ZIPs
        # remain self-contained installation packages. No imported code is run.
        scripts=str(EDITOR_ROOT/'scripts').replace('%','%%')
    commands={
        '应用主题.cmd':f'powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "{scripts}\\use-theme.ps1" -ThemeFolder "%~dp0."',
        '编辑主题.cmd':f'powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "{scripts}\\start-editor.ps1" -Project "%~dp0project\\theme.json"',
        '放大与导出.cmd':f'powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "{scripts}\\start-editor.ps1" -Module cursor_studio.ui.theme_launcher -Project "%~dp0project\\theme.json"',
    }
    for filename,command in commands.items():
        # Unicode filesystem paths are supplied through this tiny PowerShell
        # launcher encoded in the system's Windows batch code page (GBK here is
        # avoided by using UTF-8 with explicit chcp for portable Chinese paths).
        (folder/filename).write_bytes(('@echo off\r\nchcp 65001 >nul\r\n'+command+'\r\n').encode('utf-8'))


def create_theme_bundle(name,image,output,color='#f3a0b6',sizes=(64,96,128)):
    """Create a new directory atomically and return its validation report.

    Accepts a local static transparent PNG. Existing output paths are refused;
    input images, reference themes, registry and desktop cursors are untouched.
    """
    _validate_name(name)
    if not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',color):
        raise ValueError('功能颜色应为#RRGGBB格式')
    ImageColor.getrgb(color)
    sizes=tuple(sizes)
    if set(sizes)!={64,96,128} or len(sizes)!=3 or any(isinstance(size,bool) for size in sizes):
        raise ValueError('完整主题须提供64、96、128三个尺寸')
    image=Path(image).expanduser().resolve()
    output=Path(output).expanduser().resolve()
    if output.exists(): raise FileExistsError(f'输出已存在，拒绝覆盖：{output}')
    art=_read_artwork(image)
    theme=_make_theme(name,art,color)
    output.parent.mkdir(parents=True,exist_ok=True)
    native_checked=os.name=='nt'
    report={'name':name,'output':str(output),'sizes':list(sizes),'roles':len(ROLES),
            'master_size':list(art.size),'editable_source_size':256,'cursor_files':45,
            'project_roundtrip':True,'native_load_checked':native_checked,'system_changed':False}
    # The sibling staging directory stays on the same volume for final rename.
    with tempfile.TemporaryDirectory(prefix='.cursor-theme-',dir=output.parent) as temporary:
        stage=Path(temporary)/'theme'
        (stage/'artwork').mkdir(parents=True)
        shutil.copyfile(image,stage/'artwork/母版.png')
        save_project(theme,stage/'project/theme.json')
        reloaded=load_project(stage/'project/theme.json')
        for key in ROLES:
            if len(theme.roles[key].frames)!=len(reloaded.roles[key].frames):
                raise ValueError('工程保存重读后的帧数不一致')
            for original,reopened in zip(theme.roles[key].frames,reloaded.roles[key].frames):
                if (original.image.tobytes(),original.hotspot,original.duration_ms)!=(reopened.image.tobytes(),reopened.hotspot,reopened.duration_ms):
                    raise ValueError('工程保存重读结果不一致')
        manifest={'name':name,'default_size':96,'master':'artwork/母版.png','variants':{}}
        (stage/'exports').mkdir()
        for size in sizes:
            selected=resize_theme(reloaded,size)
            package=export_theme(selected,stage/'exports'/f'{name}-{size}px.zip')
            native=stage/'Windows主题'/str(size)
            native.mkdir(parents=True)
            mapping={}
            with zipfile.ZipFile(package) as archive:
                for member in archive.namelist():
                    target=native/member
                    if target.parent!=native: raise ValueError('导出包产生了意外的子路径')
                    target.write_bytes(archive.read(member))
                    if target.suffix not in ('.cur','.ani'): continue
                    frames=(decode_ani if target.suffix=='.ani' else decode_cur)(target.read_bytes())
                    expected=render_frames(selected,selected.roles[target.stem])
                    if len(frames)!=len(expected) or any(
                        f.image.size!=(size,size) or f.hotspot!=e.hotspot or f.image.tobytes()!=e.image.tobytes()
                        or (target.suffix=='.ani' and abs(f.duration_ms-e.duration_ms)>8.34)
                        for f,e in zip(frames,expected)
                    ):
                        raise ValueError('原生资源结构/尺寸/热点检查失败')
                    if native_checked:
                        from cursor_studio.windows.native import validate_cursor_file
                        if not validate_cursor_file(target): raise ValueError('Windows原生加载检查失败')
                    mapping[target.stem]=target.relative_to(stage).as_posix()
            if set(mapping)!=set(ROLES): raise ValueError('导出状态映射不完整')
            manifest['variants'][str(size)]={'roles':mapping}
        manifest['roles']=manifest['variants']['96']['roles']
        (stage/'theme-map.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
        frames=render_frames(reloaded,reloaded.roles['Arrow'])
        frames[0].image.save(stage/'预览.png')
        frames[0].image.save(stage/'动画预览.gif',save_all=True,append_images=[f.image for f in frames[1:]],duration=[round(f.duration_ms) for f in frames],loop=0,disposal=2)
        _entrypoints(stage,output)
        (stage/'使用说明.md').write_text(
            f'# {name}\n\n工程：`project/theme.json`；透明母版：`artwork/母版.png`；预制资源：`Windows主题/64`、`96`、`128`；分享包：`exports/`。\n\n'
            '在编辑器里打开或导入此文件夹即可继续修改。检查全部15种状态的热点和动画。当前动画为轻浮动和忙碌环，不是自动生成的表情动作。\n\n'
            '应用入口需要保留原编辑器仓库，仅在点击确认后更改系统；本次创作没有安装或应用。取消自定义请运行仓库根目录“取消自定义光标.cmd”。单独分享资源用exports中的ZIP。\n','utf-8')
        (stage/'验证报告.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
        if output.exists(): raise FileExistsError(f'输出在制作期间被创建，拒绝覆盖：{output}')
        stage.rename(output)
    return report
