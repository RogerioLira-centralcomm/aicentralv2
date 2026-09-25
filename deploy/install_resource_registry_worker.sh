#!/usr/bin/env bash
# Install one supervised consumer for project resource reconciliation.
set -euo pipefail
resource_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
resource_python="${RESOURCE_REGISTRY_PYTHON:-$resource_root/venv/bin/python}"
[[ -x "$resource_python" ]] || resource_python="$resource_root/venv_new/bin/python"
[[ -x "$resource_python" ]] || { echo 'Python do ambiente virtual não encontrado.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'Este instalador requer Linux/systemd.' >&2; exit 1; }
resource_user="$(systemctl show gunicorn --property=User --value)"
[[ -n "$resource_user" ]] || resource_user="$(systemctl show aicentralv2 --property=User --value)"
[[ -n "$resource_user" ]] || resource_user="www-data"
resource_tmp="$(mktemp -d)"
trap 'rm -rf "$resource_tmp"' EXIT
resource_unit="$resource_tmp/cadu-resource-registry-worker.service"
"$resource_python" - "$resource_unit" "$resource_root" "$resource_python" "$resource_user" <<'PY'
import sys
from pathlib import Path
out, root, python, user = sys.argv[1:]
if any(char in value for value in (root, python, user) for char in '\n\r"%'):
    raise SystemExit('Caminho/usuário incompatível com a unidade systemd.')
if not root.startswith('/') or not python.startswith('/'):
    raise SystemExit('A unidade systemd requer caminhos absolutos.')
Path(out).write_text(f'''[Unit]
Description=Cadu project resource registry worker
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User={user}
WorkingDirectory={root}
Environment=PATH={Path(python).parent}:/usr/local/bin:/usr/bin:/bin
Environment=AICENTRAL_ENV=production
ExecStart={python} -m flask --app run:app cadu_workspace resource-registry-worker-loop
Restart=always
RestartSec=5
TimeoutStopSec=120
[Install]
WantedBy=multi-user.target
''')
PY
if command -v systemd-analyze >/dev/null; then systemd-analyze verify "$resource_unit"; fi
sudo install -m 644 "$resource_unit" /etc/systemd/system/cadu-resource-registry-worker.service
sudo systemctl daemon-reload
sudo systemctl enable --now cadu-resource-registry-worker.service
sudo systemctl is-active --quiet cadu-resource-registry-worker.service
echo 'Worker do registro de recursos ativo.'
