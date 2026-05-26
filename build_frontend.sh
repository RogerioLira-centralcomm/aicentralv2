#!/bin/bash
# build_frontend.sh - Gera o CSS do Tailwind + daisyUI para produção
# Uso: ./build_frontend.sh

set -e

cd "$(dirname "$0")"

NODE_DIR="$(pwd)"

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

# Instala exatamente as versões do package-lock.json (reproducível no servidor).
# Não usa npm outdated/npm install — isso reinstalava deps vulneráveis e exigia audit fix manual.
echo "[INFO] Instalando dependências (npm ci)..."
npm ci

chmod +x node_modules/.bin/* 2>/dev/null || true

echo "[INFO] Gerando CSS de produção..."
npm run build

if [ -f "aicentralv2/static/css/tailwind/output.css" ]; then
  echo "[OK] CSS de produção gerado com sucesso."
else
  echo "[ERRO] Falha ao gerar o CSS de produção."
  exit 1
fi
