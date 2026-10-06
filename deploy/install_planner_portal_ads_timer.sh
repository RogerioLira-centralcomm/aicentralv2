#!/usr/bin/env bash
# Instala a verificação diária de ads.txt e sinais programáticos dos portais do Planner.
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
cat >"$tmp_dir/cadu-planner-portal-ads.service" <<EOF
[Unit]
Description=Verifica ads.txt e sinais programáticos dos portais do Planner
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User=$service_user
WorkingDirectory=$root
Environment=PATH=$(dirname "$python_bin"):/usr/local/bin:/usr/bin:/bin
Environment=AICENTRAL_ENV=production
TimeoutStartSec=3h
ExecStart=$python_bin -m flask --app run:app cadu_family crawl-planner-portals-ads --limit=400 --workers=6 --stale-days=30
EOF
cat >"$tmp_dir/cadu-planner-portal-ads.timer" <<'EOF'
[Unit]
Description=Executa a verificação de ads.txt dos portais do Planner todo dia de madrugada
[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true
Unit=cadu-planner-portal-ads.service
[Install]
WantedBy=timers.target
EOF
sudo install -m 644 "$tmp_dir/cadu-planner-portal-ads.service" /etc/systemd/system/cadu-planner-portal-ads.service
sudo install -m 644 "$tmp_dir/cadu-planner-portal-ads.timer" /etc/systemd/system/cadu-planner-portal-ads.timer
sudo systemctl daemon-reload
sudo systemctl enable --now cadu-planner-portal-ads.timer
sudo systemctl is-active --quiet cadu-planner-portal-ads.timer
echo 'Timer de ads.txt dos portais do Planner instalado e ativo.'
