"""Promote the four ready-to-use themes to the repository root, without deleting originals."""
import hashlib
import json
import sys
from pathlib import Path

EDITOR_ROOT = Path(__file__).resolve().parents[1]
ROOT = EDITOR_ROOT.parent
sys.path.insert(0, str(EDITOR_ROOT / 'src'))
from cursor_studio.io.reference import reference_mapping

NAMES = ['懒羊羊', '一二', '吹泡泡Dva', '月神天使']

def main():
    for name in NAMES:
        source = ROOT / ('themes' if name in NAMES[:2] else 'references') / name
        target = ROOT / name
        if source.exists():
            if target.exists():
                raise FileExistsError(target)
            source.rename(target)
        base = target / 'Windows主题' if name in NAMES[:2] else target
        manifest_path=target/'theme-map.json'
        # Build scripts may have supplied high-resolution variants. Never replace
        # that manifest with the original reference mapping during entrypoint setup.
        if not manifest_path.exists():
            _, mapping, _ = reference_mapping(base)
            manifest = {'name': name, 'roles': {key: path.relative_to(target).as_posix() for key, path in mapping.items()}}
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
        (target / '应用主题.cmd').write_bytes(b'@echo off\r\npowershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0..\\editor\\scripts\\use-theme.ps1" -ThemeFolder "%~dp0."\r\n')
        old_restore=target/'恢复原方案.cmd'
        if old_restore.exists():old_restore.unlink()  # Replaced generated shortcut, never original cursor resources.
        if (target/'project/theme.json').exists():
            for entry,module in [('编辑主题.cmd','cursor_studio.app'),('放大与导出.cmd','cursor_studio.ui.theme_launcher')]:
                (target / entry).write_bytes(('@echo off\r\npowershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0..\\editor\\scripts\\start-editor.ps1" -Module ' + module + ' -Project "%~dp0project\\theme.json"\r\n').encode('ascii'))
        (target / '使用说明.md').write_text(
            f'# {name}\n\n双击 `应用主题.cmd`，选择64/96/128像素后点击应用，改变全部15种系统指针。选择尺寸本身只更新预览，不修改系统。\n\n'
            '取消自定义：运行项目最根目录的 `取消自定义光标.cmd`，恢复 Windows 默认白色指针及默认大小；不是切回之前的自定义主题。\n\n'
            '直接使用仅需 Windows 10/11 自带的 Windows PowerShell，无需 Python、联网、管理员权限。请保留完整仓库目录，入口引用editor/scripts/use-theme.ps1。\n\n'
            '应用前逐个检查原生文件，先备份当前用户设置，再复制光标到 LocalAppData 持久目录。不会执行原始 INF。备份位于 `%LOCALAPPDATA%/CustomCursorStudio/portable/backups`。\n\n'
            + ('`放大与导出.cmd` 打开尺寸选择和实际鼠标试用窗口（默认96px），需要编辑器依赖。选择大小后须点击“应用所选大小”才切换系统。`编辑主题.cmd` 用于修改工程。`project/` 是可编辑工程；各尺寸均由高清母版生成，请勿把旧64px资源拉伸冒充高清版本。\n' if (target/'project/theme.json').exists() else '本目录的 CUR/ANI 与原始 INF 保持原样；推荐使用上述应用入口，不必右键运行 INF。\n'), 'utf-8')
    (ROOT/'取消自定义光标.cmd').write_bytes(b'@echo off\r\npowershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0editor\\scripts\\use-theme.ps1" -ResetDefaults\r\n')
    locations = EDITOR_ROOT / 'evidence/reference-locations.json'
    mapping = json.loads(locations.read_text('utf-8'))
    for old, current in mapping.items():
        for name in NAMES[2:]:
            current = current.replace('references/' + name + '/', name + '/')
        mapping[old] = current
    baseline = json.loads((EDITOR_ROOT / 'evidence/original-sha256.json').read_text('utf-8'))
    assert all(hashlib.sha256((ROOT / mapping[old]).read_bytes()).hexdigest() == digest for old, digest in baseline.items())
    locations.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), 'utf-8')
    # Entrypoint preparation must never rewrite application sources or the
    # PowerShell backend; those files have their own versioned implementation.
    print('Four root themes ready; all 36 original hashes unchanged.')

if __name__ == '__main__':
    main()
