import hashlib
import io
import os
import tempfile
import zipfile
from pathlib import Path
from cursor_studio.models import ROLES
from .project import atomic_write, _validate
from .render import render_frames

def validate_theme(theme):
    errors=[]
    try:_validate(theme)
    except (ValueError,TypeError) as exc:errors.append(str(exc))
    if not theme.name.strip() or any(c in theme.name for c in '\"%,;\r\n\\') or any(ord(c)<32 for c in theme.name):errors.append('主题名不能为空，且不能包含引号、百分号、逗号、分号、反斜杠或控制字符')
    for key,name in ROLES.items():
        if key not in theme.roles or not theme.roles[key].frames:errors.append(f'{key}（{name}）缺少素材，请补齐或明确选择替代角色')
    return errors

def make_inf(theme,filenames):
    folder='CursorStudio_'+hashlib.sha256(theme.name.encode('utf-8')).hexdigest()[:12]
    mapping=','.join(f'%10%\\Cursors\\{folder}\\{filenames[k]}' for k in ROLES)
    lines=['[Version]','Signature="$Windows NT$"','','[DefaultInstall]','CopyFiles=CursorFiles','AddReg=CursorScheme','','[DestinationDirs]',f'CursorFiles=10,"Cursors\\{folder}"','','[CursorFiles]']
    lines.extend(f'"{filenames[k]}"' for k in ROLES)
    lines+=['','[CursorScheme]',f'HKCU,"Control Panel\\Cursors\\Schemes","{theme.name}",0x00000000,"{mapping}"','']
    return '\r\n'.join(lines).encode('utf-16')

INSTRUCTIONS='''# 安装与恢复

1. 将 ZIP 完整解压到一个新文件夹；不要直接在 ZIP 中打开 INF。
2. 先在 Windows 设置 → 蓝牙和设备 → 鼠标 → 其他鼠标设置 → 指针中，将当前方案“另存为”备份。
3. 右键 AutoSetup.inf → 显示更多选项 → 安装。此操作将文件复制到 Windows\\Cursors，可能要求管理员权限；只执行你信任的导出包。若用另一个管理员账户安装，方案可能注册在该账户，请在当前账户逐项浏览选择资源并另存为。
4. 打开鼠标属性 → 指针，在方案下拉框选择本主题，点击“应用”。安装 INF 只注册方案，不自动切换指针。
5. 若系统阻止 INF 安装，可将本目录移动到固定位置，在指针列表逐项“浏览”选择角色文件，最后“另存为”方案。
6. 恢复：在同一窗口选择先前另存的方案，点击“应用”。不要在仍被选用时删除资源。

![步骤图](安装步骤.svg)

角色文件名采用 Windows 标准键；NWPen 为手写，Hand 为链接选择。15 个角色顺序完全匹配 Windows 方案顺序。
ANI 时间以 1/60 秒为单位，编辑器毫秒值导出时就近量化，最少 1 tick。工程 JSON 保留原毫秒值。
Windows 可能根据 DPI、鼠标大小及辅助功能设置缩放指针。文件原生加载通过不等于已人工完成系统安装、切换和恢复验收。
参考主题版权属于原作者；请遵守其使用许可。
'''

def export_theme(theme,path,overwrite=False):
    path=Path(path).resolve()
    if path.suffix.lower()!='.zip':raise ValueError('主题包必须使用 .zip 扩展名')
    if path.exists() and not overwrite:raise FileExistsError(f'目标已存在：{path}')
    errors=validate_theme(theme)
    if errors:raise ValueError('\n'.join(errors))
    from cursor_studio.io.cur import encode_cur,decode_cur
    from cursor_studio.io.ani import encode_ani,decode_ani
    from cursor_studio.windows.native import validate_cursor_file
    filenames={};output=io.BytesIO()
    with tempfile.TemporaryDirectory(prefix='cursor-export-') as directory,zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for key in ROLES:
            frames=render_frames(theme,theme.roles[key]);animated=len(frames)>1
            data=(encode_ani if animated else encode_cur)(frames)
            (decode_ani if animated else decode_cur)(data)
            filename=key+('.ani' if animated else '.cur');filenames[key]=filename
            target=Path(directory)/filename;target.write_bytes(data)
            if os.name=='nt' and not validate_cursor_file(target):raise ValueError(f'Windows 无法加载 {filename}')
            archive.writestr(filename,data)
        archive.writestr('AutoSetup.inf',make_inf(theme,filenames))
        archive.writestr('安装说明.md',INSTRUCTIONS.encode('utf-8'))
        archive.writestr('安装步骤.svg','<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="180"><rect width="1000" height="180" fill="#f3f5fa"/><g font-family="Microsoft YaHei,sans-serif" font-size="22" fill="#22314b"><text x="24" y="60">① 解压 ZIP → ② 备份原方案 → ③ 右键 INF 安装</text><text x="24" y="120">④ 鼠标属性选择方案 → 应用　　恢复：选择原方案 → 应用</text></g></svg>'.encode('utf-8'))
    atomic_write(path,output.getvalue(),overwrite)
    return path
