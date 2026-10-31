param([string]$ThemeFolder, [switch]$Restore, [switch]$ResetDefaults,
      [ValidateSet(0,32,48,64,80,96,128,256)][int]$Size=0, [switch]$Check)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class CursorThemeNative {
 [DllImport("user32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern IntPtr LoadImageW(IntPtr instance,string path,uint type,int width,int height,uint flags);
 [DllImport("user32.dll")] public static extern bool DestroyCursor(IntPtr cursor);
 [DllImport("user32.dll", EntryPoint="SystemParametersInfoW", ExactSpelling=true, CharSet=CharSet.Unicode, SetLastError=true)] public static extern bool SystemParametersInfoW(uint action,uint param,IntPtr value,uint flags);
 public static void ReloadCursors() {
     // Keep this call and GetLastWin32Error together: PowerShell interop can
     // overwrite the thread's last-error value before a later script call.
     if (!SystemParametersInfoW(0x57,0,IntPtr.Zero,2)) {
         int error = Marshal.GetLastWin32Error();
         throw new System.ComponentModel.Win32Exception(error,
             "Windows 无法重新加载指针方案 (SystemParametersInfoW/SPI_SETCURSORS, Win32=" + error + "): " +
             new System.ComponentModel.Win32Exception(error).Message);
     }
 }
 // Windows 10/11 compatibility SPI actions, not public SDK constants.
 // Keep runtime-only size changes in the same confirmed/rollback transaction.
 public static int GetCursorSize() {
     IntPtr result = Marshal.AllocHGlobal(4);
     try {
         if (!SystemParametersInfoW(0x2028,0,result,0)) {
             int error = Marshal.GetLastWin32Error();
             throw new System.ComponentModel.Win32Exception(error,"Windows 不支持读取运行时指针大小 (Win32=" + error + ")");
         }
         int size = Marshal.ReadInt32(result);
         if (size < 16 || size > 256) throw new InvalidOperationException("Windows 返回了无效指针大小：" + size);
         return size;
     } finally { Marshal.FreeHGlobal(result); }
 }
 public static void SetCursorSize(int size) {
     if (size < 16 || size > 256) throw new ArgumentOutOfRangeException("size");
     if (!SystemParametersInfoW(0x2029,0,new IntPtr(size),0)) {
         int error = Marshal.GetLastWin32Error();
         throw new System.ComponentModel.Win32Exception(error,"Windows 未能设置运行时指针大小；此系统可能不支持大小兼容接口 (Win32=" + error + ")");
     }
     if (GetCursorSize() != size) throw new InvalidOperationException("Windows 运行时指针大小未生效。");
 }
}
'@
$roles = @('Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand')
$homePath = Join-Path $env:LOCALAPPDATA 'CustomCursorStudio\portable'
$registryPath = 'Control Panel\Cursors'

function Snapshot {
    $result = @()
    foreach ($sub in @('', '\Schemes')) {
        $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($registryPath + $sub)
        $values = @()
        if ($null -ne $key) {
            try {
                foreach ($name in $key.GetValueNames()) {
                    $values += @{ Name=$name; Kind=[int]$key.GetValueKind($name); Value=$key.GetValue($name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames) }
                }
            } finally { $key.Dispose() }
        }
        $result += @{ Sub=$sub; Exists=($null -ne $key); Values=$values }
    }
    $result[0].RuntimeSize = [CursorThemeNative]::GetCursorSize()
    return ,$result
}
function Write-Snapshot($state) {
    foreach ($entry in $state) {
        if (-not $entry.Exists) {
            if ($entry.Sub -eq '\Schemes') {
                $existing = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($registryPath + $entry.Sub, $true)
                if ($null -ne $existing) {
                    try {
                        if ($existing.SubKeyCount) { throw '方案键出现未知子键，已停止删除以保护数据。' }
                        foreach ($name in $existing.GetValueNames()) { $existing.DeleteValue($name) }
                    } finally { $existing.Dispose() }
                    [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKey($registryPath + $entry.Sub, $false)
                }
            }
            continue
        }
        $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($registryPath + $entry.Sub)
        try {
            foreach ($name in $key.GetValueNames()) { $key.DeleteValue($name) }
            foreach ($value in $entry.Values) {
                $kind = [Microsoft.Win32.RegistryValueKind][int]$value.Kind
                $data = $value.Value
                if ($kind -eq [Microsoft.Win32.RegistryValueKind]::Binary) { $data = [byte[]]$data }
                if ($kind -eq [Microsoft.Win32.RegistryValueKind]::MultiString) { $data = [string[]]$data }
                if ($kind -eq [Microsoft.Win32.RegistryValueKind]::DWord) { $data = [int]$data }
                if ($kind -eq [Microsoft.Win32.RegistryValueKind]::QWord) { $data = [long]$data }
                $key.SetValue($value.Name,$data,$kind)
            }
        } finally { $key.Dispose() }
    }
}
function Assert-Snapshot($state) {
    foreach ($entry in $state) {
        $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($registryPath + $entry.Sub)
        try {
            if (($null -ne $key) -ne [bool]$entry.Exists) { throw '指针注册表键存在状态回读不一致。' }
            if ($null -eq $key) { continue }
            if ($key.ValueCount -ne @($entry.Values).Count) { throw '指针注册表值数量回读不一致。' }
            foreach ($saved in $entry.Values) {
                if ([int]$key.GetValueKind($saved.Name) -ne [int]$saved.Kind) { throw ('注册表类型回读不一致：' + $saved.Name) }
                $actual = $key.GetValue($saved.Name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
                if ($null -eq $actual -or $null -eq $saved.Value) {
                    if ($null -ne $actual -or $null -ne $saved.Value) { throw ('注册表空值回读不一致：' + $saved.Name) }
                } elseif (Compare-Object @($actual) @($saved.Value) -CaseSensitive -SyncWindow 0) {
                    throw ('注册表值回读不一致：' + $saved.Name)
                }
            }
        } finally { if ($null -ne $key) { $key.Dispose() } }
    }
}
function Reload-Cursors([int]$size=0) {
    try {
        if ($size -gt 0) { [CursorThemeNative]::SetCursorSize($size) }
        [CursorThemeNative]::ReloadCursors()
        if ($size -gt 0 -and [CursorThemeNative]::GetCursorSize() -ne $size) { throw 'Windows 运行时指针大小回读不一致。' }
    }
    catch {
        $detail = $_.Exception
        while ($detail.InnerException) { $detail = $detail.InnerException }
        throw $detail.Message
    }
}
function Save-Backup($state) {
    $dir = Join-Path $homePath 'backups'
    [void][IO.Directory]::CreateDirectory($dir)
    $path = Join-Path $dir (([guid]::NewGuid().ToString()) + '.clixml')
    $state | Export-Clixml -LiteralPath ($path + '.tmp') -Encoding UTF8
    Move-Item -LiteralPath ($path + '.tmp') -Destination $path
    return $path
}
function Rollback($state, $originalError) {
    try { Write-Snapshot $state; Reload-Cursors ([int]$state[0].RuntimeSize); Assert-Snapshot $state }
    catch { throw ('操作失败：' + $originalError + '；回滚也失败：' + $_.Exception.Message + '。请保留备份目录：' + $homePath) }
    throw ('操作失败，已回滚：' + $originalError)
}
function Select-ThemeSize($manifest, $available) {
    $form = New-Object Windows.Forms.Form
    $form.Text = '应用鼠标主题 · ' + $manifest.name
    $form.ClientSize = New-Object Drawing.Size(420,205)
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'; $form.MaximizeBox=$false; $form.MinimizeBox=$false
    $form.Font = New-Object Drawing.Font('Microsoft YaHei UI',10)
    $label = New-Object Windows.Forms.Label
    $label.Text = '选择实际系统指针大小，然后点击“应用所选大小”。'
    $label.SetBounds(20,18,380,42); $form.Controls.Add($label)
    $combo = New-Object Windows.Forms.ComboBox
    $combo.DropDownStyle='DropDownList'; $combo.SetBounds(20,72,380,30)
    foreach ($value in $available) { [void]$combo.Items.Add([string]$value + ' px') }
    $preferred = if ($manifest.default_size) { [int]$manifest.default_size } else { [int]$available[0] }
    $combo.SelectedIndex = [Array]::IndexOf([int[]]$available, $preferred)
    if ($combo.SelectedIndex -lt 0) { $combo.SelectedIndex=0 }
    $form.Controls.Add($combo)
    $apply = New-Object Windows.Forms.Button
    $apply.Text='应用所选大小'; $apply.SetBounds(20,132,220,42)
    $apply.DialogResult=[Windows.Forms.DialogResult]::OK; $form.Controls.Add($apply)
    $cancel = New-Object Windows.Forms.Button
    $cancel.Text='取消'; $cancel.SetBounds(255,132,145,42)
    $cancel.DialogResult=[Windows.Forms.DialogResult]::Cancel; $form.Controls.Add($cancel)
    $form.AcceptButton=$apply; $form.CancelButton=$cancel
    try {
        if ($form.ShowDialog() -ne [Windows.Forms.DialogResult]::OK) { return 0 }
        return [int]$available[$combo.SelectedIndex]
    } finally { $form.Dispose() }
}
try {
    if ($ResetDefaults) {
        if ($Restore -or $ThemeFolder) { throw '取消自定义不能与主题应用或备份恢复同时运行。' }
        # Empty role paths select Windows' built-in OEM resources. No custom
        # backup is used as the reset target; unknown user schemes are kept.
        if ($Check) { $null=Snapshot; Write-Output 'Windows default cursor reset validated; no changes made.'; exit 0 }
        if ([Windows.Forms.MessageBox]::Show('取消自定义光标，恢复 Windows 自带的默认白色指针和标准大小？','取消自定义光标','YesNo','Question','Button2') -ne 'Yes') { exit 0 }
        $before=Snapshot; $null=Save-Backup $before
        try {
            $key=[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($registryPath)
            try {
                foreach ($role in $roles) { $key.SetValue($role,'',[Microsoft.Win32.RegistryValueKind]::ExpandString) }
                $key.SetValue('','',[Microsoft.Win32.RegistryValueKind]::String)
                $key.SetValue('Scheme Source',0,[Microsoft.Win32.RegistryValueKind]::DWord)
                $key.SetValue('CursorBaseSize',32,[Microsoft.Win32.RegistryValueKind]::DWord)
                foreach ($role in $roles) { if ($key.GetValue($role) -ne '') { throw "默认状态回读校验失败：$role" } }
                if ($key.GetValue('CursorBaseSize') -ne 32) { throw '标准指针大小回读校验失败。' }
            } finally { $key.Dispose() }
            $wanted = Snapshot
            Reload-Cursors 32
            Assert-Snapshot $wanted
        } catch { Rollback $before $_.Exception.Message }
    } elseif ($Restore) {
        $record = Join-Path $homePath 'last-backup.txt'
        if (-not (Test-Path -LiteralPath $record)) { throw '尚无通过此入口应用的方案备份。' }
        $backup = [IO.File]::ReadAllText($record)
        $backupRoot = [IO.Path]::GetFullPath((Join-Path $homePath 'backups')) + '\'
        if (-not [IO.Path]::GetFullPath($backup).StartsWith($backupRoot,[StringComparison]::OrdinalIgnoreCase)) { throw '备份路径无效。' }
        $targetState = @(Import-Clixml -LiteralPath $backup)
        if ($Check) { Write-Output 'Backup readable; no changes made.'; exit 0 }
        if ([Windows.Forms.MessageBox]::Show('恢复应用前的指针设置及方案列表？恢复前也会备份当前设置。','恢复原方案','YesNo','Question','Button2') -ne 'Yes') { exit 0 }
        $before = Snapshot
        $null = Save-Backup $before
        $restoreSize = [int]$targetState[0].RuntimeSize
        if (-not $restoreSize) {
            $sizeValue = @($targetState[0].Values | Where-Object { $_.Name -eq 'CursorBaseSize' })
            if ($sizeValue.Count) { $restoreSize = [int]$sizeValue[0].Value }
        }
        try { Write-Snapshot $targetState; Reload-Cursors $restoreSize; Assert-Snapshot $targetState }
        catch { Rollback $before $_.Exception.Message }
    } else {
        $folder = [IO.Path]::GetFullPath($ThemeFolder)
        $manifest = Get-Content -LiteralPath (Join-Path $folder 'theme-map.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $available = if ($manifest.variants) { @($manifest.variants.PSObject.Properties.Name | ForEach-Object { [int]$_ } | Sort-Object) } else { @(64) }
        if (-not $available.Count -or @($available | Where-Object { $_ -notin @(32,48,64,80,96,128,256) }).Count) { throw '主题包含无效尺寸列表。' }
        $interactive=$false
        if ($Size -eq 0) {
            if ($Check) {
                $Size=if ($manifest.default_size) { [int]$manifest.default_size } else { [int]$available[0] }
            } else {
                $Size=Select-ThemeSize $manifest $available
                if ($Size -eq 0) { exit 0 }
                $interactive=$true
            }
        }
        if ($Size -notin $available) { throw "主题未提供 $Size px 的高清资源，请选择已提供的尺寸。" }
        $roleMapping=if ($manifest.variants) { $manifest.variants.([string]$Size).roles } else { $manifest.roles }
        $files = @{}
        foreach ($role in $roles) {
            $relative = $roleMapping.$role
            if (-not $relative -or [IO.Path]::IsPathRooted($relative)) { throw "缺少或无效的角色映射：$role" }
            $path = [IO.Path]::GetFullPath((Join-Path $folder $relative))
            if (-not $path.StartsWith($folder + '\',[StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetExtension($path) -notin @('.cur','.ani')) { throw "无效的光标路径：$role" }
            $handle = [CursorThemeNative]::LoadImageW([IntPtr]::Zero,$path,2,$Size,$Size,0x10)
            if ($handle -eq [IntPtr]::Zero) { throw "Windows 无法加载：$path" }
            [void][CursorThemeNative]::DestroyCursor($handle)
            $files[$role] = $path
        }
        if ($Check) { $null = Snapshot; Write-Output "15 native cursors validated; size=$Size px; registry snapshot readable; no changes made."; exit 0 }
        if (-not $interactive -and [Windows.Forms.MessageBox]::Show(('将“' + $manifest.name + '”应用为 ' + $Size + ' px，切换全部15种指针？'),'应用鼠标主题','YesNo','Question','Button2') -ne 'Yes') { exit 0 }
        $before = Snapshot
        $backup = Save-Backup $before
        $installed = Join-Path $homePath ('installed\' + [guid]::NewGuid().ToString())
        [void][IO.Directory]::CreateDirectory($installed)
        $paths = @{}
        foreach ($role in $roles) {
            $paths[$role] = Join-Path $installed ($role + [IO.Path]::GetExtension($files[$role]))
            Copy-Item -LiteralPath $files[$role] -Destination $paths[$role]
        }
        try {
            $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($registryPath)
            try {
                foreach ($role in $roles) { $key.SetValue($role,$paths[$role],[Microsoft.Win32.RegistryValueKind]::ExpandString) }
                $key.SetValue('',[string]$manifest.name)
                $key.SetValue('Scheme Source',1,[Microsoft.Win32.RegistryValueKind]::DWord)
                $key.SetValue('CursorBaseSize',$Size,[Microsoft.Win32.RegistryValueKind]::DWord)
                foreach ($role in $roles) { if ($key.GetValue($role) -ne $paths[$role]) { throw "注册表写入校验失败：$role" } }
                if ($key.GetValue('CursorBaseSize') -ne $Size) { throw '系统指针大小回读校验失败。' }
            } finally { $key.Dispose() }
            $schemes = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($registryPath + '\Schemes')
            try {
                $schemeValue = ($roles | ForEach-Object { $paths[$_] }) -join ','
                $schemes.SetValue([string]$manifest.name,$schemeValue,[Microsoft.Win32.RegistryValueKind]::String)
                if ($schemes.GetValue([string]$manifest.name) -ne $schemeValue) { throw '命名方案回读校验失败。' }
            } finally { $schemes.Dispose() }
            $wanted = Snapshot
            Reload-Cursors $Size
            Assert-Snapshot $wanted
            $record = Join-Path $homePath 'last-backup.txt'
            [IO.File]::WriteAllText(($record + '.tmp'),$backup)
            Move-Item -LiteralPath ($record + '.tmp') -Destination $record -Force
        } catch { Rollback $before $_.Exception.Message }
    }
    [void][Windows.Forms.MessageBox]::Show('操作完成。备份保存在：' + $homePath,'鼠标主题')
} catch {
    if ($Check) { Write-Error $_; exit 1 }
    [void][Windows.Forms.MessageBox]::Show($_.Exception.Message,'操作未完成','OK','Error')
    exit 1
}
