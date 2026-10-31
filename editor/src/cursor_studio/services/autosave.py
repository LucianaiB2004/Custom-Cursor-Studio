"""Reserve a new project without overwriting imported files or another theme."""
from pathlib import Path
import re
import uuid


def reserve_project_path(workspace, name):
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip(' .')[:60] or '未命名主题'
    # Prefix also makes reserved Windows device names (CON/AUX/COM1/...) safe.
    parent = Path(workspace).resolve() / 'projects'
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink() or parent.resolve().parent != Path(workspace).resolve():
        raise ValueError('自动保存的projects目录不能指向仓库外部。')
    while True:
        folder = parent / f'工程-{safe}-{uuid.uuid4().hex[:8]}'
        try:
            folder.mkdir()
            return folder / 'theme.json'
        except FileExistsError:
            continue
