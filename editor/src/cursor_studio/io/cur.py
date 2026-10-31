"""CUR directories and uncompressed Windows DIB images; no GUI dependencies."""
import io
import struct
from PIL import Image
from cursor_studio.models import Frame

MAX_FILE = 64 * 1024 * 1024
MAX_IMAGES = 256


def _dib(data: bytes, width: int, height: int) -> Image.Image:
    if len(data) < 40:
        raise ValueError('CUR 位图头被截断')
    header, w, double_h, planes, bits, compression = struct.unpack_from('<IiiHHI', data)
    if header not in (40, 108, 124) or len(data) < header:
        raise ValueError('不支持的 CUR DIB 头')
    if w != width or abs(double_h) != height * 2 or planes != 1:
        raise ValueError('CUR 位图尺寸与目录不符')
    if compression != 0 or bits not in (1, 4, 8, 24, 32):
        raise ValueError('仅支持未压缩 1/4/8/24/32 位 CUR 位图')
    colors_used = struct.unpack_from('<I', data, 32)[0]
    colors = (colors_used or (1 << bits)) if bits <= 8 else 0
    if colors > (1 << bits):
        raise ValueError('CUR 调色板大小非法')
    start = header + colors * 4
    stride = ((width * bits + 31) // 32) * 4
    mask_stride = ((width + 31) // 32) * 4
    mask_start = start + stride * height
    if mask_start + mask_stride * height > len(data):
        raise ValueError('CUR 像素或透明掩码被截断')
    palette = [tuple(data[header+i*4:header+i*4+3][::-1]) for i in range(colors)]
    pixels = []
    masks = []
    for y in range(height):
        row = height - 1 - y if double_h > 0 else y
        off = start + row * stride
        moff = mask_start + row * mask_stride
        for x in range(width):
            if bits == 32:
                b, g, r, a = data[off + x*4:off + x*4+4]
            elif bits == 24:
                b, g, r = data[off + x*3:off + x*3+3]
                a = 255
            else:
                if bits == 8: idx = data[off+x]
                elif bits == 4: idx = (data[off+x//2] >> (4 if x%2 == 0 else 0)) & 15
                else: idx = (data[off+x//8] >> (7-x%8)) & 1
                if idx >= colors:
                    raise ValueError('CUR 调色板索引越界')
                r, g, b = palette[idx]
                a = 255
            pixels.append((r, g, b, a))
            masks.append(bool(data[moff+x//8] & (0x80 >> (x%8))))
    # Legacy 32-bit cursors may contain an unused, entirely zero alpha plane.
    legacy_alpha = bits == 32 and not any(p[3] for p in pixels)
    pixels = [(r, g, b, 0 if masked else (255 if legacy_alpha else a))
              for (r,g,b,a), masked in zip(pixels, masks)]
    image = Image.new('RGBA', (width, height))
    image.putdata(pixels)
    return image


def decode_cur(data: bytes) -> list[Frame]:
    if not 6 <= len(data) <= MAX_FILE:
        raise ValueError('CUR 文件为空、被截断或超过 64 MiB')
    reserved, kind, count = struct.unpack_from('<HHH', data)
    if reserved != 0 or kind != 2 or not 1 <= count <= MAX_IMAGES:
        raise ValueError('不是合法的 CUR 文件，或图像数量超过限制')
    end_dir = 6 + count * 16
    if end_dir > len(data):
        raise ValueError('CUR 目录被截断')
    entries, ranges = [], []
    for i in range(count):
        wb, hb, colors, zero, x, y, size, offset = struct.unpack_from('<BBBBHHII', data, 6+i*16)
        w, h = wb or 256, hb or 256
        if zero or x >= w or y >= h or size == 0 or offset < end_dir or offset+size > len(data):
            raise ValueError('CUR 目录的热点、长度或偏移无效')
        if any(offset < b and offset+size > a for a,b in ranges):
            raise ValueError('CUR 图像数据区域重叠')
        ranges.append((offset, offset+size))
        entries.append((w,h,x,y,data[offset:offset+size]))
    result = []
    for w,h,x,y,payload in entries:
        if payload.startswith(b'\x89PNG\r\n\x1a\n'):
            if len(payload)<33 or payload[12:16]!=b'IHDR' or struct.unpack_from('>II',payload,16)!=(w,h):
                raise ValueError('CUR PNG 尺寸不符或头被截断')
            try:
                with Image.open(io.BytesIO(payload)) as im:
                    if im.size != (w,h) or getattr(im, 'n_frames', 1) != 1:
                        raise ValueError('CUR PNG 尺寸不符或包含动画')
                    image = im.convert('RGBA')
            except (OSError, SyntaxError) as e:
                raise ValueError('CUR PNG 图像损坏') from e
        else:
            image = _dib(payload,w,h)
        result.append(Frame(image, (x,y)))
    return result


def encode_cur(frames: list[Frame]) -> bytes:
    if not 1 <= len(frames) <= MAX_IMAGES:
        raise ValueError('CUR 必须包含 1–256 个分辨率条目')
    directory, payloads = [], []
    offset = 6 + len(frames)*16
    for frame in frames:
        w,h = frame.image.size
        x,y = frame.hotspot
        if not 1 <= w <= 256 or not 1 <= h <= 256:
            raise ValueError('CUR 尺寸必须在 1–256 像素内')
        if type(x) is not int or type(y) is not int or not 0 <= x < w or not 0 <= y < h:
            raise ValueError('点击热点必须在画布内且为整数')
        image = frame.image.convert('RGBA')
        # Bottom-up BGRA XOR bitmap followed by DWORD-aligned 1-bit AND mask.
        raw = image.tobytes('raw', 'BGRA')
        xor = b''.join(raw[row*w*4:(row+1)*w*4] for row in reversed(range(h)))
        mask_stride = ((w+31)//32)*4
        mask = bytearray(mask_stride*h)
        alpha = image.getchannel('A').tobytes()
        for yrow in range(h):
            for col in range(w):
                if alpha[yrow*w+col] == 0:
                    mask[(h-1-yrow)*mask_stride+col//8] |= 0x80 >> (col%8)
        header = struct.pack('<IiiHHIIiiII',40,w,h*2,1,32,0,len(xor)+len(mask),0,0,0,0)
        payload = header+xor+bytes(mask)
        directory.append(struct.pack('<BBBBHHII',w%256,h%256,0,0,x,y,len(payload),offset))
        payloads.append(payload)
        offset += len(payload)
    data = struct.pack('<HHH',0,2,len(frames))+b''.join(directory)+b''.join(payloads)
    decode_cur(data)
    return data
