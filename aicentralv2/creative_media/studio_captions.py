"""Timed caption export with shared font and style settings."""
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


def render_captions(source, dest, captions, width, height, duration, fps, style=None):
    """Sparse PNG timeline works even on FFmpeg builds without libass."""
    import subprocess
    import tempfile
    from pathlib import Path
    from .studio_caption_style import caption_image
    events=sorted({0.,duration,*[max(0,min(duration,row[key])) for row in captions for key in ('start','end')]})
    with tempfile.TemporaryDirectory(prefix='cadu-captions-') as directory:
        root=Path(directory);lines=['ffconcat version 1.0'];last=None
        for index,(start,end) in enumerate(zip(events,events[1:])):
            text='\n'.join(row['text'] for row in captions if row['start']<=start<row['end'])
            image=caption_image(text,width,height,style)
            path=root/f'caption-{index}.png';image.save(path);last=path
            lines.extend([f"file '{path}'",f'option framerate {fps}',f'duration {end-start:.6f}'])
        if last:lines.extend([f"file '{last}'",f'option framerate {fps}'])
        manifest=root/'frames.txt';manifest.write_text('\n'.join(lines)+'\n')
        subprocess.run(['ffmpeg','-y','-v','error','-i',str(source),'-f','concat','-safe','0','-i',str(manifest),
            '-filter_complex_threads','1','-filter_complex','[0:v][1:v]overlay=eof_action=pass[v]',
            '-map','[v]','-map','0:a?','-t',str(duration),'-c:v','libx264','-preset','veryfast','-crf','20','-c:a','copy',str(dest)],
            check=True,capture_output=True,timeout=600)
