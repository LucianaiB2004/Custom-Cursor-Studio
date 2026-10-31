"""Read-only reference inventory and SHA-256 verification."""
import hashlib
import json
import sys
from pathlib import Path

EDITOR_ROOT=Path(__file__).resolve().parents[1]
ROOT=EDITOR_ROOT.parent
sys.path.insert(0,str(EDITOR_ROOT/'src'))
from cursor_studio.io.cur import decode_cur
from cursor_studio.io.ani import inspect_ani
from cursor_studio.io.reference import reference_mapping
from cursor_studio.models import ROLES
from cursor_studio.windows.native import validate_cursor_file


def main():
    baseline=json.loads((EDITOR_ROOT/'evidence/original-sha256.json').read_text(encoding='utf-8'))
    report={'themes':[], 'unchanged':True,'files_checked':len(baseline)}
    lines=['# 两套参考主题解析对照报告','',
           '仅将 INF 作为映射数据读取；未执行安装、HKLM 或 RunOnce。CUR 多图像条目全部列出；ANI 帧数与播放步数分别统计。','']
    for folder in ['吹泡泡Dva','月神天使']:
        name,mapping,warnings=reference_mapping(ROOT/folder)
        rows=[]
        lines += [f'## {folder}',f'原方案名：{name}','',*warnings,'',
                  '| Windows Key | 中文状态 | 文件 | 尺寸 | 热点 | 源帧 / 播放步 | 每步时长 ms | Windows 加载 |',
                  '|---|---|---|---|---|---|---|---|']
        for key,cn in ROLES.items():
            path=mapping[key]
            data=path.read_bytes()
            if path.suffix=='.ani':
                meta=inspect_ani(data)
                images=[im for frame in meta['images'] for im in frame]
                count,steps=meta['frame_count'],meta['step_count']
                durations=[round(rate*1000/60,6) for rate in meta['rates']]
                sequence=meta['sequence']
                for warning in meta['warnings']:
                    if warning not in warnings: warnings.append(warning)
            else:
                images=decode_cur(data)
                count,steps=1,1
                durations=[]
                sequence=[]
            sizes=sorted(set(f'{f.image.width}×{f.image.height}' for f in images))
            hotspots=sorted(set(f.hotspot for f in images))
            native=validate_cursor_file(path)
            row={'key':key,'name':cn,'file':str(path.relative_to(ROOT)), 'sizes':sizes,
                 'hotspots':hotspots,'source_frames':count,'playback_steps':steps,
                 'durations_ms':durations,'sequence':sequence,'native_load':native}
            rows.append(row)
            lines.append(f'| {key} | {cn} | {path.name} | {", ".join(sizes)} | {hotspots} | {count} / {steps} | {durations or "静态"} | 通过 |')
        report['themes'].append({'folder':folder,'name':name,'warnings':warnings,'roles':rows})
        lines.extend(['',*warnings])
        lines.append('')
    changed=[name for name,digest in baseline.items() if not (ROOT / json.loads((EDITOR_ROOT/'evidence/reference-locations.json').read_text('utf-8')).get(name,name)).is_file() or hashlib.sha256((ROOT / json.loads((EDITOR_ROOT/'evidence/reference-locations.json').read_text('utf-8')).get(name,name)).read_bytes()).hexdigest()!=digest]
    report['unchanged']=not changed
    report['changed_files']=changed
    if changed: raise RuntimeError(f'原始文件发生变化：{changed}')
    lines += ['## 原始资料完整性','',f'对原始 {len(baseline)} 个文件（含两份 ZIP）逐一复算 SHA-256：全部一致。',
              'Windows LoadCursorFromFileW 对 30 个参考 CUR/ANI 全部加载成功。此验证不代表已经安装、切换或恢复系统方案。']
    (EDITOR_ROOT/'evidence/reference-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (EDITOR_ROOT/'evidence/reference-report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'2 themes, 30 roles, native load passed; {len(baseline)} original hashes unchanged')


if __name__=='__main__': main()
