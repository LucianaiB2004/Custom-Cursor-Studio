---
name: cursor-theme-creator
description: Create and refine Windows cursor themes in Custom Cursor Studio from a description, reference image, or local artwork, including editable projects and genuine CUR/ANI theme packages. Use for cursor-theme creation and visual customization, rather than drivers, macros, or webpage CSS cursors.
---

# 自定义 Windows 光标主题创作

使用 Custom Cursor Studio 的离线格式与工程模块，把用户的创意做成可继续编辑的本地主题。本技能位于仓库 `SKILLS/cursor-theme-creator/`；仓库根目录的四套案例是参考，不是需要覆盖的模板。

## 找到工程与输入

先找到包含 `editor/src/cursor_studio` 的仓库。脚本支持 `--workspace`；技能被单独复制安装后，不能假设技能文件夹的父目录仍是仓库。可先从当前工作目录向上查找，找不到时再询问仓库位置。

已有图片时直接使用本地素材，不要求模型、网络或 API Key。用户要求从文字创作、改画风或高清重绘时，使用当前宿主可用的图像生成能力，以用户提供的参考图锁定角色身份，要求真实透明背景。宿主没有生成能力时说明限制，继续处理已有素材；不要虚构生成结果、安装模型或调用付费接口。把最终选中的画稿保存到输出主题的 `artwork/`，避免只引用临时文件。

母版建议至少1024像素，轮廓清楚、主体完整。生成高分辨率画稿与插值放大是两件事；不要把小图拉伸称为高清重绘。保留原始图片，不覆盖用户素材或四套案例。

## 制作可运行的主题

先运行随技能附带的检查入口，使用仓库已经准备好的 Python 环境：

```powershell
& "<仓库>/.venv/Scripts/python.exe" "<技能目录>/scripts/create_theme.py" --workspace "<仓库>" --check
```

用透明图片创建独立的新主题：

```powershell
& "<仓库>/.venv/Scripts/python.exe" "<技能目录>/scripts/create_theme.py" --workspace "<仓库>" --name "我的狐狸主题" --image "D:/素材/狐狸.png" --color "#f3a0b6"
```

默认输出到 `<仓库>/我的狐狸主题/`。用 `--output` 指定其他新文件夹。输出路径已存在时停止，另选名称；不要靠删除旧目录解决冲突。脚本复用编辑器的公共创作服务，生成15种状态、64/96/128像素资源、相对路径JSON工程、`theme-map.json`、INF教程与ZIP；不修改系统指针。环境未准备时使用仓库根目录的编辑器启动入口准备依赖，不要将依赖或凭据写进主题。

这个入口生成的是可编辑的角色加功能符号布局，动画采用轻浮动和忙碌环。它不是“文字自动生成任意逐帧动画”。如果用户要求眨眼、行走等表情动作，先生成并检查所需帧，再用工程模型/编辑器替换对应角色的帧；保留真实帧时长。修改高级帧、布局和热点前阅读 [工程约定](references/project-contract.md)。

## 检查与交付

- 15个角色独立存在，缺失/冲突明确报告。不要悄悄把所有状态映射到同一文件。
- 热点位于功能符号的实际尖端或交点；调整输出尺寸时同步换算热点，保留高分母版到最后一次缩小。
- 保存后重读工程，核对像素、热点和帧时长。导出的CUR/ANI必须结构可解析；Windows上再验证原生加载。资源与INF、映射的路径保持一致。
- 在编辑器中打开新主题，检查浅/深背景、动态预览和实际大小试用。输出放在仓库根目录时，用户点“刷新”即可在主题列表看到它。
- 交付输出文件夹、预览、验证结果与未验证事项。不得把原生加载测试描述成已完成真实系统切换。

默认只创作、保存和导出。不要执行导入包的INF、启动项或脚本，不自动安装/应用方案。只有用户明确选择应用入口并确认后才允许更改系统；取消自定义使用仓库根目录 `取消自定义光标.cmd`，目标是Windows默认指针，不能用任意历史备份冒充默认状态。

## 使用此技能

可直接要求支持本地文件读取的助手“读取本文件并按此技能创作主题”。若希望通过 `$cursor-theme-creator` 选择技能，将整个 `cursor-theme-creator` 文件夹复制到所用助手的技能目录并重新加载；本仓库不会自动改动用户的全局技能安装。
