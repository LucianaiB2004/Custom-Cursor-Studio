"""RIFF ACON animated cursor codec; rate values are 1/60 second jiffies."""
import math
import struct
from cursor_studio.models import Frame
from .cur import decode_cur, encode_cur, MAX_FILE

MAX_FRAMES = 512
MAX_STEPS = 2048
MAX_PIXELS = 16 * 1024 * 1024


def _chunks(data: bytes, start: int, end: int):
    while start < end:
        if start+8 > end:
            raise ValueError('ANI chunk 头被截断')
        tag, size = struct.unpack_from('<4sI',data,start)
        stop = start+8+size
        padded = stop+(size&1)
        if stop > end or padded > end:
            raise ValueError('ANI chunk 长度或填充越界')
        yield tag,data[start+8:stop]
        start = padded


def inspect_ani(data: bytes) -> dict:
    if not 12 <= len(data) <= MAX_FILE or data[:4] != b'RIFF' or data[8:12] != b'ACON':
        raise ValueError('不是合法的 RIFF/ACON 动画光标，或超过 64 MiB')
    warnings=[]
    riff_size=struct.unpack_from('<I',data,4)[0]
    if riff_size==len(data):
        warnings.append('历史 ANI 将 RIFF 长度写成文件总长；按实际文件边界只读解析，导出时修正')
    elif riff_size != len(data)-8:
        raise ValueError('ANI RIFF 长度不符')
    singleton = {}
    icons = []
    for tag,payload in _chunks(data,12,len(data)):
        if tag in (b'anih',b'rate',b'seq '):
            if tag in singleton:
                raise ValueError('ANI 存在重复控制 chunk')
            singleton[tag]=payload
        elif tag == b'LIST':
            if len(payload)<4:
                raise ValueError('ANI LIST 被截断')
            if payload[:4] == b'fram':
                for subtag,subpayload in _chunks(payload,4,len(payload)):
                    if subtag == b'icon':
                        if len(icons)>=MAX_FRAMES: raise ValueError('ANI 图像帧过多')
                        icons.append(subpayload)
    header = singleton.get(b'anih',b'')
    if len(header) != 36:
        raise ValueError('ANI 缺少正确的 anih 头')
    cb, count, steps, width, height, bits, planes, default_rate, flags = struct.unpack('<9I',header)
    if cb != 36 or not 1<=count<=MAX_FRAMES or not 1<=steps<=MAX_STEPS or count != len(icons):
        raise ValueError('ANI 帧数、步数或头大小无效')
    if not flags&1 or flags&~3:
        raise ValueError('仅支持 AF_ICON 格式 ANI')
    if not 1<=default_rate<=36000:
        raise ValueError('ANI 默认时长无效（每帧最多 10 分钟）')
    def integers(tag, expected):
        payload=singleton[tag]
        if len(payload)!=4*expected: raise ValueError('ANI rate/seq 长度不符')
        return list(struct.unpack(f'<{expected}I',payload))
    rates = integers(b'rate',steps) if b'rate' in singleton else [default_rate]*steps
    if any(not 1<=r<=36000 for r in rates):
        raise ValueError('ANI 帧时长为零或超出限制')
    if flags&2:
        if b'seq ' not in singleton: raise ValueError('ANI 声明了序列但缺少 seq')
        sequence=integers(b'seq ',steps)
    else:
        if steps != count: raise ValueError('无 seq 的 ANI 步数必须等于帧数')
        sequence=list(range(count))
        if b'seq ' in singleton:
            if integers(b'seq ',steps)!=sequence:
                raise ValueError('ANI 非顺序 seq 与 AF_SEQUENCE 标志不符')
            warnings.append('历史 ANI 含顺序 seq 但未设 AF_SEQUENCE；播放顺序与 Windows 默认一致')
    if any(i>=count for i in sequence):
        raise ValueError('ANI 序列索引越界')
    decoded=[]
    pixel_budget=0
    for blob in icons:
        entries=decode_cur(blob)
        pixel_budget+=sum(f.image.width*f.image.height for f in entries)
        if pixel_budget>MAX_PIXELS: raise ValueError('ANI 解码像素总量超过限制')
        decoded.append(entries)
    if sum(max(f.image.width*f.image.height for f in decoded[i]) for i in sequence)>MAX_PIXELS:
        raise ValueError('ANI 播放序列展开像素总量超过限制')
    return {'frame_count':count,'step_count':steps,'rates':rates,'sequence':sequence,
            'images':decoded,'default_rate':default_rate,'warnings':warnings}


def decode_ani(data: bytes) -> list[Frame]:
    meta=inspect_ani(data)
    result=[]
    for idx,rate in zip(meta['sequence'],meta['rates']):
        # Preserve the highest available resolution for editing.
        source=max(meta['images'][idx],key=lambda f:f.image.width*f.image.height)
        result.append(Frame(source.image.copy(),source.hotspot,rate*1000/60))
    return result


def _chunk(tag: bytes,payload: bytes) -> bytes:
    return tag+struct.pack('<I',len(payload))+payload+(b'\0' if len(payload)&1 else b'')


def encode_ani(frames: list[Frame]) -> bytes:
    if not 1<=len(frames)<=MAX_FRAMES:
        raise ValueError('ANI 必须包含 1–512 帧')
    rates=[]
    for frame in frames:
        ms=frame.duration_ms
        if isinstance(ms,bool) or not isinstance(ms,(int,float)) or not math.isfinite(ms) or not 0<ms<=600000:
            raise ValueError('动画帧时长必须大于零且不超过 10 分钟')
        rates.append(max(1,int(ms*60/1000+0.5)))
    count=len(frames)
    header=struct.pack('<9I',36,count,count,0,0,0,0,rates[0],3)
    icons=b''.join(_chunk(b'icon',encode_cur([frame])) for frame in frames)
    payload=(b'ACON'+_chunk(b'anih',header)+_chunk(b'rate',struct.pack(f'<{count}I',*rates))+
             _chunk(b'seq ',struct.pack(f'<{count}I',*range(count)))+_chunk(b'LIST',b'fram'+icons))
    data=b'RIFF'+struct.pack('<I',len(payload))+payload
    inspect_ani(data)
    return data
