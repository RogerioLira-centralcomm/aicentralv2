#!/usr/bin/env bash
# Run from the deployed checkout. No git operations or web-service restart.
set -euo pipefail
studio_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
studio_python="${MEDIA_PYTHON:-$studio_root/venv/bin/python}"
[[ -x "$studio_python" ]] || studio_python="$studio_root/venv_new/bin/python"
[[ -x "$studio_python" ]] || { echo 'Python do ambiente virtual não encontrado.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'Este instalador requer Linux/systemd.' >&2; exit 1; }
command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null || { echo 'Instale ffmpeg e ffprobe antes de continuar.' >&2; exit 1; }
studio_user="$(systemctl show aicentralv2 --property=User --value)"
[[ -n "$studio_user" ]] || { echo 'Usuário do serviço aicentralv2 não identificado.' >&2; exit 1; }
studio_model="$studio_root/instance/media-models/whisper-small"
if ! "$studio_python" -c 'import faster_whisper, pywebpush' >/dev/null 2>&1; then
    echo 'Dependências do worker de mídia ausentes; instalando requirements-media.txt...'
    "$studio_python" -m pip install -r "$studio_root/requirements-media.txt"
else
    echo 'Dependências do worker de mídia já disponíveis; pulando instalação.'
fi
mkdir -p "$studio_model"
if [[ -f "$studio_model/config.json" && -f "$studio_model/model.bin" ]]; then
    echo 'Modelo Whisper já preparado; pulando download e carregamento inicial.'
else
    "$studio_python" - "$studio_model" <<'PY'
import sys
from faster_whisper.utils import download_model
from faster_whisper import WhisperModel
path=download_model('small',output_dir=sys.argv[1])
WhisperModel(path,device='cpu',compute_type='int8',local_files_only=True)
print('Modelo de transcrição preparado.')
PY
fi
# Editor de vídeo: o render roda o editor compilado no Chromium do Playwright (node + navegador no worker).
studio_node_dir=""
studio_browsers="$studio_root/instance/ms-playwright"
if command -v node >/dev/null && [[ -d "$studio_root/node_modules/playwright" ]]; then
    studio_node_dir="$(dirname "$(command -v node)")"
    sudo mkdir -p "$studio_browsers"
    sudo chown "$studio_user" "$studio_browsers"
    (cd "$studio_root" && sudo env PATH="$studio_node_dir:$PATH" "$studio_node_dir/npx" playwright install-deps chromium) \
        || echo 'Aviso: bibliotecas do sistema para o Chromium não instaladas; o render do editor de vídeo pode falhar.'
    (cd "$studio_root" && sudo -u "$studio_user" env PATH="$studio_node_dir:$PATH" PLAYWRIGHT_BROWSERS_PATH="$studio_browsers" \
        "$studio_node_dir/npx" playwright install chromium) \
        || echo 'Aviso: Chromium do editor de vídeo não instalado; o render do editor ficará indisponível.'
else
    echo 'Aviso: node ou playwright ausentes; o render do editor de vídeo ficará indisponível.'
fi
studio_unit_dir="$(mktemp -d)"
studio_unit="$studio_unit_dir/cadu-media-worker.service"
trap 'rm -rf "$studio_unit_dir"' EXIT
"$studio_python" - "$studio_unit" "$studio_root" "$studio_python" "$studio_user" "$studio_model" "$studio_node_dir" "$studio_browsers" <<'PY'
import sys
from pathlib import Path
out,root,python,user,model,node_dir,browsers=sys.argv[1:]
if any(c in value for value in (root,python,user,model,node_dir,browsers) for c in '\n\r"%'):
    raise SystemExit('Caminho/usuário incompatível com a unidade systemd.')
if not root.startswith('/') or not python.startswith('/') or not model.startswith('/'):
    raise SystemExit('A unidade systemd requer caminhos absolutos.')
Path(out).write_text(f'''[Unit]
Description=Cadu Media durable worker
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User={user}
WorkingDirectory={root}
Environment=PATH={Path(python).parent}:{node_dir + ':' if node_dir else ''}/usr/local/bin:/usr/bin:/bin
Environment=PLAYWRIGHT_BROWSERS_PATH={browsers}
Environment=AICENTRAL_ENV=production
Environment=MEDIA_WORKER_MODE=supervised
Environment=MEDIA_TRANSCRIBE_MODEL_PATH={model}
ExecStart={python} -m aicentralv2.creative_media.queue_worker
Restart=always
RestartSec=5
TimeoutStopSec=600
[Install]
WantedBy=multi-user.target
''')
PY
sudo -u "$studio_user" env MEDIA_TRANSCRIBE_MODEL_PATH="$studio_model" "$studio_python" -m aicentralv2.creative_media.queue_worker --check
if command -v systemd-analyze >/dev/null; then
    systemd-analyze verify "$studio_unit"
fi
sudo install -m 644 "$studio_unit" /etc/systemd/system/cadu-media-worker.service
sudo mkdir -p /etc/systemd/system/aicentralv2.service.d
printf '[Service]\nEnvironment="MEDIA_WORKER_MODE=supervised"\nEnvironment="MEDIA_TRANSCRIBE_MODEL_PATH=%s"\n' "$studio_model" | sudo tee /etc/systemd/system/aicentralv2.service.d/media-worker.conf >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable cadu-media-worker
sudo systemctl restart cadu-media-worker
sudo systemctl is-active --quiet cadu-media-worker
printf 'Worker instalado e ativo. O aplicativo adotará o modo supervisionado no próximo restart.\n'
