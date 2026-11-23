#!/bin/bash
# Cole este arquivo INTEIRO no terminal web da Hostinger (como root).
# Não precisa de git pull. Restaura HTTPS em ai.centralcomm.media e família na VPS.
# Sintoma: CN=Easypanel, HTTP 308, HTTPS 502.

set -euo pipefail

log() { echo "  > $*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "Rode como root no terminal Hostinger." >&2
  exit 1
fi

log "Passo 1 — diagnóstico"
ss -tlnp | grep -E ':80 |:443 ' || true
docker ps --format 'table {{.Names}}\t{{.Ports}}' 2>/dev/null | head -20 || true
systemctl is-active gunicorn.service nginx 2>/dev/null || true
code=$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/ -H 'Host: ai.centralcomm.media' 2>/dev/null || echo 000)
log "gunicorn :8001 → HTTP $code"
if [ "$code" = "000" ]; then
  log "Iniciando gunicorn..."
  systemctl start gunicorn.service
  sleep 2
  code=$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/ -H 'Host: ai.centralcomm.media' 2>/dev/null || echo 000)
  log "gunicorn :8001 → HTTP $code"
fi
if [ "$code" = "000" ] || [ "$code" = "502" ]; then
  echo "ERRO: Gunicorn não responde. Rode: journalctl -u gunicorn.service -n 50 --no-pager" >&2
  exit 1
fi

log "Passo 2 — liberar 80/443 (Easypanel / Docker)"
if command -v docker >/dev/null 2>&1; then
  for cid in $(docker ps -q 2>/dev/null); do
  docker inspect -f '{{json .HostConfig.PortBindings}}' "$cid" 2>/dev/null \
    | grep -qE '"(80|443)/tcp"' || continue
    name=$(docker inspect -f '{{.Name}}' "$cid" | sed 's#^/##')
    log "Parando $name"
    docker stop "$cid" >/dev/null || true
    docker update --restart=no "$cid" >/dev/null 2>&1 || true
  done
  sleep 2
fi
ss -tlnp | grep -E ':80 |:443 ' || log "Nenhum listener 80/443 (ok antes do nginx)"

log "Passo 3 — nginx + certbot"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y nginx certbot python3-certbot-nginx curl 2>/dev/null || true
systemctl enable --now nginx
systemctl start gunicorn.service 2>/dev/null || true

REPO="/var/www/aicentralv2"
if [ -f "$REPO/deploy/configure_nginx_upload.sh" ]; then
  bash "$REPO/deploy/configure_nginx_upload.sh" || true
elif [ ! -f /etc/nginx/sites-enabled/aicentralv2 ] && [ ! -f /etc/nginx/sites-enabled/default ]; then
  cat >/etc/nginx/sites-available/aicentralv2 <<'NGINX'
upstream aicentralv2_app {
    server 127.0.0.1:8001;
    keepalive 32;
}
server {
    listen 80;
    listen [::]:80;
    server_name ai.centralcomm.media aicentral.centralcomm.media
                studio.centralcomm.media skills.centralcomm.media
                planner.centralcomm.media connect.centralcomm.media reports.centralcomm.media
                workspace.centralcomm.media auth.centralcomm.media clientes.centralcomm.media;
    client_max_body_size 256M;
    location /static/ {
        alias /var/www/aicentralv2/aicentralv2/static/;
        expires 30d;
    }
    location / {
        proxy_pass http://aicentralv2_app;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_read_timeout 300s;
    }
}
NGINX
  ln -sf /etc/nginx/sites-available/aicentralv2 /etc/nginx/sites-enabled/aicentralv2
  rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
fi

nginx -t
systemctl reload nginx

if [ -f /etc/letsencrypt/live/centralcomm-products/fullchain.pem ] \
   && grep -rq 'ssl_certificate' /etc/nginx/sites-enabled/ 2>/dev/null; then
  log "Certificado existente; renovando..."
  certbot renew --nginx --quiet 2>/dev/null || certbot renew --quiet 2>/dev/null || true
else
  log "Emitindo certificado SAN (sem cadu.centralcomm.media — DNS KingHost)"
  certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email \
    --cert-name centralcomm-products --expand \
    -d ai.centralcomm.media \
    -d aicentral.centralcomm.media \
    -d studio.centralcomm.media \
    -d skills.centralcomm.media \
    -d planner.centralcomm.media \
    -d connect.centralcomm.media \
    -d reports.centralcomm.media \
    -d workspace.centralcomm.media \
    -d auth.centralcomm.media \
    -d clientes.centralcomm.media
fi

nginx -t && systemctl reload nginx

log "Passo 4 — teste"
curl -sS -o /dev/null -w 'HTTPS local → %{http_code}\n' \
  --resolve ai.centralcomm.media:443:127.0.0.1 https://ai.centralcomm.media/ || true
echo | openssl s_client -connect 127.0.0.1:443 -servername ai.centralcomm.media 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates 2>/dev/null || true
echo ""
echo "OK — teste no browser: https://ai.centralcomm.media/"