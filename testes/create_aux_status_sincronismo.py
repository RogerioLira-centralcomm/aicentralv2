"""
Cria a tabela aux_status_sincronismo no banco de dados
Execução: python create_aux_status_sincronismo.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aicentralv2 import create_app


def criar_tabela():
    """Cria a tabela aux_status_sincronismo"""
    print("=" * 70)
    print("📊 CRIANDO TABELA: aux_status_sincronismo")
    print("=" * 70)

    app = create_app()

    with app.app_context():
        from aicentralv2 import db
        conn = db.get_db()

        try:
            with conn.cursor() as cursor:
                # Criar tabela
                print("\n1️⃣ Criando tabela aux_status_sincronismo...")

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS public.aux_status_sincronismo
                    (
                        id_aux_status_sincronismo INTEGER NOT NULL,
                        display VARCHAR(30),
                        CONSTRAINT tbl_osstatussincronismo_pkey PRIMARY KEY (id_aux_status_sincronismo)
                    )
                """)

                print("   ✅ Tabela criada com sucesso!")

                # Verificar se a tabela existe
                print("\n2️⃣ Verificando tabela...")
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public'
                        AND table_name = 'aux_status_sincronismo'
                    ) as existe
                """)

                resultado = cursor.fetchone()
                existe = resultado['existe']  # ✅ CORREÇÃO: usar nome da coluna

                if existe:
                    print("   ✅ Tabela existe!")

                    # Mostrar estrutura
                    print("\n3️⃣ Estrutura da tabela:")
                    cursor.execute("""
                        SELECT 
                            column_name,
                            data_type,
                            character_maximum_length,
                            is_nullable
                        FROM information_schema.columns
                        WHERE table_name = 'aux_status_sincronismo'
                        ORDER BY ordinal_position
                    """)

                    colunas = cursor.fetchall()

                    print("   ┌─────────────────────────────┬─────────────┬─────────┬──────────┐")
                    print("   │ COLUNA                      │ TIPO        │ TAMANHO │ NULLABLE │")
                    print("   ├─────────────────────────────┼─────────────┼─────────┼──────────┤")

                    for col in colunas:
                        coluna = str(col['column_name'])[:27].ljust(27)
                        tipo = str(col['data_type'])[:11].ljust(11)
                        tamanho = str(col['character_maximum_length'] or '-')[:7].ljust(7)
                        nullable = "SIM" if col['is_nullable'] == 'YES' else "NÃO"
                        print(f"   │ {coluna} │ {tipo} │ {tamanho} │ {nullable:8s} │")

                    print("   └─────────────────────────────┴─────────────┴─────────┴──────────┘")

                    # Verificar constraints
                    print("\n4️⃣ Constraints:")
                    cursor.execute("""
                        SELECT
                            conname AS constraint_name,
                            contype AS constraint_type
                        FROM pg_constraint
                        WHERE conrelid = 'public.aux_status_sincronismo'::regclass
                    """)

                    constraints = cursor.fetchall()

                    if constraints:
                        for const in constraints:
                            tipo_map = {
                                'p': 'PRIMARY KEY',
                                'f': 'FOREIGN KEY',
                                'u': 'UNIQUE',
                                'c': 'CHECK'
                            }
                            tipo = tipo_map.get(const['constraint_type'], const['constraint_type'])
                            print(f"   ✅ {const['constraint_name']} ({tipo})")
                    else:
                        print("   ℹ️  Nenhuma constraint encontrada")

                    # Contar registros
                    print("\n5️⃣ Dados na tabela:")
                    cursor.execute("SELECT COUNT(*) as total FROM aux_status_sincronismo")
                    resultado = cursor.fetchone()
                    total = resultado['total']
                    print(f"   📊 Total de registros: {total}")

                    if total > 0:
                        cursor.execute("""
                            SELECT * FROM aux_status_sincronismo 
                            ORDER BY id_aux_status_sincronismo
                        """)
                        registros = cursor.fetchall()

                        print("\n   Registros existentes:")
                        for reg in registros:
                            print(f"   • ID {reg['id_aux_status_sincronismo']}: {reg['display']}")

                else:
                    print("   ❌ Erro: Tabela não foi criada!")
                    return False

            # Commit
            conn.commit()

            print("\n" + "=" * 70)
            print("✅ TABELA CRIADA COM SUCESSO!")
            print("=" * 70)

            # Instruções
            print("\n💡 Próximos passos:")
            print("   1. Para inserir dados de exemplo:")
            print("      python insert_status_sincronismo.py")
            print("\n   2. Para verificar a tabela:")
            print("      python verify_aux_status.py")

            return True

        except Exception as e:
            conn.rollback()
            print(f"\n❌ Erro ao criar tabela: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    print("\n🚀 Iniciando criação da tabela...\n")
    sucesso = criar_tabela()

    if sucesso:
        print("\n✅ Script executado com sucesso!")
        sys.exit(0)
    else:
        print("\n❌ Script falhou!")
        sys.exit(1)