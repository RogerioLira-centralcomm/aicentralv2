#!/usr/bin/env bash
# Install the single supervised consumer for the Workspace brand-audit queue.
# Without it, audits started from the app or the MCP stay "queued" forever.
set -euo pipefail
audit_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
audit_python="${BRAND_AUDIT_PYTHON:-$audit_root/venv/bin/python}"
[[ -x "$audit_python" ]] || audit_python="$audit_root/venv_new/bin/python"
[[ -x "$audit_python" ]] || { echo 'Python do ambiente virtual não encontrado.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'Este instalador requer Linux/systemd.' >&2; exit 1; }
audit_user="$(systemctl show gunicorn --property=User --value)"
[[ -n "$audit_user" ]] || audit_user="www-data"
audit_tmp="$(mktemp -d)"
trap 'rm -rf "$audit_tmp"' EXIT
audit_unit="$audit_tmp/cadu-brand-audit-worker.service"
"$audit_python" - "$audit_unit" "$audit_root" "$audit_python" "$audit_user" <<'PY'
import sys
from pathlib import Path
out, root, python, user = sys.argv[1:]
if any(char in value for value in (root, python, user) for char in '\n\r"%'):
    raise SystemExit('Caminho/usuário incompatível com a unidade systemd.')
if not root.startswith('/') or not python.startswith('/'):
    raise SystemExit('A unidade systemd requer caminhos absolutos.')
Path(out).write_text(f'''[Unit]
Description=Cadu brand audit worker
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User={user}
WorkingDirectory={root}
Environment=PATH={Path(python).parent}:/usr/local/bin:/usr/bin:/bin
Environment=AICENTRAL_ENV=production
Environment=CADU_BRAND_AUDIT_WORKER_ENABLED=1
ExecStart={python} -m flask --app run:app cadu_workspace brand-audit-worker-loop
Restart=always
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=120
[Install]
WantedBy=multi-user.target
''')
PY
if command -v systemd-analyze >/dev/null; then systemd-analyze verify "$audit_unit"; fi
sudo install -m 644 "$audit_unit" /etc/systemd/system/cadu-brand-audit-worker.service
sudo systemctl daemon-reload
sudo systemctl enable --now cadu-brand-audit-worker.service
sudo systemctl is-active --quiet cadu-brand-audit-worker.service
echo 'Fila de auditoria de marca: worker supervisionado ativo (uma instância).'
