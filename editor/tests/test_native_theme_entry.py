"""Exercise the native offline entry without changing registry/system cursors."""
import json
import os
import subprocess
from pathlib import Path
import pytest
from cursor_studio.models import ROLES

ROOT=Path(__file__).resolve().parents[2]

def run_check(*args):
    return subprocess.run(['powershell.exe','-NoProfile','-STA','-ExecutionPolicy','Bypass',
                           '-File',str(ROOT/'editor/scripts/use-theme.ps1'),*args,'-Check'],capture_output=True,timeout=40)

@pytest.mark.skipif(os.name!='nt',reason='Windows native launcher')
def test_cancel_custom_validates_without_needing_existing_backup():
    result=run_check('-ResetDefaults')
    assert result.returncode==0,result.stderr.decode(errors='replace')
    assert b'Windows default cursor reset validated; no changes made.' in result.stdout

@pytest.mark.skipif(os.name!='nt',reason='Windows native launcher')
def test_manifest_selected_size_not_top_level_old_resource(tmp_path):
    source=ROOT/'懒羊羊'
    data=json.loads((source/'theme-map.json').read_text('utf-8'))
    # Keep resource paths inside the test folder using real local copies.
    import shutil
    role_map={}
    for role,path in data['roles'].items():
        original=source/path
        target=tmp_path/(role+original.suffix)
        shutil.copyfile(original,target)
        role_map[role]=target.name
    manifest={'name':'test','default_size':96,'roles':{role:'missing.cur' for role in ROLES},
              'variants':{'96':{'roles':role_map},'128':{'roles':{role:'missing.cur' for role in ROLES}}}}
    (tmp_path/'theme-map.json').write_text(json.dumps(manifest),'utf-8')
    result=run_check('-ThemeFolder',str(tmp_path),'-Size','96')
    assert result.returncode==0,result.stderr.decode(errors='replace')
    assert b'size=96 px' in result.stdout
    bad=run_check('-ThemeFolder',str(tmp_path),'-Size','128')
    assert bad.returncode!=0
