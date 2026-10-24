"""Editor de vídeo do Studio sobre o OpenCut: projeto, biblioteca, upload, comandos, extensões e render.

O OpenCut roda no navegador, mas não guarda nada lá: a timeline é a chave ``video_editor`` do documento
do projeto do Studio (mesmas revisões e conflito), e cada mídia é um item da biblioteca da marca
(clip-/sound-/image-*.json), vinculado ao projeto por ``vedit-<projeto>.json``. Agentes e extensões
alteram a timeline só por comandos tipados aplicados aqui; o render final roda o mesmo editor no worker.
"""
import copy
import hashlib
import json
import re
import subprocess
import time
import uuid
from pathlib import Path

from flask import current_app, make_response, render_template, request, send_file, session

from .http import studio_http as _http
from .studio_auth import studio_or_admin_required_api
from .studio_csrf import studio_csrf_required, get_or_create_token
from .studio import _api_root, _record, _scope, _write, probe, waveform_levels

TICKS = 120_000
API = '/api/format-lab/studio/video-editor'
_ASSET_ID = re.compile(r'[A-Za-z0-9_-]{8,64}')
_HEX = re.compile(r'[0-9a-f]{32}')
_MAX_PROJECT_BYTES = 1_500_000
_MAX_IMAGE = 25 * 1024 * 1024
_MAX_VIDEO = 150 * 1024 * 1024
MEDIA_TYPES = {'video', 'image', 'audio'}


def register(bp):
    bp.add_url_rule('/video-editor', view_func=editor_page)
    bp.add_url_rule(API + '/projects', view_func=projects, methods=['GET', 'POST'])
    bp.add_url_rule(API + '/projects/<ident>', view_func=project, methods=['GET', 'PUT'])
    bp.add_url_rule(API + '/projects/<ident>/media', view_func=project_media, methods=['GET', 'POST'])
    bp.add_url_rule(API + '/projects/<ident>/media/link', view_func=link_media, methods=['POST'])
    bp.add_url_rule(API + '/projects/<ident>/media/<asset_id>', view_func=unlink_media, methods=['DELETE'])
    bp.add_url_rule(API + '/projects/<ident>/media/<asset_id>/content', view_func=media_content)
    bp.add_url_rule(API + '/projects/<ident>/commands', view_func=project_commands, methods=['POST'])
    bp.add_url_rule(API + '/projects/<ident>/extensions/<ext_id>/run', view_func=run_extension, methods=['POST'])
    bp.add_url_rule(API + '/projects/<ident>/renders', view_func=submit_render, methods=['POST'])
    bp.add_url_rule(API + '/projects/<ident>/transcriptions', view_func=submit_transcription, methods=['POST'])
    bp.add_url_rule(API + '/projects/<ident>/exports', view_func=upload_export, methods=['POST'])
    bp.add_url_rule(API + '/renders/<ident>/content', view_func=render_content)
    bp.add_url_rule(API + '/library', view_func=library)
    bp.add_url_rule(API + '/commands', view_func=command_catalog)
    bp.add_url_rule(API + '/extensions', view_func=extension_catalog)


# ---------------------------------------------------------------- página

def editor_page():
    from ..creative_modeling_routes import studio_or_admin_required
    return studio_or_admin_required(_editor_page)()


def _editor_page():
    client = request.args.get('client_id') or request.args.get('creative_client_id')
    ident = str(request.args.get('project') or '')
    _scope(client)
    _project_id(ident)
    static = Path(current_app.static_folder) / 'cadu_studio' / 'video_editor'
    version = int(max((static / name).stat().st_mtime for name in ('app.js', 'app.css'))) if (static / 'app.js').exists() else 0
    boot = {'clientId': int(client), 'projectId': ident, 'projectName': str(request.args.get('name') or '')[:120],
            'apiRoot': _api_root(), 'csrfToken': get_or_create_token(),
            'exitUrl': _local_path(request.args.get('back')),
            'editorUrl': request.path}
    response = make_response(render_template('cadu_studio/video_editor.html', boot=boot, version=version))
    response.headers['Cache-Control'] = 'no-store, private'
    return response


def _local_path(raw):
    """Só caminhos do próprio site: '//host' e '/\\host' viram redirecionamento externo no navegador."""
    value = str(raw or '')
    return value if re.fullmatch(r'/(?![/\\])[^\s]*', value) else '/studio'


# ---------------------------------------------------------------- projeto

def _project_id(ident):
    ident = str(ident or '')
    if _HEX.fullmatch(ident):
        return ident
    try:
        return str(uuid.UUID(ident))
    except ValueError:
        raise ValueError('Projeto inválido.')


def _store():
    from . import studio_projects as repository
    from .studio import _project_store
    return _project_store(repository), repository


def read_project(client, ident):
    store, _ = _store()
    row = store.read(client, _project_id(ident))
    document = row['document'] if isinstance(row['document'], dict) else {}
    return row['revision'], document


def save_timeline(client, ident, timeline, expected_revision):
    """Grava só a chave ``video_editor``; o restante do documento do projeto continua igual."""
    store, repository = _store()
    ident = _project_id(ident)
    current = store.read(client, ident)
    if current['revision'] != expected_revision:
        raise repository.RevisionConflict('O projeto foi alterado em outra aba. Recarregue o editor para continuar.')
    document = dict(current['document']) if isinstance(current['document'], dict) else {}
    document['video_editor'] = timeline
    document.setdefault('name', (timeline.get('metadata') or {}).get('name') or 'Projeto de vídeo')
    return store.save(client, document, ident, expected_revision)['revision']


def validate_timeline(raw, ident):
    """Contrato mínimo do projeto serializado do OpenCut; o conteúdo dos elementos é do editor."""
    if not isinstance(raw, dict):
        raise ValueError('Timeline inválida.')
    encoded = json.dumps(raw, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > _MAX_PROJECT_BYTES:
        raise ValueError('A timeline excede o tamanho permitido.')
    metadata = raw.get('metadata')
    if not isinstance(metadata, dict) or str(metadata.get('id')) != str(ident):
        raise ValueError('A timeline não pertence a este projeto.')
    scenes = raw.get('scenes')
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 20:
        raise ValueError('Timeline sem cenas válidas.')
    for scene in scenes:
        tracks = scene.get('tracks') if isinstance(scene, dict) else None
        if not isinstance(tracks, dict) or not isinstance(tracks.get('main'), dict) \
                or not isinstance(tracks.get('overlay'), list) or not isinstance(tracks.get('audio'), list):
            raise ValueError('Cena com faixas inválidas.')
    thumbnail = metadata.get('thumbnail')
    if isinstance(thumbnail, str) and len(thumbnail) > 300_000:
        raw = copy.deepcopy(raw)
        raw['metadata'].pop('thumbnail', None)
    return raw


@studio_or_admin_required_api
@studio_csrf_required
def projects():
    execute, body, ok, _ = _http()

    def run():
        store, _ = _store()
        if request.method == 'GET':
            client = request.args.get('client_id')
            _scope(client)
            return ok({'items': store.listing(client, int(request.args.get('offset', 0)))})
        data = body()
        client = request.args.get('client_id') or data.get('client_id')
        _scope(client)
        name = str(data.get('name') or 'Projeto de vídeo').strip()[:120]
        saved = store.save(client, {'name': name, 'video_editor': None})
        return ok({'id': saved['id'], 'revision': saved['revision'], 'name': name})
    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def project(ident):
    from flask import jsonify
    execute, body, ok, _ = _http()

    def run():
        client = request.args.get('client_id')
        _scope(client)
        if request.method == 'GET':
            revision, document = read_project(client, ident)
            return ok({'revision': revision, 'project': document.get('video_editor')})
        data = body()
        _, repository = _store()
        try:
            timeline = validate_timeline(data.get('project'), _project_id(ident))
            revision = save_timeline(client, ident, timeline, data.get('expected_revision'))
        except repository.RevisionConflict as error:
            return jsonify(success=False, error=str(error), code='revision_conflict'), 409
        return ok({'revision': revision})
    return execute(run)


# ---------------------------------------------------------------- mídia: biblioteca da marca + vínculo por projeto

def _links_path(root, ident):
    return root / f'vedit-{hashlib.sha256(_project_id(ident).encode()).hexdigest()[:32]}.json'


def read_links(root, ident):
    path = _links_path(root, ident)
    return json.loads(path.read_text()) if path.exists() else {}


def _write_links(root, ident, links):
    _write(_links_path(root, ident), links)


def _public(client, ident, asset_id, link):
    return {'id': asset_id, 'name': link['name'], 'type': link['type'], 'size': link.get('size', 0),
            'lastModified': int(link.get('created_at', 0) * 1000), 'width': link.get('width'), 'height': link.get('height'),
            'duration': link.get('duration'), 'hasAudio': link.get('has_audio'), 'ref': link['ref'], 'libraryKind': link['type'],
            'contentUrl': f'{_api_root()}/format-lab/studio/video-editor/projects/{_project_id(ident)}/media/{asset_id}/content?client_id={int(client)}'}


def resolve_ref(root, client, ref):
    """Caminho local e metadados de um item da biblioteca; só refs desta marca ou do catálogo público."""
    kind, _, key = str(ref or '').partition(':')
    if kind == 'clip' and _HEX.fullmatch(key):
        _, row = _record(root, key, 'clip')
        return root / f'{key}.mp4', 'video', row
    if kind == 'sound' and _HEX.fullmatch(key):
        _, row = _record(root, key, 'sound')
        return root / f'{key}.m4a', 'audio', row
    if kind == 'image' and _HEX.fullmatch(key):
        _, row = _record(root, key, 'image')
        return root / row['filename'], 'image', row
    if kind == 'public-sound':
        from .studio_media import public_sounds
        base, rows = public_sounds()
        row = next((item for item in rows if item['id'] == key), None)
        if row:
            return base / row['filename'], 'audio', row
    if kind == 'generated' and key:
        from .studio_media import resolve_clip
        _, _, _, service = _http()
        path = resolve_clip(root, client, key, service())
        return path, 'video', {'name': 'Vídeo gerado'}
    raise ValueError('Mídia não encontrada nesta marca.')


def _media_meta(path, kind):
    if kind == 'image':
        from PIL import Image
        with Image.open(path) as image:
            return {'width': image.width, 'height': image.height}
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,width,height',
                             '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=20)
    data = json.loads(result.stdout)
    video = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), {})
    return {'duration': float(data.get('format', {}).get('duration') or 0), 'width': video.get('width'), 'height': video.get('height'),
            'has_audio': any(s.get('codec_type') == 'audio' for s in data.get('streams', []))}


def ingest_upload(root, client, upload, declared):
    """Mesmo contrato dos uploads do Studio: conteúdo validado por FFprobe/Pillow, nunca pela extensão."""
    ident = uuid.uuid4().hex
    name = Path(upload.filename or 'mídia').name[:120]
    source = root / f'{ident}.upload'
    size = 0
    limit = _MAX_IMAGE if declared == 'image' else _MAX_VIDEO
    try:
        with source.open('wb') as handle:
            while chunk := upload.stream.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Arquivo acima do limite: imagem até 25 MB, vídeo e áudio até 150 MB.')
                handle.write(chunk)
        if not size:
            raise ValueError('Arquivo vazio.')
        if declared == 'image':
            return _ingest_image(root, ident, name, source, size)
        duration, streams = probe(source)
        if declared == 'video':
            if 'video' not in streams or not 0 < duration <= 300:
                raise ValueError('Envie um vídeo de até 5 minutos.')
            dest = root / f'{ident}.mp4'
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,matroska,webm',
                            '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?', '-map_metadata', '-1',
                            '-vf', 'scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
                            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(dest)],
                           check=True, capture_output=True, timeout=300)
            from .studio_media import inspect_clip
            meta = inspect_clip(dest, root, client, 'upload:' + ident)
            row = {'id': 'upload:' + ident, 'name': name, 'duration': meta['duration'], 'has_audio': meta['has_audio'],
                   'video_url': f'{_api_root()}/format-lab/studio/clips/{ident}/content?client_id={int(client)}',
                   'poster_url': meta['frames'][0]['url'], 'created_at': time.time()}
            _write(root / f'clip-{ident}.json', row)
            return f'clip:{ident}', 'video', dest
        if 'audio' not in streams or 'video' in streams or not 0 < duration <= 600:
            raise ValueError('Envie somente áudio, com até 10 minutos.')
        dest = root / f'{ident}.m4a'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,mp3,wav,ogg,flac,aac,matroska,webm',
                        '-i', str(source), '-vn', '-map_metadata', '-1', '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2', str(dest)],
                       check=True, timeout=120, capture_output=True)
        levels = waveform_levels(dest)
        row = {'id': ident, 'name': name, 'duration': round(duration, 2), 'category': 'music', 'waveform': levels['overview'],
               'waveform_levels': levels, 'url': f'{_api_root()}/format-lab/studio/sounds/{ident}?client_id={int(client)}', 'created_at': time.time()}
        _write(root / f'sound-{ident}.json', row)
        return f'sound:{ident}', 'audio', dest
    except (subprocess.SubprocessError, OSError) as error:
        for leftover in (root / f'{ident}.mp4', root / f'{ident}.m4a'):
            leftover.unlink(missing_ok=True)
        raise ValueError('Não foi possível preparar a mídia. Use MP4, MOV, WebM, MP3, WAV, M4A, PNG, JPG ou WebP.') from error
    finally:
        source.unlink(missing_ok=True)


def _ingest_image(root, ident, name, source, size):
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(source) as image:
            if image.format not in {'PNG', 'JPEG', 'WEBP', 'GIF'}:
                raise ValueError('Use PNG, JPG, WebP ou GIF.')
            if image.width * image.height > 40_000_000:
                raise ValueError('Imagem grande demais (máximo 40 megapixels).')
            image.load()
            keep_alpha = image.mode in {'RGBA', 'LA', 'P'}
            extension = 'png' if keep_alpha else 'jpg'
            clean = image.convert('RGBA' if keep_alpha else 'RGB')
            dest = root / f'{ident}.{extension}'
            clean.save(dest, format='PNG' if keep_alpha else 'JPEG', quality=92)
    except UnidentifiedImageError as error:
        raise ValueError('Arquivo de imagem inválido.') from error
    row = {'id': ident, 'name': name, 'filename': dest.name, 'width': clean.width, 'height': clean.height,
           'mime': 'image/png' if keep_alpha else 'image/jpeg', 'size': size, 'created_at': time.time()}
    _write(root / f'image-{ident}.json', row)
    return f'image:{ident}', 'image', dest


def _link(root, client, ident, asset_id, ref, name=None):
    path, kind, row = resolve_ref(root, client, ref)
    links = read_links(root, ident)
    if len(links) >= 300 and asset_id not in links:
        raise ValueError('Limite de 300 mídias por projeto.')
    links[asset_id] = {'ref': ref, 'type': kind, 'name': str(name or row.get('name') or 'Mídia')[:120],
                       'size': path.stat().st_size, 'created_at': time.time(), **_media_meta(path, kind)}
    _write_links(root, ident, links)
    return links[asset_id]


@studio_or_admin_required_api
@studio_csrf_required
def project_media(ident):
    execute, _, ok, _ = _http()

    def run():
        client = request.args.get('client_id')
        root = _scope(client)
        read_project(client, ident)  # o projeto precisa existir nesta marca
        if request.method == 'GET':
            links = read_links(root, ident)
            return ok({'items': [_public(client, ident, key, value) for key, value in links.items()]})
        asset_id = str(request.form.get('asset_id') or '')
        declared = request.form.get('type')
        upload = request.files.get('file')
        if not _ASSET_ID.fullmatch(asset_id) or declared not in MEDIA_TYPES or not upload:
            raise ValueError('Envio de mídia inválido.')
        ref, _, _ = ingest_upload(root, client, upload, declared)
        link = _link(root, client, ident, asset_id, ref, request.form.get('name'))
        return ok(_public(client, ident, asset_id, link))
    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def link_media(ident):
    execute, body, ok, _ = _http()

    def run():
        client = request.args.get('client_id')
        root = _scope(client)
        read_project(client, ident)
        data = body()
        asset_id = uuid.uuid4().hex
        link = _link(root, client, ident, asset_id, data.get('ref'))
        return ok(_public(client, ident, asset_id, link))
    return execute(run)


@studio_or_admin_required_api
@studio_csrf_required
def unlink_media(ident, asset_id):
    execute, _, ok, _ = _http()

    def run():
        client = request.args.get('client_id')
        root = _scope(client)
        links = read_links(root, ident)
        links.pop(asset_id, None)  # a biblioteca da marca continua com o arquivo
        _write_links(root, ident, links)
        return ok({'id': asset_id})
    return execute(run)


@studio_or_admin_required_api
def media_content(ident, asset_id):
    execute, _, _, _ = _http()

    def run():
        client = request.args.get('client_id')
        root = _scope(client)
        link = read_links(root, ident).get(asset_id)
        if not link:
            raise ValueError('Mídia não vinculada a este projeto.')
        path, kind, row = resolve_ref(root, client, link['ref'])
        mime = row.get('mime') or {'video': 'video/mp4', 'audio': 'audio/mp4'}.get(kind)
        response = send_file(path, mimetype=mime, conditional=True)
        response.headers['Cache-Control'] = 'private, max-age=3600'  # mídia da marca: nunca em cache compartilhado
        return response
    return execute(run)


@studio_or_admin_required_api
def library():
    """Biblioteca única da marca: enviados no editor ou no Studio, gerados e sons públicos."""
    execute, _, ok, service = _http()

    def run():
        client = request.args.get('client_id')
        root = _scope(client)
        items = []
        for path in sorted(root.glob('clip-*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            row = json.loads(path.read_text())
            items.append({'ref': 'clip:' + path.stem[5:], 'kind': 'video', 'name': row.get('name'), 'poster_url': row.get('poster_url'),
                          'duration': row.get('duration'), 'source': 'Exportado do editor' if row.get('source') == 'editor' else 'Enviado'})
        for path in sorted(root.glob('image-*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            row = json.loads(path.read_text())
            items.append({'ref': 'image:' + row['id'], 'kind': 'image', 'name': row.get('name'), 'source': 'Imagem enviada'})
        for path in sorted(root.glob('sound-*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            row = json.loads(path.read_text())
            items.append({'ref': 'sound:' + row['id'], 'kind': 'audio', 'name': row.get('name'), 'duration': row.get('duration'), 'source': 'Áudio da marca'})
        try:
            generated = service().load_format_lab_swap_library({'client_id': client, 'media': 'video'}, session.get('user_id'))
            for row in (generated or {}).get('items', [])[:60]:
                if row.get('video_url'):
                    items.append({'ref': 'generated:' + str(row['id']), 'kind': 'video', 'name': row.get('title') or row.get('name') or 'Vídeo gerado',
                                  'poster_url': row.get('thumbnail_url') or row.get('image_url'), 'duration': row.get('duration'), 'source': 'Gerado no Studio'})
        except Exception:
            current_app.logger.warning('Vídeos gerados indisponíveis na biblioteca do editor', exc_info=True)
        from .studio_media import public_sounds
        items.extend({'ref': 'public-sound:' + row['id'], 'kind': 'audio', 'name': row.get('name'), 'duration': row.get('duration'),
                      'source': 'Efeito sonoro (CC0)'} for row in public_sounds()[1])
        return ok({'items': items})
    return execute(run)


# ---------------------------------------------------------------- comandos (Editor API)

def _ticks(seconds, low=0.0, high=3600.0):
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        raise ValueError('Tempo inválido.')
    return round(max(low, min(high, value)) * TICKS)


def _new_id():
    return str(uuid.uuid4())


def _scene(timeline):
    scenes = timeline['scenes']
    current = timeline.get('currentSceneId')
    return next((s for s in scenes if s.get('id') == current), next((s for s in scenes if s.get('isMain')), scenes[0]))


def _all_tracks(scene):
    tracks = scene['tracks']
    return [*tracks['overlay'], tracks['main'], *tracks['audio']]


def _find(scene, element_id):
    for track in _all_tracks(scene):
        for index, element in enumerate(track['elements']):
            if element.get('id') == element_id:
                return track, index, element
    raise ValueError('Elemento não encontrado na timeline.')


def _canvas(timeline):
    size = (timeline.get('settings') or {}).get('canvasSize') or {}
    return float(size.get('width') or 1920), float(size.get('height') or 1080)


VISUAL_PARAMS = {'transform.positionX', 'transform.positionY', 'transform.scaleX', 'transform.scaleY', 'transform.rotate', 'opacity', 'volume', 'muted'}
TEXT_PARAMS = VISUAL_PARAMS | {'content', 'fontSize', 'fontFamily', 'color', 'textAlign', 'fontWeight', 'fontStyle', 'letterSpacing', 'lineHeight',
                               'background.enabled', 'background.color', 'background.cornerRadius', 'background.paddingX', 'background.paddingY'}


def _number(args, key, default, low, high):
    try:
        value = float(args.get(key, default) if args.get(key) is not None else default)
    except (TypeError, ValueError):
        raise ValueError(f'Valor inválido em {key}.')
    return max(low, min(high, value))


FONT_SIZE_REFERENCE = 90  # OpenCut: pixels da fonte = fontSize × altura do quadro / 90
_CHAR_WIDTH = {True: .60, False: .55}  # largura média de um caractere em fração do tamanho (Arial)


def fit_text(text, size, width, height, bold):
    """Quebra e reduz o texto para caber em 88% da largura do quadro.

    O OpenCut não quebra linha sozinho e mede a fonte pela altura do quadro: num vertical, o mesmo tamanho
    fica bem mais largo. Abaixo de 3% da altura o texto fica ilegível no celular; aí a linha é quebrada.
    """
    import textwrap
    usable = width * .88
    char = _CHAR_WIDTH[bold]
    pixels = size * height / FONT_SIZE_REFERENCE
    minimum = max(height * .03, 24.0)
    lines = []
    for line in text.split('\n'):
        per_line = max(6, int(usable / (char * max(pixels, minimum))))
        lines.extend(textwrap.wrap(line, per_line, break_long_words=True) or [''])
    longest = max((len(line) for line in lines), default=1) or 1
    pixels = min(pixels, usable / (char * longest))
    return '\n'.join(lines), round(max(pixels, 1) * FONT_SIZE_REFERENCE / height, 2)


def _text_params(timeline, args):
    width, height = _canvas(timeline)
    color = str(args.get('color') or '#ffffff')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError('Cor inválida.')
    background = str(args.get('background') or '')
    content, font_size = fit_text(str(args.get('text') or '').strip()[:500] or 'Texto', _number(args, 'size', 15, 1, 60),
                                  width, height, bool(args.get('bold')))
    params = {
        'content': content,
        'fontSize': font_size,
        'fontFamily': str(args.get('font') or 'Arial')[:80], 'color': color, 'textAlign': 'center',
        'fontWeight': 'bold' if args.get('bold') else 'normal', 'fontStyle': 'normal', 'textDecoration': 'none',
        'letterSpacing': 0, 'lineHeight': 1.2,
        'background.enabled': bool(re.fullmatch(r'#[0-9a-fA-F]{6}', background)), 'background.color': background or '#000000',
        'background.cornerRadius': 12, 'background.paddingX': 30, 'background.paddingY': 18, 'background.offsetX': 0, 'background.offsetY': 0,
        # Posição: fração do quadro (0–1), convertida para pixels a partir do centro como no OpenCut.
        'transform.positionX': (_number(args, 'x', .5, 0, 1) - .5) * width,
        'transform.positionY': (_number(args, 'y', .5, 0, 1) - .5) * height,
        'transform.scaleX': 1, 'transform.scaleY': 1, 'transform.rotate': 0, 'opacity': 1, 'blendMode': 'normal',
    }
    return params


def _text_track(scene, track_id=None):
    overlay = scene['tracks']['overlay']
    if track_id:
        track = next((t for t in overlay if t.get('id') == track_id and t.get('type') == 'text'), None)
        if not track:
            raise ValueError('Faixa de texto não encontrada.')
        return track
    track = {'id': _new_id(), 'name': 'Texto', 'type': 'text', 'elements': [], 'hidden': False}
    overlay.insert(0, track)
    return track


def cmd_add_text(timeline, args, links):
    scene = _scene(timeline)
    track = _text_track(scene, args.get('track_id'))
    element = {'id': _new_id(), 'type': 'text', 'name': str(args.get('name') or args.get('text') or 'Texto')[:60],
               'startTime': _ticks(args.get('start', 0)), 'duration': max(TICKS // 10, _ticks(args.get('duration', 3), .1, 600)),
               'trimStart': 0, 'trimEnd': 0, 'params': _text_params(timeline, args)}
    track['elements'].append(element)
    return {'element_id': element['id'], 'track_id': track['id']}


def _default_visual_params(kind):
    params = {'transform.positionX': 0, 'transform.positionY': 0, 'transform.scaleX': 1, 'transform.scaleY': 1,
              'transform.rotate': 0, 'opacity': 1, 'blendMode': 'normal'}
    if kind == 'video':
        params.update({'volume': 0, 'muted': False})
    return params


def cmd_add_media(timeline, args, links):
    asset_id = str(args.get('asset_id') or '')
    link = links.get(asset_id)
    if not link:
        raise ValueError('Mídia não vinculada a este projeto.')
    scene = _scene(timeline)
    kind = link['type']
    source_duration = _ticks(link.get('duration') or 5, .1, 3600) if kind != 'image' else None
    duration = _ticks(args['duration'], .1, 3600) if args.get('duration') else (source_duration or 5 * TICKS)
    base = {'id': _new_id(), 'name': link['name'][:60], 'mediaId': asset_id, 'duration': duration, 'trimStart': 0, 'trimEnd': 0}
    if kind == 'audio':
        element = {**base, 'type': 'audio', 'sourceType': 'upload', 'sourceDuration': source_duration, 'params': {'volume': 0, 'muted': False}}
        track = {'id': _new_id(), 'name': 'Áudio', 'type': 'audio', 'elements': [], 'muted': False}
        scene['tracks']['audio'].append(track)
    else:
        element = {**base, 'type': kind, 'hidden': False, 'params': _default_visual_params(kind)}
        if kind == 'video':
            element.update({'sourceDuration': source_duration, 'isSourceAudioEnabled': True})
        if args.get('track') == 'overlay':
            track = {'id': _new_id(), 'name': 'Sobreposição', 'type': 'video', 'elements': [], 'muted': False, 'hidden': False}
            scene['tracks']['overlay'].insert(0, track)
        else:
            track = scene['tracks']['main']
    end = max((e['startTime'] + e['duration'] for e in track['elements']), default=0)
    element['startTime'] = _ticks(args['start']) if args.get('start') is not None else end
    if kind != 'audio':
        scale = _number(args, 'scale', 1, .1, 10)
        element['params'].update({'transform.scaleX': scale, 'transform.scaleY': scale})
        _apply_motion(element, args.get('motion'), scale)
    else:
        element['params']['volume'] = _number(args, 'volume', 0, -60, 12)
    track['elements'].append(element)
    track['elements'].sort(key=lambda e: e['startTime'])
    return {'element_id': element['id'], 'track_id': track['id']}


def cmd_split(timeline, args, links):
    scene = _scene(timeline)
    track, index, element = _find(scene, args.get('element_id'))
    at = _ticks(args.get('at'))
    start, end = element['startTime'], element['startTime'] + element['duration']
    if not start < at < end:
        raise ValueError('O ponto de corte precisa estar dentro do elemento.')
    rate = float((element.get('retime') or {}).get('rate') or 1)
    left = at - start
    right = copy.deepcopy(element)
    right['id'] = _new_id()
    right['startTime'] = at
    right['duration'] = end - at
    right['trimStart'] = element['trimStart'] + round(left * rate)
    element['duration'] = left
    element['trimEnd'] = element['trimEnd'] + round((end - at) * rate)
    track['elements'].insert(index + 1, right)
    return {'left_id': element['id'], 'right_id': right['id']}


def cmd_delete(timeline, args, links):
    scene = _scene(timeline)
    track, index, element = _find(scene, args.get('element_id'))
    del track['elements'][index]
    if args.get('ripple') and track is scene['tracks']['main']:
        for later in track['elements'][index:]:
            later['startTime'] = max(0, later['startTime'] - element['duration'])
    return {'deleted': element['id']}


def cmd_move(timeline, args, links):
    scene = _scene(timeline)
    track, _, element = _find(scene, args.get('element_id'))
    element['startTime'] = _ticks(args.get('start'))
    track['elements'].sort(key=lambda e: e['startTime'])
    return {'element_id': element['id']}


def cmd_trim(timeline, args, links):
    scene = _scene(timeline)
    _, _, element = _find(scene, args.get('element_id'))
    trim_start, trim_end = _ticks(args.get('trim_start', 0)), _ticks(args.get('trim_end', 0))
    source = element.get('sourceDuration')
    if source and trim_start + trim_end >= source:
        raise ValueError('O corte remove o elemento inteiro.')
    used = (source - trim_start - trim_end) if source else element['duration']
    element.update({'trimStart': trim_start, 'trimEnd': trim_end, 'duration': max(TICKS // 30, used)})
    return {'element_id': element['id']}


def cmd_set_params(timeline, args, links):
    scene = _scene(timeline)
    _, _, element = _find(scene, args.get('element_id'))
    allowed = TEXT_PARAMS if element.get('type') == 'text' else VISUAL_PARAMS
    params = args.get('params') if isinstance(args.get('params'), dict) else {}
    for key, value in params.items():
        if key not in allowed or not isinstance(value, (int, float, str, bool)) or isinstance(value, str) and len(value) > 500:
            raise ValueError(f'Propriedade não permitida: {key}.')
        element.setdefault('params', {})[key] = value
    return {'element_id': element['id']}


def cmd_set_canvas(timeline, args, links):
    """Formato do projeto (ex.: 1080×1920 para Reels) e cor de fundo."""
    width, height = int(_number(args, 'width', 1920, 240, 4096)), int(_number(args, 'height', 1080, 240, 4096))
    if width % 2 or height % 2:
        raise ValueError('Largura e altura precisam ser pares (H.264).')
    settings = timeline.setdefault('settings', {})
    settings['canvasSize'] = {'width': width, 'height': height}
    settings['canvasSizeMode'] = 'custom'
    settings['lastCustomCanvasSize'] = {'width': width, 'height': height}
    background = str(args.get('background') or '')
    if background:
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', background):
            raise ValueError('Cor de fundo inválida.')
        settings['background'] = {'type': 'color', 'color': background}
    return {'canvas': f'{width}x{height}'}


ANIMATABLE = {'transform.positionX', 'transform.positionY', 'transform.scaleX', 'transform.scaleY', 'transform.rotate', 'opacity', 'volume'}


def _keyframes(element, prop, points, ease):
    """Grava um canal de keyframes no formato do OpenCut (tempo relativo ao início do elemento)."""
    keys = []
    for at, value in sorted(points, key=lambda point: point[0]):
        keys.append({'id': _new_id(), 'time': max(0, min(element['duration'], round(at * TICKS))), 'value': value,
                     'segmentToNext': 'bezier' if ease == 'ease' else 'linear', 'tangentMode': 'auto' if ease == 'ease' else 'flat'})
    element.setdefault('animations', {})[prop] = {'keys': keys}


def cmd_animate(timeline, args, links):
    scene = _scene(timeline)
    _, _, element = _find(scene, args.get('element_id'))
    prop = args.get('property')
    if prop not in ANIMATABLE:
        raise ValueError(f'Propriedade não animável: {prop}.')
    raw = args.get('keyframes') if isinstance(args.get('keyframes'), list) else []
    if not 2 <= len(raw) <= 60:
        raise ValueError('Envie de 2 a 60 keyframes.')
    points = [(_number(row, 'at', 0, 0, 3600), _number(row, 'value', 0, -100000, 100000)) for row in raw if isinstance(row, dict)]
    _keyframes(element, prop, points, 'ease' if args.get('ease') == 'ease' else 'linear')
    return {'element_id': element['id']}


def _apply_motion(element, motion, base_scale=1.0):
    """Zoom lento em imagem ou vídeo (Ken Burns): evita quadro parado e dá ritmo à montagem."""
    if motion not in {'zoom_in', 'zoom_out'}:
        return
    seconds = element['duration'] / TICKS
    start, end = (base_scale, base_scale * 1.08) if motion == 'zoom_in' else (base_scale * 1.08, base_scale)
    for prop in ('transform.scaleX', 'transform.scaleY'):
        _keyframes(element, prop, [(0, start), (seconds, end)], 'linear')


COMMANDS = {
    'set_canvas': (cmd_set_canvas, 'Formato do projeto e fundo (width, height, background #rrggbb).'),
    'add_text': (cmd_add_text, 'Adiciona um texto (text, start, duration, x, y, size, color, background, bold).'),
    'add_media': (cmd_add_media, 'Coloca uma mídia do projeto na timeline (asset_id, track main|overlay, start, duration, scale, motion zoom_in|zoom_out).'),
    'split': (cmd_split, 'Divide um elemento num instante (element_id, at).'),
    'delete': (cmd_delete, 'Remove um elemento (element_id, ripple).'),
    'move': (cmd_move, 'Move um elemento no tempo (element_id, start).'),
    'trim': (cmd_trim, 'Corta início/fim da fonte (element_id, trim_start, trim_end).'),
    'set_params': (cmd_set_params, 'Altera propriedades permitidas (element_id, params).'),
    'animate': (cmd_animate, 'Keyframes de escala, posição, rotação, opacidade ou volume (element_id, property, keyframes[{at, value}], ease linear|ease).'),
}


def apply_commands(timeline, commands, links):
    """Aplica uma lista de comandos numa cópia; qualquer erro descarta a lista inteira."""
    if not isinstance(timeline, dict):
        raise ValueError('Abra o editor neste projeto antes de aplicar comandos.')
    if not isinstance(commands, list) or not 1 <= len(commands) <= 500:
        raise ValueError('Envie de 1 a 500 comandos.')
    result = copy.deepcopy(timeline)
    outputs = []
    for command in commands:
        name = command.get('op') if isinstance(command, dict) else None
        if name not in COMMANDS:
            raise ValueError(f'Comando desconhecido: {name}.')
        args = dict(command.get('args') or {})
        if args.get('track_id') == '@previous':
            # Lote de comandos na mesma faixa criada antes (ex.: todas as legendas).
            args['track_id'] = next((out['track_id'] for out in reversed(outputs) if out.get('track_id')), None)
        if args.get('element_id') == '@last':
            # Ajuste no elemento que o comando anterior criou (ex.: animar o texto recém-inserido).
            args['element_id'] = next((out['element_id'] for out in reversed(outputs) if out.get('element_id')), None)
        outputs.append(COMMANDS[name][0](result, args, links))
    _refresh_duration(result)
    return result, outputs


def _refresh_duration(timeline):
    ends = [e['startTime'] + e['duration'] for scene in timeline['scenes'] for track in _all_tracks(scene) for e in track['elements']]
    timeline['metadata']['duration'] = max(ends, default=0)
    timeline['metadata']['updatedAt'] = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    for scene in timeline['scenes']:
        scene['updatedAt'] = timeline['metadata']['updatedAt']


def _apply_and_save(client, ident, commands):
    root = _scope(client)
    revision, document = read_project(client, ident)
    timeline, outputs = apply_commands(document.get('video_editor'), commands, read_links(root, ident))
    return save_timeline(client, ident, timeline, revision), outputs


@studio_or_admin_required_api
def command_catalog():
    execute, _, ok, _ = _http()
    return execute(lambda: ok({'time_unit': 'seconds', 'items': [{'op': key, 'description': value[1]} for key, value in COMMANDS.items()]}))


@studio_or_admin_required_api
@studio_csrf_required
def project_commands(ident):
    from flask import jsonify
    execute, body, ok, _ = _http()

    def run():
        client = request.args.get('client_id')
        _scope(client)
        _, repository = _store()
        try:
            revision, outputs = _apply_and_save(client, ident, body().get('commands'))
        except repository.RevisionConflict as error:
            return jsonify(success=False, error=str(error), code='revision_conflict'), 409
        return ok({'revision': revision, 'results': outputs})
    return execute(run)


# ---------------------------------------------------------------- extensões internas por manifesto

@studio_or_admin_required_api
def extension_catalog():
    from .video_editor_extensions import catalog
    execute, _, ok, _ = _http()
    return execute(lambda: ok({'items': catalog()}))


@studio_or_admin_required_api
@studio_csrf_required
def run_extension(ident, ext_id):
    from flask import jsonify
    from .video_editor_extensions import run as run_ext
    execute, body, ok, _ = _http()

    def run():
        client = request.args.get('client_id')
        root = _scope(client)
        _, repository = _store()
        revision, document = read_project(client, ident)
        context = {'client_id': int(client), 'root': root, 'project_id': _project_id(ident), 'timeline': document.get('video_editor'),
                   'links': read_links(root, ident), 'resolve': lambda ref: resolve_ref(root, client, ref)}
        commands, summary = run_ext(ext_id, context, (body() or {}).get('params') or {})
        timeline, outputs = apply_commands(document.get('video_editor'), commands, context['links'])
        try:
            revision = save_timeline(client, ident, timeline, revision)
        except repository.RevisionConflict as error:
            return jsonify(success=False, error=str(error), code='revision_conflict'), 409
        return ok({'revision': revision, 'summary': summary, 'results': outputs})
    return execute(run)


# ---------------------------------------------------------------- export feito no navegador → biblioteca da marca

_MAX_EXPORT = 1024 * 1024 * 1024


def _codecs(path):
    data = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=format_name,duration:stream=codec_type,codec_name',
                                      '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=30).stdout)
    streams = {row.get('codec_type'): row.get('codec_name') for row in data.get('streams', [])}
    return str(data.get('format', {}).get('format_name') or ''), float(data.get('format', {}).get('duration') or 0), streams


@studio_or_admin_required_api
@studio_csrf_required
def upload_export(ident):
    """O navegador exporta com a GPU de quem edita; o servidor só valida e guarda na biblioteca da marca.

    MP4 H.264 entra direto como clipe. Outro formato (WebM de navegador sem H.264) vira tarefa ``import``,
    que converte para H.264 no worker. O render no servidor fica para automação (agente, lote).
    """
    execute, _, ok, _ = _http()

    def run():
        client = request.args.get('client_id')
        root = _scope(client)
        revision, document = read_project(client, ident)
        upload = request.files.get('file')
        if not upload:
            raise ValueError('Arquivo exportado não enviado.')
        name = Path(str(request.form.get('name') or 'Vídeo editado')).name[:110]
        ident_file = uuid.uuid4().hex
        source = root / f'{ident_file}.upload'
        size = 0
        try:
            with source.open('wb') as handle:
                while chunk := upload.stream.read(4 * 1024 * 1024):
                    size += len(chunk)
                    if size > _MAX_EXPORT:
                        raise ValueError('O vídeo exportado passa de 1 GB.')
                    handle.write(chunk)
            try:
                container, duration, streams = _codecs(source)
            except (subprocess.SubprocessError, OSError, ValueError):
                raise ValueError('O arquivo exportado não é um vídeo válido.')
            if streams.get('video') is None or not 0 < duration <= 1800:
                raise ValueError('O arquivo exportado não é um vídeo válido (até 30 minutos).')
            origin = {'project_id': _project_id(ident), 'revision': revision}
            if 'mp4' in container and streams.get('video') == 'h264' and streams.get('audio') in (None, 'aac'):
                dest = root / f'{ident_file}.mp4'
                source.replace(dest)
                if 'audio' in streams:
                    normalize_loudness(dest)  # entrega no volume das redes, como o render do servidor
                from .studio_media import inspect_clip
                meta = inspect_clip(dest, root, client, 'upload:' + ident_file) if duration <= 300 else {
                    'duration': duration, 'has_audio': 'audio' in streams, 'frames': [{'url': ''}]}
                row = {'id': 'upload:' + ident_file, 'name': name, 'duration': meta['duration'], 'has_audio': meta['has_audio'],
                       'video_url': f'{_api_root()}/format-lab/studio/clips/{ident_file}/content?client_id={int(client)}',
                       'poster_url': meta['frames'][0]['url'], 'created_at': time.time(), 'source': 'editor', **origin}
                _write(root / f'clip-{ident_file}.json', row)
                return ok({'status': 'ready', 'clip': row, 'ref': f'clip:{ident_file}'})
            if duration > 300:
                raise ValueError('Exporte em MP4 (H.264) para vídeos acima de 5 minutos; a conversão no servidor vai até 5 minutos.')
            row = {'id': ident_file, 'kind': 'import', 'status': 'queued', 'created_at': time.time(), 'user_id': session.get('user_id'),
                   'client_id': int(client), 'work': {'source': str(source), 'name': name, 'autocut': {'enabled': False}, 'origin': {'source': 'editor', **origin}}}
            _enqueue(root, row)
            source = None  # a tarefa é dona do arquivo agora
            return ok({'status': 'queued', 'task_id': ident_file})
        finally:
            if source is not None:
                source.unlink(missing_ok=True)
    return execute(run)


# ---------------------------------------------------------------- legendas: áudio da timeline → Whisper do worker

def _enqueue(root, row):
    from .jobs import wake_worker, worker_mode
    _write(root / f'task-{row["id"]}.json', row)
    if worker_mode() in {'process', 'supervised'}:
        wake_worker()
        return
    from .studio import _POOL
    from .studio_tasks import run_task
    app = current_app._get_current_object()

    def background():
        with app.app_context():
            run_task(root, row['id'])
    _POOL.submit(background)


@studio_or_admin_required_api
@studio_csrf_required
def submit_transcription(ident):
    """O editor manda o áudio já mixado da timeline; os tempos voltam relativos à timeline."""
    execute, _, ok, _ = _http()

    def run():
        client = request.args.get('client_id')
        root = _scope(client)
        read_project(client, ident)
        upload = request.files.get('file')
        if not upload:
            raise ValueError('Áudio da timeline não enviado.')
        language = str(request.form.get('language') or '')
        language = language if re.fullmatch(r'[a-z]{2,3}', language) else None
        task = uuid.uuid4().hex
        source = root / f'{task}.transcribe.wav'
        size = 0
        with source.open('wb') as handle:
            while chunk := upload.stream.read(1024 * 1024):
                size += len(chunk)
                if size > 200 * 1024 * 1024:
                    source.unlink(missing_ok=True)
                    raise ValueError('Áudio longo demais para legendar (máximo de 20 minutos).')
                handle.write(chunk)
        try:
            duration, streams = probe(source)
        except (subprocess.SubprocessError, OSError):
            duration, streams = 0, set()
        if 'audio' not in streams or not 0 < duration <= 1200:
            source.unlink(missing_ok=True)
            raise ValueError('A timeline não tem áudio para legendar.')
        row = {'id': task, 'kind': 'transcribe', 'status': 'queued', 'created_at': time.time(), 'user_id': session.get('user_id'),
               'client_id': int(client), 'work': {'source': str(source), 'language': language}}
        _enqueue(root, row)
        return ok({'id': task, 'status': 'queued'})
    return execute(run)


# ---------------------------------------------------------------- render no servidor (mesmo editor, Chromium headless)

@studio_or_admin_required_api
@studio_csrf_required
def submit_render(ident):
    execute, body, ok, _ = _http()

    def run():
        client = request.args.get('client_id')
        root = _scope(client)
        revision, document = read_project(client, ident)
        timeline = document.get('video_editor')
        if not isinstance(timeline, dict):
            raise ValueError('Salve a timeline antes de renderizar.')
        if not any(track['elements'] for scene in timeline['scenes'] for track in _all_tracks(scene)):
            raise ValueError('A timeline está vazia: adicione mídia ou texto antes de renderizar.')
        data = body() or {}
        options = {'format': 'webm' if data.get('format') == 'webm' else 'mp4',
                   # very_high: em 1080p fica acima de 5 Mb/s mesmo no codificador por hardware (teste profissional).
                   'quality': data.get('quality') if data.get('quality') in {'low', 'medium', 'high', 'very_high'} else 'very_high',
                   'includeAudio': data.get('include_audio') is not False}
        links = read_links(root, ident)
        used = {e.get('mediaId') for scene in timeline['scenes'] for track in _all_tracks(scene) for e in track['elements'] if e.get('mediaId')}
        media = []
        for asset_id in used & set(links):
            path, kind, row = resolve_ref(root, client, links[asset_id]['ref'])
            media.append({'id': asset_id, 'path': str(path), 'type': kind, 'name': links[asset_id]['name'],
                          'mime': row.get('mime') or {'video': 'video/mp4', 'audio': 'audio/mp4'}.get(kind, 'application/octet-stream'),
                          'meta': _public(client, ident, asset_id, links[asset_id])})
        task = uuid.uuid4().hex
        row = {'id': task, 'kind': 'opencut_render', 'status': 'queued', 'created_at': time.time(), 'user_id': session.get('user_id'),
               'client_id': int(client), 'work': {'project_id': _project_id(ident), 'revision': revision, 'timeline': timeline,
                                                   'media': media, 'options': options, 'api_root': _api_root()}}
        _enqueue(root, row)
        return ok({'id': task, 'status': 'queued', 'revision': revision})
    return execute(run)


DELIVERY_LUFS, DELIVERY_TRUE_PEAK = -14.0, -1.0  # padrão de Instagram, TikTok e YouTube


def normalize_loudness(path, timeout=600):
    """Leva o áudio da entrega a −14 LUFS e pico ≤ −1 dBTP (duas passadas do loudnorm); o vídeo é copiado.

    Não faz nada se o arquivo não tem áudio ou já está dentro de ±1 LU e do pico. Devolve as medições.
    """
    measured = subprocess.run(['ffmpeg', '-nostats', '-i', str(path), '-vn', '-af',
                               f'loudnorm=I={DELIVERY_LUFS}:TP={DELIVERY_TRUE_PEAK}:LRA=11:print_format=json', '-f', 'null', '-'],
                              capture_output=True, text=True, timeout=timeout)
    found = re.search(r'\{[^{}]*"input_i"[^{}]*\}', measured.stderr)
    if not found:
        return None
    stats = json.loads(found.group(0))
    loudness, peak = float(stats['input_i']), float(stats['input_tp'])
    if loudness < -70 or (abs(loudness - DELIVERY_LUFS) <= 1 and peak <= DELIVERY_TRUE_PEAK):
        return {'lufs': loudness, 'true_peak': peak, 'changed': False}
    target = path.with_name(f'{path.stem}.loudnorm{path.suffix}')
    filters = (f'loudnorm=I={DELIVERY_LUFS}:TP={DELIVERY_TRUE_PEAK}:LRA=11:measured_I={stats["input_i"]}:measured_TP={stats["input_tp"]}:'
               f'measured_LRA={stats["input_lra"]}:measured_thresh={stats["input_thresh"]}:offset={stats["target_offset"]}:linear=true,'
               'aresample=48000')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(path), '-map', '0', '-c:v', 'copy', '-af', filters, '-c:a', 'aac', '-b:a', '192k',
                    '-shortest', '-movflags', '+faststart', str(target)], check=True, capture_output=True, timeout=timeout)
    target.replace(path)
    return {'lufs': loudness, 'true_peak': peak, 'changed': True}


def _run_render(command, cwd, timeout):
    """Node e o Chromium que ele abre ficam num grupo próprio; no timeout o grupo inteiro é encerrado."""
    import os
    import signal
    env = dict(os.environ)
    browsers = Path(cwd) / 'instance' / 'ms-playwright'
    if not env.get('PLAYWRIGHT_BROWSERS_PATH') and browsers.is_dir():
        env['PLAYWRIGHT_BROWSERS_PATH'] = str(browsers)  # instalado pelo deploy; unidade antiga do worker não tem a variável
    process = subprocess.Popen(command, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               start_new_session=True, env=env)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # o grupo terminou junto com o prazo
        process.communicate()
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def render_project(work, dest, timeout=900):
    """Roda o editor compilado no Chromium do worker; projeto e mídias saem do disco, sem HTTP nem login."""
    import tempfile
    repo = Path(__file__).resolve().parents[2]
    script = repo / 'scripts' / 'studio-video-render.mjs'
    static = Path(current_app.static_folder) / 'cadu_studio' / 'video_editor'
    if not (static / 'app.js').exists():
        raise ValueError('Editor de vídeo não compilado no servidor (npm run build:video-editor).')
    with tempfile.TemporaryDirectory(prefix='vedit-render-') as temp:
        job = Path(temp) / 'job.json'
        job.write_text(json.dumps({**work, 'static': str(static), 'output': str(dest)}, ensure_ascii=False))
        result = _run_render(['node', str(script), str(job)], repo, timeout)
    if result.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        current_app.logger.error('Render do editor falhou: %s', (result.stderr or result.stdout)[-2000:])
        raise ValueError('O render do vídeo falhou no servidor.')
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        report = {}
    produced, wanted = report.get('format') or work['options']['format'], work['options']['format']
    if produced != wanted:
        # Chromium sem H.264/AAC (Linux) entrega WebM; o arquivo final continua no formato pedido.
        source = dest.with_suffix(f'.{produced}.tmp')
        dest.replace(source)
        try:
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(source), '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-f', wanted, str(dest)],
                           check=True, capture_output=True, timeout=timeout)
        finally:
            source.unlink(missing_ok=True)
    duration, streams = probe(dest)
    if 'video' not in streams:
        raise ValueError('O render não produziu vídeo.')
    loudness = normalize_loudness(dest) if 'audio' in streams and work['options']['format'] == 'mp4' else None
    return {'duration': duration, 'has_audio': 'audio' in streams, 'loudness': loudness}


@studio_or_admin_required_api
def render_content(ident):
    execute, _, _, _ = _http()

    def run():
        root = _scope(request.args.get('client_id'))
        _, row = _record(root, ident, 'task')
        if row.get('kind') != 'opencut_render' or row.get('status') != 'ready' or row.get('user_id') != session.get('user_id'):
            raise ValueError('Render indisponível.')
        extension = row['work']['options']['format']
        return send_file(root / f'{ident}.{extension}', mimetype=f'video/{extension}', as_attachment=True,
                         download_name=f'video-{row["work"]["project_id"][:8]}-r{row["work"]["revision"]}.{extension}')
    return execute(run)
