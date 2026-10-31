import hashlib
import subprocess
import sys
from pathlib import Path
import pytest
from PIL import Image,ImageDraw
from cursor_studio.models import ROLES
from cursor_studio.services.creation import create_theme_bundle
from cursor_studio.services.library import discover_themes,open_theme_source
from cursor_studio.paths import EDITOR_ROOT,WORKSPACE_ROOT

def test_module_boundaries_and_root_launchers():
    import re
    assert EDITOR_ROOT==WORKSPACE_ROOT/'editor'
    assert not (WORKSPACE_ROOT/'src').exists()
    for entry in ['启动编辑器.cmd','取消自定义光标.cmd']:
        assert b'editor\\scripts\\' in (WORKSPACE_ROOT/entry).read_bytes()
    for folder in [WORKSPACE_ROOT,*[WORKSPACE_ROOT/name for name in ['懒羊羊','一二','吹泡泡Dva','月神天使']]]:
        for path in folder.glob('*.cmd'):
            command=path.read_text('ascii')
            target=re.search(r'-File "([^"]+)"',command)
            if target:
                resolved=Path(target[1].replace('%~dp0',str(folder)+'\\')).resolve()
                assert resolved.is_file(),(path,resolved)
                assert resolved.is_relative_to(EDITOR_ROOT/'scripts')

def test_skill_checks_copied_install_and_creates_editable_theme(tmp_path):
    import shutil
    installed=tmp_path/'skills/cursor-theme-creator'
    shutil.copytree(WORKSPACE_ROOT/'SKILLS/cursor-theme-creator',installed)
    result=subprocess.run([sys.executable,str(installed/'scripts/create_theme.py'),
                           '--workspace',str(WORKSPACE_ROOT),'--check'],capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr.decode('utf-8',errors='replace')
    assert b'offline_creator_ready' in result.stdout
    source=tmp_path/'source.png'
    image=Image.new('RGBA',(256,256));ImageDraw.Draw(image).ellipse((20,20,230,230),fill='#a8e2d0');image.save(source)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    output=tmp_path/'themes/我的新主题'
    report=create_theme_bundle('我的新主题',source,output)
    assert report['cursor_files']==45 and report['system_changed'] is False
    assert len(list(output.glob('exports/*.zip')))==3
    assert len(list((output/'Windows主题').rglob('*.cur')))+len(list((output/'Windows主题').rglob('*.ani')))==45
    theme,path=open_theme_source(output)
    assert path==output/'project/theme.json' and set(theme.roles)==set(ROLES)
    assert all(role.frames for role in theme.roles.values())
    assert any(entry.folder==output for entry in discover_themes(output.parent))
    before=(output/'project/theme.json').read_bytes()
    with pytest.raises(FileExistsError):create_theme_bundle('我的新主题',source,output)
    assert (output/'project/theme.json').read_bytes()==before
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest


def test_nested_skill_finds_workspace_from_external_directory(tmp_path):
    result=subprocess.run([sys.executable,str(WORKSPACE_ROOT/'SKILLS/cursor-theme-creator/scripts/create_theme.py'),
                           '--check'],cwd=tmp_path,capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr.decode('utf-8',errors='replace')
    assert b'offline_creator_ready' in result.stdout
