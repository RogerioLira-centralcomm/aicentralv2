#!/usr/bin/env bash
set -euo pipefail
supertag_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
supertag_python="${REPORTS_PYTHON:-$supertag_root/venv/bin/python}"
[[ -x "$supertag_python" ]] || supertag_python="$supertag_root/venv_new/bin/python"
[[ -x "$supertag_python" ]] || { echo 'Python do ambiente virtual não encontrado.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'Este instalador requer Linux/systemd.' >&2; exit 1; }
supertag_user="$(systemctl show gunicorn --property=User --value)"
[[ -n "$supertag_user" ]] || supertag_user="www-data"
supertag_tmp="$(mktemp -d)"
trap 'rm -rf "$supertag_tmp"' EXIT
"$supertag_python" - "$supertag_tmp" "$supertag_root" "$supertag_python" "$supertag_user" <<'PY'
import sys
from pathlib import Path

out, root, python, user = sys.argv[1:]
if any(char in value for value in (root, python, user) for char in '\n\r"%'):
    raise SystemExit('Caminho/usuário incompatível com a unidade systemd.')
if not root.startswith('/') or not python.startswith('/'):
    raise SystemExit('A unidade systemd requer caminhos absolutos.')
Path(out, 'cadu-reports-supertag-retention.service').write_text(f'''[Unit]
Description=Prune expired Cadu Super Tag events
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User={user}
WorkingDirectory={root}
Environment=PATH={Path(python).parent}:/usr/local/bin:/usr/bin:/bin
Environment=AICENTRAL_ENV=production
ExecStart={python} {root}/scripts/purge_reports_supertag_events.py
''')
Path(out, 'cadu-reports-supertag-retention.timer').write_text('''[Unit]
Description=Hourly cleanup of expired Cadu Super Tag events
[Timer]
OnCalendar=hourly
Persistent=true
RandomizedDelaySec=5m
[Install]
WantedBy=timers.target
''')
PY
if command -v systemd-analyze >/dev/null; then
    systemd-analyze verify "$supertag_tmp/cadu-reports-supertag-retention.service" "$supertag_tmp/cadu-reports-supertag-retention.timer"
fi
sudo install -m 644 "$supertag_tmp/cadu-reports-supertag-retention.service" /etc/systemd/system/cadu-reports-supertag-retention.service
sudo install -m 644 "$supertag_tmp/cadu-reports-supertag-retention.timer" /etc/systemd/system/cadu-reports-supertag-retention.timer
sudo systemctl daemon-reload
sudo systemctl enable --now cadu-reports-supertag-retention.timer
sudo systemctl start cadu-reports-supertag-retention.service
echo 'Retenção da Super Tag ativa; limpeza executada e agendada por hora.'
