#!/usr/bin/env bash
# Instala um timer persistente para os e-mails pós-onboarding.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${ONBOARDING_PYTHON:-$root/venv/bin/python}"
[[ -x "$python_bin" ]] || python_bin="$root/venv_new/bin/python"
[[ -x "$python_bin" ]] || { echo 'Python do ambiente virtual não encontrado.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'Este instalador requer Linux/systemd.' >&2; exit 1; }
service_user="$(systemctl show gunicorn --property=User --value)"
[[ -n "$service_user" ]] || service_user="www-data"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
cat >"$tmp_dir/cadu-onboarding-followup.service" <<EOF
[Unit]
Description=Processa e-mails pós-onboarding do Cadu
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User=$service_user
WorkingDirectory=$root
Environment=PATH=$(dirname "$python_bin"):/usr/local/bin:/usr/bin:/bin
Environment=AICENTRAL_ENV=production
ExecStart=$python_bin -m flask --app run:app process-onboarding-followups
EOF
cat >"$tmp_dir/cadu-onboarding-followup.timer" <<'EOF'
[Unit]
Description=Executa follow-ups de onboarding a cada minuto
[Timer]
OnCalendar=*-*-* *:*:00
Persistent=true
Unit=cadu-onboarding-followup.service
[Install]
WantedBy=timers.target
EOF
sudo install -m 644 "$tmp_dir/cadu-onboarding-followup.service" /etc/systemd/system/cadu-onboarding-followup.service
sudo install -m 644 "$tmp_dir/cadu-onboarding-followup.timer" /etc/systemd/system/cadu-onboarding-followup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now cadu-onboarding-followup.timer
sudo systemctl is-active --quiet cadu-onboarding-followup.timer
echo 'Timer de follow-up do onboarding instalado e ativo.'
