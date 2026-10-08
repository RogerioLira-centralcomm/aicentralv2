#!/bin/bash
# build_frontend_fast.sh - Versão otimizada com cache agressivo

set -e
cd "$(dirname "$0")"

# Cachear node_modules dos subprojetos
cache_prefix() {
    local prefix="$1"
    local lock_hash_file="logs/.cache-${prefix//\//-}.sha256"
    local lock_file="$prefix/package-lock.json"
    
    if [ ! -f "$lock_file" ]; then return 0; fi
    
    mkdir -p "$(dirname "$lock_hash_file")"
    
    if command -v sha256sum >/dev/null 2>&1; then
        lock_hash="$(sha256sum "$lock_file" | awk '{print $1}')"
    else
        lock_hash="$(shasum -a 256 "$lock_file" | awk '{print $1}')"
    fi
    
    if [ ! -f "$lock_hash_file" ] || [ "$(cat "$lock_hash_file")" != "$lock_hash" ]; then
        echo "[INFO] Atualizando $prefix..."
        npm ci --prefix "$prefix" --no-audit --no-fund --prefer-offline --progress=false
        printf '%s\n' "$lock_hash" > "$lock_hash_file"
    else
        echo "[INFO] Cache OK: $prefix"
    fi
}

# Instalar dependências raiz
if [ ! -d "node_modules" ]; then
    echo "[INFO] Instalando dependências raiz..."
    npm ci --no-audit --no-fund --prefer-offline --progress=false
fi

# Cachear subprojetos
cache_prefix "frontend/reports-v1/untitled-kit"
cache_prefix "frontend/cadu-design-system/untitled-kit"
cache_prefix "frontend/planner/untitled-kit"

# Build Tailwind (rápido)
echo "[INFO] Gerando CSS..."
npm run build:vanilla
npm run build:artifact  
npm run build:studio

# Build Vite em paralelo (rápido)
echo "[INFO] Gerando bundles Vite..."
npm run build:reports &
npm run build:conversations &
npm run build:planner &
npm run build:auth &
npm run build:editor &
npm run build:audio &
npm run build:studio-ui &
npm run build:lab &
npm run build:studio-home &
wait

echo "[OK] Build concluído com sucesso!"
