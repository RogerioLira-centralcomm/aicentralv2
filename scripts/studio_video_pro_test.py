"""Teste profissional do editor de vídeo (roteiro em docs/video-editor-teste-profissional.md).

Monta a peça de 12 s em 9:16 pela Editor API, renderiza pelos caminhos do servidor (software e, se houver,
GPU) e mede a entrega: resolução, fps, codec, taxa de bits, volume (LUFS), pico, quadros pretos/congelados,
quadros de referência e semelhança entre caminhos. Também grava o lote de comandos e copia as mídias para
o servidor de teste, para gerar o mesmo vídeo pelo botão Exportar do navegador.

Uso: .venv/bin/python scripts/studio_video_pro_test.py [--assets PASTA] [--out PASTA] [--gpu metal|vulkan|gl]
     [--compare caminho.mp4 ...]   (inclui outros arquivos, como o export do navegador, nas medições)
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
if (REPO / 'instance/ms-playwright').is_dir():
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(REPO / 'instance/ms-playwright'))

from flask import Flask  # noqa: E402

from aicentralv2.creative_media.studio_video_editor import apply_commands, render_project  # noqa: E402

ASSETS = {
    'hero': ('4ae3092d598f4780947f8ed0978c5f15.mp4', 'video'),
    'telas': ('0110880e0e3a4170bb6bd078b5424317.png', 'image'),
    'paineis': ('09153d03984a4b369c4683a97ba1e324.png', 'image'),
    'equipe': ('4b9cf17b9bdc41f582a32bf9f4e3b215.png', 'image'),
    'mapa': ('d71071ac219a47aabbc9432b072c20de.png', 'image'),
    'trilha': ('a3f61ccb25974bfe968f882298c5992a.mp4', 'audio-from-video'),
}
W, H, FPS = 1080, 1920, 30
BACKGROUND = '#3a0b3d'  # roxo das ilustrações


def run(*args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs)


def probe(path):
    data = json.loads(run('ffprobe', '-v', 'error', '-show_entries',
                          'format=duration,bit_rate:stream=codec_type,codec_name,profile,width,height,r_frame_rate,avg_frame_rate',
                          '-of', 'json', str(path)).stdout)
    return data


def prepare_media(assets, work):
    media = []
    for key, (name, kind) in ASSETS.items():
        source = assets / name
        if not source.exists():
            raise SystemExit(f'Mídia ausente: {source}')
        if kind == 'audio-from-video':
            target = work / f'{key}.m4a'
            run('ffmpeg', '-y', '-v', 'error', '-i', str(source), '-vn', '-c:a', 'aac', '-b:a', '192k', str(target))
            kind = 'audio'
        else:
            target = work / f'{key}{source.suffix}'
            shutil.copy(source, target)
        info = probe(target)
        video = next((s for s in info['streams'] if s['codec_type'] == 'video'), {})
        duration = float(info['format'].get('duration') or 0) or None
        width, height = video.get('width'), video.get('height')
        if kind == 'image':
            from PIL import Image
            with Image.open(target) as image:
                width, height = image.size
            duration = None
        mime = {'video': 'video/mp4', 'audio': 'audio/mp4', 'image': 'image/png'}[kind]
        media.append({'id': f'pro-{key}', 'key': key, 'path': str(target), 'type': kind, 'name': target.name, 'mime': mime,
                      'duration': duration, 'width': width, 'height': height})
    return media


def commands():
    """Roteiro da peça (segundos). Texto em fração do quadro; y 0,15 fica abaixo da área do Reels.

    Recursos de acabamento usados: escala para cobrir o quadro, zoom lento nas imagens, entrada suave dos
    textos e trilha cobrindo a peça inteira (o áudio de origem tem 8 s, então entra de novo aos 8 s).
    """
    shots = [('telas', 'Gestão em qualquer tela', 'zoom_in'), ('paineis', 'Dados em tempo real', 'zoom_out'),
             ('equipe', 'Sua equipe conectada', 'zoom_in')]
    fade = lambda: {'op': 'animate', 'args': {'element_id': '@last', 'property': 'opacity', 'ease': 'ease',
                                               'keyframes': [{'at': 0, 'value': 0}, {'at': .3, 'value': 1}]}}
    # O vídeo é 16:9: escala para cobrir a altura do quadro vertical, com zoom lento.
    batch = [{'op': 'set_canvas', 'args': {'width': W, 'height': H, 'background': BACKGROUND}},
             {'op': 'add_media', 'args': {'asset_id': 'pro-hero', 'duration': 3, 'scale': 3.2, 'motion': 'zoom_in'}}]
    for key, _, motion in shots:
        batch.append({'op': 'add_media', 'args': {'asset_id': f'pro-{key}', 'duration': 2.25, 'motion': motion}})
    batch.append({'op': 'add_media', 'args': {'asset_id': 'pro-mapa', 'duration': 2.25, 'motion': 'zoom_out'}})
    batch.append({'op': 'add_media', 'args': {'asset_id': 'pro-trilha', 'start': 0, 'volume': -12}})
    batch.append({'op': 'add_media', 'args': {'asset_id': 'pro-trilha', 'start': 8, 'duration': 4, 'volume': -12}})
    batch.append({'op': 'add_text', 'args': {'text': 'Seu negócio na palma da mão', 'start': 0.2, 'duration': 2.8, 'y': .18, 'size': 6,
                                             'bold': True, 'name': 'Gancho'}})
    batch.append(fade())
    start = 3.0
    for key, line, _ in shots:
        batch.append({'op': 'add_text', 'args': {'text': line, 'start': start, 'duration': 2.25, 'y': .18, 'size': 5, 'bold': True,
                                                 'track_id': '@previous'}})
        batch.append(fade())
        start += 2.25
    batch.append({'op': 'add_text', 'args': {'text': 'Teste grátis por 30 dias', 'start': start, 'duration': 2.25, 'y': .74, 'size': 4,
                                             'bold': True, 'color': '#0b2b26', 'background': '#2ee6b6', 'track_id': '@previous'}})
    batch.append(fade())
    return batch


def build_timeline(media):
    base = json.loads((REPO / 'scripts/fixtures/opencut-empty-timeline.json').read_text())
    base['metadata']['name'] = 'Teste profissional 9x16'
    links = {row['id']: {'ref': row['id'], 'type': row['type'], 'name': row['name'], 'duration': row['duration']} for row in media}
    timeline, outputs, text_track = base, [], None
    for command in commands():
        if command['args'].get('element_id') == '@last':
            command = {**command, 'args': {**command['args'], 'element_id': outputs[-1]['element_id']}}
        if command['args'].get('track_id') == '@previous':
            command = {**command, 'args': {**command['args'], 'track_id': text_track}}
        timeline, result = apply_commands(timeline, [command], links)
        outputs.extend(result)
        if command['op'] == 'add_text':
            text_track = result[0]['track_id']
    return timeline, links


def measure(path, reference_frames):
    info = probe(path)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    audio = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
    loud = subprocess.run(['ffmpeg', '-nostats', '-i', str(path), '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                          capture_output=True, text=True).stderr
    lufs = re.findall(r'I:\s+(-?[\d.]+) LUFS', loud)
    peak = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', loud)
    detect = subprocess.run(['ffmpeg', '-nostats', '-i', str(path), '-vf', 'blackdetect=d=0.2:pix_th=0.05,freezedetect=n=0.001:d=1.5',
                             '-an', '-f', 'null', '-'], capture_output=True, text=True).stderr
    blacks = re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', detect)
    freezes = re.findall(r'freeze_start: ([\d.]+)', detect)
    silence = subprocess.run(['ffmpeg', '-nostats', '-i', str(path), '-vn', '-af', 'silencedetect=noise=-50dB:d=0.7', '-f', 'null', '-'],
                             capture_output=True, text=True).stderr
    silences = re.findall(r'silence_start: ([\d.]+)', silence)
    frames = []
    for at in reference_frames:
        target = path.with_name(f'{path.stem}-{at:.1f}s.png')
        run('ffmpeg', '-y', '-v', 'error', '-ss', str(at), '-i', str(path), '-frames:v', '1', str(target))
        frames.append(target)
    num, den = map(int, video['avg_frame_rate'].split('/'))
    return {
        'arquivo': path.name, 'resolucao': f'{video["width"]}x{video["height"]}', 'fps': round(num / den, 2) if den else 0,
        'duracao_s': round(float(info['format']['duration']), 3), 'video': f'{video["codec_name"]} {video.get("profile", "")}'.strip(),
        'audio': audio['codec_name'] if audio else None, 'mbps': round(int(info['format'].get('bit_rate', 0)) / 1e6, 2),
        'lufs': float(lufs[-1]) if lufs else None, 'pico_dbfs': float(peak[-1]) if peak else None,
        'pretos': [(float(a), float(b)) for a, b in blacks], 'congelados_desde': [float(x) for x in freezes],
        'silencios_desde': [float(x) for x in silences], 'quadros': [str(f) for f in frames],
    }


def ssim(a, b):
    result = subprocess.run(['ffmpeg', '-nostats', '-i', str(a), '-i', str(b), '-lavfi',
                             '[0:v]scale=540:960,setsar=1[x];[1:v]scale=540:960,setsar=1[y];[x][y]ssim', '-f', 'null', '-'],
                            capture_output=True, text=True).stderr
    found = re.findall(r'All:([\d.]+)', result)
    return float(found[-1]) if found else None


def verdict(row):
    checks = {
        '1080x1920': row['resolucao'] == f'{W}x{H}',
        '30 fps': abs(row['fps'] - FPS) < 0.1,
        'duração 12 s': abs(row['duracao_s'] - 12) <= 1 / FPS + 0.05,
        'H.264 + AAC': row['video'].startswith('h264') and row['audio'] == 'aac',
        'taxa ≥ 5 Mb/s': row['mbps'] >= 5,
        '−14 LUFS ±1': row['lufs'] is not None and abs(row['lufs'] + 14) <= 1,
        'pico ≤ −1 dBFS': row['pico_dbfs'] is not None and row['pico_dbfs'] <= -1,
        'sem quadro preto': not row['pretos'],
        'sem quadro congelado': not row['congelados_desde'],
        'sem silêncio longo': not row['silencios_desde'],
    }
    return checks


def contact_sheet(rows, out):
    from PIL import Image, ImageDraw
    thumbs = [[Image.open(f).convert('RGB').resize((216, 384)) for f in row['quadros']] for row in rows]
    sheet = Image.new('RGB', (len(thumbs[0]) * 226 + 10, len(thumbs) * 414 + 10), '#111')
    draw = ImageDraw.Draw(sheet)
    for r, (row, line) in enumerate(zip(rows, thumbs)):
        for c, thumb in enumerate(line):
            sheet.paste(thumb, (10 + c * 226, 30 + r * 414))
        draw.text((10, 10 + r * 414), row['arquivo'], fill='#eee')
    sheet.save(out, quality=88)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets', type=Path, default=REPO / 'aicentralv2/static/uploads/creative_generated')
    parser.add_argument('--out', type=Path, default=REPO / 'instance/video-editor-pro-test')
    parser.add_argument('--gpu', choices=['metal', 'vulkan', 'gl'])
    parser.add_argument('--compare', type=Path, nargs='*', default=[])
    parser.add_argument('--skip-render', action='store_true', help='só mede os arquivos já gerados e os de --compare')
    parser.add_argument('--quality', choices=['medium', 'high', 'very_high'], default='very_high')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    media = prepare_media(args.assets, args.out)
    timeline, _ = build_timeline(media)
    (args.out / 'comandos.json').write_text(json.dumps(commands(), ensure_ascii=False, indent=1))
    # Mesmas mídias no servidor de teste, para o caminho do navegador.
    samples = REPO / 'instance/video-editor-dev/samples'
    samples.mkdir(parents=True, exist_ok=True)
    for row in media:
        shutil.copy(row['path'], samples / Path(row['path']).name)

    app = Flask('pro_test', static_folder=str(REPO / 'aicentralv2/static'))
    for row in media:
        row['meta'] = {'id': row['id'], 'name': row['name'], 'type': row['type'], 'size': Path(row['path']).stat().st_size, 'lastModified': 0,
                       'duration': row['duration'], 'width': row['width'], 'height': row['height']}
    outputs = []
    paths = [('servidor-software', None)] + ([(f'servidor-gpu-{args.gpu}', args.gpu)] if args.gpu else [])
    for label, gpu in paths:
        dest = args.out / f'{label}.mp4'
        if not args.skip_render:
            os.environ.pop('CADU_RENDER_GPU', None)
            if gpu:
                os.environ['CADU_RENDER_GPU'] = gpu
            started = time.time()
            with app.app_context():
                render_project({'project_id': 'pro-test', 'revision': 1, 'timeline': timeline, 'media': media,
                                'options': {'format': 'mp4', 'quality': args.quality, 'includeAudio': True}}, dest, timeout=1800)
            print(f'{label}: render em {time.time() - started:.1f} s')
        if dest.exists():
            outputs.append(dest)
    for extra in args.compare:
        extra = extra.resolve()
        target = extra if extra.parent == args.out.resolve() else args.out / f'navegador-{extra.name}'
        if extra != target:
            shutil.copy(extra, target)
        outputs.append(target)

    reference = [1.0, 2.6, 4.0, 6.3, 8.6, 11.0]
    rows = [measure(path, reference) for path in outputs]
    for row in rows:
        checks = verdict(row)
        print(f"\n{row['arquivo']}: {row['resolucao']} {row['fps']} fps {row['duracao_s']} s {row['video']} + {row['audio']} "
              f"{row['mbps']} Mb/s {row['lufs']} LUFS pico {row['pico_dbfs']} dBFS")
        for name, passed in checks.items():
            print(f'  {"✓" if passed else "✗"} {name}')
        if row['pretos']:
            print(f'    pretos: {row["pretos"]}')
        if row['congelados_desde']:
            print(f'    congelado a partir de: {row["congelados_desde"]}')
        if row['silencios_desde']:
            print(f'    silêncio a partir de: {row["silencios_desde"]}')
    for a, b in zip(outputs, outputs[1:]):
        print(f'\nSSIM {a.name} × {b.name}: {ssim(a, b)}')
    contact_sheet(rows, args.out / 'quadros.jpg')
    (args.out / 'medicoes.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f'\nArquivos em {args.out}')


if __name__ == '__main__':
    main()
