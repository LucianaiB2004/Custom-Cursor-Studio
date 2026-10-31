"""Prepare the edited pixels once, then apply persistent files after UI consent."""
import os
from pathlib import Path
import tempfile
import uuid

from cursor_studio.models import ROLES
from cursor_studio.io.cur import encode_cur, decode_cur
from cursor_studio.io.ani import encode_ani, decode_ani
from cursor_studio.services.export import validate_theme
from cursor_studio.services.render import render_frames
from cursor_studio.windows import schemes


def application_home():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'CustomCursorStudio'


def apply_theme(theme, home=None):
    """Caller must obtain explicit confirmation; never run during preview/import."""
    errors = validate_theme(theme)
    if errors:
        raise ValueError('\n'.join(errors))
    home = Path(home) if home is not None else application_home()
    installed = home / 'installed'
    installed.mkdir(parents=True, exist_ok=True)
    target = installed / uuid.uuid4().hex
    names = {}
    # Finish all encoding/structural checks before any system mutation. Keep the
    # final directory even if applying fails: a failed rollback may reference it.
    with tempfile.TemporaryDirectory(prefix='.prepare-', dir=installed) as temp:
        for key in ROLES:
            frames = render_frames(theme, theme.roles[key])
            animated = len(frames) > 1
            name = key + ('.ani' if animated else '.cur')
            data = (encode_ani if animated else encode_cur)(frames)
            (decode_ani if animated else decode_cur)(data)
            (Path(temp) / name).write_bytes(data)
            names[key] = name
        Path(temp).rename(target)
    mapping = {key: target / name for key, name in names.items()}
    size = theme.roles['Arrow'].size or theme.canvas_size
    return schemes.apply_files(mapping, theme.name, home / 'backups', size=size)
