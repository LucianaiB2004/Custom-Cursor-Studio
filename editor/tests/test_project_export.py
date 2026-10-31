import json
import zipfile
import pytest
from PIL import Image
from cursor_studio.models import Frame, Role, Theme, ROLES
from cursor_studio.services.project import save_project, load_project
from cursor_studio.services.render import render_frames
from cursor_studio.services.export import export_theme, validate_theme

def sample():
    theme = Theme(name='中文狐狸', author='作者')
    theme.roles['Arrow'] = Role([Frame(Image.new('RGBA',(4,2),(255,0,0,128)),(3,2),125.0)], size=8)
    return theme

def test_roundtrip_preserves_source_and_metadata(tmp_path):
    t=sample(); p=tmp_path/'project.json'; save_project(t,p)
    r=load_project(p)
    assert r.name=='中文狐狸'
    assert r.roles['Arrow'].frames[0].image.tobytes()==t.roles['Arrow'].frames[0].image.tobytes()
    assert r.roles['Arrow'].frames[0].hotspot==(3,2)
    assert r.roles['Arrow'].frames[0].duration_ms==125
    with pytest.raises(FileExistsError): save_project(t,p)
    assert all(not f['asset'].startswith('/') for f in json.loads(p.read_text('utf-8'))['roles']['Arrow']['frames'])

def test_render_letterbox_opacity_hotspot():
    t=sample(); role=t.roles['Arrow']; role.opacity=.5
    out=render_frames(t,role)[0]
    assert out.image.size==(8,8)
    assert out.image.getpixel((0,0))[3]==0
    assert out.image.getpixel((0,2))==(255,0,0,64)
    assert out.hotspot==(3,2)
    role.frames[0].hotspot=(8,0)
    with pytest.raises(ValueError): render_frames(t,role)

@pytest.mark.parametrize('asset',['../outside.png','C:\\outside.png','/tmp/a.png','assets/../../x.png'])
def test_reject_traversal(tmp_path,asset):
    p=tmp_path/'t.json';save_project(sample(),p)
    d=json.loads(p.read_text('utf-8'));d['roles']['Arrow']['frames'][0]['asset']=asset;p.write_text(json.dumps(d),'utf-8')
    with pytest.raises(ValueError):load_project(p)

def test_missing_blocks_export(tmp_path):
    t=sample(); assert any('Help' in x for x in validate_theme(t))
    with pytest.raises(ValueError):export_theme(t,tmp_path/'x.zip')
    assert not (tmp_path/'x.zip').exists()

def test_complete_package_mapping_and_conflict(tmp_path):
    t=sample()
    for key in ROLES:t.roles[key]=Role([Frame(Image.new('RGBA',(8,8),'red'),(1,2),100)],size=8)
    t.roles['Wait'].frames*=4
    p=export_theme(t,tmp_path/'theme.zip')
    with zipfile.ZipFile(p) as z:
        names=z.namelist(); assert sum(n.endswith(('.cur','.ani')) for n in names)==15
        inf=z.read('AutoSetup.inf').decode('utf-16')
        assert '中文狐狸' in inf and 'RunOnce' not in inf and 'HKLM' not in inf
        assert 'Wait.ani' in inf
        for name in names:
            if name.endswith(('.cur','.ani')):assert name in inf
    with pytest.raises(FileExistsError):export_theme(t,p)

@pytest.mark.parametrize('name',['bad"name','bad%10%','bad\nname','bad,name'])
def test_reject_inf_injection(tmp_path,name):
    t=sample();t.name=name
    assert validate_theme(t)

def test_reject_invalid_project_type(tmp_path):
    p=tmp_path/'t.json';save_project(sample(),p)
    d=json.loads(p.read_text('utf-8'));d['canvas_size']=True;p.write_text(json.dumps(d),'utf-8')
    with pytest.raises(ValueError):load_project(p)

def test_resave_keeps_previous_assets_and_no_pixel_loss(tmp_path):
    t=sample();p=tmp_path/'project.json';save_project(t,p)
    before=set((tmp_path/'assets').iterdir())
    t.roles['Arrow'].frames[0].image.putpixel((0,0),(0,255,0,17))
    save_project(t,p,overwrite=True)
    assert before.issubset(set((tmp_path/'assets').iterdir()))
    assert load_project(p).roles['Arrow'].frames[0].image.getpixel((0,0))==(0,255,0,17)

def test_failed_save_keeps_existing_json(tmp_path):
    t=sample();p=tmp_path/'project.json';save_project(t,p);before=p.read_bytes()
    t.roles['Arrow'].frames[0].hotspot=(999,0)
    with pytest.raises(ValueError):save_project(t,p,overwrite=True)
    assert p.read_bytes()==before

def test_cover_crop_alignment_and_override():
    t=sample();r=t.roles['Arrow'];r.fit='cover';r.size=4;r.alignment='top-left';r.scale=1
    r.frames[0].hotspot=(1,1)
    out=render_frames(t,r)[0]
    assert out.image.size==(4,4)
    assert out.image.getpixel((3,3))[3]==128
    assert r.frames[0].image.size==(4,2)

def test_reject_nonfinite_values(tmp_path):
    t=sample();t.scale=float('nan')
    with pytest.raises(ValueError):save_project(t,tmp_path/'p.json')

def test_reject_render_expansion_bomb():
    t=sample();r=t.roles['Arrow'];r.size=256
    r.frames=[Frame(Image.new('RGBA',(1,1)),(0,0),100)]*512
    with pytest.raises(ValueError):render_frames(t,r)
