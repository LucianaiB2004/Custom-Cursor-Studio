# Repository guidance

The four ready-to-use themes live at the repository root. All editor implementation, tests and tools live in `editor/`; keep root launchers thin. Preserve the original reference resource hashes recorded in `editor/evidence/`.

For requests to create or customize a cursor theme, read and follow the repository skill [SKILLS/cursor-theme-creator/SKILL.md](SKILLS/cursor-theme-creator/SKILL.md). Keep reusable skills under `SKILLS/`. Use its script or `cursor_studio.services.creation.create_theme_bundle` instead of copying binary codecs or role glyph implementations. Do not overwrite existing themes or automatically apply system cursors during creation.

Run tests from the repository root with `.venv/Scripts/python.exe -m pytest -q`. Native checks must use `-Check`; actual cursor application or cancellation requires the user's explicit confirmation in the corresponding UI.
