"""Deterministic, bounded editing composition compiled to FFmpeg by the server."""
from .studio_keyframes import normalize_keyframes, expression, transform_filters
import json
import subprocess
import tempfile
from pathlib import Path
from .studio import number, probe
from .studio_layers import normalize_layers, render_layers

TRANSITIONS={'cut','fade','fadeblack','slideleft','wipeleft'}


def normalize_composition(raw):
    raw=raw if isinstance(raw,dict) else {}
    items=[]
    for row in (raw.get('items') if isinstance(raw.get('items'),list) else [])[:30]:
        if not isinstance(row,dict):continue
        kind='image' if row.get('kind')=='image' else 'video'
        start=number(row.get('in'),0,0,300);end=number(row.get('out'),0,0,300)
        items.append({'id':str(row.get('id') or '')[:80],'asset_id':str(row.get('asset_id') or '')[:120],
            'kind':kind,'in':start,'out':end,'duration':number(row.get('duration'),4,.2,300),
            'speed':number(row.get('speed'),1,.25,4),'volume':number(row.get('volume'),1,0,1),
            'fit':'cover' if row.get('fit')=='cover' else 'contain',
            'keyframes':normalize_keyframes(row.get('keyframes')),
            'motion':'zoom' if row.get('motion')=='zoom' else 'none',
            'transition':row.get('transition') if row.get('transition') in TRANSITIONS else 'cut',
            'transition_duration':number(row.get('transition_duration'),.4,.1,2)})
    audio=[]
    for row in (raw.get('audio') if isinstance(raw.get('audio'),list) else [])[:8]:
        if not isinstance(row,dict):continue
        audio.append({'sound_id':str(row.get('sound_id') or '')[:32], 'start':number(row.get('start'),0,0,600),
            'in':number(row.get('in'),0,0,600),'duration':number(row.get('duration'),10,.1,600),
            'volume':number(row.get('volume'),.35,0,1),'muted':row.get('muted') is True,
            'fade_in':number(row.get('fade_in'),0,0,10),'fade_out':number(row.get('fade_out'),0,0,10),
            'loop':row.get('loop') is True})
    captions=[]
    for row in (raw.get('captions') if isinstance(raw.get('captions'),list) else [])[:500]:
        if not isinstance(row,dict):continue
        start=number(row.get('start'),0,0,600);end=number(row.get('end'),0,0,600)
        if end>start:captions.append({'start':start,'end':end,'text':str(row.get('text') or '')[:300]})
    return {'items':items,'audio':audio,'captions':captions,'layers':normalize_layers(raw.get('layers')),
            'ratio':raw.get('ratio') if raw.get('ratio') in {'16:9','9:16','1:1','4:5','3:4','4:3','21:9'} else '16:9',
            'resolution':1080 if raw.get('resolution')==1080 else 720,
            'fps':24 if raw.get('fps')==24 else 30}


def output_dimensions(composition):
    a,b=(int(x) for x in composition['ratio'].split(':'))
    short=composition['resolution']
    return (round(short*a/b/2)*2,short) if a>=b else (short,round(short*b/a/2)*2)


def run(command):
    subprocess.run(['ffmpeg','-y','-v','error','-threads','2',*command],check=True,capture_output=True,timeout=600)


def render_composition(composition, sources, sounds, dest):
    from .studio import _atempo
    if not composition['items']:raise ValueError('Adicione imagens ou vídeos à montagem.')
    if len(sources)!=len(composition['items']) or len(sounds)!=len(composition['audio']):raise ValueError('Ativos da montagem incompletos.')
    width,height=output_dimensions(composition);fps=composition['fps']
    with tempfile.TemporaryDirectory(prefix='cadu-compose-') as directory:
        temp=Path(directory);segments=[];lengths=[]
        for index,(item,source) in enumerate(zip(composition['items'],sources)):
            video=item['kind']=='video';duration,streams=probe(source) if video else (item['duration'],set())
            length=(min(item['out'] or duration,duration)-item['in'])/item['speed'] if video else item['duration']
            if length<.1 or length>300:raise ValueError('Um clipe tem um intervalo de corte inválido.')
            lengths.append(length)
            if sum(lengths)>600:raise ValueError('A montagem deve ter no máximo 10 minutos.')
            path=temp/f'segment-{index}.mp4';segments.append(path)
            command=(['-ss',str(item['in']),'-i',str(source)] if video else ['-loop','1','-framerate',str(fps),'-i',str(source)])
            native=video and 'audio' in streams
            if not native:command+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
            mode='increase' if item['fit']=='cover' else 'decrease'
            visual=f'scale={width}:{height}:force_original_aspect_ratio={mode}:force_divisible_by=2,'
            visual+=f'crop={width}:{height}' if mode=='increase' else f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2'
            visual+=f',setsar=1,setpts=(PTS-STARTPTS)/{item["speed"] if video else 1},fps={fps},format=yuv420p'
            if not video and item['motion']=='zoom':
                visual+=f",zoompan=z='min(1+on*0.08/{max(1,round(length*fps))},1.08)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps={fps}"
            audio=(f'asetpts=PTS-STARTPTS,{_atempo(item["speed"])},volume={item["volume"]},' if native else '')+f'apad,atrim=duration={length},aresample=48000,aformat=channel_layouts=stereo'
            command+=['-map','0:v:0','-map','0:a:0' if native else '1:a:0','-vf',visual,'-af',audio,'-t',str(length),'-c:v','libx264','-preset','veryfast','-crf','20','-c:a','aac',str(path)]
            run(command)
            if item.get('keyframes'):
                frames=item['keyframes'];animated=temp/f'animated-{index}.mp4'
                filters=[f'color=c=black:s={width}x{height}:r={fps}:d={length}[back]',*transform_filters('0:v',frames,'moving')]
                x=expression(frames,'x');y=expression(frames,'y')
                filters.append(f"[back][moving]overlay=x='W*({x})-w/2':y='H*({y})-h/2':shortest=1[v]")
                run(['-i',str(path),'-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','[v]','-map','0:a','-c:a','copy','-c:v','libx264','-preset','veryfast','-crf','20','-t',str(length),str(animated)])
                segments[-1]=animated
        merged=segments[0];total=lengths[0]
        for index in range(1,len(segments)):
            previous=composition['items'][index-1];next_path=temp/f'merge-{index}.mp4'
            transition=previous['transition'];overlap=min(previous['transition_duration'],lengths[index-1]/2,lengths[index]/2)
            if transition=='cut':
                filters='[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]';total+=lengths[index]
            else:
                filters=f'[0:v][1:v]xfade=transition={transition}:duration={overlap}:offset={total-overlap}[v];[0:a][1:a]acrossfade=d={overlap}:c1=tri:c2=tri[a]'
                total+=lengths[index]-overlap
            run(['-i',str(merged),'-i',str(segments[index]),'-filter_complex_threads','1','-filter_complex',filters,'-map','[v]','-map','[a]','-c:v','libx264','-preset','veryfast','-crf','20','-c:a','aac',str(next_path)])
            merged=next_path
        if composition['audio']:
            command=['-i',str(merged)];filters=['[0:a]anull[original]'];labels=['[original]']
            for index,(track,source) in enumerate(zip(composition['audio'],sounds),1):
                if track['loop']:command+=['-stream_loop','-1']
                command+=['-ss',str(track['in']),'-i',str(source)]
                length=min(track['duration'],max(.1,total-track['start']))
                volume=0 if track['muted'] else track['volume']
                filters.append(f'[{index}:a]asetpts=PTS-STARTPTS,atrim=duration={length},volume={volume},afade=t=in:d={min(track["fade_in"],length)},afade=t=out:st={max(0,length-track["fade_out"])}:d={min(track["fade_out"],length)},adelay={round(track["start"]*1000)}:all=1[a{index}]')
                labels.append(f'[a{index}]')
            filters.append(''.join(labels)+f'amix=inputs={len(labels)}:duration=first:normalize=0,alimiter=limit=.95[a]')
            mixed=temp/'mixed.mp4';run(command+['-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac','-t',str(total),str(mixed)]);merged=mixed
        if composition['layers']:
            layered=temp/'layers.mp4';render_layers(merged,layered,composition['layers']);merged=layered
        if composition['captions']:
            from .studio_captions import render_captions
            captioned=temp/'captioned.mp4'
            render_captions(merged,captioned,composition['captions'],width,height,total,fps)
            merged=captioned
        run(['-i',str(merged),'-map','0','-c','copy','-movflags','+faststart',str(dest)])
        return {'duration':total,'width':width,'height':height,'fps':fps}


def resolve_inputs(root, client, composition, service, ident):
    import base64
    from io import BytesIO
    from PIL import Image, ImageOps
    from .studio_media import resolve_clip, public_sounds
    from .studio import _record
    from flask import session
    rows=service.load_format_lab_swap_library({'client_id':client,'media':'still'},session.get('user_id')).get('items',[])
    images={row['id']:row for row in rows}
    sources=[]
    for index,item in enumerate(composition['items']):
        if item['kind']=='video':sources.append(str(resolve_clip(root,client,item['asset_id'],service)));continue
        row=images.get(item['asset_id'])
        if not row:raise ValueError('Uma imagem da montagem não está na biblioteca desta marca.')
        reference=service._format_lab()._trocr_store().materialize_reference(row.get('image_url') or row.get('image') or '')
        if not str(reference).startswith('data:'):raise ValueError('Não foi possível preparar a imagem da montagem.')
        image=ImageOps.exif_transpose(Image.open(BytesIO(base64.b64decode(reference.split(',',1)[1])))).convert('RGB')
        image.thumbnail((3840,3840));path=root/f'compose-{ident}-{index}.jpg';image.save(path,quality=95)
        sources.append(str(path))
    sounds=[];catalog_root,catalog=public_sounds();public={r['id']:r for r in catalog}
    for track in composition['audio']:
        if track['sound_id'] in public:sounds.append(str(catalog_root/public[track['sound_id']]['filename']))
        else:
            _record(root,track['sound_id'],'sound');sounds.append(str(root/f"{track['sound_id']}.m4a"))
    return sources,sounds
