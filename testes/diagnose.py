import psycopg
from psycopg.rows import dict_row

# Configuração do banco
DATABASE_URL = "postgresql://postgres:nova_senha@212.85.13.233:123/cpythondev"

try:
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    cursor = conn.cursor()

    print("✅ Conexão estabelecida!\n")

    # Verificar tabelas
    print("📋 Verificando tabelas...\n")

    tables = [
        'tbl_cliente',
        'tbl_estado',
        'aux_agencia',
        'aux_apresentacao_executivo',
        'aux_fluxo_boas_vindas',
        'aux_percentual',
        'tbl_setor',
        'tbl_contato_cliente'
    ]

    for table in tables:
        cursor.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{table}'
            )
        """)
        exists = cursor.fetchone()['exists']

        if exists:
            cursor.execute(f'SELECT COUNT(*) as total FROM {table}')
            total = cursor.fetchone()['total']
            print(f"✅ {table}: {total} registros")
        else:
            print(f"❌ {table}: NÃO EXISTE!")

    conn.close()
    print("\n✅ Diagnóstico concluído!")

except Exception as e:
    print(f"❌ Erro: {str(e)}")
    import traceback

    traceback.print_exc()