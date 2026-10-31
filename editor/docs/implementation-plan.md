# Custom Cursor Studio 实施计划（2026-10-29）

当前目录只有两套主题目录和对应 ZIP，无代码、Git 或局部 AGENTS。原始 36 文件已做 SHA-256 基线，保留原位且只读。按用户给定详细规格直接执行，无需重复设计审批。

## 架构与接口

- `models/theme.py`：Frame(image: Pillow RGBA, hotspot: 像素坐标, duration_ms: 浮点毫秒)、Role、Theme 和按 Windows 方案顺序排列的 15 个 ROLES。
- `io/cur.py`：decode_cur(data)->list[Frame]（多分辨率条目）；encode_cur(frames)->bytes。
- `io/ani.py`：decode_ani(data)->list[Frame]（按 seq 展开的播放帧）；encode_ani(frames)->bytes。jiffy=1/60 秒，毫秒导出量化明确提示。
- `io/importers.py`：import_media(path)->list[Frame]；reference.py: import_reference(path)->Theme。参考 INF 仅作为数据读取，禁止执行。
- `services/project.py`：save_project(theme,path,overwrite=False)、load_project(path)。相对路径素材、不可变内容寻址资源、原子 JSON 提交。
- `services/render.py`：render_frames(theme,role)->list[Frame]；导入帧保留像素素材，hotspot 记录最终画布坐标，导入角色默认尺寸为素材尺寸以保留参考热点。更换尺寸需重新校准，非法值禁止导出。
- `services/export.py`：validate_theme(theme)->list[str]、export_theme(theme,path,overwrite=False)->Path。ZIP 包含 15 资源、Unicode INF 和教程；注册方案不主动切换。
- `windows/native.py`：validate_cursor_file(path)，只加载/销毁不切换。安装/备份恢复另行隔离，应用必须有 UI 确认。
- `ui/`：可伸缩三栏、左侧角色、中间画布/场景预览、右侧属性/帧、顶部工程/导入/导出。

## 分阶段任务与验收

1. A：编写 CUR/ANI 二进制边界测试、实现解码、只读解析 GBK INF；运行 `editor/scripts/analyze_references.py` 输出完整对照报告和最终 SHA-256 校验。
2. B：PNG/JPG/GIF/APNG/SVG/序列导入，严格资源上限；JSON 保存/重开像素/热点/时长不变；静态编辑预览，CUR 原生加载测试。
3. C：RIFF chunk/奇数字节 padding、seq/rate、非法索引、零时长和截断测试；帧增删排序，单次定时器按帧实际时长播放。
4. D：完整主题映射、不完整时阻止导出并允许用户显式复制替代；生成 ZIP/UTF-16 INF；检查精确引用、输出冲突/原子替换、15 文件 Windows 加载。
5. E：安全 ZIP/SVG/工程路径测试；备份恢复能力；中文教程/启动脚本；PySide6 真实窗口检查、独立复核与修复。按用户反馈移除无生成能力的AI素材占位入口，集中完善编辑、尺寸与启用流程。

## 验证与边界

使用本目录 `.venv`（宿主 Python 3.13），`python -m pytest`；结构验证与 LoadCursorFromFile 分开。真实桌面安装、切换及恢复必须人工确认后操作，未完成时明确列出；不运行参考 INF。参考素材不重新许可，不冒称原创。无需网络或账号运行。

重点防回归：CUR alpha/AND mask 与多条目偏移；ANI 非顺序 seq；手写 NWPen 与链接 Hand 不混淆；损坏/巨大输入与 ZIP 越界；保存失败不破坏已有工程。
