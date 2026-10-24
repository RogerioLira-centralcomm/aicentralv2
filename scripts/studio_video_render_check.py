"""Verifica o render do editor de vídeo nesta máquina (rodar no servidor Linux antes de liberar).

Uso, no checkout do servidor:  .venv/bin/python scripts/studio_video_render_check.py

Gera mídias de teste com FFmpeg, monta a timeline pela Editor API e renderiza pelo mesmo caminho
do worker (``render_project``), duas vezes: com o codec que o Chromium tiver e simulando Chromium
sem H.264 (WebM convertido para MP4). Confere imagem, texto e áudio em instantes conhecidos.
Não usa banco nem rede além das fontes do Google. Sai com código 1 se algo falhar.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
# Mesmo navegador do worker (instalado por deploy/install_media_worker.sh).
if (REPO / 'instance/ms-playwright').is_dir():
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(REPO / 'instance/ms-playwright'))

from flask import Flask  # noqa: E402

from aicentralv2.creative_media.studio_video_editor import apply_commands, render_project  # noqa: E402


def ff(*args):
    subprocess.run(['ffmpeg', '-y', '-v', 'error', *args], check=True, capture_output=True)


def luma(path, at):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(at), '-i', str(path), '-frames:v', '1', '-vf', 'scale=96:-2',
                          '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], check=True, capture_output=True).stdout
    return sum(raw) / max(1, len(raw))


def volume(path, at, span=0.6):
    result = subprocess.run(['ffmpeg', '-ss', str(at), '-t', str(span), '-i', str(path), '-vn', '-af', 'volumedetect', '-f', 'null', '-'],
                            capture_output=True, text=True)
    line = next((row for row in result.stderr.splitlines() if 'mean_volume' in row), '')
    return float(line.split('mean_volume:')[1].split('dB')[0]) if line else -99.0


def probe(path):
    data = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,codec_name',
                                      '-of', 'json', str(path)], check=True, capture_output=True, text=True).stdout)
    return float(data['format']['duration']), {s['codec_type']: s['codec_name'] for s in data['streams']}


def main():
    work_dir = Path(tempfile.mkdtemp(prefix='render-check-'))
    clip, music, cover = work_dir / 'clip.mp4', work_dir / 'music.m4a', work_dir / 'cover.png'
    # Clipe colorido com tom de 440 Hz; trilha de 660 Hz; capa em gradiente claro.
    ff('-f', 'lavfi', '-i', 'testsrc2=s=1280x720:d=4:r=30', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=4',
       '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(clip))
    ff('-f', 'lavfi', '-i', 'sine=frequency=660:duration=3', '-c:a', 'aac', str(music))
    ff('-f', 'lavfi', '-i', 'color=c=0xc8b4ff:s=1080x1080:d=1', '-frames:v', '1', str(cover))
    media = [
        {'id': 'check-video', 'path': str(clip), 'type': 'video', 'name': 'clip.mp4', 'mime': 'video/mp4', 'duration': 4.0},
        {'id': 'check-audio', 'path': str(music), 'type': 'audio', 'name': 'music.m4a', 'mime': 'audio/mp4', 'duration': 3.0},
        {'id': 'check-image', 'path': str(cover), 'type': 'image', 'name': 'cover.png', 'mime': 'image/png', 'width': 1080, 'height': 1080},
    ]
    links = {row['id']: {'ref': row['id'], 'type': row['type'], 'name': row['name'], 'duration': row.get('duration')} for row in media}
    base = json.loads((REPO / 'scripts/fixtures/opencut-empty-timeline.json').read_text())
    timeline, _ = apply_commands(base, [
        {'op': 'add_media', 'args': {'asset_id': 'check-image', 'duration': 2}},
        {'op': 'add_media', 'args': {'asset_id': 'check-video'}},
        {'op': 'add_media', 'args': {'asset_id': 'check-audio', 'start': 0.5}},
        {'op': 'add_text', 'args': {'text': 'VERIFICA', 'start': 0.2, 'duration': 1.5, 'y': .8, 'size': 20, 'background': '#000000', 'bold': True}},
    ], links)
    for row in media:
        row['meta'] = {'id': row['id'], 'name': row['name'], 'type': row['type'], 'size': Path(row['path']).stat().st_size,
                       'lastModified': 0, 'duration': row.get('duration'), 'width': row.get('width'), 'height': row.get('height')}

    app = Flask('render_check', static_folder=str(REPO / 'aicentralv2/static'))
    failures = []
    for label, env in (('codec do navegador', {}), ('sem H.264 (WebM → MP4)', {'CADU_RENDER_SIMULATE_NO_H264': '1'})):
        dest = work_dir / f'out-{len(failures)}-{int(time.time())}.mp4'
        os.environ.pop('CADU_RENDER_SIMULATE_NO_H264', None)
        os.environ.update(env)
        started = time.time()
        try:
            with app.app_context():
                render_project({'project_id': 'render-check', 'revision': 1, 'timeline': timeline, 'media': media,
                                'options': {'format': 'mp4', 'quality': 'high', 'includeAudio': True}}, dest, timeout=600)
        except Exception as error:  # o relatório precisa mostrar as duas tentativas
            failures.append(f'{label}: {error}')
            print(f'FALHOU  {label}: {error}')
            continue
        seconds = time.time() - started
        duration, codecs = probe(dest)
        checks = {
            'duração ≈ 6 s': abs(duration - 6) < 0.3,
            'MP4 H.264 + AAC': codecs.get('video') == 'h264' and codecs.get('audio') == 'aac',
            'imagem não está preta (1 s)': luma(dest, 1.0) > 40,
            'vídeo não está preto (4 s)': luma(dest, 4.0) > 40,
            'texto muda o quadro (1 s × 1,9 s)': abs(luma(dest, 1.0) - luma(dest, 1.9)) > 2,
            'silêncio antes da trilha (0–0,4 s)': volume(dest, 0.0, 0.4) < -60,
            'áudio presente (3 s)': volume(dest, 3.0) > -40,
        }
        status = 'OK' if all(checks.values()) else 'FALHOU'
        print(f'{status:7} {label}: {seconds:.1f} s de render, {duration:.2f} s, {codecs}')
        for name, passed in checks.items():
            print(f'        {"✓" if passed else "✗"} {name}')
        if status != 'OK':
            failures.append(label)
        shutil.copy(dest, work_dir / f'resultado-{"webm" if env else "nativo"}.mp4')
    print(f'Arquivos em {work_dir}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
