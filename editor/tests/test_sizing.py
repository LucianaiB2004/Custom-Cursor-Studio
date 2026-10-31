from PIL import Image
from cursor_studio.models import Theme,Role,Frame
from cursor_studio.services.sizing import resize_theme
from cursor_studio.services.render import render_frames

def test_resize_preserves_hotspot_fraction_and_delays():
    t=Theme();t.roles['Arrow']=Role([Frame(Image.new('RGBA',(64,64),'red'),(12,20),150)],size=64)
    bigger=resize_theme(t,96)
    f=render_frames(bigger,bigger.roles['Arrow'])[0]
    assert f.image.size==(96,96) and f.hotspot==(18,30) and f.duration_ms==150
    assert t.roles['Arrow'].size==64 and t.roles['Arrow'].frames[0].hotspot==(12,20)

def test_role_independent_sizes_and_edge_hotspot():
    t=Theme();t.roles['Wait']=Role([Frame(Image.new('RGBA',(32,32)),(31,31),200)],size=32)
    b=resize_theme(t,128)
    assert b.roles['Wait'].frames[0].hotspot==(124,124)

def test_high_resolution_detail_is_not_lost_through_small_intermediate():
    image=Image.new('RGBA',(256,256))
    image.putdata([(255,255,255,255) if (x//2)%2 else (0,0,0,255) for y in range(256) for x in range(256)])
    t=Theme(canvas_size=64)
    t.roles['Arrow']=Role([Frame(image,(4,5),100)],size=64,interpolation='smooth')
    selected=resize_theme(t,128)
    output=render_frames(selected,selected.roles['Arrow'])[0].image
    direct=image.resize((128,128),Image.Resampling.LANCZOS)
    assert output.tobytes()==direct.tobytes()
    low,high=output.getextrema()[0]
    assert high-low>150
