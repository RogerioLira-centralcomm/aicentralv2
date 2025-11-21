"""
Migração: Adicionar coluna user_type à tabela tbl_contato_cliente
Descrição: Suporte para diferentes tipos de usuários (client, admin, superadmin, readonly)
Data: 2025-11-21
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

def adicionar_user_type():
    """Adiciona coluna user_type à tabela tbl_contato_cliente"""
    conn = psycopg.connect(
        dbname=os.getenv('DATABASE_NAME'),
        user=os.getenv('DATABASE_USER'),
        password=os.getenv('DATABASE_PASSWORD'),
        host=os.getenv('DATABASE_HOST'),
        port=os.getenv('DATABASE_PORT'),
        row_factory=dict_row
    )
    
    try:
        with conn.cursor() as cursor:
            # Verificar se coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='tbl_contato_cliente' 
                AND column_name='user_type'
            """)
            
            if cursor.fetchone():
                print("⚠️  Coluna user_type já existe, pulando...")
                return
            
            # Adicionar coluna user_type
            cursor.execute("""
                ALTER TABLE tbl_contato_cliente 
                ADD COLUMN user_type VARCHAR(20) DEFAULT 'client' 
                CHECK (user_type IN ('client', 'admin', 'superadmin', 'readonly'))
            """)
            
            # Atualizar usuários existentes
            cursor.execute("""
                UPDATE tbl_contato_cliente 
                SET user_type = 'client' 
                WHERE user_type IS NULL
            """)
            
            # Criar índice
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_contato_user_type 
                ON tbl_contato_cliente(user_type)
            """)
            
            conn.commit()
            print("✅ Coluna user_type adicionada com sucesso!")
            print("✅ Índice criado")
            print("📋 Tipos disponíveis: client, admin, superadmin, readonly")
            print("📋 Todos os usuários existentes foram definidos como 'client'")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao adicionar coluna user_type: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    print("🔧 Iniciando migração: Adicionar user_type")
    adicionar_user_type()
    print("✅ Migração concluída!")
