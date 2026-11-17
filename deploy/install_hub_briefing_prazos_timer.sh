#!/usr/bin/env bash
# Instala o timer dos lembretes de prazo (12 h, 4 h e atraso) dos briefings de cotação do hub.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${HUB_PRAZOS_PYTHON:-$root/venv/bin/python}"
[[ -x "$python_bin" ]] || python_bin="$root/venv_new/bin/python"
[[ -x "$python_bin" ]] || { echo 'Python do ambiente virtual não encontrado.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'Este instalador requer Linux/systemd.' >&2; exit 1; }
service_user="$(systemctl show gunicorn --property=User --value)"
[[ -n "$service_user" ]] || service_user="www-data"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
cat >"$tmp_dir/cadu-hub-briefing-prazos.service" <<EOF
[Unit]
Description=Lembretes do prazo de 24 h dos briefings de cotação do hub
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User=$service_user
WorkingDirectory=$root
Environment=PATH=$(dirname "$python_bin"):/usr/local/bin:/usr/bin:/bin
Environment=AICENTRAL_ENV=production
ExecStart=$python_bin -m flask --app run:app process-hub-briefing-prazos
EOF
cat >"$tmp_dir/cadu-hub-briefing-prazos.timer" <<'EOF'
[Unit]
Description=Verifica prazos de cotação do hub a cada 15 minutos
[Timer]
OnCalendar=*-*-* *:00,15,30,45:00
Persistent=true
Unit=cadu-hub-briefing-prazos.service
[Install]
WantedBy=timers.target
EOF
sudo install -m 644 "$tmp_dir/cadu-hub-briefing-prazos.service" /etc/systemd/system/cadu-hub-briefing-prazos.service
sudo install -m 644 "$tmp_dir/cadu-hub-briefing-prazos.timer" /etc/systemd/system/cadu-hub-briefing-prazos.timer
sudo systemctl daemon-reload
sudo systemctl enable --now cadu-hub-briefing-prazos.timer
sudo systemctl is-active --quiet cadu-hub-briefing-prazos.timer
echo 'Timer de follow-up do onboarding instalado e ativo.'
