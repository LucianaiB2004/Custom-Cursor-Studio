import json
from pathlib import Path
import pytest
from PIL import Image
from cursor_studio.services.library import discover_themes, open_theme_source
from cursor_studio.services.project import save_project
from cursor_studio.models import Theme, Frame, Role

ROOT = Path(__file__).resolve().parents[2]

def test_repository_themes_discovered_and_editable():
    found = {item.folder.name: item for item in discover_themes(ROOT)}
    for name in ['懒羊羊', '一二', '吹泡泡Dva', '月神天使']:
        theme, project = open_theme_source(found[name].folder)
        assert all(role.frames for role in theme.roles.values())
        assert project==ROOT/name/'project/theme.json'


def test_skills_collection_never_appears_as_a_user_theme(tmp_path):
    skills=tmp_path/'SKILLS';skills.mkdir()
    Image.new('RGBA',(32,32),'red').save(skills/'Arrow.png')
    assert discover_themes(tmp_path)==[]

def test_new_project_and_named_material_folder(tmp_path):
    project = tmp_path/'新增工程'
    theme = Theme(name='新增主题')
    theme.roles['Arrow'] = Role([Frame(Image.new('RGBA',(32,32),'red'),(7,8),125)])
    save_project(theme, project/'theme.json')
    material = tmp_path/'图片素材'
    material.mkdir()
    Image.new('RGBA',(48,48),'blue').save(material/'正常选择.png')
    Image.new('RGBA',(48,48),'green').save(material/'Help.png')
    found = discover_themes(tmp_path)
    assert {item.folder.name for item in found} == {'新增工程', '图片素材'}
    loaded, path = open_theme_source(project)
    assert loaded.roles['Arrow'].frames[0].hotspot == (7,8)
    assert path == (project/'theme.json').resolve()
    imported, path = open_theme_source(material)
    assert path is None and len(imported.roles['Help'].frames) == 1
    assert not imported.roles['Wait'].frames  # Never invent missing mappings.

def test_mapping_without_inf_and_traversal_rejected(tmp_path):
    from cursor_studio.io.cur import encode_cur
    folder = tmp_path/'新光标'
    folder.mkdir()
    (folder/'Arrow.cur').write_bytes(encode_cur([Frame(Image.new('RGBA',(32,32),'red'),(3,4))]))
    manifest = {'name':'新主题','roles':{'Arrow':'Arrow.cur'}}
    (folder/'theme-map.json').write_text(json.dumps(manifest),'utf-8')
    theme, path = open_theme_source(folder)
    assert theme.roles['Arrow'].frames[0].hotspot == (3,4)
    manifest['roles']['Arrow'] = '../Arrow.cur'
    (folder/'theme-map.json').write_text(json.dumps(manifest),'utf-8')
    with pytest.raises(ValueError, match='路径'):
        open_theme_source(folder)

def test_ambiguous_role_and_unknown_folder_reported(tmp_path):
    Image.new('RGBA',(32,32)).save(tmp_path/'Arrow.png')
    Image.new('RGBA',(32,32)).save(tmp_path/'正常选择.png')
    with pytest.raises(ValueError, match='重复|冲突'):
        open_theme_source(tmp_path)
    with pytest.raises(ValueError, match='识别'):
        open_theme_source(tmp_path/'empty')

def test_discovery_does_not_follow_external_symlink(tmp_path):
    outside = tmp_path/'outside'
    root = tmp_path/'repo'
    root.mkdir(); outside.mkdir()
    Image.new('RGBA',(32,32)).save(outside/'Arrow.png')
    try: (root/'linked').symlink_to(outside, target_is_directory=True)
    except OSError: pytest.skip('Windows symlink privilege unavailable')
    assert not discover_themes(root)

def test_unsupported_animation_duration_rejected_before_ui_load(tmp_path):
    from cursor_studio.io.ani import encode_ani
    (tmp_path/'Arrow.ani').write_bytes(encode_ani([Frame(Image.new('RGBA',(32,32)),(0,0),70000)]))
    with pytest.raises(ValueError,match='帧时间'):
        open_theme_source(tmp_path)

def test_frame_folder_order_and_imported_project_roundtrip(tmp_path):
    from cursor_studio.services.project import load_project
    folder=tmp_path/'素材'
    frames=folder/'Arrow'
    frames.mkdir(parents=True)
    Image.new('RGBA',(32,32),'blue').save(frames/'002.png')
    Image.new('RGBA',(32,32),'red').save(frames/'001.png')
    theme,source=open_theme_source(folder)
    assert source is None
    assert theme.roles['Arrow'].frames[0].image.getpixel((0,0))==(255,0,0,255)
    theme.roles['Arrow'].frames[0].hotspot=(7,8)
    theme.roles['Arrow'].frames[0].duration_ms=123
    path=tmp_path/'工程/theme.json'
    save_project(theme,path)
    reloaded=load_project(path)
    assert reloaded.roles['Arrow'].frames[0].hotspot==(7,8)
    assert reloaded.roles['Arrow'].frames[0].duration_ms==123
    assert reloaded.roles['Arrow'].frames[1].image.tobytes()==theme.roles['Arrow'].frames[1].image.tobytes()
