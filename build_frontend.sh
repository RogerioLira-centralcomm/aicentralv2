#!/bin/bash
# build_frontend.sh - Gera os bundles vanilla e legado para produção
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
# Keep the dependency marker outside node_modules: npm ci removes and
# recreates that directory, which otherwise makes every deploy reinstall the
# complete frontend even when package-lock.json did not change.
lock_hash_file="${FRONTEND_DEPENDENCY_STATE_FILE:-$NODE_DIR/logs/.frontend-dependencies.sha256}"
if command -v sha256sum >/dev/null 2>&1; then
  lock_hash="$(sha256sum "$NODE_DIR/package-lock.json" | awk '{print $1}')"
else
  lock_hash="$(shasum -a 256 "$NODE_DIR/package-lock.json" | awk '{print $1}')"
fi
if [ "$FORCE_CI" = "1" ]; then
  need_ci=1
elif [ ! -d "$NODE_DIR/node_modules" ]; then
  need_ci=1
elif [ ! -f "$NODE_DIR/node_modules/.bin/tailwindcss" ] && [ ! -f "$NODE_DIR/node_modules/.bin/tailwindcss.cmd" ]; then
  need_ci=1
elif [ ! -f "$lock_hash_file" ] || [ "$(cat "$lock_hash_file")" != "$lock_hash" ]; then
  need_ci=1
fi

if [ "$need_ci" = "1" ]; then
  echo "[INFO] Instalando dependências (npm ci)..."
  npm ci --no-audit --no-fund --prefer-offline --progress=false
else
  echo "[INFO] Dependências já instaladas, pulando npm ci."
fi

mkdir -p "$(dirname "$lock_hash_file")"
printf '%s\n' "$lock_hash" > "$lock_hash_file"

# Audit fica fora do build: as deps são só de compilação do CSS
# (não vão para produção) e npm audit/fix costuma ser lento e falhar
# por vulnerabilidades transitivas sem correção disponível.

chmod +x node_modules/.bin/* 2>/dev/null || true

if [ "${FULL_FRONTEND_BUILD:-0}" = "1" ]; then
  echo "[INFO] Gerando todos os bundles frontend..."
  npm run build
else
  # Workspace deploys do not need the artifact safelist or the unrelated
  # Studio/auth/editor bundles. Keeping this path focused avoids the long
  # Tailwind artifact build while still rebuilding the shared shell and chat.
  echo "[INFO] Gerando bundles necessários do Workspace..."
  npm run build:vanilla
  npm run build:legacy
  npm run build:conversations
  npm run build:reports
fi

if [ -f "aicentralv2/static/css/tailwind/output.css" ] && [ -f "aicentralv2/static/css/tailwind/output-legacy.css" ]; then
  echo "[OK] Bundles vanilla e legado gerados com sucesso."
else
  echo "[ERRO] Falha ao gerar um dos bundles CSS."
  exit 1
fi
