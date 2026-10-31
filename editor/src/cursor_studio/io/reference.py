"""Read INF cursor mappings as inert data. Never installs or executes anything."""
import csv
import re
from pathlib import Path, PureWindowsPath
from cursor_studio.models import Theme, Role, ROLES
from .cur import decode_cur
from .ani import decode_ani


def read_inf(path: Path) -> tuple[str, dict[str,list[str]]]:
    raw=path.read_bytes()
    if len(raw)>1024*1024: raise ValueError('INF 超过 1 MiB')
    for encoding in ('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig','gb18030'):
        try:
            text=raw.decode(encoding)
            break
        except UnicodeError:
            continue
    else:
        raise ValueError('无法识别 INF 文本编码')
    sections={}
    current=''
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith((';','//')): continue
        if line.startswith('[') and line.endswith(']'):
            current=line[1:-1].casefold()
            sections.setdefault(current,[])
        elif current:
            sections[current].append(line)
    return text,sections


def reference_mapping(path: Path) -> tuple[str,dict[str,Path],list[str]]:
    path=Path(path)
    if path.is_dir():
        candidates=list(path.glob('*.inf'))
        preferred=[p for p in candidates if p.name.casefold()=='autosetup.inf']
        if len(preferred)==1: path=preferred[0]
        elif len(candidates)==1: path=candidates[0]
        else: raise ValueError('主题目录需要一份明确的 AutoSetup.inf')
    if path.suffix.casefold()!='.inf': raise ValueError('参考主题应为目录或 INF 文件')
    text,sections=read_inf(path)
    strings={}
    for line in sections.get('strings',[]):
        if '=' in line:
            key,value=line.split('=',1)
            strings[key.strip().casefold()]=value.strip().strip('"')
    def expand(value):
        for _ in range(8):
            updated=re.sub(r'%([^%]+)%',lambda m:strings.get(m[1].casefold(),m[0]),value)
            if updated==value: return value
            value=updated
        raise ValueError('INF 字符串递归过深')
    mappings={}
    scheme_name=expand(strings.get('scheme_name',path.parent.name))
    scheme_values=[]
    for lines in sections.values():
        for line in lines:
            if not line.upper().startswith('HKCU,'): continue
            try: fields=next(csv.reader([line],skipinitialspace=True))
            except csv.Error as e: raise ValueError('INF 注册表映射格式无效') from e
            if len(fields)<5: continue
            key=fields[1].replace('/','\\').casefold()
            value_name=expand(fields[2])
            value=expand(fields[4])
            if key=='control panel\\cursors':
                role=next((k for k in ROLES if k.casefold()==value_name.casefold()),None)
                if role:
                    if role in mappings and mappings[role]!=value: raise ValueError(f'INF 对 {role} 有冲突映射')
                    mappings[role]=value
            elif key=='control panel\\cursors\\schemes':
                scheme_values.append((value_name,value))
    if not mappings and len(scheme_values)==1:
        scheme_name,value=scheme_values[0]
        values=value.split(',')
        if len(values)!=15: raise ValueError('INF 指针方案不是 15 状态映射')
        mappings=dict(zip(ROLES,values))
    files={}
    base=path.parent.resolve()
    for role,value in mappings.items():
        winpath=PureWindowsPath(value)
        if '..' in winpath.parts: raise ValueError('INF 引用包含路径穿越')
        leaf=winpath.name
        if '%' in leaf or winpath.suffix.casefold() not in ('.cur','.ani'):
            raise ValueError(f'{role} 指向不支持的光标文件')
        target=(base/leaf).resolve()
        if target.parent!=base or not target.is_file():
            raise ValueError(f'{role} 引用的文件不存在或超出主题目录：{leaf}')
        files[role]=target
    if not files: raise ValueError('INF 中未找到可识别的指针方案')
    warnings=[]
    if re.search(r'(?im)^HKLM\s*,',text): warnings.append('原 INF 含 HKLM 写入；仅读取映射，未执行')
    if re.search(r'(?i)runonce',text): warnings.append('原 INF 含 RunOnce；不会复制或执行该指令')
    return scheme_name,files,warnings


def import_reference(path: Path) -> Theme:
    name,files,warnings=reference_mapping(Path(path))
    theme=Theme(name=name,description='从参考主题只读导入；请遵守原作者授权。'+ ('；'.join(warnings)))
    for key,file in files.items():
        if file.stat().st_size>64*1024*1024: raise ValueError('光标文件超过 64 MiB')
        raw=file.read_bytes()
        if file.suffix.casefold()=='.ani': frames=decode_ani(raw)
        else: frames=[max(decode_cur(raw),key=lambda f:f.image.width*f.image.height)]
        width,height=frames[0].image.size
        if any(f.image.size!=(width,height) for f in frames):
            raise ValueError(f'{key} 动画帧画布尺寸不一致，请单独导入编辑')
        theme.roles[key]=Role(frames=frames,size=max(width,height))
    return theme
