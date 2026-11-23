#!/bin/bash
# Restaura HTTPS (Nginx + Let's Encrypt) na VPS dos produtos *.centralcomm.media.
# Sintoma típico: certificado CN=Easypanel, HTTP 308, HTTPS 502.
#
# Rodar no servidor (como root ou sudo):
#   cd /var/www/aicentralv2 && sudo bash deploy/restore_https_products.sh
#
# Ou a partir de um PC com chave SSH:
#   ssh root@ai.centralcomm.media 'bash -s' < deploy/restore_https_products.sh
#
# Para parar containers Docker que ocupam 80/443 (Easypanel/Traefik):
#   RESTORE_HTTPS_STOP_DOCKER_80_443=1 sudo bash deploy/restore_https_products.sh

if grep -qP '\r' "$0" 2>/dev/null; then
  sed -i 's/\r$//' "$0"
  exec bash "$0" "$@"
fi

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_SERVICE="${APP_SERVICE:-gunicorn.service}"

log() { echo "  > $*"; }
need_root() {
  if [ "$(id -u)" -ne 0 ] && ! command -v sudo >/dev/null 2>&1; then
    echo "Execute como root ou com sudo." >&2
    exit 1
  fi
}
SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"

need_root

echo ""
echo "========================================"
echo "  Restaurar HTTPS — produtos CentralComm"
echo "========================================"
echo ""

log "Repositório: $REPO_ROOT"
log "Diagnóstico de portas 80/443:"
$SUDO ss -tlnp 2>/dev/null | grep -E ':80 |:443 ' || true

listeners_443="$($SUDO ss -tlnp 2>/dev/null | grep ':443 ' || true)"
if echo "$listeners_443" | grep -q nginx; then
  log "Nginx já escuta na 443."
elif [ -n "$listeners_443" ]; then
  log "AVISO: a porta 443 não parece ser do Nginx (possível Easypanel/Traefik)."
  auto_stop="${RESTORE_HTTPS_STOP_DOCKER_80_443:-1}"
  if [ "$auto_stop" = "1" ] && command -v docker >/dev/null 2>&1; then
    while read -r cid; do
      [ -n "$cid" ] || continue
      name="$($SUDO docker inspect -f '{{.Name}}' "$cid" 2>/dev/null | sed 's#^/##')"
      ports="$($SUDO docker inspect -f '{{json .HostConfig.PortBindings}}' "$cid" 2>/dev/null || echo '{}')"
      if echo "$ports" | grep -qE '"(80|443)/tcp"'; then
        log "Parando container Docker em 80/443: $name ($cid)"
        $SUDO docker stop "$cid" >/dev/null || true
      fi
    done < <($SUDO docker ps -q 2>/dev/null || true)
    sleep 2
  else
    log "Defina RESTORE_HTTPS_STOP_DOCKER_80_443=1 para parar containers Docker em 80/443."
  fi
fi

log "Gunicorn ($APP_SERVICE)..."
if ! $SUDO systemctl is-active --quiet "$APP_SERVICE" 2>/dev/null; then
  log "Iniciando $APP_SERVICE..."
  $SUDO systemctl start "$APP_SERVICE" || true
fi
$SUDO systemctl is-active --quiet "$APP_SERVICE" || {
  echo "ERRO: $APP_SERVICE não está ativo. Corrija antes do HTTPS." >&2
  exit 1
}

code="$($SUDO curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/ -H 'Host: ai.centralcomm.media' 2>/dev/null || echo 000)"
log "Backend :8001 (Host ai.centralcomm.media) → HTTP $code"
if [ "$code" = "000" ] || [ "$code" = "502" ]; then
  echo "ERRO: Gunicorn não responde em 127.0.0.1:8001." >&2
  $SUDO journalctl -u "$APP_SERVICE" -n 30 --no-pager 2>/dev/null || true
  exit 1
fi

log "Ajustando client_max_body_size no Nginx..."
bash "$REPO_ROOT/deploy/configure_nginx_upload.sh"

if ! $SUDO nginx -t 2>&1 | cat; then
  echo "ERRO: nginx -t falhou." >&2
  exit 1
fi

$SUDO systemctl enable nginx 2>/dev/null || true
$SUDO systemctl start nginx 2>/dev/null || $SUDO service nginx start 2>/dev/null || true

cert_dir="/etc/letsencrypt/live/centralcomm-products"
has_le=0
if [ -f "$cert_dir/fullchain.pem" ] && [ -f "$cert_dir/privkey.pem" ]; then
  has_le=1
fi

ssl_in_nginx=0
if grep -rq 'ssl_certificate' /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ 2>/dev/null; then
  ssl_in_nginx=1
fi

if [ "$has_le" -eq 0 ] || [ "$ssl_in_nginx" -eq 0 ]; then
  log "Emitindo ou expandindo certificado SAN (certbot)..."
  if [ -x "$REPO_ROOT/deploy/configure_letsencrypt_products.sh" ]; then
    bash "$REPO_ROOT/deploy/configure_letsencrypt_products.sh"
  elif command -v certbot >/dev/null 2>&1; then
    $SUDO certbot --nginx --cert-name centralcomm-products --expand \
      -d ai.centralcomm.media -d aicentral.centralcomm.media \
      -d studio.centralcomm.media \
      -d skills.centralcomm.media -d planner.centralcomm.media \
      -d connect.centralcomm.media -d reports.centralcomm.media \
      -d workspace.centralcomm.media -d auth.centralcomm.media \
      -d clientes.centralcomm.media
  else
    echo "ERRO: certbot não encontrado e sem SSL no nginx." >&2
    exit 1
  fi
else
  log "Certificado centralcomm-products e SSL no nginx já existem; renovando se necessário..."
  $SUDO certbot renew --nginx --quiet 2>/dev/null || $SUDO certbot renew --quiet 2>/dev/null || true
fi

$SUDO nginx -t
$SUDO systemctl reload nginx 2>/dev/null || $SUDO service nginx reload

log "Teste local HTTPS (SNI ai.centralcomm.media)..."
local_code="$($SUDO curl -sS -o /dev/null -w '%{http_code}' --resolve ai.centralcomm.media:443:127.0.0.1 \
  https://ai.centralcomm.media/ 2>/dev/null || echo 000)"
log "curl --resolve → HTTP $local_code"

if [ "$local_code" != "200" ] && [ "$local_code" != "302" ] && [ "$local_code" != "301" ] && [ "$local_code" != "303" ]; then
  echo "AVISO: resposta local inesperada ($local_code). Verifique ss -tlnp e sites-enabled." >&2
  exit 1
fi

echo ""
echo "OK — HTTPS restaurado no servidor. Teste no browser: https://ai.centralcomm.media/"
echo "Se ainda aparecer CN=Easypanel, pare o Docker em 80/443 e rode de novo com:"
echo "  RESTORE_HTTPS_STOP_DOCKER_80_443=1 sudo bash deploy/restore_https_products.sh"
echo ""