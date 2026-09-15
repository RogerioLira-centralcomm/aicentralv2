"""Typed text overlays; user text never enters an FFmpeg expression."""
from .studio_keyframes import normalize_keyframes, expression, transform_filters
import re
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def normalize_layers(raw):
    from .studio import number
    return [{
        'text': str(row.get('text') or '')[:200],
        'start': number(row.get('start'),0,0,1200),
        'end': number(row.get('end'),5,.1,1200),
        'x': number(row.get('x'),.5,0,1), 'y': number(row.get('y'),.8,0,1),
        'size': number(row.get('size'),.06,.02,.2),
        'color': row.get('color') if re.fullmatch(r'#[0-9a-fA-F]{6}',str(row.get('color') or '')) else '#ffffff',
        'animation': 'fade' if row.get('animation') == 'fade' else 'none',
        'hidden': row.get('hidden') is True,
        'keyframes': normalize_keyframes(row.get('keyframes')),
    } for row in (raw if isinstance(raw,list) else [])[:8] if isinstance(row,dict)]


def render_layers(source, dest, layers):
    import json
    result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','json',str(source)],check=True,capture_output=True,text=True,timeout=20)
    stream=json.loads(result.stdout)['streams'][0]; width,height=stream['width'],stream['height']
    font_path=Path(__file__).resolve().parents[1] / 'static/fonts/OpenSans-Regular.ttf'
    with tempfile.TemporaryDirectory(prefix='studio-layers-') as temp:
        command=['ffmpeg','-y','-v','error','-i',str(source)]
        active=[row for row in layers if row['text'] and not row['hidden'] and row['end']>row['start']]
        filters=[];last='0:v'
        for index,row in enumerate(active,1):
            animated=bool(row.get('keyframes'))
            canvas=Image.new('RGBA',(width,height));draw=ImageDraw.Draw(canvas)
            font=ImageFont.truetype(str(font_path),max(10,round(height*row['size'])))
            draw.multiline_text((round(width*(.5 if animated else row['x'])),round(height*(.5 if animated else row['y']))),row['text'],font=font,fill=row['color'],anchor='mm',align='center',stroke_width=1,stroke_fill='#000000')
            if animated:
                bbox=canvas.getbbox()
                if bbox:canvas=canvas.crop(bbox)
            path=Path(temp)/f'{index}.png';canvas.save(path)
            command+=['-loop','1','-i',str(path)]
            overlay=f'{index}:v'
            if row['animation']=='fade':
                fade=min(.3,(row['end']-row['start'])/2)
                filters.append(f'[{overlay}]format=rgba,fade=t=in:st={row["start"]}:d={fade}:alpha=1,fade=t=out:st={row["end"]-fade}:d={fade}:alpha=1[layer{index}]')
                overlay=f'layer{index}'
            x=y='0'
            if animated:
                frames=row['keyframes'];prefix=f'animated{index}'
                filters.extend(transform_filters(overlay,frames,prefix,row['start']));overlay=prefix
                x=f"W*({expression(frames,'x',offset=row['start'])})-w/2"
                y=f"H*({expression(frames,'y',offset=row['start'])})-h/2"
            filters.append(f"[{last}][{overlay}]overlay=x='{x}':y='{y}':enable='between(t,{row['start']},{row['end']})':shortest=1[v{index}]")
            last=f'v{index}'
        if not active:
            import shutil
            shutil.copyfile(source,dest)
            return
        command+=['-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map',f'[{last}]','-map','0:a?','-c:a','copy','-c:v','libx264','-crf','18','-preset','veryfast','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)]
        subprocess.run(command,check=True,capture_output=True,timeout=240)
