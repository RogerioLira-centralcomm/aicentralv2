#!/usr/bin/env bash
# Install two bounded, supervised consumers for the Workspace link-icon queue.
set -euo pipefail
link_icon_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
link_icon_python="${LINK_ICON_PYTHON:-$link_icon_root/venv/bin/python}"
[[ -x "$link_icon_python" ]] || link_icon_python="$link_icon_root/venv_new/bin/python"
[[ -x "$link_icon_python" ]] || { echo 'Python do ambiente virtual não encontrado.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'Este instalador requer Linux/systemd.' >&2; exit 1; }
link_icon_user="$(systemctl show gunicorn --property=User --value)"
[[ -n "$link_icon_user" ]] || link_icon_user="www-data"
link_icon_tmp="$(mktemp -d)"
trap 'rm -rf "$link_icon_tmp"' EXIT
link_icon_unit="$link_icon_tmp/cadu-link-icon-worker@.service"
"$link_icon_python" - "$link_icon_unit" "$link_icon_root" "$link_icon_python" "$link_icon_user" <<'PY'
import sys
from pathlib import Path
out, root, python, user = sys.argv[1:]
if any(char in value for value in (root, python, user) for char in '\n\r"%'):
    raise SystemExit('Caminho/usuário incompatível com a unidade systemd.')
if not root.startswith('/') or not python.startswith('/'):
    raise SystemExit('A unidade systemd requer caminhos absolutos.')
Path(out).write_text(f'''[Unit]
Description=Cadu link icon worker %i
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User={user}
WorkingDirectory={root}
Environment=PATH={Path(python).parent}:/usr/local/bin:/usr/bin:/bin
Environment=AICENTRAL_ENV=production
ExecStart={python} -m flask --app run:app cadu_workspace link-icon-worker-loop
Restart=always
RestartSec=5
TimeoutStopSec=120
[Install]
WantedBy=multi-user.target
''')
PY
if command -v systemd-analyze >/dev/null; then systemd-analyze verify "$link_icon_unit"; fi
sudo install -m 644 "$link_icon_unit" /etc/systemd/system/cadu-link-icon-worker@.service
sudo systemctl daemon-reload
sudo systemctl enable --now cadu-link-icon-worker@1.service cadu-link-icon-worker@2.service
sudo systemctl is-active --quiet cadu-link-icon-worker@1.service
sudo systemctl is-active --quiet cadu-link-icon-worker@2.service
echo 'Fila de ícones: dois workers supervisionados ativos.'
