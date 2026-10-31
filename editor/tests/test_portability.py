"""Copy the deliverable to a new location; never reuse the original import path."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT=Path(__file__).resolve().parents[2]
NAMES=('懒羊羊','一二','吹泡泡Dva','月神天使')


def test_relocated_repository_loads_all_projects_and_native_mappings(tmp_path):
    relocated=tmp_path/'新的目录 with spaces'/'共享光标编辑器'
    shutil.copytree(ROOT/'editor/src',relocated/'editor/src',ignore=shutil.ignore_patterns('__pycache__'))
    scripts=relocated/'editor/scripts';scripts.mkdir(parents=True)
    shutil.copy2(ROOT/'editor/scripts/use-theme.ps1',scripts/'use-theme.ps1')
    for name in NAMES:
        shutil.copytree(ROOT/name,relocated/name,
                        ignore=shutil.ignore_patterns('exports','*.zip','*.gif'))
    env=os.environ.copy();env['PYTHONPATH']=str(relocated/'editor/src')
    code="""import json
from cursor_studio.paths import WORKSPACE_ROOT
from cursor_studio.services.library import discover_themes,open_theme_source
entries=discover_themes(WORKSPACE_ROOT)
result={entry.folder.name:len([r for r in open_theme_source(entry.folder)[0].roles.values() if r.frames]) for entry in entries}
print(json.dumps({'root':str(WORKSPACE_ROOT.resolve()),'roles':result}))
"""
    result=subprocess.run([sys.executable,'-c',code],env=env,cwd=tmp_path,
                          capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr.decode(errors='replace')
    data=json.loads(result.stdout)
    assert Path(data['root'])==relocated.resolve()
    assert data['roles']=={name:15 for name in NAMES}
    for name in NAMES:
        project=json.loads((relocated/name/'project/theme.json').read_text('utf-8'))
        for role in project['roles'].values():
            assert all(not Path(f['asset']).is_absolute() and ':' not in f['asset'] for f in role['frames'])
        if os.name=='nt':
            result=subprocess.run(['powershell.exe','-NoProfile','-STA','-ExecutionPolicy','Bypass',
                                   '-File',str(scripts/'use-theme.ps1'),'-ThemeFolder',str(relocated/name),'-Check'],
                                  cwd=tmp_path,capture_output=True,timeout=40)
            assert result.returncode==0,result.stderr.decode(errors='replace')
            assert b'15 native cursors validated' in result.stdout
