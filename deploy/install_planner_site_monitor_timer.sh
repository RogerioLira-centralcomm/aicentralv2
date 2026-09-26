#!/usr/bin/env bash
# Instala verificações de disponibilidade para os sites do Planner.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PLANNER_MONITOR_PYTHON:-$root/venv/bin/python}"
[[ -x "$python_bin" ]] || python_bin="$root/venv_new/bin/python"
[[ -x "$python_bin" ]] || { echo 'Python do ambiente virtual não encontrado.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'Este instalador requer Linux/systemd.' >&2; exit 1; }
service_user="$(systemctl show gunicorn --property=User --value)"
[[ -n "$service_user" ]] || service_user="www-data"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
cat >"$tmp_dir/cadu-planner-site-monitor.service" <<EOF
[Unit]
Description=Verifica disponibilidade dos sites do Planner
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User=$service_user
WorkingDirectory=$root
Environment=PATH=$(dirname "$python_bin"):/usr/local/bin:/usr/bin:/bin
Environment=AICENTRAL_ENV=production
ExecStart=$python_bin -m flask --app run:app cadu_family monitor-planner-sites --limit=1
EOF
cat >"$tmp_dir/cadu-planner-site-monitor.timer" <<'EOF'
[Unit]
Description=Executa as verificações de sites do Planner a cada minuto
[Timer]
OnCalendar=*-*-* *:*:00
Persistent=true
Unit=cadu-planner-site-monitor.service
[Install]
WantedBy=timers.target
EOF
sudo install -m 644 "$tmp_dir/cadu-planner-site-monitor.service" /etc/systemd/system/cadu-planner-site-monitor.service
sudo install -m 644 "$tmp_dir/cadu-planner-site-monitor.timer" /etc/systemd/system/cadu-planner-site-monitor.timer
sudo systemctl daemon-reload
sudo systemctl enable --now cadu-planner-site-monitor.timer
sudo systemctl is-active --quiet cadu-planner-site-monitor.timer
echo 'Timer de disponibilidade do Planner instalado e ativo.'
