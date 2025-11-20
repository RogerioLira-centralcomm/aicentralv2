#!/bin/bash

# Script de Deploy para Produção
# Uso: ./deploy.sh

set -e  # Parar em caso de erro

echo "🚀 Iniciando Deploy..."

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configurações
APP_DIR="/var/www/aicentralv2"
VENV_DIR="$APP_DIR/venv"
SERVICE_NAME="aicentralv2"

# Verificar se .env existe
if [ ! -f "$APP_DIR/.env" ]; then
    echo -e "${RED}❌ ERRO: Arquivo .env não encontrado!${NC}"
    echo -e "${YELLOW}Crie o arquivo .env com as variáveis necessárias:${NC}"
    echo "  - DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD"
    echo "  - SECRET_KEY"
    echo "  - OPENROUTER_API_KEY"
    exit 1
fi

echo -e "${YELLOW}📥 Atualizando código...${NC}"
cd $APP_DIR
git pull origin main

echo -e "${YELLOW}📦 Ativando ambiente virtual...${NC}"
source $VENV_DIR/bin/activate

echo -e "${YELLOW}📥 Instalando/Atualizando dependências...${NC}"
pip install -r requirements.txt --upgrade

# Criar diretório de uploads se não existir
echo -e "${YELLOW}📁 Verificando diretórios...${NC}"
mkdir -p $APP_DIR/aicentralv2/static/uploads/audiencias
chmod 755 $APP_DIR/aicentralv2/static/uploads/audiencias

# Limpar cache Python
echo -e "${YELLOW}🧹 Limpando cache Python...${NC}"
find $APP_DIR -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find $APP_DIR -type f -name "*.pyc" -delete 2>/dev/null || true

echo -e "${YELLOW}🔄 Reiniciando serviço...${NC}"
sudo systemctl restart $SERVICE_NAME

echo -e "${YELLOW}✅ Verificando status...${NC}"
sudo systemctl status $SERVICE_NAME --no-pager

echo -e "${GREEN}✅ Deploy concluído com sucesso!${NC}"