"""Select output size without baking and enlarging a low-resolution intermediate."""
import copy
from .render import number,validate_role

STANDARD_SIZE = 32
OUTPUT_SIZES = (32,48,64,96,128,256)


def size_label(size):
    return f'{size} px' + ('（标准版）' if size == STANDARD_SIZE else '')

def resize_theme(theme,size):
    number(size,16,256,'指针尺寸',True)
    result=copy.deepcopy(theme);result.canvas_size=size
    for key,role in theme.roles.items():
        old,_=validate_role(theme,role)
        selected=result.roles[key];selected.size=size
        for f in selected.frames:
            f.hotspot=tuple(min(size-1,round(v*size/old)) for v in f.hotspot)
        validate_role(result,selected)
    return result
