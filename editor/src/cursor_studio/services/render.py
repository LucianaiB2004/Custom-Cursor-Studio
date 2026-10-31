import math
from PIL import Image
from cursor_studio.models import Frame

MAX_FRAMES = 512
MAX_PIXELS = 16_777_216

def number(value, low, high, label, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high or (integer and not isinstance(value, int)):
        raise ValueError(f'{label}必须在 {low}–{high} 范围内')
    return value

def validate_role(theme, role):
    size=number(role.size if role.size is not None else theme.canvas_size,1,256,'画布尺寸',True)
    scale=number(role.scale if role.scale is not None else theme.scale,.01,8,'缩放')
    number(role.opacity,0,1,'透明度')
    if role.interpolation not in ('nearest','smooth') or role.fit not in ('contain','cover') or role.alignment not in ('center','top-left','top-right','bottom-left','bottom-right'):
        raise ValueError('未知图像处理选项')
    if not isinstance(role.frames,list) or len(role.frames)>MAX_FRAMES:raise ValueError('帧数超出限制')
    if len(role.frames)*size*size>MAX_PIXELS:raise ValueError('输出动画总像素过大，请减少帧数或尺寸')
    total=0
    for f in role.frames:
        if not isinstance(f.image,Image.Image) or min(f.image.size)<1 or max(f.image.size)>4096:raise ValueError('素材尺寸非法或过大')
        total+=f.image.width*f.image.height
        if total>MAX_PIXELS:raise ValueError('动画总像素过大')
        number(f.duration_ms,1,60000,'帧时间')
        if not isinstance(f.hotspot,(tuple,list)) or len(f.hotspot)!=2:raise ValueError('热点必须有 X/Y 两个坐标')
        for v in f.hotspot:number(v,0,size-1,'热点',True)
    return size,scale

def render_frames(theme, role):
    size,scale=validate_role(theme,role)
    output=[]
    for f in role.frames:
        src=f.image.convert('RGBA')
        factor=(min if role.fit=='contain' else max)(size/src.width,size/src.height)*scale
        dimensions=(max(1,round(src.width*factor)),max(1,round(src.height*factor)))
        if max(dimensions)>4096 or dimensions[0]*dimensions[1]>MAX_PIXELS:raise ValueError('缩放后的素材过大')
        im=src.resize(dimensions,Image.Resampling.NEAREST if role.interpolation=='nearest' else Image.Resampling.LANCZOS)
        if role.opacity!=1:im.putalpha(im.getchannel('A').point(lambda a:round(a*role.opacity)))
        x=(size-im.width)//2;y=(size-im.height)//2
        if 'left' in role.alignment:x=0
        if 'right' in role.alignment:x=size-im.width
        if 'top' in role.alignment:y=0
        if 'bottom' in role.alignment:y=size-im.height
        canvas=Image.new('RGBA',(size,size));canvas.alpha_composite(im,(x,y))
        output.append(Frame(canvas,tuple(f.hotspot),f.duration_ms))
    return output
