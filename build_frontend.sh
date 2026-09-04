#!/bin/bash
# build_frontend.sh - Gera o CSS do Tailwind + daisyUI para produção
# Uso: ./build_frontend.sh [--clean]
#   --clean  Força reinstalação das dependências (npm ci)

set -e

cd "$(dirname "$0")"

NODE_DIR="$(pwd)"
FORCE_CI=0

for arg in "$@"; do
  case "$arg" in
    --clean) FORCE_CI=1 ;;
  esac
done

if [ ! -f "$NODE_DIR/package.json" ]; then
  echo "[ERRO] package.json não encontrado em $NODE_DIR"
  exit 1
fi

if [ ! -f "$NODE_DIR/package-lock.json" ]; then
  echo "[ERRO] package-lock.json não encontrado. Rode 'npm install' localmente e commite o lockfile."
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "[ERRO] Node.js não está instalado. Instale antes de continuar."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[ERRO] npm não está instalado. Instale antes de continuar."
  exit 1
fi

need_ci=0
if [ "$FORCE_CI" = "1" ]; then
  need_ci=1
elif [ ! -d "$NODE_DIR/node_modules" ]; then
  need_ci=1
elif [ ! -f "$NODE_DIR/node_modules/.bin/tailwindcss" ] && [ ! -f "$NODE_DIR/node_modules/.bin/tailwindcss.cmd" ]; then
  need_ci=1
fi

if [ "$need_ci" = "1" ]; then
  echo "[INFO] Instalando dependências (npm ci)..."
  npm ci
else
  echo "[INFO] Dependências já instaladas, pulando npm ci."
fi

# Audit fica fora do build: as deps são só de compilação do CSS
# (não vão para produção) e npm audit/fix costuma ser lento e falhar
# por vulnerabilidades transitivas sem correção disponível.

chmod +x node_modules/.bin/* 2>/dev/null || true

echo "[INFO] Gerando CSS de produção..."
npm run build

if [ -f "aicentralv2/static/css/tailwind/output.css" ]; then
  echo "[OK] CSS de produção gerado com sucesso."
else
  echo "[ERRO] Falha ao gerar o CSS de produção."
  exit 1
fi

