"""Fresh-checkout entrypoints must work without the ignored Python environment."""
import json
import os
import subprocess
from pathlib import Path
import pytest
from cursor_studio.models import ROLES

ROOT = Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('name', ['懒羊羊', '一二', '吹泡泡Dva', '月神天使'])
def test_ready_theme(name):
    folder = ROOT / name
    data = json.loads((folder / 'theme-map.json').read_text('utf-8'))
    assert set(data['roles']) == set(ROLES)
    for relative in data['roles'].values():
        target = (folder / relative).resolve()
        assert target.is_relative_to(folder) and target.is_file()
    for entry in ['应用主题.cmd']:
        command = (folder / entry).read_text('ascii')
        assert 'powershell.exe' in command and '.venv' not in command
    assert not (folder/'恢复原方案.cmd').exists()
    cancel=(ROOT/'取消自定义光标.cmd').read_text('ascii')
    assert '-ResetDefaults' in cancel and '-Restore' not in cancel
    if os.name == 'nt':
        result = subprocess.run(['powershell.exe', '-NoProfile', '-STA', '-ExecutionPolicy', 'Bypass',
                                 '-File', str(ROOT/'editor/scripts/use-theme.ps1'),
                                 '-ThemeFolder', str(folder), '-Check'], capture_output=True, timeout=40)
        assert result.returncode == 0, result.stderr.decode(errors='replace')
        assert b'15 native cursors validated' in result.stdout
