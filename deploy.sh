#!/bin/bash

# Script de Deploy - AIcentral v2
set -e

echo "========================================"
echo "Deploy AIcentral v2"
echo "========================================"

# 1. Parar servico ANTES de tudo
echo "Parando servico..."
sudo systemctl stop aicentralv2 2>/dev/null || true
sleep 2

# Garantir que nenhum gunicorn ficou vivo
sudo pkill -9 -f "gunicorn.*run:app" 2>/dev/null || true
sleep 1

# Verificar que a porta 8001 está livre
if ss -tlnp | grep -q ':8001'; then
    echo "⚠ Porta 8001 ainda ocupada, matando processo..."
    sudo fuser -k 8001/tcp 2>/dev/null || true
    sleep 2
fi

sudo rm -f gunicorn.pid

# 2. Atualizar codigo
echo "Atualizando codigo..."
git pull origin main

# 3. Ativar ambiente virtual
echo "Ativando ambiente virtual..."
source venv/bin/activate || source venv_new/bin/activate

# 4. Atualizar dependencias
echo "Atualizando dependencias..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --upgrade --quiet

# 5. Criar diretorios
mkdir -p aicentralv2/static/uploads/audiencias aicentralv2/static/uploads/cotacoes logs
chmod 755 aicentralv2/static/uploads/audiencias aicentralv2/static/uploads/cotacoes logs

# 6. Limpar cache Python (com servico parado)
echo "Limpando cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# 7. Atualizar systemd
echo "Atualizando systemd..."
sudo cp aicentralv2.service /etc/systemd/system/
sudo systemctl daemon-reload

# 8. Iniciar servico
echo "Iniciando servico..."
sudo systemctl start aicentralv2

# 9. Verificar
sleep 3
if sudo systemctl is-active --quiet aicentralv2; then
    echo "✓ Servico ativo!"
    sudo systemctl status aicentralv2 --no-pager -l
else
    echo "✗ ERRO ao iniciar servico"
    sudo systemctl status aicentralv2 --no-pager -l
    sudo journalctl -u aicentralv2 -n 50 --no-pager
    exit 1
fi

# 10. Health check
sleep 2
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "000" ]; then
    echo "⚠ Servidor não respondeu ao health check (pode precisar de login)"
elif [ "$HTTP_CODE" -lt "400" ] || [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "302" ]; then
    echo "✓ Health check OK (HTTP $HTTP_CODE)"
else
    echo "⚠ Health check retornou HTTP $HTTP_CODE"
fi

echo ""
echo "========================================"
echo "Deploy concluido com sucesso!"
echo "========================================"
echo ""
echo "Verifique o status:"
echo "  sudo systemctl status aicentralv2"
echo ""
echo "Logs:"
echo "  sudo journalctl -u aicentralv2 -f"
echo "  tail -f logs/error.log"
echo ""
