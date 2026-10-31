"""Check the actual PowerShell interop declaration without changing cursors."""
import json
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'editor/scripts/use-theme.ps1'


@pytest.mark.skipif(os.name != 'nt', reason='Windows P/Invoke')
def test_native_reload_uses_explicit_unicode_binding_and_reports_win32_errors(tmp_path):
    # Compile precisely the C# used by the launcher, without executing its UI,
    # registry writes or SPI_SETCURSORS. GETBEEP is a read-only ABI smoke check.
    source = SCRIPT.read_text('utf-8-sig').split("Add-Type @'", 1)[1].split("'@", 1)[0]
    harness = tmp_path / 'interop.ps1'
    harness.write_text("""$ErrorActionPreference = 'Stop'
Add-Type @'
""" + source + """
'@
$method = [CursorThemeNative].GetMethod('SystemParametersInfoW')
if ($null -eq $method) { throw 'Missing explicit Unicode native binding' }
$attribute = $method.GetCustomAttributes([Runtime.InteropServices.DllImportAttribute], $false)[0]
$beep = [Runtime.InteropServices.Marshal]::AllocHGlobal(4)
try {
    if (-not [CursorThemeNative]::SystemParametersInfoW(1,0,$beep,0)) { throw 'Read-only native probe failed' }
} finally { [Runtime.InteropServices.Marshal]::FreeHGlobal($beep) }
""" + f"""
$tokens=$null; $errors=$null
$tree=[Management.Automation.Language.Parser]::ParseFile('{str(SCRIPT).replace(chr(39), chr(39)*2)}',[ref]$tokens,[ref]$errors)
foreach ($name in @('Snapshot','Assert-Snapshot')) {{
    $definition=$tree.FindAll({{param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name}},$true)[0]
    . ([ScriptBlock]::Create($definition.Extent.Text))
}}
$registryPath='Control Panel\\Cursors'
$snapshot=Snapshot
Assert-Snapshot $snapshot
""" + """
@{entry=$attribute.EntryPoint; exact=$attribute.ExactSpelling; lastError=$attribute.SetLastError} | ConvertTo-Json -Compress
""", 'utf-8-sig')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-File', str(harness)],
                            capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    assert json.loads(result.stdout) == {
        'entry': 'SystemParametersInfoW', 'exact': True, 'lastError': True}

    # Replace only the OS call with a failing implementation. Exercise the real
    # error wrapper to ensure the original error survives the interop boundary.
    import re
    fake = re.sub(
        r'\[DllImport\([^\n]+\)\]\s*public static extern bool SystemParametersInfoW\([^;]+;',
        'public static bool SystemParametersInfoW(uint action,uint param,IntPtr value,uint flags) '
        '{ if (action != 0x57 || param != 0 || value != IntPtr.Zero || flags != 2) '
        'throw new Exception("Wrong reload arguments"); SetLastError(5); return false; }\n'
        '[DllImport("kernel32.dll", SetLastError=true)] private static extern void SetLastError(uint error);',
        source)
    harness.write_text("Add-Type @'\n" + fake + "\n'@\n"
                       "try { [CursorThemeNative]::ReloadCursors(); exit 1 } catch { "
                       "$e=$_.Exception; while ($e.InnerException) {$e=$e.InnerException}; "
                       "if ($e -isnot [ComponentModel.Win32Exception] -or $e.NativeErrorCode -ne 5) "
                       "{Write-Error $e; exit 2}; Write-Output $e.Message }", 'utf-8-sig')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-File', str(harness)],
                            capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    assert b'Win32=5' in result.stdout


@pytest.mark.skipif(os.name != 'nt', reason='Windows PowerShell interop')
def test_powershell_runtime_size_and_rollback_use_separate_cached_value(tmp_path):
    import re
    source = SCRIPT.read_text('utf-8-sig').split("Add-Type @'",1)[1].split("'@",1)[0]
    fake = re.sub(
        r'\[DllImport\([^\n]+\)\]\s*public static extern bool SystemParametersInfoW\([^;]+;',
        '''private static int cachedSize = 32;
 public static bool SystemParametersInfoW(uint action,uint param,IntPtr value,uint flags) {
     if (param != 0) throw new Exception("Wrong param");
     if (action == 0x2028 && flags == 0) {Marshal.WriteInt32(value,cachedSize);return true;}
     if (action == 0x2029 && flags == 0) {cachedSize=value.ToInt32();return true;}
     if (action == 0x57 && flags == 2 && value == IntPtr.Zero) return true;
     throw new Exception("Wrong API arguments");
 }''',source)
    script_path = str(SCRIPT).replace("'", "''")
    harness = tmp_path/'size-rollback.ps1'
    harness.write_text("$ErrorActionPreference='Stop'\nAdd-Type @'\n" + fake + "\n'@\n" + f"""
$tokens=$null; $errors=$null
$tree=[Management.Automation.Language.Parser]::ParseFile('{script_path}',[ref]$tokens,[ref]$errors)
if ($errors.Count) {{throw 'Invalid launcher syntax'}}
foreach ($name in @('Reload-Cursors','Rollback')) {{
    $definition=$tree.FindAll({{param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name}},$true)[0]
    . ([ScriptBlock]::Create($definition.Extent.Text))
}}
$homePath='test-backup'
function Write-Snapshot($state) {{$script:restored=$state}}
function Assert-Snapshot($state) {{$script:verified=$true}}
if ([CursorThemeNative]::GetCursorSize() -ne 32) {{throw 'Wrong initial cache'}}
Reload-Cursors 128
if ([CursorThemeNative]::GetCursorSize() -ne 128) {{throw 'Requested size not applied'}}
$state=@(@{{RuntimeSize=32; Values=@(@{{Name='CursorBaseSize';Value=128}})}})
$rolled=$false
try {{Rollback $state 'simulated failure'}} catch {{$rolled=$_.Exception.Message.Contains('已回滚')}}
if (-not $rolled -or -not $script:verified -or $null -eq $script:restored) {{throw 'Rollback not verified'}}
if ([CursorThemeNative]::GetCursorSize() -ne 32) {{throw 'Rolled back registry size rather than original cache'}}
Write-Output 'Runtime size and rollback verified without system mutation.'
""", 'utf-8-sig')
    result = subprocess.run(['powershell.exe','-NoProfile','-File',str(harness)],
                            capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    assert b'Runtime size and rollback verified' in result.stdout
