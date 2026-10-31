param(
    [Parameter(Position=0)][string]$Project,
    [ValidateSet('cursor_studio.app','cursor_studio.ui.theme_launcher')][string]$Module='cursor_studio.app',
    [switch]$Check
)
$ErrorActionPreference = 'Stop'
$editorRoot = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $editorRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
try {
    Set-Location -LiteralPath $root
    if (-not (Test-Path -LiteralPath $python)) {
        if ($Check) { throw '编辑器环境尚未创建。请双击启动编辑器.cmd，首次运行会安装依赖。' }
        Write-Host '首次启动：正在准备编辑器环境，需要已安装 Python 3.11+；安装依赖需要网络。'
        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($launcher) { $command=$launcher.Source; $prefix=@('-3') }
        else {
            $launcher=Get-Command python.exe -ErrorAction SilentlyContinue
            if (-not $launcher -or $launcher.Source -like '*WindowsApps*') { throw '请先安装 Python 3.11或更新版本（建议3.11~3.13），再运行本入口。' }
            $command=$launcher.Source; $prefix=@()
        }
        & $command @prefix -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'
        if ($LASTEXITCODE -ne 0) { throw '需要 Python 3.11或更新版本。' }
        & $command @prefix -m venv (Join-Path $root '.venv')
        if ($LASTEXITCODE -ne 0) { throw '无法创建本地 Python 环境，请检查 Python 安装。' }
    }
    & $python -c 'import PySide6.QtWidgets, PySide6.QtSvg, PIL, defusedxml'
    if ($LASTEXITCODE -ne 0) {
        if ($Check) { throw '编辑器依赖不完整。请双击启动编辑器.cmd修复。' }
        Write-Host '正在安装/修复编辑器依赖，完成后自动打开窗口……'
        & $python -m pip install -r (Join-Path $editorRoot 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw '依赖安装失败。请检查网络与上述错误后重试。已有主题的直接应用入口仍可离线使用。' }
    }
    $env:PYTHONPATH=Join-Path $editorRoot 'src'
    if ($Check) {
        & $python -c 'from pathlib import Path; from cursor_studio.services.library import discover_themes; from cursor_studio.ui.main_window import MainWindow; print(len(discover_themes(Path.cwd())))'
        if ($LASTEXITCODE -ne 0) { throw '编辑器模块加载失败。' }
        exit 0
    }
    $logs=Join-Path $env:LOCALAPPDATA 'CustomCursorStudio\logs'
    [void][IO.Directory]::CreateDirectory($logs)
    $id=[guid]::NewGuid().ToString()
    $errorLog=Join-Path $logs ($id + '.error.log')
    $arguments=@('-m',$Module)
    if ($Project) {
        $resolved=[IO.Path]::GetFullPath($Project)
        if (-not (Test-Path -LiteralPath $resolved)) { throw ('主题路径不存在：' + $resolved) }
        $arguments += '"' + $resolved + '"'
    }
    $process=Start-Process -FilePath (Join-Path $root '.venv\Scripts\pythonw.exe') -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardError $errorLog -RedirectStandardOutput (Join-Path $logs ($id + '.output.log')) -PassThru
    if ($process.WaitForExit(2000) -and $process.ExitCode -ne 0) { throw ('编辑器启动失败。诊断日志：' + $errorLog) }
} catch {
    if ($Check) { Write-Error $_; exit 1 }
    Write-Host $_.Exception.Message -ForegroundColor Red
    Read-Host '按回车关闭'
    exit 1
}
