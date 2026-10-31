"""Build four cursor themes from newly drawn high-resolution character masters.

Only cursor layout, function glyphs and frame timing are composed here. Character
illustrations are imagegen outputs in each theme's artwork/ directory. Never
changes system cursors; original reference CUR/ANI/INF stay byte-for-byte intact.
"""
import hashlib
import json
import math
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

EDITOR_ROOT=Path(__file__).resolve().parents[1]
ROOT=EDITOR_ROOT.parent
sys.path.insert(0,str(EDITOR_ROOT/'src'))
from cursor_studio.models import Theme,Role,Frame,ROLES
from cursor_studio.services.glyphs import glyph
from cursor_studio.services.project import save_project,load_project
from cursor_studio.services.render import render_frames
from cursor_studio.services.sizing import resize_theme
from cursor_studio.services.export import export_theme
from cursor_studio.io.cur import decode_cur
from cursor_studio.io.ani import decode_ani
from cursor_studio.windows.native import validate_cursor_file

CASES={'懒羊羊':'#f5cb6c','一二':'#f3a0b6','吹泡泡Dva':'#f58bc4','月神天使':'#acb4f7'}
SIZES=(64,96,128)
EDGE=256


def build(name,color):
    folder=ROOT/name;master=folder/'artwork/高清母版.png'
    with Image.open(master) as source:
        art=source.convert('RGBA')
    if min(art.size)<1024 or art.getextrema()[3][0]!=0:raise ValueError(f'{name} 母版必须为1024px以上透明图')
    art=art.crop(art.getchannel('A').getbbox())
    art.thumbnail((224,224),Image.Resampling.LANCZOS)
    # Preserve earlier editable projects and generated 64px resources once.
    archive=EDITOR_ROOT/'archives/before-hd-refinement'/name
    existing=folder/'theme-map.json'
    already_hd=existing.exists() and bool(json.loads(existing.read_text('utf-8')).get('variants'))
    for relative in ['project','Windows主题','exports','动画预览.gif']:
        old=folder/relative;target=archive/relative
        if not already_hd and old.exists() and not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(old),str(target))
    theme=Theme(name=name,author='Custom Cursor Studio',canvas_size=96,
                description='根据原案例重新生成高清透明角色母版，256px编辑素材直接缩小到64/96/128px。四帧轻浮动与忙碌环动画，非逐帧表情重绘；角色权利属于原权利人。')
    for key in ROLES:
        count=8 if key in ('Wait','AppStarting') else (4 if key in ('Arrow','Hand') else 1)
        frames=[]
        for step in range(count):
            image=Image.new('RGBA',(EDGE,EDGE))
            dy=[0,-2,-4,-2][step%4] if count>1 else 0
            image.alpha_composite(art,(EDGE-art.width-3,EDGE-art.height-3+dy))
            symbol,hot=glyph(key,step,color);image.alpha_composite(symbol)
            duration=120 if count==8 else ([400,120,120,240][step] if count==4 else 100)
            frames.append(Frame(image,tuple(round(v*96/EDGE) for v in hot),duration))
        theme.roles[key]=Role(frames=frames,size=96,interpolation='smooth')
    project=folder/'project/theme.json'
    save_project(theme,project,overwrite=project.exists())
    reopened=load_project(project)
    for key in ROLES:
        for a,b in zip(theme.roles[key].frames,reopened.roles[key].frames):
            assert (a.image.tobytes(),a.hotspot,a.duration_ms)==(b.image.tobytes(),b.hotspot,b.duration_ms)
    manifest={'name':name,'default_size':96,'master':'artwork/高清母版.png','variants':{}}
    report={'name':name,'master_size':list(Image.open(master).size),'source_frame_size':256,'roundtrip':True,'variants':[]}
    for size in SIZES:
        selected=resize_theme(reopened,size)
        archive_path=folder/'exports'/f'{name}-{size}px.zip'
        archive_path.parent.mkdir(exist_ok=True)
        export_theme(selected,archive_path,overwrite=archive_path.exists())
        native=folder/'Windows主题'/str(size);native.mkdir(parents=True,exist_ok=True)
        mapping={}
        with zipfile.ZipFile(archive_path) as package:
            for member in package.namelist():
                target=native/member
                if target.parent!=native:raise ValueError('Unexpected exported path')
                target.write_bytes(package.read(member))
                if target.suffix in ('.cur','.ani'):
                    frames=(decode_ani if target.suffix=='.ani' else decode_cur)(target.read_bytes())
                    assert all(f.image.size==(size,size) for f in frames)
                    assert validate_cursor_file(target)
                    mapping[target.stem]=target.relative_to(folder).as_posix()
        assert set(mapping)==set(ROLES)
        manifest['variants'][str(size)]={'roles':mapping}
        report['variants'].append({'size':size,'files':len(mapping),'native_load':True})
    manifest['roles']=manifest['variants']['96']['roles']
    (folder/'theme-map.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
    preview=render_frames(reopened,reopened.roles['Arrow'])
    preview[0].image.save(folder/'动画预览.gif',save_all=True,append_images=[f.image for f in preview[1:]],duration=[round(f.duration_ms) for f in preview],loop=0,disposal=2)
    return report

def main():
    reports=[build(name,color) for name,color in CASES.items()]
    baseline=json.loads((EDITOR_ROOT/'evidence/original-sha256.json').read_text('utf-8'))
    locations=json.loads((EDITOR_ROOT/'evidence/reference-locations.json').read_text('utf-8'))
    assert all(hashlib.sha256((ROOT/locations[old]).read_bytes()).hexdigest()==digest for old,digest in baseline.items())
    (EDITOR_ROOT/'evidence/hd-cases-verification.json').write_text(json.dumps({'themes':reports,'original_hashes_unchanged':len(baseline),'native_files':180,'system_switched':False},ensure_ascii=False,indent=2),'utf-8')
    print('4 HD masters; 12 size variants; 180 native cursors; original 36 hashes unchanged.')

if __name__=='__main__':main()
