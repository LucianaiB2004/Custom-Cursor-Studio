import os
import subprocess
from pathlib import Path
import pytest

@pytest.mark.skipif(os.name!='nt',reason='Windows editor launcher')
def test_windows_startup_checks_editor_and_discovers_bundled_themes():
    root=Path(__file__).resolve().parents[2]
    if not (root/'.venv/Scripts/python.exe').exists(): pytest.skip('Local .venv not present on CI')
    result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
                           str(root/'editor/scripts/start-editor.ps1'),'-Check'],capture_output=True,timeout=40,cwd=root.parent)
    assert result.returncode==0,result.stderr.decode(errors='replace')
    assert int(result.stdout.strip().splitlines()[-1])>=4
