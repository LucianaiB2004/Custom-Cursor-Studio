import struct
from pathlib import Path

import pytest
from PIL import Image

from cursor_studio.models import Frame, ROLES
from cursor_studio.io.cur import decode_cur, encode_cur
from cursor_studio.io.ani import decode_ani, encode_ani


def sample(size=32, duration=100):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    im.putpixel((3, 4), (120, 45, 67, 128))
    im.putpixel((5, 6), (200, 100, 50, 255))
    return Frame(im, (7, 9), duration)


def test_cur_header_and_rgba_hotspot_roundtrip():
    data = encode_cur([sample()])
    assert struct.unpack_from('<HHH', data) == (0, 2, 1)
    assert struct.unpack_from('<BBBBHHII', data, 6) == (32, 32, 0, 0, 7, 9, 4264, 22)
    decoded = decode_cur(data)
    assert decoded[0].hotspot == (7, 9)
    assert decoded[0].image.tobytes() == sample().image.tobytes()


def test_cur_multiple_resolutions_and_256():
    data = encode_cur([sample(32), sample(64), sample(256)])
    assert [f.image.size for f in decode_cur(data)] == [(32, 32), (64, 64), (256, 256)]


@pytest.mark.parametrize('mutation', ['offset', 'overlap', 'size', 'hotspot', 'truncate'])
def test_cur_rejects_invalid_directory(mutation):
    data = bytearray(encode_cur([sample(), sample(48)]))
    if mutation == 'offset': struct.pack_into('<I', data, 18, 3)
    if mutation == 'overlap': struct.pack_into('<I', data, 34, 38)
    if mutation == 'size': struct.pack_into('<I', data, 14, 2**31)
    if mutation == 'hotspot': struct.pack_into('<H', data, 10, 32)
    if mutation == 'truncate': data = data[:-10]
    with pytest.raises(ValueError): decode_cur(bytes(data))


def test_ani_four_frames_variable_rate_and_roundtrip():
    frames = [sample(duration=x) for x in [50, 100, 200, 150]]
    data = encode_ani(frames)
    assert data[:4] == b'RIFF' and data[8:12] == b'ACON'
    assert struct.unpack_from('<I', data, 4)[0] == len(data) - 8
    result = decode_ani(data)
    assert [f.duration_ms for f in result] == [50, 100, 200, 150]
    assert len(result) == 4 and result[3].hotspot == (7, 9)


def test_ani_nontrivial_sequence():
    frames = [sample(duration=x) for x in [50, 100, 200, 150]]
    frames[1].hotspot = (12, 13)
    data = bytearray(encode_ani(frames))
    pos = data.index(b'seq ') + 8
    struct.pack_into('<4I', data, pos, 1, 0, 1, 3)
    decoded = decode_ani(bytes(data))
    assert [f.hotspot for f in decoded] == [(12, 13), (7, 9), (12, 13), (7, 9)]
    assert [f.duration_ms for f in decoded] == [50, 100, 200, 150]


@pytest.mark.parametrize('mutation', ['seq', 'rate', 'length', 'frames', 'truncated'])
def test_ani_rejects_bad_sequence_rate_and_structure(mutation):
    data = bytearray(encode_ani([sample(), sample()]))
    if mutation == 'seq': struct.pack_into('<I', data, data.index(b'seq ') + 8, 2)
    if mutation == 'rate': struct.pack_into('<I', data, data.index(b'rate') + 8, 0)
    if mutation == 'length': struct.pack_into('<I', data, 4, len(data)+4)
    if mutation == 'frames': struct.pack_into('<I', data, data.index(b'anih') + 12, 8)
    if mutation == 'truncated': data = data[:-1]
    with pytest.raises(ValueError): decode_ani(bytes(data))


@pytest.mark.parametrize('duration', [0, -1, float('nan'), float('inf'), 10000000])
def test_ani_rejects_invalid_duration(duration):
    with pytest.raises(ValueError): encode_ani([sample(duration=duration)])


def test_reference_themes_have_all_roles():
    from cursor_studio.io.reference import import_reference
    root = Path(__file__).resolve().parents[2]
    for name in ['吹泡泡Dva', '月神天使']:
        theme = import_reference(root / name)
        assert list(theme.roles) == list(ROLES)
        assert all(r.frames for r in theme.roles.values())
        assert theme.roles['NWPen'].frames[0].image.size[0] > 0


def test_legacy_total_riff_size_and_identity_sequence_are_bounded():
    from cursor_studio.io.ani import inspect_ani
    data=bytearray(encode_ani([sample(),sample()]))
    struct.pack_into('<I',data,4,len(data))
    struct.pack_into('<I',data,data.index(b'anih')+40,1)
    meta=inspect_ani(bytes(data))
    assert len(meta['warnings'])==2
    assert len(decode_ani(bytes(data)))==2
    struct.pack_into('<I',data,data.index(b'seq ')+8,1)
    with pytest.raises(ValueError): decode_ani(bytes(data))


def test_palette_mask_and_png_cursor():
    import io
    # A hand-constructed 2x1, 8-bit DIB: red opaque, blue transparent.
    header=struct.pack('<IiiHHIIiiII',40,2,2,1,8,0,8,0,0,2,0)
    payload=header+bytes([0,0,255,0,255,0,0,0])+bytes([0,1,0,0])+bytes([0x40,0,0,0])
    raw=struct.pack('<HHH',0,2,1)+struct.pack('<BBBBHHII',2,1,2,0,1,0,len(payload),22)+payload
    image=decode_cur(raw)[0].image
    assert [image.getpixel((x,0)) for x in range(2)]==[(255,0,0,255),(0,0,255,0)]
    png=io.BytesIO()
    sample().image.save(png,format='PNG')
    payload=png.getvalue()
    raw=struct.pack('<HHH',0,2,1)+struct.pack('<BBBBHHII',32,32,0,0,7,9,len(payload),22)+payload
    assert decode_cur(raw)[0].image.getpixel((3,4))==(120,45,67,128)


def test_ani_rejects_expanded_memory_bomb():
    # Sequence repetition must be bounded before allocating copied images.
    data=bytearray(encode_ani([sample(256)]))
    # Construct a valid 2,048-step sequence from one 256x256 image.
    def chunk(tag,payload): return tag+struct.pack('<I',len(payload))+payload
    iconpos=data.index(b'LIST')
    header=struct.pack('<9I',36,1,2048,0,0,0,0,6,3)
    body=b'ACON'+chunk(b'anih',header)+chunk(b'seq ',bytes(2048*4))+bytes(data[iconpos:])
    data=b'RIFF'+struct.pack('<I',len(body))+body
    with pytest.raises(ValueError,match='像素'): decode_ani(data)


def test_generated_files_load_in_windows(tmp_path):
    import os
    if os.name!='nt': pytest.skip('Windows only')
    from cursor_studio.windows.native import validate_cursor_file
    for name,data in [('sample.cur',encode_cur([sample()])),('four.ani',encode_ani([sample(duration=x) for x in [50,100,200,150]]))]:
        path=tmp_path/name
        path.write_bytes(data)
        assert validate_cursor_file(path)


def test_cur_rejects_png_dimension_bomb_before_decode():
    # Directory is small, embedded PNG IHDR lies about a huge canvas.
    import zlib,io
    ihdr=struct.pack('>IIBBBBB',100000,100000,8,6,0,0,0)
    chunk=b'IHDR'+ihdr
    stream=io.BytesIO();sample().image.save(stream,format='PNG')
    payload=b'\x89PNG\r\n\x1a\n'+struct.pack('>I',len(ihdr))+chunk+struct.pack('>I',zlib.crc32(chunk))+stream.getvalue()[33:]
    raw=struct.pack('<HHH',0,2,1)+struct.pack('<BBBBHHII',32,32,0,0,0,0,len(payload),22)+payload
    with pytest.raises(ValueError): decode_cur(raw)


def test_native_hotspot_matches_serialized_coordinates(tmp_path):
    import os,ctypes
    from ctypes import wintypes
    if os.name!='nt': pytest.skip('Windows only')
    class ICONINFO(ctypes.Structure):
        _fields_=[('fIcon',wintypes.BOOL),('xHotspot',wintypes.DWORD),('yHotspot',wintypes.DWORD),('hbmMask',wintypes.HBITMAP),('hbmColor',wintypes.HBITMAP)]
    user32=ctypes.WinDLL('user32',use_last_error=True)
    user32.LoadCursorFromFileW.argtypes=[wintypes.LPCWSTR]
    user32.LoadCursorFromFileW.restype=wintypes.HANDLE
    user32.GetIconInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(ICONINFO)]
    user32.DestroyCursor.argtypes=[wintypes.HANDLE]
    gdi32=ctypes.WinDLL('gdi32',use_last_error=True)
    gdi32.DeleteObject.argtypes=[wintypes.HANDLE]
    path=tmp_path/'hotspot.cur';path.write_bytes(encode_cur([sample()]))
    handle=user32.LoadCursorFromFileW(str(path)); assert handle
    info=ICONINFO()
    try:
        assert user32.GetIconInfo(handle,ctypes.byref(info))
        assert not info.fIcon and (info.xHotspot,info.yHotspot)==(7,9)
    finally:
        if info.hbmMask: gdi32.DeleteObject(info.hbmMask)
        if info.hbmColor: gdi32.DeleteObject(info.hbmColor)
        user32.DestroyCursor(handle)
