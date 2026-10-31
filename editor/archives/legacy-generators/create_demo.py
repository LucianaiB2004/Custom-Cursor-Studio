"""Build original pixel-art demo assets and verify project/native export roundtrips.

All graphics are drawn from geometric primitives here; no reference-theme artwork
is used. Re-running requires --overwrite, so edited examples are not replaced
accidentally. This script does not install or activate any cursor scheme.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import zipfile

from PIL import Image, ImageDraw

EDITOR_ROOT = Path(__file__).resolve().parents[1]
ROOT = EDITOR_ROOT.parent
sys.path.insert(0, str(EDITOR_ROOT / 'src'))
from cursor_studio.models import Theme, Role, Frame, ROLES
from cursor_studio.services.project import save_project, load_project, atomic_write
from cursor_studio.services.export import export_theme
from cursor_studio.io.cur import decode_cur
from cursor_studio.io.ani import decode_ani
from cursor_studio.io.reference import reference_mapping
from cursor_studio.windows.native import validate_cursor_file

INK = '#26334b'
MINT = '#9be8d2'
WHITE = '#f7fffc'
CORAL = '#ec7693'


def canvas():
    image = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def arrow(blink=0):
    image, draw = canvas()
    points = [(4, 3), (4, 24), (10, 18), (14, 27), (19, 24), (14, 15), (24, 15)]
    draw.polygon(points, fill=MINT, outline=INK, width=2)
    draw.line([(6, 7), (6, 19)], fill=WHITE, width=1)
    if blink != 2:
        draw.rectangle((8, 11, 9, 12), fill=INK)
        draw.rectangle((12, 11, 13, 12), fill=INK)
    else:
        draw.line((8, 12, 9, 12), fill=INK)
        draw.line((12, 12, 13, 12), fill=INK)
    if blink:
        x, y = 25, 6
        radius = [0, 2, 3, 2][blink]
        draw.line((x-radius, y, x+radius, y), fill=CORAL, width=1)
        draw.line((x, y-radius, x, y+radius), fill=CORAL, width=1)
    return image


def line_arrow(draw, points, fill=MINT):
    draw.line(points, fill=INK, width=5)
    draw.line(points, fill=fill, width=3)


def resize_cursor(diagonal=False, reverse=False, vertical=False, both=False):
    image, draw = canvas()
    if diagonal:
        points = [(8, 8), (24, 24)]
        line_arrow(draw, points)
        for triangle in [[(6, 6), (16, 7), (7, 16)], [(26, 26), (16, 25), (25, 16)]]:
            draw.polygon(triangle, fill=MINT, outline=INK, width=2)
        if reverse: image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    else:
        line_arrow(draw, [(7, 16), (25, 16)])
        draw.polygon([(4, 16), (12, 9), (12, 23)], fill=MINT, outline=INK, width=2)
        draw.polygon([(28, 16), (20, 9), (20, 23)], fill=MINT, outline=INK, width=2)
        if vertical: image = image.transpose(Image.Transpose.ROTATE_90)
        if both:
            image.alpha_composite(image.transpose(Image.Transpose.ROTATE_90))
            ImageDraw.Draw(image).rectangle((14, 14, 18, 18), fill=MINT)
    return image


def role_art(key, step=0):
    image, draw = canvas()
    hotspot = (16, 16)
    if key in ('Arrow', 'Help', 'AppStarting'):
        image = arrow(step if key == 'AppStarting' else 0)
        draw = ImageDraw.Draw(image)
        hotspot = (4, 3)
        if key == 'Help':
            draw.rectangle((22, 18, 30, 28), fill=WHITE, outline=INK)
            draw.text((24, 18), '?', fill=INK)
    elif key == 'Wait':
        draw.ellipse((7, 7, 25, 25), fill=WHITE, outline=INK, width=2)
        draw.ellipse((11, 11, 21, 21), fill=INK)
        positions = [(16, 5), (27, 16), (16, 27), (5, 16)]
        for i, (x, y) in enumerate(positions):
            color = CORAL if i == step else MINT
            draw.polygon([(x, y-3), (x+3, y), (x, y+3), (x-3, y)], fill=color, outline=INK)
    elif key == 'Crosshair':
        for points in [[(16, 3), (16, 12)], [(16, 20), (16, 29)], [(3, 16), (12, 16)], [(20, 16), (29, 16)]]:
            line_arrow(draw, points)
        draw.rectangle((15, 15, 17, 17), fill=CORAL)
    elif key == 'IBeam':
        for points in [[(16, 5), (16, 27)], [(10, 5), (22, 5)], [(10, 27), (22, 27)]]:
            line_arrow(draw, points)
    elif key == 'NWPen':
        draw.polygon([(7, 25), (10, 17), (23, 4), (28, 9), (15, 22)], fill=MINT, outline=INK, width=2)
        draw.polygon([(7, 25), (10, 17), (15, 22)], fill=WHITE, outline=INK)
        hotspot = (7, 25)
    elif key == 'No':
        draw.ellipse((5, 5, 27, 27), fill=WHITE, outline=INK, width=2)
        draw.ellipse((7, 7, 25, 25), outline=CORAL, width=3)
        draw.line((9, 9, 23, 23), fill=CORAL, width=4)
    elif key.startswith('Size'):
        image = resize_cursor(diagonal=key in ('SizeNWSE', 'SizeNESW'), reverse=key == 'SizeNESW', vertical=key == 'SizeNS', both=key == 'SizeAll')
    elif key == 'UpArrow':
        draw.polygon([(16, 3), (5, 16), (12, 16), (12, 28), (20, 28), (20, 16), (27, 16)], fill=MINT, outline=INK, width=2)
        hotspot = (16, 3)
    elif key == 'Hand':
        draw.polygon([(10, 16), (10, 5), (14, 5), (14, 14), (17, 12), (20, 14), (23, 14), (27, 18), (26, 25), (21, 29), (14, 28), (7, 20), (7, 17)], fill=MINT, outline=INK, width=2)
        draw.line((17, 16, 17, 20), fill=INK)
        draw.line((21, 17, 21, 21), fill=INK)
        hotspot = (11, 5)
    return image.resize((64, 64), Image.Resampling.NEAREST), (hotspot[0]*2, hotspot[1]*2)


def png_bytes(image):
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--overwrite', action='store_true', help='明确允许替换已有示例输出')
    args = parser.parse_args()
    example_dir = ROOT / 'examples'
    if (example_dir / 'demo/theme.json').exists() and not args.overwrite:
        raise FileExistsError('示例工程已存在；如需重新生成，请明确传入 --overwrite')
    theme = Theme(name='薄荷星光', author='Custom Cursor Studio', description='由本仓库脚本绘制的原创像素示例。15 个角色均有对应图形；后台运行和忙状态各有四帧。可自由修改和使用。', canvas_size=64)
    durations = [400, 100, 100, 200]
    for key in ROLES:
        frames = []
        for step in range(4 if key in ('AppStarting', 'Wait') else 1):
            image, hotspot = role_art(key, step)
            frames.append(Frame(image, hotspot, durations[step] if key in ('AppStarting', 'Wait') else 100))
        theme.roles[key] = Role(frames=frames, size=64)
    atomic_write(example_dir/'source/arrow.png', png_bytes(theme.roles['Arrow'].frames[0].image), args.overwrite)
    for index, frame in enumerate(theme.roles['AppStarting'].frames):
        atomic_write(example_dir/f'source/blink/{index+1:02d}.png', png_bytes(frame.image), args.overwrite)
    atomic_write(example_dir/'source/blink/durations.json', json.dumps(durations).encode(), args.overwrite)
    project = save_project(theme, example_dir/'demo/theme.json', args.overwrite)
    reopened = load_project(project)
    for key in ROLES:
        before, after = theme.roles[key].frames, reopened.roles[key].frames
        assert len(before) == len(after)
        for original, restored in zip(before, after):
            assert original.image.tobytes() == restored.image.tobytes()
            assert original.hotspot == restored.hotspot
            assert original.duration_ms == restored.duration_ms
    archive = export_theme(reopened, example_dir/'demo-theme.zip', args.overwrite)
    native_results = []
    with tempfile.TemporaryDirectory(prefix='cursor-demo-verify-') as temp:
        target = Path(temp)
        with zipfile.ZipFile(archive) as package:
            expected = {key+('.ani' if key in ('AppStarting', 'Wait') else '.cur') for key in ROLES}
            actual = {name for name in package.namelist() if name.endswith(('.cur', '.ani'))}
            assert actual == expected and len(actual) == 15
            # All members are produced by our own exporter, never untrusted ZIPs.
            for name in package.namelist():
                (target/name).write_bytes(package.read(name))
            name, mapping, warnings = reference_mapping(target/'AutoSetup.inf')
            assert name == theme.name and set(mapping) == set(ROLES)
            for key in ROLES:
                path = mapping[key]
                data = path.read_bytes()
                frames = (decode_ani if path.suffix == '.ani' else decode_cur)(data)
                native_results.append({'role': key, 'file': path.name, 'native_load': validate_cursor_file(path), 'frames': len(frames), 'hotspots': [list(f.hotspot) for f in frames], 'durations_ms': [f.duration_ms for f in frames] if path.suffix == '.ani' else []})
    baseline = json.loads((EDITOR_ROOT/'evidence/original-sha256.json').read_text(encoding='utf-8'))
    changed = [name for name, digest in baseline.items() if hashlib.sha256((ROOT / json.loads((EDITOR_ROOT/'evidence/reference-locations.json').read_text('utf-8')).get(name,name)).read_bytes()).hexdigest() != digest]
    assert not changed, changed
    evidence = {'project': str(project.relative_to(ROOT)), 'archive': str(archive.relative_to(ROOT)), 'original_graphics': True, 'reference_artwork_used': False, 'project_pixel_hotspot_duration_roundtrip': True, 'cursor_files': 15, 'native_validation': native_results, 'original_reference_files_checked': len(baseline), 'original_reference_hashes_unchanged': not changed, 'installed_or_activated': False}
    (EDITOR_ROOT/'evidence/demo-verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Original demo: 15 roles, 2 four-frame ANI, JSON roundtrip and Windows native load passed; 36 original hashes unchanged.')


if __name__ == '__main__':
    main()
