"""Skill CLI: locate Custom Cursor Studio and call its shared offline creator."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def find_workspace(explicit: str | None) -> Path:
    if explicit:
        root=Path(explicit).expanduser().resolve()
        if not (root/'editor/src/cursor_studio').is_dir():
            raise ValueError('--workspace 必须指向含 editor/src/cursor_studio 的仓库根目录')
        return root
    checked=set()
    for start in [Path.cwd(),Path(__file__).resolve().parent]:
        for root in [start,*start.parents]:
            if root in checked: continue
            checked.add(root)
            if (root/'editor/src/cursor_studio').is_dir(): return root
    raise ValueError('找不到编辑器仓库；请用 --workspace 指定 Custom Cursor Studio 根目录')


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description='由本地透明画稿创建可编辑 Windows 光标主题；不安装或应用系统指针')
    parser.add_argument('--workspace',help='Custom Cursor Studio 仓库根目录；技能安装到其他位置后也可显式指定')
    parser.add_argument('--name',help='新主题名称')
    parser.add_argument('--image',help='本地透明静态PNG母版，至少256像素，建议1024以上')
    parser.add_argument('--output',help='尚不存在的输出文件夹；默认<仓库>/<主题名>')
    parser.add_argument('--color',default='#f3a0b6',help='功能符号颜色，例如 #f3a0b6')
    parser.add_argument('--check',action='store_true',help='只检查仓库与离线创作依赖，不创建文件')
    args=parser.parse_args(argv)
    try:
        workspace=find_workspace(args.workspace)
        sys.path.insert(0,str(workspace/'editor/src'))
        from cursor_studio.services.creation import create_theme_bundle
        if args.check:
            print(json.dumps({'workspace':str(workspace),'offline_creator_ready':True,'system_changed':False},ensure_ascii=False))
            return 0
        if not args.name or not args.image:
            parser.error('创作时必须同时提供 --name 和 --image；仅检查时使用 --check')
        output=Path(args.output).expanduser().resolve() if args.output else workspace/args.name
        report=create_theme_bundle(name=args.name,image=Path(args.image).expanduser().resolve(),output=output,color=args.color)
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,ImportError) as error:
        print(f'无法创建主题：{error}',file=sys.stderr)
        if isinstance(error,ImportError):
            print('请使用仓库 .venv/Scripts/python.exe 运行；依赖未准备时先运行根目录启动编辑器.cmd。',file=sys.stderr)
        return 1


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr,'reconfigure'): sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
