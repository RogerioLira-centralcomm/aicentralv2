#!/bin/bash
# Aplica client_max_body_size 256M no nginx (snippet global + site do gunicorn :8001).

if grep -qP '\r' "$0" 2>/dev/null; then
    sed -i 's/\r$//' "$0"
    exec bash "$0" "$@"
fi

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SNIPPET_SRC="$REPO_ROOT/deploy/nginx-upload-limits.conf"
SITE_SRC="$REPO_ROOT/deploy/nginx-aicentralv2.conf"

if ! command -v nginx >/dev/null 2>&1; then
    echo "  > nginx não instalado, pulando"
    exit 0
fi

echo "  > Instalando snippet global..."
sudo cp "$SNIPPET_SRC" /etc/nginx/conf.d/aicentralv2-upload-limits.conf

patched=0
for f in /etc/nginx/sites-enabled/* /etc/nginx/sites-available/* /etc/nginx/conf.d/*; do
    [ -f "$f" ] || continue
    case "$f" in
        */aicentralv2-upload-limits.conf) continue ;;
    esac
    if ! grep -qE '127\.0\.0\.1:8001|:8001|aicentralv2_app' "$f" 2>/dev/null; then
        continue
    fi
    if grep -q 'client_max_body_size' "$f"; then
        sudo sed -i 's/client_max_body_size[^;]*;/client_max_body_size 256M;/g' "$f"
    else
        sudo sed -i '/server[[:space:]]*{/a\    client_max_body_size 256M;' "$f"
    fi
    echo "  > client_max_body_size 256M em $(basename "$f")"
    patched=$((patched + 1))
done

if [ "$patched" -eq 0 ]; then
    echo "  > Nenhum site :8001 encontrado; instalando deploy/nginx-aicentralv2.conf..."
    sudo cp "$SITE_SRC" /etc/nginx/sites-available/aicentralv2
    sudo ln -sf /etc/nginx/sites-available/aicentralv2 /etc/nginx/sites-enabled/aicentralv2
fi

if sudo nginx -t 2>&1 | cat; then
    sudo systemctl reload nginx 2>/dev/null || sudo service nginx reload 2>/dev/null || true
    echo "  > nginx recarregado"
else
    echo "  > ERRO: nginx -t falhou — corrija manualmente em /etc/nginx/"
    exit 1
fi
