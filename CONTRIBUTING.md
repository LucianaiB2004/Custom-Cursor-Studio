# 开发指南

使用 Python 3.11+。代码位于 editor/src/cursor_studio，测试位于 editor/tests，格式编解码不依赖 GUI。在仓库根目录准备环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r editor/requirements.txt
$env:PYTHONPATH = "$PWD/editor/src"
.\.venv\Scripts\python.exe -m cursor_studio.app
```

运行测试：`.\.venv\Scripts\python.exe -m pytest -q`。仓库技能统一放在 `SKILLS/`；创作入口为 [SKILLS/cursor-theme-creator/SKILL.md](SKILLS/cursor-theme-creator/SKILL.md)，复用 `services/creation.py`，不要在技能中复制格式编解码逻辑。

每个可直接使用的主题放在根目录 `主题名称/`，包含 `应用主题.cmd`、`使用说明.md`、`theme-map.json`。应用入口调用 `editor/scripts/use-theme.ps1`，无需 Python。只在仓库根目录放一个 `取消自定义光标.cmd`，调用 `-ResetDefaults` 恢复 Windows 默认指针，不在案例内恢复上一方案。可编辑案例还包含 `编辑主题.cmd`、`放大与导出.cmd`、`project/theme.json` 和素材目录。不要给正常用户暴露多个 v1/v2 入口，旧版放 archives。原始参考文件不改动内容。

`theme-map.json` 的 `variants` 保存64/96/128各尺寸的独立15角色资源映射，`default_size` 默认96。入口准备脚本必须保留已存在的高分辨率工程与尺寸映射，不能用旧参考资源覆盖。尺寸输出应从高清母版直接生成，避免64px中间结果重复放大。尺寸选择只更新预览，必须明确点击应用才写系统设置。

两套原始参考资源位于根目录 `吹泡泡Dva/`、`月神天使/`，原始 ZIP 位于 `editor/references/packages/`，这些原始文件内容保持只读。原始哈希基线及迁移路径映射位于 evidence；验证脚本 `editor/scripts/analyze_references.py`。修改应用/恢复功能时必须保留用户确认、备份、回读验证和失败回滚。自动化测试不得实际修改系统指针。

本地 .venv、缓存、运行日志不应提交。角色素材授权与程序源码分别处理，见 NOTICE.md。

编辑器本地主题发现与读取位于 `services/library.py`；界面不得硬编码新案例按钮。根目录/`projects` 下的主题在刷新后被发现，外部目录走“导入文件夹”。新工程优先 `project/theme.json`，没有工程时依次解析显式映射、INF或按角色命名的素材。修改格式识别应补充 `test_theme_library.py` 与必要的界面交互回归。`editor/scripts/start-editor.ps1 -Check` 可只读检查本机启动依赖及主题数量，不安装依赖、不切换系统指针。
