"""
Verifica estrutura do banco de dados
"""

import psycopg
import os
from dotenv import load_dotenv

load_dotenv()

db_config = {
    'dbname': os.getenv('DB_NAME', 'aicentral_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432')
}

print("\n" + "="*60)
print("🔍 VERIFICANDO BANCO DE DADOS")
print("="*60)

try:
    conn = psycopg.connect(**db_config)
    cursor = conn.cursor()
    
    print("\n1. Tabelas existentes:")
    cursor.execute('''
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    ''')
    
    tables = cursor.fetchall()
    if tables:
        for table in tables:
            print(f"   ✅ {table[0]}")
    else:
        print("   ⚠️ Nenhuma tabela encontrada!")
    
    print("\n2. Colunas de tbl_contato_cliente:")
    cursor.execute('''
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_name = 'tbl_contato_cliente'
        ORDER BY ordinal_position
    ''')
    
    columns = cursor.fetchall()
    if columns:
        for col in columns:
            col_name = col[0]
            col_type = col[1]
            col_length = f"({col[2]})" if col[2] else ""
            print(f"   ✅ {col_name}: {col_type}{col_length}")
    else:
        print("   ⚠️ Tabela tbl_contato_cliente não existe!")
    
    print("\n3. Dados:")
    
    try:
        cursor.execute("SELECT COUNT(*) FROM tbl_cliente")
        total_clientes = cursor.fetchone()[0]
        print(f"   📊 Clientes: {total_clientes}")
    except:
        print("   ⚠️ Erro ao contar clientes")
    
    try:
        cursor.execute("SELECT COUNT(*) FROM tbl_contato_cliente")
        total_contatos = cursor.fetchone()[0]
        print(f"   📊 Contatos: {total_contatos}")
    except:
        print("   ⚠️ Erro ao contar contatos")
    
    print("\n4. Contatos cadastrados:")
    try:
        cursor.execute('''
            SELECT 
                c.id_contato_cliente,
                c.email,
                c.nome_completo,
                c.status,
                cli.nome_fantasia
            FROM tbl_contato_cliente c
            LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente
            ORDER BY c.id_contato_cliente
        ''')
        
        contatos = cursor.fetchall()
        if contatos:
            for contato in contatos:
                status = "🟢" if contato[3] else "🔴"
                print(f"   {status} ID: {contato[0]} | {contato[2]} ({contato[1]}) | Cliente: {contato[4]}")
        else:
            print("   ⚠️ Nenhum contato cadastrado")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*60 + "\n")

except Exception as e:
    print(f"\n❌ ERRO: {e}\n")