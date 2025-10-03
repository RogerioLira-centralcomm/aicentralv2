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

echo -e "${YELLOW}📥 Atualizando código...${NC}"
cd $APP_DIR
git pull origin main

echo -e "${YELLOW}📦 Ativando ambiente virtual...${NC}"
source $VENV_DIR/bin/activate

echo -e "${YELLOW}📥 Instalando/Atualizando dependências...${NC}"
pip install -r requirements.txt --upgrade

echo -e "${YELLOW}🔄 Reiniciando serviço...${NC}"
sudo systemctl restart $SERVICE_NAME

echo -e "${YELLOW}✅ Verificando status...${NC}"
sudo systemctl status $SERVICE_NAME --no-pager

echo -e "${GREEN}✅ Deploy concluído com sucesso!${NC}"