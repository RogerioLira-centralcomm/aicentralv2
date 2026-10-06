#!/usr/bin/env bash
# Instala o agendador dos radares ativos do Planner (a cada 5 minutos pega os que chegaram no horário).
# Sem CADU_RADAR_ENABLED ou sem a migração add_cadu_radar_v2, o comando não faz nada.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${RADAR_WATCH_PYTHON:-$root/venv/bin/python}"
[[ -x "$python_bin" ]] || python_bin="$root/venv_new/bin/python"
[[ -x "$python_bin" ]] || { echo 'Python do ambiente virtual não encontrado.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'Este instalador requer Linux/systemd.' >&2; exit 1; }
service_user="$(systemctl show gunicorn --property=User --value)"
[[ -n "$service_user" ]] || service_user="www-data"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
cat >"$tmp_dir/cadu-radar-watch.service" <<EOF2
[Unit]
Description=Roda os radares ativos do Planner que chegaram no horário
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User=$service_user
WorkingDirectory=$root
Environment=PATH=$(dirname "$python_bin"):/usr/local/bin:/usr/bin:/bin
Environment=AICENTRAL_ENV=production
TimeoutStartSec=30min
ExecStart=$python_bin -m flask --app run:app cadu_family radar-due --limit=3
EOF2
cat >"$tmp_dir/cadu-radar-watch.timer" <<'EOF2'
[Unit]
Description=Verifica a cada 5 minutos se algum radar ativo do Planner está no horário
[Timer]
OnCalendar=*:0/5
Persistent=false
Unit=cadu-radar-watch.service
[Install]
WantedBy=timers.target
EOF2
sudo install -m 644 "$tmp_dir/cadu-radar-watch.service" /etc/systemd/system/cadu-radar-watch.service
sudo install -m 644 "$tmp_dir/cadu-radar-watch.timer" /etc/systemd/system/cadu-radar-watch.timer
sudo systemctl daemon-reload
sudo systemctl enable --now cadu-radar-watch.timer
sudo systemctl is-active --quiet cadu-radar-watch.timer
echo 'Timer dos radares ativos do Planner instalado e ativo.'
