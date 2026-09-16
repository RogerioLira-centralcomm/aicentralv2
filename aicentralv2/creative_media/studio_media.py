"""Brand-scoped imported clips and cached editorial media inspection."""
import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path

from flask import request, send_file, session
from ..creative_format_lab.studio_auth import studio_or_admin_required_api
from ..creative_format_lab.swap_csrf import trocr_csrf_required
from .studio import _api_root, _scope, _record, _write, probe, waveform_levels


def public_sounds():
    root = Path(__file__).resolve().parents[1] / 'static/audio/studio'
    return root, json.loads((root / 'catalog.json').read_text())


def resolve_clip(root, client, ident, service):
    if str(ident).startswith('upload:'):
        key = ident.split(':', 1)[1]
        _record(root, key, 'clip')
        return root / f'{key}.mp4'
    import re
    rows = service.load_format_lab_swap_library({'client_id': client, 'media': 'video'}, session.get('user_id'))
    clip = next((r for r in rows.get('items', []) if r.get('id') == ident), None)
    match = re.fullmatch(r'/(?:parametros|studio)/api/media/assets/([\w-]+)/content', str((clip or {}).get('video_url') or ''))
    if not match:
        raise ValueError('Abra um vídeo desta marca antes de editar.')
    source, _ = service.serve_media_asset(match.group(1))
    return Path(source)


def inspect_clip(source, root, client, ident):
    stat = source.stat()
    key = hashlib.sha256(f'{ident}:{stat.st_size}:{stat.st_mtime_ns}'.encode()).hexdigest()[:32]
    cache = root / f'inspect-{key}.json'
    if cache.exists():
        cached=json.loads(cache.read_text())
        if cached.get('has_audio') and not cached.get('waveform_levels'):
            levels=waveform_levels(source);cached['waveform']=levels['overview'];cached['waveform_levels']=levels;_write(cache,cached)
        return cached
    duration, streams = probe(source)
    if 'video' not in streams or not 0 < duration <= 300:
        raise ValueError('Use um vídeo com até 5 minutos.')
    frames = []
    for index in range(8):
        at = duration * index / 8
        dest = root / f'frame-{key}-{index}.jpg'
        subprocess.run(['ffmpeg','-y','-v','error','-ss',str(at),'-i',str(source),'-frames:v','1','-vf','scale=192:108:force_original_aspect_ratio=decrease,pad=192:108:(ow-iw)/2:(oh-ih)/2','-threads','1',str(dest)],check=True,capture_output=True,timeout=30)
        frames.append({'time': round(at, 3), 'url': f'{_api_root()}/format-lab/studio/frames/{key}/{index}?client_id={int(client)}'})
    levels=waveform_levels(source) if 'audio' in streams else {'overview':[],'medium':[],'detail':[]}
    row = {'duration': duration, 'has_audio': 'audio' in streams, 'frames': frames,
           'waveform': levels['overview'], 'waveform_levels':levels}
    _write(cache, row)
    return row


def register(blueprint):
    from .studio_tasks import register as register_tasks
    register_tasks(blueprint)
    from .studio_push import register as register_push
    register_push(blueprint)
    from .studio_delivery import register as register_delivery
    register_delivery(blueprint)
    blueprint.add_url_rule('/api/format-lab/studio/composition/exports', view_func=composition_export, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/jobs', view_func=job_list)
    blueprint.add_url_rule('/api/format-lab/studio/archive-clip', view_func=archive_clip, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/clips', view_func=clips, methods=['GET','POST'])
    blueprint.add_url_rule('/api/format-lab/studio/clips/<ident>/content', view_func=clip_content)
    blueprint.add_url_rule('/api/format-lab/studio/inspect', view_func=inspect, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/extract-audio', view_func=extract_audio, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/frames/<ident>/<int:index>', view_func=frame_content)


@studio_or_admin_required_api
@trocr_csrf_required
def clips():
    from ..creative_format_lab.swap_routes import _http
    execute, _, ok, _ = _http()
    def run():
        client = request.args.get('client_id') if request.method == 'GET' else request.form.get('client_id')
        root = _scope(client)
        if request.method == 'GET':
            return ok({'items': [json.loads(p.read_text()) for p in sorted(root.glob('clip-*.json'))]})
        upload = request.files.get('file')
        if not upload:
            raise ValueError('Escolha um vídeo.')
        ident = uuid.uuid4().hex
        source, dest = root / f'{ident}.upload', root / f'{ident}.mp4'
        try:
            size = 0
            with source.open('wb') as handle:
                while chunk := upload.stream.read(1024*1024):
                    size += len(chunk)
                    if size > 150*1024*1024:
                        raise ValueError('Envie um vídeo de até 150 MB.')
                    handle.write(chunk)
            duration, streams = probe(source)
            if 'video' not in streams or not 0 < duration <= 300:
                raise ValueError('Envie um vídeo de até 5 minutos.')
            subprocess.run(['ffmpeg','-y','-v','error','-protocol_whitelist','file,pipe','-format_whitelist','mov,matroska,webm','-i',str(source),'-map','0:v:0','-map','0:a:0?','-map_metadata','-1','-vf','scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',str(dest)],check=True,capture_output=True,timeout=240)
            meta = inspect_clip(dest, root, client, 'upload:'+ident)
            row = {'id':'upload:'+ident,'name':Path(upload.filename or 'Vídeo enviado').name[:120], 'duration':meta['duration'],'has_audio':meta['has_audio'],'video_url':f'{_api_root()}/format-lab/studio/clips/{ident}/content?client_id={int(client)}','poster_url':meta['frames'][0]['url'],'created_at':time.time()}
            _write(root / f'clip-{ident}.json', row)
            return ok(row)
        except (subprocess.SubprocessError, OSError) as error:
            dest.unlink(missing_ok=True)
            raise ValueError('Não foi possível preparar o vídeo. Use MP4, MOV ou WebM.') from error
        finally:
            source.unlink(missing_ok=True)
    return execute(run)


@studio_or_admin_required_api
def clip_content(ident):
    from ..creative_format_lab.swap_routes import _http
    execute, _, _, _ = _http()
    def run():
        root = _scope(request.args.get('client_id')); _record(root,ident,'clip')
        return send_file(root / f'{ident}.mp4',mimetype='video/mp4',conditional=True)
    return execute(run)


@studio_or_admin_required_api
@trocr_csrf_required
def inspect():
    from ..creative_format_lab.swap_routes import _http
    execute, body, ok, service = _http()
    def run():
        data=body(); root=_scope(data.get('client_id'))
        source=resolve_clip(root,data.get('client_id'),data.get('clip_id'),service())
        return ok(inspect_clip(source,root,data['client_id'],data['clip_id']))
    return execute(run)


@studio_or_admin_required_api
def frame_content(ident,index):
    from ..creative_format_lab.swap_routes import _http
    execute, _, _, _ = _http()
    def run():
        root=_scope(request.args.get('client_id')); _record(root,ident,'inspect')
        if not 0 <= index < 8:
            raise ValueError('Quadro inválido.')
        return send_file(root / f'frame-{ident}-{index}.jpg',mimetype='image/jpeg',conditional=True)
    return execute(run)


@studio_or_admin_required_api
@trocr_csrf_required
def extract_audio():
    from ..creative_format_lab.swap_routes import _http
    execute, body, ok, service = _http()
    def run():
        data=body(); client=data.get('client_id'); root=_scope(client)
        source=resolve_clip(root,client,data.get('clip_id'),service())
        duration, streams=probe(source)
        if 'audio' not in streams:
            raise ValueError('Este vídeo não contém uma faixa de áudio.')
        ident=uuid.uuid4().hex; dest=root / f'{ident}.m4a'
        subprocess.run(['ffmpeg','-y','-v','error','-i',str(source),'-map','0:a:0','-vn','-c:a','aac','-b:a','128k',str(dest)],check=True,capture_output=True,timeout=90)
        levels=waveform_levels(dest)
        row={'id':ident,'name':'Áudio extraído do vídeo','category':'voice','duration':duration,'waveform':levels['overview'],'waveform_levels':levels,'url':f'{_api_root()}/format-lab/studio/sounds/{ident}?client_id={int(client)}','created_at':time.time()}
        _write(root / f'sound-{ident}.json',row)
        return ok(row)
    return execute(run)


@studio_or_admin_required_api
@trocr_csrf_required
def archive_clip():
    from ..creative_format_lab.swap_routes import _http
    execute, body, ok, _ = _http()
    def run():
        data = body()
        root = _scope(data.get('client_id'))
        ident = str(data.get('clip_id') or '').removeprefix('upload:')
        path, _ = _record(root, ident, 'clip')
        # Keep source bytes for render jobs already in flight and saved revisions.
        path.replace(root / f'archived-clip-{ident}.json')
        return ok({'archived': True})
    return execute(run)


@studio_or_admin_required_api
def job_list():
    from ..creative_format_lab.swap_routes import _http
    from .public import job_payload
    from .studio import export_public
    from .studio_tasks import public as task_public
    execute, _, ok, service = _http()
    def run():
        client = request.args.get('client_id')
        root = _scope(client)
        repository = service()._format_lab()._media_repository()
        rows = [job_payload(row) for row in repository.list_jobs(int(client),session.get('user_id'))]
        exports = [export_public(json.loads(path.read_text())) for path in root.glob('export-*.json')]
        return ok({'items':rows, 'exports':sorted(exports,key=lambda r:r.get('created_at',0),reverse=True)[:50], 'tasks':sorted([task_public(json.loads(p.read_text())) for p in root.glob('task-*.json') if json.loads(p.read_text()).get('user_id')==session.get('user_id')],key=lambda row:row.get('created_at',0),reverse=True)[:50], 'background_supported':True})
    return execute(run)


@studio_or_admin_required_api
@trocr_csrf_required
def composition_export():
    from ..creative_format_lab.swap_routes import _http
    from .studio import _ID, _SLOTS, _POOL, _render_job, export_public
    from .studio_composition import normalize_composition, resolve_inputs
    from .jobs import worker_mode, wake_worker
    execute, body, ok, service = _http()
    def run():
        data=body();client=data.get('client_id');root=_scope(client)
        ident=str(data.get('request_id') or '')
        if not _ID.fullmatch(ident):raise ValueError('Identificador inválido.')
        composition=normalize_composition(data.get('composition'))
        if not composition['items']:raise ValueError('Adicione imagens ou vídeos à montagem.')
        path=root/f'export-{ident}.json'
        try:
            with path.open('x') as handle:json.dump({'id':ident,'status':'preparing','created_at':time.time()},handle)
        except FileExistsError:return ok(export_public(json.loads(path.read_text())))
        try:
            from .studio_delivery import reserve_delivery
            delivery=reserve_delivery(root,data,service(),composition['ratio'])
            sources,sounds=resolve_inputs(root,client,composition,service(),ident)
            _write(path,{'delivery':delivery,'id':ident,'status':'queued','created_at':time.time(),
                         'user_id':session.get('user_id'),'work':{'source':sources[0],'sound':'','edit':{},'composition':composition,'sources':sources,'sounds':sounds}})
            if worker_mode() in {'process','supervised'}:wake_worker()
            else:
                if not _SLOTS.acquire(blocking=False):raise ValueError('Há exportações em andamento. Tente novamente em instantes.')
                try:_POOL.submit(_render_job,root,ident,Path(sources[0]),{},None)
                except Exception:_SLOTS.release();raise
        except Exception as error:
            _write(path,{'id':ident,'status':'failed','created_at':time.time(),'error':str(error)[:300]})
            raise
        return ok({'id':ident,'status':'queued'})
    return execute(run)
