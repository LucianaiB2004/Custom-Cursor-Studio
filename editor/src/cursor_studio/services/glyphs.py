"""Shared high-resolution function glyphs for all 15 Windows cursor roles."""
import math
import os
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

EDGE=256

def glyph(key,step,color):
    im=Image.new('RGBA',(EDGE,EDGE));d=ImageDraw.Draw(im)
    ink='#302a40';white='#fffdfb'
    hot=(52,52)
    if key in ('Arrow','Help','AppStarting'):
        polygon=[(8,8),(8,105),(35,83),(57,125),(77,114),(55,73),(103,73)]
        d.line(polygon+[polygon[0]],fill=white,width=13,joint='curve')
        d.polygon(polygon,fill=color,outline=ink,width=5);hot=(8,8)
        if key=='Help':
            font=ImageFont.truetype(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/msyhbd.ttc'),50)
            d.text((77,71),'?',font=font,fill=ink,stroke_width=2,stroke_fill=white)
        if key=='AppStarting':d.arc((65,70,123,128),step*45,step*45+250,fill=ink,width=8)
    elif key=='Wait':
        d.ellipse((7,7,111,111),outline=white,width=13)
        d.arc((7,7,111,111),step*45,step*45+250,fill=color,width=9);hot=(59,59)
    elif key=='Crosshair':
        for fill,width in [(white,14),(ink,7)]:
            d.line((52,7,52,101),fill=fill,width=width);d.line((7,52,101,52),fill=fill,width=width)
        d.ellipse((40,40,64,64),outline=color,width=5)
    elif key=='IBeam':
        for fill,width in [(white,14),(ink,6)]:
            for line in [(52,8,52,104),(31,8,73,8),(31,104,73,104)]:d.line(line,fill=fill,width=width)
    elif key=='NWPen':
        d.polygon([(9,105),(19,72),(83,8),(106,31),(42,95)],fill=color,outline=ink,width=5)
        d.polygon([(9,105),(19,72),(42,95)],fill=white,outline=ink,width=4);hot=(9,105)
    elif key=='No':
        d.ellipse((7,7,108,108),fill=white,outline=ink,width=5)
        d.ellipse((19,19,96,96),outline='#e36e87',width=8)
        d.line((28,28,88,88),fill='#e36e87',width=10);hot=(57,57)
    elif key.startswith('Size'):
        segments=[]
        if key in ('SizeNS','SizeAll'):segments.append(((56,8),(56,104)))
        if key in ('SizeWE','SizeAll'):segments.append(((8,56),(104,56)))
        if key=='SizeNWSE':segments.append(((12,12),(100,100)))
        if key=='SizeNESW':segments.append(((12,100),(100,12)))
        for a,b in segments:
            d.line((a,b),fill=white,width=17);d.line((a,b),fill=ink,width=9)
            for tip,other in [(a,b),(b,a)]:
                dx,dy=other[0]-tip[0],other[1]-tip[1];length=math.hypot(dx,dy)
                ux,uy=dx/length,dy/length
                points=[tip,(round(tip[0]+ux*23-uy*16),round(tip[1]+uy*23+ux*16)),(round(tip[0]+ux*23+uy*16),round(tip[1]+uy*23-ux*16))]
                d.polygon(points,fill=color,outline=ink,width=4)
        hot=(56,56)
    elif key=='UpArrow':
        d.polygon([(56,7),(8,55),(37,55),(37,108),(75,108),(75,55),(104,55)],fill=color,outline=ink,width=5);hot=(56,7)
    elif key=='Hand':
        points=[(35,65),(35,12),(49,12),(49,57),(62,47),(74,57),(86,57),(107,75),(103,106),(85,121),(58,118),(22,83),(22,68)]
        d.line(points+[points[0]],fill=white,width=13,joint='curve');d.polygon(points,fill=color,outline=ink,width=5)
        d.line((66,67,66,86),fill=ink,width=4);d.line((83,71,83,91),fill=ink,width=4);hot=(40,12)
    return im,hot
