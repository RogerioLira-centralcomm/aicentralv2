#!/bin/bash

# Script para executar migrações do painel admin em produção
# Execute APÓS fazer o deploy do código

set -e

echo "========================================"
echo "Migrações - Painel Admin"
echo "========================================"

# Ativar ambiente virtual
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "venv_new" ]; then
    source venv_new/bin/activate
else
    echo "ERRO: Ambiente virtual não encontrado"
    exit 1
fi

# Executar migrações na ordem correta
echo ""
echo "1/4 - Adicionando coluna user_type..."
python migrations/add_user_type_to_contatos.py

echo ""
echo "2/4 - Criando tabela de audit log..."
python migrations/create_admin_audit_log.py

echo ""
echo "3/4 - Criando tabela de planos..."
python migrations/create_cadu_client_plans.py

echo ""
echo "4/4 - Criando tabela de invoices..."
python migrations/create_cadu_invoices.py

echo ""
echo "========================================"
echo "✅ Migrações concluídas!"
echo "========================================"
echo ""
echo "PRÓXIMOS PASSOS:"
echo ""
echo "1. Definir usuário(s) admin:"
echo "   UPDATE tbl_contato_cliente SET user_type='admin' WHERE email='seu_email@exemplo.com';"
echo ""
echo "2. Reiniciar o serviço:"
echo "   sudo systemctl restart aicentralv2"
echo ""
echo "3. Acessar painel admin:"
echo "   http://seu-dominio.com/admin/"
echo ""
