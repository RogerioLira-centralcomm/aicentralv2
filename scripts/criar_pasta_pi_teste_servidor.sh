#!/bin/bash
# Cria estrutura de pastas de PI só para testar permissão/acesso no servidor.
# Apagar depois: ./scripts/remover_pasta_pi_teste_servidor.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Mesmo default do app (PI_UPLOAD_ROOT no .env ou instance/uploads/pi)
ROOT="${PI_UPLOAD_ROOT:-/var/www/aicentralv2/instance/uploads/pi}"
CODIGO="${1:-PI_TESTE_PERMISSAO}"
ID_PI="${2:-0}"
DIR="$ROOT/${CODIGO}__${ID_PI}"

GUNI_USER="$(systemctl show gunicorn --property=User --value 2>/dev/null || true)"
GUNI_GROUP="$(systemctl show gunicorn --property=Group --value 2>/dev/null || true)"
[ -n "$GUNI_GROUP" ] || GUNI_GROUP="$GUNI_USER"

mkdir -p "$DIR"/{principal,financeiro,pecas,assinados}

for sub in principal financeiro pecas assinados; do
  printf '%s\n' "Teste de permissão — $CODIGO / $sub" "$(date -Is)" > "$DIR/$sub/LEIA-ME.txt"
done
echo "arquivo-teste-upload.txt" > "$DIR/principal/arquivo-teste-upload.txt"

if [ -n "$GUNI_USER" ]; then
  sudo chown -R "$GUNI_USER:${GUNI_GROUP:-$GUNI_USER}" "$DIR" 2>/dev/null || chown -R "$GUNI_USER:${GUNI_GROUP:-$GUNI_USER}" "$DIR" 2>/dev/null || true
fi

echo "=== Pasta de teste criada ==="
echo "DIR=$DIR"
echo ""
ls -la "$DIR"
echo ""
ls -la "$DIR/principal"
echo ""
echo "Teste escrita como usuário atual ($(whoami)):"
if touch "$DIR/principal/.write_test_$$" 2>/dev/null; then
  rm -f "$DIR/principal/.write_test_$$"
  echo "  OK — usuário $(whoami) pode escrever."
else
  echo "  FALHA — $(whoami) não consegue escrever (esperado se não for o usuário do gunicorn)."
fi

if [ -n "$GUNI_USER" ]; then
  echo ""
  echo "Teste escrita como $GUNI_USER (como o app faria no upload):"
  if sudo -u "$GUNI_USER" touch "$DIR/principal/.write_guni_$$" 2>/dev/null; then
    sudo -u "$GUNI_USER" rm -f "$DIR/principal/.write_guni_$$"
    echo "  OK — $GUNI_USER pode escrever."
  else
    echo "  FALHA — ajuste dono/permissões em: $ROOT"
  fi
fi

echo ""
echo "No app (após deploy com pastas locais): links são por PI real."
echo "Este diretório é só teste de disco; apague com:"
echo "  PI_UPLOAD_ROOT='$ROOT' ./scripts/remover_pasta_pi_teste_servidor.sh '$CODIGO' '$ID_PI'"