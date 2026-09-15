"""Timed captions with ASS control sequences escaped before FFmpeg."""
def ass_time(seconds):
    value=round(seconds*100)
    return f'{value//360000}:{value//6000%60:02}:{value//100%60:02}.{value%100:02}'


def write_ass(path, captions, width, height):
    size=round(height*.045)
    header=f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Open Sans,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,{round(width*.07)},{round(width*.07)},{round(height*.08)},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    lines=[]
    for row in captions:
        text=row['text'].replace('\\','\\\\').replace('{','\\{').replace('}','\\}').replace('\r','').replace('\n','\\N')
        lines.append(f"Dialogue: 0,{ass_time(row['start'])},{ass_time(row['end'])},Default,,0,0,0,,{text}")
    path.write_text(header+'\n'.join(lines),encoding='utf-8')


def render_captions(source, dest, captions, width, height, duration, fps):
    """Sparse PNG timeline works even on FFmpeg builds without libass."""
    import subprocess
    import tempfile
    from pathlib import Path
    from PIL import Image, ImageDraw, ImageFont
    font=ImageFont.truetype(str(Path(__file__).resolve().parents[1]/'static/fonts/OpenSans-Regular.ttf'),round(height*.045))
    events=sorted({0.,duration,*[max(0,min(duration,row[key])) for row in captions for key in ('start','end')]})
    with tempfile.TemporaryDirectory(prefix='cadu-captions-') as directory:
        root=Path(directory);lines=['ffconcat version 1.0'];last=None
        for index,(start,end) in enumerate(zip(events,events[1:])):
            image=Image.new('RGBA',(width,height));draw=ImageDraw.Draw(image)
            content=[]
            for row in captions:
                if not row['start']<=start<row['end']:continue
                for paragraph in row['text'].splitlines():
                    line=''
                    for word in paragraph.split():
                        candidate=f'{line} {word}'.strip()
                        if draw.textlength(candidate,font=font)>width*.86 and line:
                            content.append(line);line=word
                        else:line=candidate
                    content.append(line)
            text='\n'.join(content)
            if text:
                draw.multiline_text((width//2,round(height*.91)),text,font=font,anchor='md',align='center',fill='white',stroke_width=2,stroke_fill='black')
            path=root/f'caption-{index}.png';image.save(path);last=path
            lines.extend([f"file '{path}'",f'option framerate {fps}',f'duration {end-start:.6f}'])
        if last:lines.extend([f"file '{last}'",f'option framerate {fps}'])
        manifest=root/'frames.txt';manifest.write_text('\n'.join(lines)+'\n')
        subprocess.run(['ffmpeg','-y','-v','error','-i',str(source),'-f','concat','-safe','0','-i',str(manifest),
            '-filter_complex_threads','1','-filter_complex','[0:v][1:v]overlay=eof_action=pass[v]',
            '-map','[v]','-map','0:a?','-t',str(duration),'-c:v','libx264','-preset','veryfast','-crf','20','-c:a','copy',str(dest)],
            check=True,capture_output=True,timeout=600)
