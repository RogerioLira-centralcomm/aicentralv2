#!/usr/bin/env bash
# Install the supervised Reports page-availability monitor.
set -euo pipefail
reports_monitor_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
reports_monitor_python="${REPORTS_MONITOR_PYTHON:-$reports_monitor_root/venv/bin/python}"
[[ -x "$reports_monitor_python" ]] || reports_monitor_python="$reports_monitor_root/venv_new/bin/python"
[[ -x "$reports_monitor_python" ]] || { echo 'Python do ambiente virtual não encontrado.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'Este instalador requer Linux/systemd.' >&2; exit 1; }
reports_monitor_user="$(systemctl show gunicorn --property=User --value)"
[[ -n "$reports_monitor_user" ]] || reports_monitor_user="www-data"
reports_monitor_tmp="$(mktemp -d)"
trap 'rm -rf "$reports_monitor_tmp"' EXIT
reports_monitor_unit="$reports_monitor_tmp/cadu-reports-flow-monitor.service"
"$reports_monitor_python" - "$reports_monitor_unit" "$reports_monitor_root" "$reports_monitor_python" "$reports_monitor_user" <<'PY'
import sys
from pathlib import Path
out, root, python, user = sys.argv[1:]
if any(char in value for value in (root, python, user) for char in '\n\r"%'):
    raise SystemExit('Caminho/usuário incompatível com a unidade systemd.')
if not root.startswith('/') or not python.startswith('/'):
    raise SystemExit('A unidade systemd requer caminhos absolutos.')
Path(out).write_text(f'''[Unit]
Description=Cadu Reports flow page monitor
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User={user}
WorkingDirectory={root}
Environment=PATH={Path(python).parent}:/usr/local/bin:/usr/bin:/bin
Environment=AICENTRAL_ENV=production
ExecStart={python} -m flask --app run:app cadu_connect reports-flow-monitor-loop
Restart=always
RestartSec=5
TimeoutStopSec=30
[Install]
WantedBy=multi-user.target
''')
PY
if command -v systemd-analyze >/dev/null; then systemd-analyze verify "$reports_monitor_unit"; fi
sudo install -m 644 "$reports_monitor_unit" /etc/systemd/system/cadu-reports-flow-monitor.service
sudo systemctl daemon-reload
sudo systemctl enable --now cadu-reports-flow-monitor.service
sudo systemctl is-active --quiet cadu-reports-flow-monitor.service
echo 'Monitor de disponibilidade de páginas Reports instalado e ativo.'
