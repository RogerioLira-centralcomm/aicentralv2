#!/bin/bash
# build_frontend.sh - Gera o CSS do Tailwind + daisyUI para produção
# Uso: ./build_frontend.sh

set -e

cd "$(dirname "$0")"

# Caminho do projeto Node
NODE_DIR="$(pwd)"

# Verifica se package.json existe
if [ ! -f "$NODE_DIR/package.json" ]; then
  echo "[ERRO] package.json não encontrado em $NODE_DIR"
  exit 1
fi

# Verifica se Node está instalado
if ! command -v node >/dev/null 2>&1; then
  echo "[ERRO] Node.js não está instalado. Instale antes de continuar."
  exit 1
fi

# Verifica se npm está instalado
if ! command -v npm >/dev/null 2>&1; then
  echo "[ERRO] npm não está instalado. Instale antes de continuar."
  exit 1
fi

# Verifica se dependências precisam de atualização
if [ -d "node_modules" ]; then
  echo "[INFO] node_modules encontrado. Verificando atualizações..."
  npm outdated || true
else
  echo "[INFO] Instalando dependências Node..."
  npm install
fi

# Atualiza dependências se houverem updates
if npm outdated | grep -q .; then
  echo "[INFO] Atualizando dependências Node..."
  npm install
fi

# Gera o CSS de produção
npm run build

# Confirma se o CSS foi gerado
if [ -f "aicentralv2/static/css/tailwind/output.css" ]; then
  echo "[OK] CSS de produção gerado com sucesso."
else
  echo "[ERRO] Falha ao gerar o CSS de produção."
  exit 1
fi
