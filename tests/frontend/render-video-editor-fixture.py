"""Build the actual video editor template and a deterministic A/V fixture."""
from pathlib import Path
import subprocess
from jinja2 import Environment, FileSystemLoader
root=Path('tmp/studio-editor-check');root.mkdir(parents=True,exist_ok=True)
html=Environment(loader=FileSystemLoader('aicentralv2/templates'),autoescape=True).get_template('parametros/_mc_video.html').render()
(root/'index.html').write_text('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/css/modelagem_criativos.css"><link rel="stylesheet" href="/static/css/video-studio.css"><style>body{margin:0;font-family:Arial}</style></head><body>'+html+'<script type="module" src="/static/js/mc-cadu-video.js"></script></body></html>')
subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','testsrc2=s=320x180:d=3:r=24','-f','lavfi','-i','sine=frequency=440:duration=3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(root/'clip.mp4')],check=True)
