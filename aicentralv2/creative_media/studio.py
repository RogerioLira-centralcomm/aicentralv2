"""Biblioteca privada de áudio e exportação de clipes do estúdio."""
from __future__ import annotations

import hashlib
from array import array
import logging
import json
import math
import re
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import request, session, send_file

from ..auth import admin_required_api
from ..creative_format_lab.swap_csrf import trocr_csrf_required
from .storage import media_root
from .transcode import ffmpeg_available

logger = logging.getLogger(__name__)

_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="studio-export")
_SLOTS = threading.BoundedSemaphore(2)
_MAX_UPLOAD = 25 * 1024 * 1024
_ID = re.compile(r"^[a-f0-9]{32}$")


def number(raw, default, low, high):
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = default
    return max(low, min(high, value)) if math.isfinite(value) else default


def normalize_edit(raw):
    from .studio_layers import normalize_layers
    data = raw if isinstance(raw, dict) else {}
    return {
        "layers": normalize_layers(data.get("layers")),
        "output_ratio": data.get("output_ratio") if data.get("output_ratio") in {"16:9","9:16","1:1","4:5","3:4","4:3","21:9"} else "",
        "start": number(data.get("start"), 0, 0, 300),
        "end": number(data.get("end"), 0, 0, 300),
        "speed": number(data.get("speed"), 1, .25, 4),
        "original_volume": number(data.get("original_volume"), 1, 0, 1),
        "sound_id": str(data.get("sound_id") or "")[:32],
        "sound_volume": number(data.get("sound_volume"), .35, 0, 1),
        "sound_offset": number(data.get("sound_offset"), 0, 0, 600),
        "fade_in": number(data.get("fade_in"), 0, 0, 10),
        "fade_out": number(data.get("fade_out"), 0, 0, 10),
        "loop": data.get("loop") is True,
        "video_fade_in": number(data.get("video_fade_in"), 0, 0, 10),
        "video_fade_out": number(data.get("video_fade_out"), 0, 0, 10),
        "grayscale": data.get("grayscale") is True,
        "flip": data.get("flip") is True,
    }


def probe(path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-format_whitelist", "mov,mp3,wav,ogg,flac,aac,matroska,webm", "-show_entries", "format=duration:stream=codec_type",
        "-of", "json", str(path),
    ], capture_output=True, text=True, check=True, timeout=20)
    data = json.loads(result.stdout)
    duration = number(data.get("format", {}).get("duration"), 0, 0, 36000)
    return duration, {row.get("codec_type") for row in data.get("streams", [])}


def waveform(path):
    result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-vn', '-ac', '1', '-ar', '1000', '-f', 's16le', '-'], capture_output=True, check=True, timeout=30)
    samples = array('h')
    samples.frombytes(result.stdout)
    if not samples:
        return []
    step = max(1, len(samples) // 96)
    peaks = [max(abs(value) for value in samples[i:i+step]) / 32768 for i in range(0, len(samples), step)][:96]
    scale = max(peaks) or 1
    return [round(value / scale, 3) for value in peaks]


def _write(path, data):
    temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False))
    temporary.replace(path)


def _scope(client):
    if not str(client or "").isdigit() or int(client) <= 0:
        raise ValueError("Escolha uma marca para abrir a biblioteca de sons.")
    # Same authentication boundary as the existing admin-only studio; files are brand scoped.
    key = hashlib.sha256(f"client:{int(client)}".encode()).hexdigest()[:32]
    root = media_root() / "studio" / key
    root.mkdir(parents=True, exist_ok=True)
    return root


def _record(root, ident, kind):
    if not _ID.fullmatch(str(ident or "")):
        raise ValueError("Arquivo inválido.")
    path = root / f"{kind}-{ident}.json"
    if not path.is_file():
        raise ValueError("Arquivo não encontrado nesta marca.")
    return path, json.loads(path.read_text())


def register_studio_routes(blueprint):
    from .studio_media import register
    register(blueprint)
    blueprint.add_url_rule('/api/format-lab/studio/agent/plan', view_func=studio_agent_plan, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/agent/narration', view_func=studio_agent_narration, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/projects', view_func=studio_projects, methods=['GET', 'POST'])
    blueprint.add_url_rule('/api/format-lab/studio/projects/<ident>', view_func=studio_project, methods=['GET', 'POST'])
    blueprint.add_url_rule('/api/format-lab/studio/capabilities', view_func=capabilities)
    blueprint.add_url_rule('/api/format-lab/studio/sounds', view_func=sounds, methods=['GET', 'POST'])
    blueprint.add_url_rule('/api/format-lab/studio/sounds/<ident>', view_func=sound_content)
    blueprint.add_url_rule('/api/format-lab/studio/exports', view_func=export_clip, methods=['POST'])
    blueprint.add_url_rule('/api/format-lab/studio/exports/<ident>', view_func=export_status)
    blueprint.add_url_rule('/api/format-lab/studio/exports/<ident>/content', view_func=export_content)


@admin_required_api
@trocr_csrf_required
def studio_agent_plan():
    from ..creative_format_lab.swap_routes import _http
    from ..services.openrouter_service import chat_completion
    from .studio_agent import plan_request
    execute, json_body, ok, _ = _http()
    def run():
        data = json_body()
        _scope(data.get('client_id'))
        return ok(plan_request(data.get('message'), data.get('context'), text_callable=chat_completion))
    return execute(run)


@admin_required_api
@trocr_csrf_required
def studio_agent_narration():
    from ..creative_format_lab.swap_routes import _http
    from ..services.openrouter_service import chat_completion
    from .studio_agent import suggest_narration
    execute, json_body, ok, _ = _http()
    def run():
        data = json_body()
        _scope(data.get('client_id'))
        return ok(suggest_narration(data.get('creative'), data.get('duration'), text_callable=chat_completion))
    return execute(run)


@admin_required_api
@trocr_csrf_required
def studio_projects():
    from ..creative_format_lab.swap_routes import _http
    from . import studio_projects as repository
    execute, json_body, ok, _ = _http()
    def run():
        store = _project_store(repository)
        if request.method == 'GET':
            client_id = request.args.get('client_id')
            root = _scope(client_id)
            if hasattr(store, 'import_legacy'):
                store.import_legacy(root, client_id)
            return ok({'items': store.listing(client_id, int(request.args.get('offset', 0)))})
        data = json_body()
        client_id = data.get('client_id')
        _scope(client_id)
        return ok(store.save(client_id, data.get('document')))
    return execute(run)


@admin_required_api
@trocr_csrf_required
def studio_project(ident):
    from flask import jsonify
    from ..creative_format_lab.swap_routes import _http
    from . import studio_projects as repository
    execute, json_body, ok, _ = _http()
    def run():
        if not _ID.fullmatch(ident):
            # PostgreSQL projects use UUIDs; local legacy projects use a compact hex id.
            try:
                uuid.UUID(ident)
            except ValueError:
                raise ValueError('Projeto inválido.')
        store = _project_store(repository)
        if request.method == 'GET':
            revision = request.args.get('revision')
            client_id = request.args.get('client_id')
            _scope(client_id)
            return ok(store.read(client_id, ident, int(revision) if revision else None))
        data = json_body()
        try:
            client_id = data.get('client_id')
            _scope(client_id)
            return ok(store.save(client_id, data.get('document'), ident, data.get('expected_revision')))
        except repository.RevisionConflict as error:
            return jsonify(success=False, error=str(error), code='revision_conflict'), 409
    return execute(run)


def _project_store(repository):
    """Use Postgres in the application; retain the file store only for test isolation."""
    from flask import current_app
    if current_app.testing or not current_app.config.get('STUDIO_PROJECTS_POSTGRES', False):
        class LocalStore:
            def listing(self, client_id, offset): return repository.listing(_scope(client_id), offset)
            def read(self, client_id, ident, revision=None): return repository.read(_scope(client_id), ident, revision)
            def save(self, client_id, document, project_id=None, expected_revision=0): return repository.save(_scope(client_id), document, project_id, expected_revision)
        return LocalStore()
    from .. import db
    connection = db.get_db()
    # The media schema is idempotent and carries the studio-project tables too.
    from .schema import ensure_schema
    ensure_schema(connection)
    return repository.PostgresProjectRepository(connection)


@admin_required_api
def capabilities():
    from flask import jsonify
    from . import settings
    from .planner import AUDIO_MODES, MOTION_PRESETS
    return jsonify(success=True, data={
        "model": settings.MODEL,
        "skills": {
            "single_image": {
                "id": "seedance-2-5-image-to-video",
                "label": "Seedance 2.5 · imagem para vídeo",
                "resolution": "720p",
                "duration_min": 4,
                "duration_max": 30,
                "native_audio": True,
                "aspect_ratio": "source_image",
                "supports_seed": False,
            }
        },
        "durations": [value for value in settings.DURATIONS if value <= settings.MAX_DURATION],
        "ratios": [*settings.SEEDANCE_RATIOS, "4:5"],
        "qualities": {"draft": settings.DRAFT_RESOLUTION, "production": settings.PRODUCTION_RESOLUTION},
        "audio_modes": AUDIO_MODES,
        "motion_presets": MOTION_PRESETS,
        "seed": {"min": 0, "max": 2147483647},
    })


@admin_required_api
@trocr_csrf_required
def sounds():
    from ..creative_format_lab.swap_routes import _http
    execute, _, ok, _ = _http()
    def run():
        client = request.args.get('client_id') if request.method == 'GET' else request.form.get('client_id')
        root = _scope(client)
        if request.method == 'GET':
            rows = sorted((json.loads(p.read_text()) for p in root.glob('sound-*.json')), key=lambda row: row.get('created_at', 0), reverse=True)
            from .studio_media import public_sounds
            return ok({"items": rows + public_sounds()[1]})
        if not ffmpeg_available():
            raise ValueError('O processamento de áudio não está disponível no servidor.')
        upload = request.files.get('file')
        if not upload:
            raise ValueError('Escolha um arquivo de áudio.')
        payload = upload.stream.read(_MAX_UPLOAD + 1)
        if not payload or len(payload) > _MAX_UPLOAD:
            raise ValueError('Envie um áudio de até 25 MB.')
        ident = uuid.uuid4().hex
        source = root / f'{ident}.upload'
        dest = root / f'{ident}.m4a'
        source.write_bytes(payload)
        try:
            duration, streams = probe(source)
            if 'audio' not in streams or 'video' in streams or not 0 < duration <= 600:
                raise ValueError('Envie somente áudio, com duração de até 10 minutos.')
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,mp3,wav,ogg,flac,aac,matroska,webm', '-i', str(source), '-vn', '-map_metadata', '-1',
                            '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2', str(dest)],
                           check=True, timeout=90, capture_output=True)
        except Exception as error:
            dest.unlink(missing_ok=True)
            raise ValueError('Não foi possível processar o áudio. Use MP3, WAV, M4A ou OGG de até 10 minutos.') from error
        finally:
            source.unlink(missing_ok=True)
        try:
            peaks = waveform(dest)
        except (subprocess.SubprocessError, OSError):
            peaks = []
        row = {'waveform': peaks, 'id': ident, 'name': str(upload.filename or 'Áudio').replace('\\', '/').split('/')[-1][:120],
               'duration': round(duration, 2), 'category': request.form.get('category') if request.form.get('category') in {'music', 'effect', 'ambient', 'voice'} else 'music',
               'url': f'/parametros/api/format-lab/studio/sounds/{ident}?client_id={int(client)}',
               'created_at': time.time()}
        _write(root / f'sound-{ident}.json', row)
        return ok(row)
    return execute(run)


@admin_required_api
def sound_content(ident):
    from ..creative_format_lab.swap_routes import _http
    execute, _, _, _ = _http()
    def run():
        root = _scope(request.args.get('client_id'))
        _record(root, ident, 'sound')
        return send_file(root / f'{ident}.m4a', mimetype='audio/mp4', conditional=True)
    return execute(run)


def render_clip(source, dest, edit, sound=None):
    duration, streams = probe(source)
    if 'video' not in streams:
        raise ValueError('O arquivo selecionado não é um vídeo.')
    start = edit['start']
    end = edit['end'] or duration
    end = min(end, duration)
    length = end - start
    if length < .1 or length > 300:
        raise ValueError('Escolha um intervalo de corte válido, de até 5 minutos.')
    speed = edit['speed']
    output_length = length / speed
    command = ['ffmpeg', '-y', '-v', 'error', '-ss', str(start), '-i', str(source)]
    if sound:
        if edit['loop']:
            command += ['-stream_loop', '-1']
        command += ['-ss', str(edit['sound_offset']), '-i', str(sound)]
    filters = []
    labels = []
    if 'audio' in streams and edit['original_volume'] > 0:
        filters += [f"[0:a]asetpts=PTS-STARTPTS,{_atempo(speed)},volume={edit['original_volume']},apad[original]"]
        labels += ['[original]']
    if sound:
        filters += [f"[1:a]asetpts=PTS-STARTPTS,volume={edit['sound_volume']},apad,atrim=duration={output_length},"
                    f"afade=t=in:d={min(edit['fade_in'], output_length)},"
                    f"afade=t=out:st={max(0, output_length-edit['fade_out'])}:d={min(edit['fade_out'], output_length)}[sound]"]
        labels += ['[sound]']
    command += ['-t', str(output_length)]
    if labels:
        filters += [''.join(labels) + f'amix=inputs={len(labels)}:normalize=0,alimiter=limit=0.95[audio]']
        command += ['-filter_complex', ';'.join(filters), '-map', '0:v:0', '-map', '[audio]', '-c:a', 'aac']
    else:
        command += ['-map', '0:v:0', '-an']
    visual = []
    if edit.get('output_ratio'):
        from .studio_composition import output_dimensions
        width,height=output_dimensions({'ratio':edit['output_ratio'],'resolution':720})
        visual.append(f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1')
    if speed != 1:
        visual.append(f'setpts=(PTS-STARTPTS)/{speed}')
    if edit['grayscale']:
        visual.append('hue=s=0')
    if edit['flip']:
        visual.append('hflip')
    if edit['video_fade_in']:
        visual.append(f"fade=t=in:d={min(edit['video_fade_in'], output_length)}")
    if edit['video_fade_out']:
        visual.append(f"fade=t=out:st={max(0, output_length-edit['video_fade_out'])}:d={min(edit['video_fade_out'], output_length)}")
    if visual:
        command += ['-vf', ','.join(visual)]
    command += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-movflags', '+faststart', str(dest)]
    subprocess.run(command, check=True, capture_output=True, timeout=240)


def _atempo(speed):
    value = float(speed or 1)
    parts = []
    while value < .5:
        parts.append('atempo=0.5')
        value /= .5
    while value > 2:
        parts.append('atempo=2.0')
        value /= 2
    parts.append(f'atempo={value}')
    return ','.join(parts)


def _render_job(root, ident, source, edit, sound, release_slot=True):
    path = root / f'export-{ident}.json'
    envelope = json.loads(path.read_text()) if path.exists() else {}
    _write(path, {**envelope, 'id':ident, 'status':'rendering'})
    try:
        work = envelope.get('work') or {}
        if work.get('composition'):
            from .studio_composition import render_composition
            render_composition(work['composition'], work['sources'], work['sounds'], root / f'{ident}.mp4')
        elif edit.get('layers'):
            from .studio_layers import render_layers
            intermediate = root / f'{ident}-base.mp4'
            try:
                render_clip(source, intermediate, edit, sound)
                render_layers(intermediate, root / f'{ident}.mp4', edit['layers'])
            finally:
                intermediate.unlink(missing_ok=True)
        else:
            render_clip(source, root / f'{ident}.mp4', edit, sound)
        from .studio_delivery import finish_delivery
        delivery_result=finish_delivery(root,ident,envelope)
        _write(path, {**envelope, **delivery_result, 'id': ident, 'status': 'ready', 'created_at': time.time()})
    except Exception:
        logger.exception("Studio export failed: %s", ident)
        (root / f'{ident}.mp4').unlink(missing_ok=True)
        _write(path, {**envelope, 'id': ident, 'status': 'failed', 'error': 'Não foi possível exportar. Verifique o intervalo de corte e tente novamente.', 'created_at': time.time()})
    finally:
        if release_slot:
            _SLOTS.release()


@admin_required_api
@trocr_csrf_required
def export_clip():
    from ..creative_format_lab.swap_routes import _http
    execute, json_body, ok, service = _http()
    def run():
        data = json_body()
        root = _scope(data.get('client_id'))
        from .studio_media import resolve_clip, public_sounds
        source = resolve_clip(root, data.get('client_id'), data.get('clip_id'), service())
        edit = normalize_edit(data.get('edit'))
        sound = None
        if edit['sound_id']:
            public_root, catalog = public_sounds()
            public = next((r for r in catalog if r['id'] == edit['sound_id']), None)
            if public:
                sound = public_root / public['filename']
            else:
                _record(root, edit['sound_id'], 'sound')
                sound = root / f"{edit['sound_id']}.m4a"
        if not ffmpeg_available():
            raise ValueError('A exportação não está disponível no servidor.')
        ident = str(data.get('request_id') or '')
        if not _ID.fullmatch(ident):
            raise ValueError('Identificador da exportação inválido.')
        path = root / f'export-{ident}.json'
        # Exclusive creation makes retries idempotent, including across web workers.
        try:
            with path.open('x') as handle:
                from .studio_delivery import reserve_delivery
                delivery=reserve_delivery(root,data,service(),edit.get('output_ratio'))
                json.dump({'delivery':delivery,'id': ident, 'status': 'queued', 'created_at': time.time(), 'user_id': session.get('user_id'), 'work': {'source':str(source), 'sound':str(sound) if sound else '', 'edit':edit}}, handle)
        except FileExistsError:
            return ok(export_public(json.loads(path.read_text())))
        except Exception:
            path.unlink(missing_ok=True)
            raise
        from .jobs import worker_mode, wake_worker
        if worker_mode() in {'process', 'supervised'}:
            wake_worker()
            return ok({'id':ident, 'status':'queued'})
        if not _SLOTS.acquire(blocking=False):
            path.unlink(missing_ok=True)
            raise ValueError('Há exportações em andamento. Tente novamente em instantes.')
        try:
            _POOL.submit(_render_job, root, ident, Path(source), edit, sound)
        except Exception:
            _SLOTS.release()
            path.unlink(missing_ok=True)
            raise
        return ok({'id': ident, 'status': 'rendering'})
    return execute(run)


@admin_required_api
def export_status(ident):
    from ..creative_format_lab.swap_routes import _http
    execute, _, ok, _ = _http()
    def run():
        _, row = _record(_scope(request.args.get('client_id')), ident, 'export')
        if row['status'] == 'rendering' and not row.get('work') and time.time() - row['created_at'] > 600:
            row.update(status='failed', error='A exportação foi interrompida. Tente novamente.')
        return ok(export_public(row))
    return execute(run)


@admin_required_api
def export_content(ident):
    from ..creative_format_lab.swap_routes import _http
    execute, _, _, _ = _http()
    def run():
        root = _scope(request.args.get('client_id'))
        _, row = _record(root, ident, 'export')
        if row['status'] != 'ready':
            raise ValueError('A exportação ainda não está pronta.')
        kind=request.args.get('format') or row.get('format','mp4')
        if kind not in {'mp4','gif','html'} or not (root/f'{ident}.{kind}').is_file():raise ValueError('Formato indisponível nesta exportação.')
        name=row.get('filename','cadu_studio.mp4')
        if kind!=row.get('format','mp4'):name=str(Path(name).with_suffix('.'+kind))
        return send_file(root / f'{ident}.{kind}', mimetype={'mp4':'video/mp4','gif':'image/gif','html':'text/html'}[kind], as_attachment=request.args.get('inline')!='1', download_name=name, conditional=True)
    return execute(run)


def export_public(row):
    return {key:row[key] for key in ('id','status','created_at','error','filename','format','download_url','public_url') if key in row}
