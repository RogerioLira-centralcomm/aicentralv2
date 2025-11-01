"""
Verifica estrutura das tabelas
"""
from aicentralv2.db import get_db

def check_table_structure():
    """Verifica estrutura das tabelas"""
    conn = get_db()
    with conn.cursor() as cursor:
        # Verifica tabela aux_setor
        print("\n=== Estrutura da tabela aux_setor ===")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'aux_setor'
            ORDER BY ordinal_position;
        """)
        columns = cursor.fetchall()
        for col in columns:
            print(f"Coluna: {col['column_name']}, Tipo: {col['data_type']}, Nullable: {col['is_nullable']}")
            
        # Verifica dados da tabela aux_setor
        print("\n=== Dados da tabela aux_setor ===")
        cursor.execute("SELECT * FROM aux_setor ORDER BY id_aux_setor")
        setores = cursor.fetchall()
        for setor in setores:
            print(setor)
            
        # Verifica tabela cargo_contato
        print("\n=== Estrutura da tabela tbl_cargo_contato ===")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'tbl_cargo_contato'
            ORDER BY ordinal_position;
        """)
        columns = cursor.fetchall()
        for col in columns:
            print(f"Coluna: {col['column_name']}, Tipo: {col['data_type']}, Nullable: {col['is_nullable']}")

if __name__ == '__main__':
    check_table_structure()