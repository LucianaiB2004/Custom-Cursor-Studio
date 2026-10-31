# 系统方案备份、应用与恢复

根目录四套主题的直接入口使用 `editor/scripts/use-theme.ps1`，不依赖 Python。映射来自随仓库附带的 `theme-map.json`，每个尺寸在 `variants` 中有独立15角色映射，只接受主题内 CUR/ANI。选择64/96/128像素后必须点击应用，才会修改系统。应用同时记录所选 `CursorBaseSize`，仅改变文件像素尺寸无法保证 Windows 实际显示大小发生变化。备份使用 PowerShell CLIXML，保存在 `%LOCALAPPDATA%/CustomCursorStudio/portable/backups`，记录全部指针值与方案列表的原始类型。资源复制到持久目录后才修改当前用户注册表，失败尝试回滚。自动化 `-Check` 仅验证原生加载及读取快照，不写注册表；真实应用/取消仍需人工验收。

用户取消自定义的唯一案例入口是仓库最根目录 `取消自定义光标.cmd`，调用 `editor/scripts/use-theme.ps1 -ResetDefaults`，恢复 Windows 默认白色指针和默认大小，不读取“上次应用前”的主题备份。该操作也需要明确确认并先备份当前设置；备份恢复仍留在编辑器高级故障处理工具中，不能把“恢复上一套自定义主题”称为“取消自定义”。每个案例目录与尺寸窗口中都不提供恢复上一方案按钮。

默认先导出 ZIP，由用户自行选择安装。打开应用、导入图片、打开参考主题、预览和导出均不会调用系统切换接口。参考主题中的 INF 只解析数据，绝不执行；其中的 HKLM RunOnce 也不会复制到应用逻辑。

`windows/schemes.py` 的应用和恢复函数必须由界面在用户点击确认后调用，不能在启动、导入或导出过程中自动调用。仅访问当前用户 `HKCU\Control Panel\Cursors` 与固定的 `Schemes` 子键，不能通过备份文件指定任意注册表路径，不申请管理员权限。

应用前检查 15 角色是否完整、文件是否存在、Windows 是否可加载；检查当前用户写权限。然后将原键是否存在、全部值、每个值的原始类型，以及方案子键全部值写入本地 JSON。二进制值用 base64，缺失的键用 `exists: false`，缺失的值由完整值集合表达。临时文件写入并 fsync 后原子提交；备份失败不会开始系统修改。

应用使用持久路径。调用者应先把导出的 CUR/ANI 放入不会被清理的个人目录，再传入映射；不可使用临时导出目录。适配层只写 15 个指针值、当前方案名称、Scheme Source、所选 CursorBaseSize 和对应命名方案。刷新使用 Windows `SystemParametersInfoW(SPI_SETCURSORS, 0, NULL, SPIF_SENDCHANGE)`，随后回读全部值。

任何写入、刷新或回读失败都会立即尝试恢复完整旧值集合、删除新增值并刷新。若回滚也失败，错误会明确区分，并保留备份供手工处理。恢复旧备份前同样会备份当前状态。恢复会覆盖备份之后在这两个键中的更改，包括方案列表，界面须明确提示这一影响。

当前自动化测试使用内存注册表适配器验证事务、原始类型、缺失值、权限拒绝、错误回滚和输入校验；**未执行真实桌面方案切换、安装或恢复，不能把这些测试描述为 Windows 实机切换验收通过**。真实验收需用户确认后检查指针形状、热点、动画、切换与恢复结果。

恢复可能因旧文件已被移动/删除而不能恢复原视觉外观；注册表备份不复制旧系统素材。未知子键不会被递归删除。当前适配器恢复精确注册表值，未实现其他程序并发修改下的跨进程事务隔离。

参考官方接口：[SystemParametersInfoW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-systemparametersinfow)、[注册表权限](https://learn.microsoft.com/en-us/windows/win32/sysinfo/registry-key-security-and-access-rights)、[Python winreg](https://docs.python.org/3/library/winreg.html)。

### 原生刷新故障排查

直接启动脚本也显式绑定 `SystemParametersInfoW`（Unicode、精确入口名称），与 Python 适配层使用相同的 `SPI_SETCURSORS, 0, NULL, SPIF_SENDCHANGE` 参数。失败时在 C# 调用边界立即读取错误码，弹窗包含 `Win32=数字` 及系统说明，避免仅显示“无法重新加载”而无法定位原因。出现回滚失败时应保留 `%LOCALAPPDATA%/CustomCursorStudio/portable/backups`，不要删除旧资源目录。

`editor/tests/test_native_reload.py` 编译启动脚本中的实际声明，用只读 `SPI_GETBEEP` 检查绑定，并通过注入失败验证刷新参数和错误码传递。它不调用真实 `SPI_SETCURSORS`，也不能证明真实方案切换已经成功。截图中的旧错误没有保存 Windows 错误码，因此目前只能确认调用差异已修正；需要用户在应用或取消窗口确认后复验原报错。

### 实际大小与编辑器内启用

主编辑器和案例“放大与导出”共用 `services/application.py`：验证完整15状态，从当前源图渲染一次，检查CUR/ANI结构，先写完暂存目录再改名为持久目录，最后调用同一系统应用事务。不会重新打开旧工程或旧的预生成ZIP覆盖当前编辑结果。整套尺寸通过 `resize_theme()` 覆盖每个角色尺寸，并换算热点，解决案例独立尺寸导致主题设置无效的问题。

本机 Windows 11 build 26200 只读诊断发现，`CursorBaseSize=128`、素材128px，但运行时大小查询为32；证据在 `editor/evidence/runtime-size-diagnostic.json`。因此仅写注册表加 `SPI_SETCURSORS` 不足以证明尺寸立即生效。

`windows/pointer_size.py` 隔离两项**未公开**的 Windows 兼容行为：SPI action `0x2028` 查询运行时基础尺寸，`0x2029` 用 `pvParam=(PVOID)size` 设置运行时大小。它们不是公开SDK常量，不声称微软提供稳定兼容保证。调用约定依据 [Mozilla原始讨论](https://bugzilla.mozilla.org/show_bug.cgi?id=1712669#c4) 与 [实现作者的原始C++](https://github.com/marco-kretz/win11-multi-dpi-cursor/blob/main/multi-dpi-cursor.wh.cpp)。设置flags=0，持久注册表仍由事务管理；不修改其他辅助功能注册表键。未来Windows拒绝接口时显式失败，不偷偷用注册表读数代替运行时结果。

用户确认后，事务分别备份原注册表和原运行时大小，更新目标、设置运行时大小、刷新，再检查两者。任何失败均尝试恢复两份原始状态；不会把原注册表128误当作原运行时32恢复。新JSON/CLIXML备份包含运行时大小，旧备份只能使用其保存的CursorBaseSize（没有时保持当前运行时大小）。根目录取消脚本同样同步为默认32。大小接口的SET、刷新、回滚均只做注入测试，未自动操作真实桌面；真实GET已在本机验证。原生资源检查使用 `LoadImageW(LR_LOADFROMFILE)` 拥有型句柄，避免销毁共享光标。
