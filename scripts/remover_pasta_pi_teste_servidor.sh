#!/bin/bash
set -euo pipefail
ROOT="${PI_UPLOAD_ROOT:-/var/www/aicentralv2/instance/uploads/pi}"
CODIGO="${1:-PI_TESTE_PERMISSAO}"
ID_PI="${2:-0}"
DIR="$ROOT/${CODIGO}__${ID_PI}"
if [ ! -d "$DIR" ]; then
  echo "Nada a remover: $DIR"
  exit 0
fi
rm -rf "$DIR"
echo "Removido: $DIR"