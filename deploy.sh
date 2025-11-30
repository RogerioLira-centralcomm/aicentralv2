#!/bin/bash

# Script de Deploy - AIcentral v2
set -e

echo "========================================"
echo "Deploy AIcentral v2"
echo "========================================"

# Atualizar codigo
echo "Atualizando codigo..."
git pull origin main

# Atualizar systemd
echo "Atualizando systemd..."
sudo cp aicentralv2.service /etc/systemd/system/
sudo systemctl daemon-reload

# Ativar ambiente virtual
echo "Ativando ambiente virtual..."
source venv/bin/activate || source venv_new/bin/activate

# Instalar dependencias
echo "Instalando dependencias..."
pip install -r requirements.txt --upgrade --quiet

# Criar diretorios
mkdir -p aicentralv2/static/uploads/audiencias logs
chmod 755 aicentralv2/static/uploads/audiencias logs

# Limpar cache
echo "Limpando cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Parar e limpar
echo "Parando servico..."
sudo systemctl stop aicentralv2 2>/dev/null || true
sudo pkill -9 gunicorn 2>/dev/null || true
sleep 2
sudo rm -f gunicorn.pid

# Iniciar
echo "Iniciando servico..."
sudo systemctl start aicentralv2

# Verificar
sleep 3
if sudo systemctl is-active --quiet aicentralv2; then
    echo "✓ Deploy concluido com sucesso!"
    sudo systemctl status aicentralv2 --no-pager -l
else
    echo "✗ ERRO ao iniciar servico"
    sudo systemctl status aicentralv2 --no-pager -l
    sudo journalctl -u aicentralv2 -n 50 --no-pager
    exit 1
fi

echo "========================================"
echo "Deploy concluido com sucesso!"
echo "========================================"
echo ""
echo "Imagens serao salvas em:"
echo "aicentralv2/static/uploads/audiencias/"
echo ""
echo "Verifique o status:"
echo "sudo systemctl status aicentralv2"
echo ""
echo "Logs:"
echo "sudo journalctl -u aicentralv2 -f"
echo ""
