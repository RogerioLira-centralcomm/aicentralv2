#!/usr/bin/env bash
# Install one supervised consumer for durable conversation-memory checkpoints.
set -euo pipefail
memory_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
memory_python="${CONVERSATION_MEMORY_PYTHON:-$memory_root/venv/bin/python}"
[[ -x "$memory_python" ]] || memory_python="$memory_root/venv_new/bin/python"
[[ -x "$memory_python" ]] || { echo 'Python do ambiente virtual não encontrado.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'Este instalador requer Linux/systemd.' >&2; exit 1; }
memory_user="$(systemctl show aicentralv2 --property=User --value)"
[[ -n "$memory_user" ]] || memory_user="$(systemctl show gunicorn --property=User --value)"
[[ -n "$memory_user" ]] || memory_user="www-data"
memory_tmp="$(mktemp -d)"
trap 'rm -rf "$memory_tmp"' EXIT
memory_unit="$memory_tmp/cadu-conversation-memory-worker.service"
"$memory_python" - "$memory_unit" "$memory_root" "$memory_python" "$memory_user" <<'PY'
import sys
from pathlib import Path
out, root, python, user = sys.argv[1:]
if any(char in value for value in (root, python, user) for char in '\n\r"%'):
    raise SystemExit('Caminho/usuário incompatível com a unidade systemd.')
if not root.startswith('/') or not python.startswith('/'):
    raise SystemExit('A unidade systemd requer caminhos absolutos.')
Path(out).write_text(f'''[Unit]
Description=Cadu conversation memory worker
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User={user}
WorkingDirectory={root}
Environment=PATH={Path(python).parent}:/usr/local/bin:/usr/bin:/bin
Environment=AICENTRAL_ENV=production
ExecStart={python} -m flask --app run:app conversation-memory-worker-loop
Restart=always
RestartSec=5
TimeoutStopSec=120
[Install]
WantedBy=multi-user.target
''')
PY
if command -v systemd-analyze >/dev/null; then systemd-analyze verify "$memory_unit"; fi
sudo install -m 644 "$memory_unit" /etc/systemd/system/cadu-conversation-memory-worker.service
sudo systemctl daemon-reload
sudo systemctl enable --now cadu-conversation-memory-worker.service
sudo systemctl is-active --quiet cadu-conversation-memory-worker.service
echo 'Worker de memória longa ativo.'
