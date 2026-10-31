"""Repository boundaries shared by the editor, without using the launch cwd."""
from pathlib import Path

EDITOR_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = EDITOR_ROOT.parent
