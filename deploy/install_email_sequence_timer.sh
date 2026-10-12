#!/usr/bin/env bash
# Instala um timer persistente para os e-mails da sequência de adoção.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${EMAIL_SEQUENCE_PYTHON:-$root/venv/bin/python}"
[[ -x "$python_bin" ]] || python_bin="$root/venv_new/bin/python"
[[ -x "$python_bin" ]] || { echo 'Python do ambiente virtual não encontrado.' >&2; exit 1; }
command -v systemctl >/dev/null || { echo 'Este instalador requer Linux/systemd.' >&2; exit 1; }
service_user="$(systemctl show gunicorn --property=User --value)"
[[ -n "$service_user" ]] || service_user="www-data"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
cat >"$tmp_dir/cadu-email-sequence.service" <<EOF
[Unit]
Description=Processa e-mails da sequência de adoção do Cadu
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User=$service_user
WorkingDirectory=$root
Environment=PATH=$(dirname "$python_bin"):/usr/local/bin:/usr/bin:/bin
Environment=AICENTRAL_ENV=production
ExecStart=$python_bin -m flask --app run:app process-email-sequence
EOF
cat >"$tmp_dir/cadu-email-sequence.timer" <<'EOF'
[Unit]
Description=Executa a sequência de e-mails a cada 15 minutos
[Timer]
OnCalendar=*:0/15
Persistent=true
Unit=cadu-email-sequence.service
[Install]
WantedBy=timers.target
EOF
sudo install -m 644 "$tmp_dir/cadu-email-sequence.service" /etc/systemd/system/cadu-email-sequence.service
sudo install -m 644 "$tmp_dir/cadu-email-sequence.timer" /etc/systemd/system/cadu-email-sequence.timer
sudo systemctl daemon-reload
sudo systemctl enable --now cadu-email-sequence.timer
sudo systemctl is-active --quiet cadu-email-sequence.timer
echo 'Timer da sequência de e-mails instalado e ativo.'
