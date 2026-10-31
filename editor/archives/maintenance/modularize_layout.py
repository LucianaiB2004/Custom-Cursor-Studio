"""One-time, lossless migration of editor implementation into editor/."""
import hashlib
import json
from pathlib import Path

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'懒羊羊').is_dir() and (p/'pyproject.toml').is_file())

def main():
    editor=ROOT/'editor';editor.mkdir(exist_ok=True)
    for name in ['src','scripts','tests','docs','evidence','references','archives','requirements.txt']:
        source=(ROOT/name).resolve();target=(editor/name).resolve()
        if not source.is_relative_to(ROOT) or not target.is_relative_to(editor):raise ValueError('Workspace boundary')
        if source.exists():
            if target.exists():raise FileExistsError(target)
            source.rename(target)
    for path in (editor/'scripts').glob('*.py'):
        if path.name=='modularize_layout.py':continue
        text=path.read_text('utf-8-sig')
        text=text.replace('ROOT=Path(__file__).resolve().parents[1]', 'EDITOR_ROOT=Path(__file__).resolve().parents[1]\nROOT=EDITOR_ROOT.parent')
        text=text.replace('ROOT = Path(__file__).resolve().parents[1]', 'EDITOR_ROOT = Path(__file__).resolve().parents[1]\nROOT = EDITOR_ROOT.parent')
        text=text.replace("str(ROOT/'src')", "str(EDITOR_ROOT/'src')")
        for name in ['evidence','archives','references']:
            text=text.replace(f"ROOT/'{name}'",f"EDITOR_ROOT/'{name}'")
            text=text.replace(f"ROOT / '{name}'",f"EDITOR_ROOT / '{name}'")
        text=text.replace('..\\\\scripts\\\\','..\\\\editor\\\\scripts\\\\').replace('%~dp0scripts\\\\','%~dp0editor\\\\scripts\\\\')
        text=text.replace('root scripts/use-theme.ps1','root editor/scripts/use-theme.ps1').replace('根目录 scripts/use-theme.ps1','editor/scripts/use-theme.ps1')
        path.write_text(text,'utf-8')
    for path in (editor/'tests').glob('*.py'):
        text=path.read_text('utf-8')
        text=text.replace('Path(__file__).resolve().parents[1]','Path(__file__).resolve().parents[2]')
        text=text.replace("root/'scripts/", "root/'editor/scripts/").replace("ROOT/'scripts/", "ROOT/'editor/scripts/")
        text=text.replace("(tmp_path/'evidence')", "(tmp_path/'editor/evidence')")
        text=text.replace("monkeypatch.setattr(module,'ROOT',tmp_path)","monkeypatch.setattr(module,'ROOT',tmp_path)\n    monkeypatch.setattr(module,'EDITOR_ROOT',tmp_path/'editor')")
        text=text.replace("(tmp_path/'editor/evidence').mkdir()", "(tmp_path/'editor/evidence').mkdir(parents=True)")
        path.write_text(text,'utf-8')
    project=ROOT/'pyproject.toml'
    text=project.read_text('utf-8').replace('where = ["src"]','where = ["editor/src"]').replace('pythonpath = ["src"]','pythonpath = ["editor/src"]').replace('testpaths = ["tests"]','testpaths = ["editor/tests"]')
    project.write_text(text,'utf-8')
    workflow=ROOT/'.github/workflows/tests.yml'
    workflow.write_text(workflow.read_text('utf-8').replace('-r requirements.txt','-r editor/requirements.txt'),'utf-8')
    startup=editor/'scripts/start-editor.ps1'
    text=startup.read_text('utf-8-sig').replace('$root = Split-Path -Parent $PSScriptRoot','$editorRoot = Split-Path -Parent $PSScriptRoot\n$root = Split-Path -Parent $editorRoot')
    text=text.replace("Join-Path $root 'requirements.txt'","Join-Path $editorRoot 'requirements.txt'").replace("Join-Path $root 'src'","Join-Path $editorRoot 'src'")
    startup.write_text(text,'utf-8-sig')
    for filename in ['启动编辑器.cmd','取消自定义光标.cmd']:
        path=ROOT/filename
        path.write_bytes(path.read_bytes().replace(b'%~dp0scripts\\',b'%~dp0editor\\scripts\\'))
    locations=editor/'evidence/reference-locations.json'
    mapping=json.loads(locations.read_text('utf-8'))
    mapping={old:('editor/'+new if new.startswith('references/') else new) for old,new in mapping.items()}
    locations.write_text(json.dumps(mapping,ensure_ascii=False,indent=2),'utf-8')
    baseline=json.loads((editor/'evidence/original-sha256.json').read_text('utf-8'))
    assert all(hashlib.sha256((ROOT/mapping[old]).read_bytes()).hexdigest()==digest for old,digest in baseline.items())
    print('Editor code, tools, tests and support materials moved; 36 original hashes unchanged.')

if __name__=='__main__':main()
