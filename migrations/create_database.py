"""
AIcentralv2 - Script para criar o banco de dados PostgreSQL (psycopg3)
"""
import psycopg
from dotenv import load_dotenv
import os
import sys

# Carregar variáveis de ambiente
load_dotenv()

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', '../aicentralv2')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

def create_database():
    """Cria o banco de dados se não existir"""
    try:
        # Conectar ao banco postgres padrão
        conn_string = f"host={DB_HOST} port={DB_PORT} dbname=postgres user={DB_USER} password={DB_PASSWORD}"
        
        print("🔌 Conectando ao PostgreSQL...")
        conn = psycopg.connect(conn_string, autocommit=True)
        
        with conn.cursor() as cursor:
            # Verificar se o banco já existe
            cursor.execute(
                "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
                (DB_NAME,)
            )
            exists = cursor.fetchone()
            
            if not exists:
                # Criar banco de dados
                # Usar SQL direto pois IDENTIFIER não existe no psycopg3 da mesma forma
                cursor.execute(f'CREATE DATABASE {DB_NAME}')
                print(f"✅ Banco de dados '{DB_NAME}' criado com sucesso!")
            else:
                print(f"ℹ️  Banco de dados '{DB_NAME}' já existe!")
        
        conn.close()
        
    except psycopg.OperationalError as e:
        print(f"❌ Erro de conexão: {e}")
        print("\n💡 Possíveis causas:")
        print("   1. PostgreSQL não está instalado ou não está rodando")
        print("   2. Credenciais incorretas no arquivo .env")
        print("   3. Porta incorreta (padrão: 5432)")
        print("\n🔧 Como verificar:")
        print("   - Windows: Services -> PostgreSQL")
        print("   - Teste: psql -U postgres")
        sys.exit(1)
    except psycopg.Error as e:
        print(f"❌ Erro ao criar banco de dados: {e}")
        print(f"💡 Verifique as permissões do usuário '{DB_USER}'")
        sys.exit(1)


if __name__ == '__main__':
    print("=" * 70)
    print("🤖 AIcentralv2 - Criação de Banco de Dados (psycopg3)")
    print("=" * 70)
    print(f"📍 Host: {DB_HOST}:{DB_PORT}")
    print(f"📦 Database: {DB_NAME}")
    print(f"👤 User: {DB_USER}")
    print("=" * 70)
    
    create_database()
    
    print("=" * 70)
    print("✅ Processo concluído!")
    print("📌 Próximo passo: execute 'python run.py'")
    print("=" * 70)