# 编辑器实现

这里集中保存 Custom Cursor Studio 的代码、开发工具和历史验证资料。用户仍从仓库根目录双击 `启动编辑器.cmd`，也可在任意主题文件夹点击 `编辑主题.cmd`。四套主题及之后新增的主题留在仓库根目录，不属于编辑器源码。

```text
editor/
├── src/cursor_studio/
│   ├── app.py              GUI入口
│   ├── paths.py            编辑器与仓库路径边界
│   ├── models/             主题、角色与帧模型
│   ├── io/                 素材、CUR/ANI与参考主题读取
│   ├── services/           创作、发现、工程保存、渲染、尺寸和导出
│   ├── ui/                 主窗口、预览、尺寸选择
│   └── windows/            当前用户的系统指针适配与备份事务
├── scripts/                启动、应用、取消、案例构建与检查
├── tests/                  格式、工程、交互与事务测试
├── requirements.txt
├── docs/                   用户教程与技术说明
├── evidence/               验证记录、预览和原始文件哈希映射
├── references/             原始参考ZIP
└── archives/               历史素材、工程与迁移记录
```

`services/creation.py` 是 skill 与编辑器可复用的离线创作服务。它只制作新文件，不应用系统指针。`services/library.py` 读取根目录/`projects` 下的工程、映射、INF与按状态命名的素材。`paths.py` 根据代码位置确定目录，不依赖启动时的当前工作目录。

在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
powershell.exe -NoProfile -ExecutionPolicy Bypass -File editor/scripts/start-editor.ps1 -Check
.\.venv\Scripts\python.exe editor/scripts/analyze_references.py
```

运行时 `.venv/` 留在仓库根目录且由 Git 忽略；目录调整不移动已有虚拟环境。需要分享完整编辑器时保留整个仓库。分享主题资源可使用各主题 `exports/` 的 ZIP。
