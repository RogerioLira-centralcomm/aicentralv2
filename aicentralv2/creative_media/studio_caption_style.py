"""Shared caption catalog and deterministic raster styling; no system font fallback."""
import json
import re
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .studio import number

FONT_ROOT=Path(__file__).resolve().parents[1]/'static/fonts'

@lru_cache(maxsize=1)
def catalog():
    return json.loads((FONT_ROOT/'captions/styles.json').read_text())


def normalize_style(raw):
    raw=raw if isinstance(raw,dict) else {}
    preset=next((p for p in catalog()['presets'] if p['id']==raw.get('preset')),catalog()['presets'][0])
    s={**preset['style'],**raw};out={'preset':preset['id']}
    out['font']=s['font'] if any(f['id']==s['font'] for f in catalog()['fonts']) else 'open'
    for key,low,high in [('size',.02,.12),('x',0,1),('y',0,1),('outline',0,.15),('background_opacity',0,1)]:
        out[key]=number(s.get(key),preset['style'][key],low,high)
    for key in ['color','outline_color','background']:
        out[key]=s[key] if re.fullmatch(r'#[0-9a-fA-F]{6}',str(s.get(key))) else preset['style'][key]
    out['uppercase']=s.get('uppercase') is True
    out['align']=s.get('align') if s.get('align') in {'left','center','right'} else 'center'
    return out


def caption_image(text,width,height,raw=None):
    s=normalize_style(raw);image=Image.new('RGBA',(width,height));draw=ImageDraw.Draw(image)
    if not text.strip():return image
    text=text.upper() if s['uppercase'] else text
    font_file=next(f['file'] for f in catalog()['fonts'] if f['id']==s['font'])
    size=max(6,round(height*s['size']));max_width=width*.86
    def wrap(font):
        lines=[]
        for paragraph in text.split('\n'):
            line=''
            for word in paragraph.split():
                candidate=(line+' '+word).strip()
                if draw.textlength(candidate,font=font)<=max_width:line=candidate;continue
                if line:lines.append(line);line=''
                for char in word:
                    if line and draw.textlength(line+char,font=font)>max_width:lines.append(line);line=''
                    line+=char
            lines.append(line)
        return lines
    while True:
        font=ImageFont.truetype(str(FONT_ROOT/font_file),size);lines=wrap(font)
        pad=size*.3;line_height=size*1.3
        box_height=line_height*len(lines)+pad*2
        if box_height<=height*.94 or size<=6:break
        size-=1
    box_width=max(draw.textlength(line,font=font) for line in lines)+2*pad
    x=max(width*.02,min(width-box_width-width*.02,width*s['x']-box_width/2))
    y=max(height*.02,min(height-box_height-height*.02,height*s['y']-box_height/2))
    if s['background_opacity']:
        rgb=tuple(int(s['background'][i:i+2],16) for i in (1,3,5))
        draw.rounded_rectangle((x,y,x+box_width,y+box_height),radius=size*.15,fill=(*rgb,round(255*s['background_opacity'])))
    for i,line in enumerate(lines):
        text_width=draw.textlength(line,font=font)
        tx=x+pad if s['align']=='left' else x+box_width-pad-text_width if s['align']=='right' else x+(box_width-text_width)/2
        draw.text((tx,y+pad+size+i*line_height),line,font=font,anchor='ls',fill=s['color'],stroke_width=round(size*s['outline']),stroke_fill=s['outline_color'])
    return image
