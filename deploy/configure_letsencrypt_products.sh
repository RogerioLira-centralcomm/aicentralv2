#!/bin/bash
# Emite ou expande o certificado SAN compartilhado pelos produtos Cadu.
# Execute no servidor somente depois de o DNS de todos os domínios apontar
# para este host e o Nginx já responder na porta 80.

set -euo pipefail

CERT_NAME="centralcomm-products"
DOMAINS=(
  ai.centralcomm.media
  aicentral.centralcomm.media
  cadu.centralcomm.media
  studio.centralcomm.media
  skills.centralcomm.media
  planner.centralcomm.media
  connect.centralcomm.media
  reports.centralcomm.media
  workspace.centralcomm.media
  auth.centralcomm.media
)

if ! command -v certbot >/dev/null 2>&1; then
  echo "certbot não está instalado. Instale-o antes de emitir o certificado." >&2
  exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
  echo "nginx não está instalado; não é possível validar o desafio HTTP." >&2
  exit 1
fi

sudo nginx -t

certbot_args=(--nginx --cert-name "$CERT_NAME" --expand)
for domain in "${DOMAINS[@]}"; do
  certbot_args+=(--domains "$domain")
done

sudo certbot "${certbot_args[@]}"
sudo nginx -t
sudo systemctl reload nginx 2>/dev/null || sudo service nginx reload
