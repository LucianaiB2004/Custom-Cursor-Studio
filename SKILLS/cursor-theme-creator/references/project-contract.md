# 与编辑器共享的工程约定

只在需要高级帧/热点编辑时读取。本文件描述仓库当前公开模块，不另写CUR/ANI编解码器。

运行前把 `<仓库>/editor/src` 加入 Python 模块搜索路径。公共模块：

- `cursor_studio.models`：`Theme`、`Role`、`Frame`、`ROLES`。
- `cursor_studio.services.project`：`save_project(theme, path, overwrite=False)`、`load_project(path)`。
- `cursor_studio.services.render`：`render_frames(theme, role)`、`validate_role(theme, role)`。
- `cursor_studio.services.sizing`：`resize_theme(theme, size)`，保留高分辨率素材、同步热点。
- `cursor_studio.services.export`：`export_theme(theme, path, overwrite=False)`，输出15个真实CUR/ANI、INF、说明与步骤图的ZIP。
- `cursor_studio.io.cur`、`cursor_studio.io.ani`：独立格式读写与ANI结构检查。

`Frame(image, hotspot=(x,y), duration_ms=100)` 中 `image` 是Pillow RGBA，`hotspot` 是最终输出画布坐标，不是母版坐标。`Role` 保存帧列表、独立输出大小、缩放、适配、对齐和透明度。工程可以保存256px素材而输出96px；不要先把角色烘焙成64px，再放大到128px。

15个精确Windows键由 `ROLES` 唯一维护：Arrow、Help、AppStarting、Wait、Crosshair、IBeam、NWPen、No、SizeNS、SizeWE、SizeNWSE、SizeNESW、SizeAll、UpArrow、Hand。程序中的中文名也从这个映射读取，不自行维护第二套次序。

新增动作示例：给 `theme.roles['Wait'].frames` 设置四张独立画稿及各自时长，逐帧检查热点。帧图像使用透明画布；同一状态的点击热点通常应保持一致，避免动画时点击位置跳动。忙碌动画和角色眨眼不是同一动作，不以旋转环冒称已生成表情帧。

保存工程时旁边的 `assets/` 保存内容寻址PNG，JSON使用相对路径，整个项目文件夹可移动。完成后重读，逐帧对比 `image.tobytes()`、`hotspot`、`duration_ms`。ANI时长导出量化到1/60秒，检查允许最多半个tick的差异；工程原始毫秒数应不变。

已存在的文件需要用户确认覆盖，创作脚本默认拒绝整个输出目录已存在。先输出到新目录检查，再交付；不执行包内脚本，不安装系统指针。Windows原生加载是额外检查，不能据此声称桌面已切换。
