import json
from pathlib import Path
import pytest
from PIL import Image
from cursor_studio.models import ROLES
from cursor_studio.services.project import load_project
from cursor_studio.services.sizing import resize_theme
from cursor_studio.services.render import render_frames
from cursor_studio.io.cur import decode_cur
from cursor_studio.io.ani import decode_ani

ROOT=Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('name',['懒羊羊','一二','吹泡泡Dva','月神天使'])
def test_hd_case_variants_and_true_master_detail(name):
    folder=ROOT/name
    with Image.open(folder/'artwork/高清母版.png') as master:
        assert min(master.size)>=1024 and master.mode=='RGBA'
        assert master.getextrema()[3][0]==0
    theme=load_project(folder/'project/theme.json')
    assert all(f.image.size==(256,256) for role in theme.roles.values() for f in role.frames)
    manifest=json.loads((folder/'theme-map.json').read_text('utf-8'))
    assert manifest['default_size']==96 and set(manifest['variants'])=={'64','96','128'}
    # The editable project can legitimately have a user's saved size/hotspots.
    # Shipped variants were built from the immutable 96px export baseline;
    # verify their cross-size mapping against that baseline, not user edits.
    theme=resize_theme(theme,96)
    for key,relative in manifest['variants']['96']['roles'].items():
        path=folder/relative
        baseline=(decode_ani if path.suffix=='.ani' else decode_cur)(path.read_bytes())
        assert len(baseline)==len(theme.roles[key].frames)
        for frame,reference in zip(theme.roles[key].frames,baseline):frame.hotspot=reference.hotspot
    for size in [64,96,128]:
        selected=resize_theme(theme,size)
        mapping=manifest['variants'][str(size)]['roles']
        assert set(mapping)==set(ROLES)
        for key,relative in mapping.items():
            path=folder/relative
            frames=(decode_ani if path.suffix=='.ani' else decode_cur)(path.read_bytes())
            expected=render_frames(selected,selected.roles[key])
            assert len(frames)==len(expected)
            for actual,source in zip(frames,expected):
                assert actual.image.size==(size,size)
                assert actual.hotspot==source.hotspot
                assert abs(actual.duration_ms-source.duration_ms)<=8.34 or path.suffix=='.cur'
