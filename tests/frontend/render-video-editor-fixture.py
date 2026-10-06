"""Build the actual video editor template and a deterministic A/V fixture."""
from pathlib import Path
import subprocess
from jinja2 import Environment, FileSystemLoader


def _atomic_write(target, text):
    # Vários testes de navegador renderizam a mesma fixture em paralelo; troca atômica evita ler arquivo pela metade.
    import os
    tmp = target.with_name(f'.{target.name}.{os.getpid()}.tmp')
    tmp.write_text(text)
    os.replace(tmp, target)
root=Path('tests/frontend/.fixtures/studio-editor');root.mkdir(parents=True,exist_ok=True)
html=Environment(loader=FileSystemLoader('aicentralv2/templates'),autoescape=True).get_template('parametros/_mc_video.html').render()
_atomic_write(root/'index.html', '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/css/modelagem_criativos.css"><link rel="stylesheet" href="/static/css/video-studio.css"><style>body{margin:0;font-family:Arial}</style></head><body>'+html+'<script type="module" src="/static/js/mc-cadu-video.js"></script></body></html>')
if not (root/'clip.mp4').exists(): subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','testsrc2=s=320x180:d=3:r=24','-f','lavfi','-i','sine=frequency=440:duration=3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(root/'clip.mp4')],check=True)
