import io
import zipfile
from pathlib import Path
import pytest
from PIL import Image
from cursor_studio.io.importers import import_media, safe_extract_reference

def test_rgba_and_gif_delays(tmp_path):
    p = tmp_path / 'alpha.png'
    Image.new('RGBA', (32, 48), (10, 20, 30, 123)).save(p)
    f = import_media(p)[0]
    assert f.image.getpixel((0, 0)) == (10, 20, 30, 123)
    p = tmp_path / 'animation.gif'
    ims = [Image.new('RGB', (16, 16), c) for c in ['red','blue','green','yellow']]
    ims[0].save(p, save_all=True, append_images=ims[1:], duration=[40, 120, 250, 80], loop=0)
    frames = import_media(p)
    assert [f.duration_ms for f in frames] == [40, 120, 250, 80]
    assert len(frames) == 4

def test_apng_default_not_animation(tmp_path):
    p = tmp_path / 'a.png'
    ims = [Image.new('RGBA', (8, 8), c) for c in ['white', 'red', 'blue']]
    ims[0].save(p, save_all=True, append_images=ims[1:], default_image=True, duration=[50, 150])
    frames = import_media(p)
    assert len(frames) == 2
    assert [f.duration_ms for f in frames] == [50, 150]

@pytest.mark.parametrize('body', [
    '<image href="file:///C:/secret.png"/>', '<script>alert(1)</script>',
    '<rect fill="url(https://evil/x)"/>', '<animate attributeName="x"/>',
    '<use href="#a"/>', '<style>rect{fill:url(file:///a)}</style>',
])
def test_svg_active_content_rejected(tmp_path, body):
    p = tmp_path / 'evil.svg'
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg">'+body+'</svg>')
    with pytest.raises(ValueError): import_media(p)

def test_safe_svg_raster(tmp_path):
    p = tmp_path / 'safe.svg'
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="16" height="16" fill="red"/></svg>')
    f = import_media(p)[0]
    assert f.image.size == (32, 32)
    assert f.image.getpixel((2, 2)) == (255, 0, 0, 255)
    assert f.image.getpixel((31, 31))[3] == 0

@pytest.mark.parametrize('name', ['../evil.cur', '/evil.cur', 'C:/evil.cur', 'x/../../evil.cur', 'x\\..\\evil.cur'])
def test_zip_traversal(tmp_path, name):
    p = tmp_path / 'bad.zip'
    with zipfile.ZipFile(p, 'w') as z: z.writestr(name, b'1234')
    with pytest.raises(ValueError): safe_extract_reference(p, tmp_path/'out')

def test_zip_script_rejected(tmp_path):
    p = tmp_path / 'bad.zip'
    with zipfile.ZipFile(p, 'w') as z: z.writestr('setup.exe', b'1234')
    with pytest.raises(ValueError): safe_extract_reference(p, tmp_path/'out')

def test_corrupt_or_unsupported(tmp_path):
    p = tmp_path / 'x.png'; p.write_bytes(b'bad')
    with pytest.raises(ValueError): import_media(p)
    p = tmp_path / 'x.exe'; p.write_bytes(b'123')
    with pytest.raises(ValueError): import_media(p)

def test_oversize_rejected_before_decoding(tmp_path):
    p = tmp_path / 'big.png'
    Image.new('L', (4100, 2)).save(p)
    with pytest.raises(ValueError): import_media(p)
