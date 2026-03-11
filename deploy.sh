#!/bin/bash

# Auto-fix: remove \r (Windows line endings) e re-executa se necessario
if grep -qP '\r' "$0" 2>/dev/null; then
    sed -i 's/\r$//' "$0"
    exec bash "$0" "$@"
fi

# Script de Deploy - AIcentral v2
set -e
export SYSTEMD_PAGER=""
export PAGER="cat"
export SYSTEMD_LESS=""
export TERM="${TERM:-xterm}"

echo ""
echo "========================================"
echo "  Deploy AIcentral v2"
echo "========================================"
echo ""

# 1. Parar servico ANTES de tudo
echo "[1/7] Parando servico..."
sudo systemctl stop aicentralv2 2>/dev/null || true
sleep 2

# Garantir que nenhum gunicorn ficou vivo
sudo pkill -9 -f "gunicorn.*run:app" 2>/dev/null || true
sleep 1

# Verificar que a porta 8001 esta livre
if sudo ss -tlnp 2>/dev/null | grep -q ':8001'; then
    echo "  > Porta 8001 ainda ocupada, matando processo..."
    sudo fuser -k 8001/tcp 2>/dev/null || true
    sleep 2
fi

sudo rm -f gunicorn.pid
echo "  > OK"

# 2. Atualizar codigo
echo ""
echo "[2/7] Atualizando codigo..."
git pull origin main 2>&1
# Renormalizar line endings apos pull
git checkout -- . 2>/dev/null || true
echo "  > OK"

# 3. Atualizar dependencias
echo ""
echo "[3/7] Atualizando dependencias..."
VENV_PIP="venv/bin/pip"
[ ! -f "$VENV_PIP" ] && VENV_PIP="venv_new/bin/pip"
$VENV_PIP install --upgrade pip --quiet 2>&1
$VENV_PIP install -r requirements.txt --upgrade --quiet 2>&1
echo "  > OK"

# 4. Criar diretorios
mkdir -p aicentralv2/static/uploads/audiencias aicentralv2/static/uploads/cotacoes logs
chmod 755 aicentralv2/static/uploads/audiencias aicentralv2/static/uploads/cotacoes logs

# 5. Limpar cache Python
echo ""
echo "[4/7] Limpando cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "  > OK"

# 6. Atualizar systemd
echo ""
echo "[5/7] Atualizando systemd..."
sudo cp aicentralv2.service /etc/systemd/system/
sudo systemctl daemon-reload
echo "  > OK"

# 7. Iniciar servico
echo ""
echo "[6/7] Iniciando servico..."
sudo systemctl start aicentralv2
sleep 3

if sudo systemctl is-active --quiet aicentralv2; then
    echo "  > Servico ativo!"
else
    echo "  > ERRO ao iniciar servico"
    sudo journalctl -u aicentralv2 -n 30 --no-pager 2>&1 | cat
    exit 1
fi

# 8. Health check
echo ""
echo "[7/7] Health check..."
sleep 2
HTTP_CODE=$(curl -s -m 10 -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "000" ]; then
    echo "  > Servidor nao respondeu (pode precisar de login)"
elif [ "$HTTP_CODE" -lt "400" ] || [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "302" ]; then
    echo "  > OK (HTTP $HTTP_CODE)"
else
    echo "  > Retornou HTTP $HTTP_CODE"
fi

echo ""
echo "========================================"
echo "  Deploy concluido com sucesso!"
echo "========================================"
echo ""

# Restaurar terminal
stty sane 2>/dev/null || true
