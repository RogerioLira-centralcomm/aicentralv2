#!/bin/bash

# Script de Deploy - AIcentral v2
# Atualiza codigo, instala dependencias e reinicia servico

set -e  # Parar execucao em caso de erro

echo "========================================"
echo "Deploy AIcentral v2"
echo "========================================"

# Verificar se .env existe
if [ ! -f .env ]; then
    echo "ERRO: Arquivo .env nao encontrado!"
    echo "Copie .env.example para .env e configure as variaveis"
    exit 1
fi

# Atualizar codigo
echo "Atualizando codigo..."
git pull origin main

# Ativar ambiente virtual
echo "Ativando ambiente virtual..."
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "venv_new" ]; then
    source venv_new/bin/activate
else
    echo "ERRO: Ambiente virtual nao encontrado (venv ou venv_new)"
    exit 1
fi

# Instalar/atualizar dependencias
echo "Instalando dependencias..."
pip install -r requirements.txt --upgrade

# Criar diretorio de uploads se nao existir
echo "Verificando diretorio de uploads..."
mkdir -p aicentralv2/static/uploads/audiencias
chmod 755 aicentralv2/static/uploads/audiencias

# Limpar cache Python
echo "Limpando cache Python..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Parar servico e limpar processos travados
echo "Parando servico..."
sudo systemctl stop aicentralv2 || true

echo "Limpando processos gunicorn travados..."
sudo pkill -9 gunicorn 2>/dev/null || true
sleep 2

# Remover arquivo PID se existir
if [ -f "gunicorn.pid" ]; then
    echo "Removendo arquivo PID antigo..."
    sudo rm -f gunicorn.pid
fi

# Reiniciar servico
echo "Iniciando servico..."
sudo systemctl start aicentralv2

# Verificar status
sleep 3
if sudo systemctl is-active --quiet aicentralv2; then
    echo "✓ Servico iniciado com sucesso!"
else
    echo "✗ ERRO: Falha ao iniciar servico"
    echo "Executando diagnostico..."
    sudo systemctl status aicentralv2 --no-pager
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
