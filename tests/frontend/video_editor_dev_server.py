"""Servidor isolado do editor de vídeo para testes no navegador.

Só registra as rotas do Studio, em modo de teste: projetos no SQLite local e arquivos num diretório
temporário. Não abre conexão com o banco configurado no .env (que é o de produção). A rota /__dev/login
existe apenas aqui e cria uma sessão de administrador de teste.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

from flask import Blueprint, Flask, redirect, request, session

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from aicentralv2.creative_media.studio import register_studio_routes  # noqa: E402
from aicentralv2.creative_media import studio_video_editor  # noqa: E402
from aicentralv2.creative_media.http import _execute, _json, _ok  # noqa: E402


class NoService:
    """Bloqueia o serviço que fala com o banco: vídeos gerados ficam fora da biblioteca neste servidor."""
    def __getattr__(self, name):
        raise RuntimeError('Serviço de banco desligado no servidor de teste.')


instance = Path(os.environ.get('VIDEO_EDITOR_DEV_INSTANCE') or REPO / 'instance' / 'video-editor-dev')
instance.mkdir(parents=True, exist_ok=True)
app = Flask('video_editor_dev', instance_path=str(instance), static_folder=str(REPO / 'aicentralv2/static'),
            template_folder=str(REPO / 'aicentralv2/templates'))
app.secret_key = 'dev-only'
app.testing = True
app.config['MEDIA_WORKER_MODE'] = 'thread'
bp = Blueprint('studio', __name__, url_prefix='/parametros')
register_studio_routes(bp)
app.register_blueprint(bp)
app.add_url_rule('/', 'index', lambda: redirect('/__dev/login'))
http = (_execute, _json, _ok, NoService)
for target in ('aicentralv2.creative_media.studio_video_editor._http', 'aicentralv2.creative_media.studio._http',
               'aicentralv2.creative_media.studio_tasks._http', 'aicentralv2.creative_media.studio_media._http'):
    patch(target, return_value=http).start()


@app.route('/__dev/login')
def dev_login():
    session.update(user_id=7, user_type='admin', is_centralcomm=True)
    client = request.args.get('client_id', '31')
    from aicentralv2.creative_media.studio import _project_store
    from aicentralv2.creative_media import studio_projects
    project = request.args.get('project')
    if not project:
        project = _project_store(studio_projects).save(client, {'name': 'Projeto de teste', 'video_editor': None})['id']
    return redirect(f'/parametros/video-editor?client_id={client}&project={project}&name=Projeto%20de%20teste')


@app.route('/__dev/sample/<name>')
def dev_sample(name):
    # Amostras locais para simular upload no navegador de teste.
    from flask import send_from_directory
    return send_from_directory(_samples(), name)


def _samples():
    """Gera com FFmpeg, uma vez, um vídeo com som, uma trilha e uma imagem para os testes."""
    import subprocess
    folder = instance / 'samples'
    folder.mkdir(exist_ok=True)
    jobs = {
        'clip.mp4': ['-f', 'lavfi', '-i', 'testsrc2=s=1280x720:d=6:r=30', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=6',
                     '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest'],
        'music.wav': ['-f', 'lavfi', '-i', 'sine=frequency=660:duration=4'],
        'cover.png': ['-f', 'lavfi', '-i', 'gradients=s=1080x1080:d=1', '-frames:v', '1'],
    }
    for name, args in jobs.items():
        if not (folder / name).exists():
            subprocess.run(['ffmpeg', '-y', '-v', 'error', *args, str(folder / name)], check=True)
    return str(folder)


if __name__ == '__main__':
    print('instance:', instance, flush=True)
    app.run(port=int(os.environ.get('PORT', 5077)), threaded=True)
