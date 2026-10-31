"""Contact sheet from delivered CUR/ANI pixels, at their actual output sizes."""
import json
import sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
EDITOR_ROOT=Path(__file__).resolve().parents[1]
ROOT=EDITOR_ROOT.parent
sys.path.insert(0,str(EDITOR_ROOT/'src'))
from cursor_studio.io.cur import decode_cur
from cursor_studio.io.ani import decode_ani

def main():
    board=Image.new('RGB',(1100,1130),'#f4f2f8');draw=ImageDraw.Draw(board)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
    title=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc',25)
    draw.text((28,18),'四套高清案例 · 母版与真实 CUR / ANI 输出',font=title,fill='#353044')
    for row,name in enumerate(['懒羊羊','一二','吹泡泡Dva','月神天使']):
        y=68+row*262;folder=ROOT/name
        draw.rounded_rectangle((18,y,1082,y+247),radius=16,fill='white')
        draw.text((36,y+12),name,font=title,fill='#353044')
        artwork=Image.open(folder/'artwork/高清母版.png').convert('RGBA')
        artwork.thumbnail((172,172),Image.Resampling.LANCZOS)
        board.paste(artwork,(115-artwork.width//2,y+54+(172-artwork.height)//2),artwork)
        draw.text((45,y+222),'新生成的透明母版',font=font,fill='#777080')
        manifest=json.loads((folder/'theme-map.json').read_text('utf-8'))
        for col,size in enumerate([64,96,128]):
            x=275+col*260
            draw.rounded_rectangle((x,y+54,x+224,y+218),radius=10,fill='#eeedf2' if col%2==0 else '#363943')
            path=folder/manifest['variants'][str(size)]['roles']['Arrow']
            frame=(decode_ani if path.suffix=='.ani' else decode_cur)(path.read_bytes())[0]
            board.paste(frame.image,(x+(224-size)//2,y+54+(164-size)//2),frame.image)
            draw.text((x+65,y+222),f'{size} × {size} px',font=font,fill='#777080')
    board.save(EDITOR_ROOT/'evidence/高清案例对照.png')

if __name__=='__main__':main()
