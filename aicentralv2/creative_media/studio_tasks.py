"""Durable preparation and local transcription. HTTP only stages input bytes/IDs."""
import json
import os
import time
import uuid
import subprocess
from pathlib import Path
from flask import request, session, current_app
from ..creative_format_lab.studio_auth import studio_or_admin_required_api
from ..creative_format_lab.swap_csrf import trocr_csrf_required
from .studio import _scope, _record, _write, probe, waveform_levels


def public(row):
    return {key:row[key] for key in ('id','kind','status','created_at','stage','error','result') if key in row}


def register(bp):
    bp.add_url_rule('/api/format-lab/studio/tasks',view_func=submit,methods=['POST'])
    bp.add_url_rule('/api/format-lab/studio/tasks/<ident>',view_func=status)


@studio_or_admin_required_api
@trocr_csrf_required
def submit():
    from ..creative_format_lab.swap_routes import _http
    from .studio_media import resolve_clip
    from .studio_composition import normalize_composition, resolve_inputs
    from .jobs import wake_worker, worker_mode
    execute,body,ok,service=_http()
    def run():
        data=request.form if request.files else body()
        client=data.get('client_id');root=_scope(client);kind=data.get('kind')
        if kind not in {'import','inspect','extract','transcribe'}:raise ValueError('Operação de mídia inválida.')
        ident=uuid.uuid4().hex;work={};source=None
        if kind=='import':
            upload=request.files.get('file')
            if not upload:raise ValueError('Escolha um vídeo.')
            source=root/f'{ident}.upload';size=0
            try:
                with source.open('wb') as handle:
                    while chunk:=upload.stream.read(1024*1024):
                        size+=len(chunk)
                        if size>150*1024*1024:raise ValueError('Envie um vídeo de até 150 MB.')
                        handle.write(chunk)
            except Exception:
                source.unlink(missing_ok=True);raise
            from .studio_autocut import options
            try:cut_options=json.loads(data.get('autocut') or '{}')
            except (ValueError,TypeError):raise ValueError('Parâmetros de corte inválidos.')
            work={'source':str(source),'name':Path(upload.filename or 'Vídeo enviado').name[:120],'autocut':options(cut_options)}
        elif kind=='transcribe' and data.get('composition'):
            composition=normalize_composition(data['composition']);composition['captions']=[];composition['layers']=[]
            if not composition['items']:raise ValueError('Adicione uma mídia à sequência.')
            sources,sounds=resolve_inputs(root,client,composition,service(),ident)
            work={'composition':composition,'sources':sources,'sounds':sounds}
        else:
            source=resolve_clip(root,client,data.get('clip_id'),service())
            work={'source':str(source),'clip_id':data.get('clip_id')}
        row={'id':ident,'kind':kind,'status':'queued','created_at':time.time(),'user_id':session.get('user_id'),'client_id':int(client),'work':work}
        _write(root/f'task-{ident}.json',row)
        if worker_mode() in {'process','supervised'}:wake_worker()
        else:
            from .studio import _POOL
            app=current_app._get_current_object()
            def background():
                with app.app_context():run_task(root,ident)
            _POOL.submit(background)
        return ok(public(row))
    return execute(run)


@studio_or_admin_required_api
def status(ident):
    from ..creative_format_lab.swap_routes import _http
    execute,_,ok,_=_http()
    def run():
        _,row=_record(_scope(request.args.get('client_id')),ident,'task')
        if row.get('user_id')!=session.get('user_id'):raise ValueError('Tarefa indisponível.')
        return ok(public(row))
    return execute(run)


def transcribe(source):
    """Model is provisioned by the installer, never downloaded on an HTTP request."""
    try:from faster_whisper import WhisperModel
    except ImportError as error:raise ValueError('Transcrição não instalada no worker. Execute deploy/install_media_worker.sh.') from error
    model_path=os.getenv('MEDIA_TRANSCRIBE_MODEL_PATH')
    if not model_path or not Path(model_path).is_dir():raise ValueError('Modelo de transcrição não preparado no servidor.')
    model=WhisperModel(model_path,device='cpu',compute_type='int8',cpu_threads=2,local_files_only=True)
    segments,info=model.transcribe(str(source),beam_size=5,vad_filter=True,word_timestamps=True)
    rows=[];timed_words=[]
    for segment in segments:
        words=list(segment.words or [])
        timed_words.extend({'start':float(w.start),'end':float(w.end),'text':w.word.strip(),'probability':float(getattr(w,'probability',0))} for w in words)
        if not words:
            if segment.text.strip():rows.append({'start':round(float(segment.start),3),'end':round(float(segment.end),3),'text':segment.text.strip()[:300]})
            continue
        group=[]
        for word in words:
            if group and (word.end-group[0].start>4 or len(''.join(w.word for w in group))+len(word.word)>70):
                rows.append({'start':round(float(group[0].start),3),'end':round(float(group[-1].end),3),'text':''.join(w.word for w in group).strip()});group=[]
            group.append(word)
        if group:rows.append({'start':round(float(group[0].start),3),'end':round(float(group[-1].end),3),'text':''.join(w.word for w in group).strip()})
        if len(rows)>500:raise ValueError('Transcrição excede 500 legendas. Divida o projeto.')
    return {'captions':rows,'words':timed_words,'language':info.language}


def run_task(root,ident):
    from .studio_media import inspect_clip
    path=root/f'task-{ident}.json';row=json.loads(path.read_text());work=row['work'];source=Path(work['source']) if work.get('source') else None
    _write(path,{**row,'status':'processing'})
    try:
        kind=row['kind'];client=row['client_id']
        if kind=='import':
            _write(path,{**row,'status':'processing','stage':'Validando vídeo'})
            duration,streams=probe(source)
            if 'video' not in streams or not 0<duration<=300:raise ValueError('Envie um vídeo com até cinco minutos.')
            dest=root/f'{ident}.mp4'
            _write(path,{**row,'status':'processing','stage':'Preparando vídeo e áudio'})
            subprocess.run(['ffmpeg','-y','-v','error','-protocol_whitelist','file,pipe','-format_whitelist','mov,matroska,webm','-i',str(source),'-map','0:v:0','-map','0:a:0?','-map_metadata','-1','-vf','scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',str(dest)],check=True,capture_output=True,timeout=300)
            meta=inspect_clip(dest,root,client,'upload:'+ident)
            result={'id':'upload:'+ident,'name':work['name'],'duration':meta['duration'],'has_audio':meta['has_audio'],'video_url':f'/parametros/api/format-lab/studio/clips/{ident}/content?client_id={client}','poster_url':meta['frames'][0]['url'],'created_at':row['created_at']}
            if work.get('autocut',{}).get('enabled') and meta['has_audio']:
                _write(path,{**row,'status':'processing','stage':'Analisando pausas e fala'})
                try:
                    from .studio_autocut import analyze,silences
                    speech=transcribe(dest)
                    result['autocut']=analyze(meta['duration'],speech['words'],silences(dest,meta['duration'],work['autocut']['mode']),work['autocut'])
                except Exception:
                    result['autocut_warning']='Análise automática indisponível. O vídeo original está pronto para edição; confira a transcrição instalada no servidor.'
            elif work.get('autocut',{}).get('enabled'):
                result['autocut_warning']='Vídeo sem áudio: nenhum corte automático aplicado.'
            _write(root/f'clip-{ident}.json',result)
        elif kind=='inspect':result=inspect_clip(source,root,client,work['clip_id'])
        elif kind=='extract':
            duration,streams=probe(source)
            if 'audio' not in streams:raise ValueError('Este vídeo não contém áudio.')
            dest=root/f'{ident}.m4a'
            subprocess.run(['ffmpeg','-y','-v','error','-i',str(source),'-map','0:a:0','-vn','-c:a','aac','-b:a','128k',str(dest)],check=True,capture_output=True,timeout=120)
            levels=waveform_levels(dest)
            result={'id':ident,'name':'Áudio extraído do vídeo','category':'voice','duration':duration,'waveform':levels['overview'],'waveform_levels':levels,'url':f'/parametros/api/format-lab/studio/sounds/{ident}?client_id={client}','created_at':row['created_at']}
            _write(root/f'sound-{ident}.json',result)
        else:
            if work.get('composition'):
                from .studio_composition import render_composition
                source=root/f'transcribe-{ident}.mp4'
                render_composition(work['composition'],list(map(Path,work['sources'])),list(map(Path,work['sounds'])),source)
            if 'audio' not in probe(source)[1]:raise ValueError('Este vídeo não contém áudio para transcrever.')
            result=transcribe(source)
        _write(path,{**row,'status':'ready','result':result})
    except Exception as error:
        import logging
        logging.getLogger(__name__).exception('Media task failed: %s',ident)
        message=str(error) if isinstance(error,ValueError) else 'Não foi possível processar a mídia. Confira o arquivo e tente novamente.'
        _write(path,{**row,'status':'failed','error':message[:300]})
    finally:
        if row['kind']=='import' and source and source.exists():
            # Preserve the exact original upload, independent from the editing copy.
            source.replace(root/f'{ident}.original')
        if work.get('composition') and source:source.unlink(missing_ok=True)
