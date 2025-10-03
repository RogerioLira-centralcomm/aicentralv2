"""
Cria a tabela tbl_cliente e adiciona FK em users
Execução: python create_tbl_cliente.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aicentralv2 import create_app


def criar_estrutura():
    """Cria a tabela tbl_cliente e relacionamento com users"""
    print("=" * 70)
    print("🏢 CRIANDO ESTRUTURA: tbl_cliente")
    print("=" * 70)

    app = create_app()

    with app.app_context():
        from aicentralv2 import db
        conn = db.get_db()

        try:
            with conn.cursor() as cursor:
                # 1. Criar sequence para id_cliente
                print("\n1️⃣ Criando sequence cliente_id_seq...")
                cursor.execute("""
                    CREATE SEQUENCE IF NOT EXISTS cliente_id_seq
                    START WITH 1
                    INCREMENT BY 1
                    NO MINVALUE
                    NO MAXVALUE
                    CACHE 1
                """)
                print("   ✅ Sequence criada!")

                # 2. Criar tabela tbl_cliente
                print("\n2️⃣ Criando tabela tbl_cliente...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS public.tbl_cliente
                    (
                        id_cliente INTEGER NOT NULL DEFAULT nextval('cliente_id_seq'::regclass),
                        cnpj VARCHAR(40),
                        pk_id_aux_status_sincronismo INTEGER,
                        inscricao_municipal VARCHAR(30),
                        inscricao_estadual VARCHAR(30),
                        nome_fantasia VARCHAR(300),
                        bairro VARCHAR(100),
                        cep VARCHAR(9),
                        cidade VARCHAR(100),
                        complemento VARCHAR(60),
                        responsavel_centralcomm INTEGER,
                        id_centralx VARCHAR(100),
                        razao_social VARCHAR(300),
                        numero VARCHAR(30),
                        status BOOLEAN DEFAULT TRUE,
                        data_cadastro TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,

                        CONSTRAINT tbl_cliente_pkey PRIMARY KEY (id_cliente)
                    )
                """)
                print("   ✅ Tabela tbl_cliente criada!")

                # 3. Adicionar FK para aux_status_sincronismo
                print("\n3️⃣ Adicionando FK para aux_status_sincronismo...")
                try:
                    cursor.execute("""
                        ALTER TABLE public.tbl_cliente
                        ADD CONSTRAINT id_aux_status_sincronismo 
                        FOREIGN KEY (pk_id_aux_status_sincronismo)
                        REFERENCES public.aux_status_sincronismo (id_aux_status_sincronismo)
                        ON UPDATE NO ACTION
                        ON DELETE NO ACTION
                    """)
                    print("   ✅ FK aux_status_sincronismo adicionada!")
                except Exception as e:
                    if 'already exists' in str(e).lower():
                        print("   ⚠️  FK aux_status_sincronismo já existe")
                    else:
                        raise

                # 4. Adicionar FK para users (responsavel_centralcomm)
                print("\n4️⃣ Adicionando FK para users (responsavel_centralcomm)...")
                try:
                    cursor.execute("""
                        ALTER TABLE public.tbl_cliente
                        ADD CONSTRAINT "ID_OSUser"
                        FOREIGN KEY (responsavel_centralcomm)
                        REFERENCES public.users (id)
                        ON UPDATE NO ACTION
                        ON DELETE NO ACTION
                    """)
                    print("   ✅ FK responsavel_centralcomm adicionada!")
                except Exception as e:
                    if 'already exists' in str(e).lower():
                        print("   ⚠️  FK responsavel_centralcomm já existe")
                    else:
                        raise

                # 5. Adicionar coluna id_cliente na tabela users
                print("\n5️⃣ Adicionando coluna id_cliente na tabela users...")
                try:
                    cursor.execute("""
                        ALTER TABLE public.users
                        ADD COLUMN id_cliente INTEGER
                    """)
                    print("   ✅ Coluna id_cliente adicionada!")
                except Exception as e:
                    if 'already exists' in str(e).lower():
                        print("   ⚠️  Coluna id_cliente já existe")
                    else:
                        raise

                # 6. Adicionar FK de users para tbl_cliente
                print("\n6️⃣ Adicionando FK de users para tbl_cliente...")
                try:
                    cursor.execute("""
                        ALTER TABLE public.users
                        ADD CONSTRAINT fk_users_cliente
                        FOREIGN KEY (id_cliente)
                        REFERENCES public.tbl_cliente (id_cliente)
                        ON UPDATE NO ACTION
                        ON DELETE SET NULL
                    """)
                    print("   ✅ FK users -> tbl_cliente adicionada!")
                except Exception as e:
                    if 'already exists' in str(e).lower():
                        print("   ⚠️  FK users -> tbl_cliente já existe")
                    else:
                        raise

                # 7. Criar índices
                print("\n7️⃣ Criando índices...")
                indices = [
                    ("idx_cliente_cnpj", "tbl_cliente", "cnpj"),
                    ("idx_cliente_status", "tbl_cliente", "status"),
                    ("idx_cliente_responsavel", "tbl_cliente", "responsavel_centralcomm"),
                    ("idx_users_id_cliente", "users", "id_cliente"),
                ]

                for nome_idx, tabela, coluna in indices:
                    try:
                        cursor.execute(f"""
                            CREATE INDEX IF NOT EXISTS {nome_idx} 
                            ON public.{tabela}({coluna})
                        """)
                        print(f"   ✅ Índice {nome_idx} criado")
                    except Exception as e:
                        print(f"   ⚠️  Erro ao criar índice {nome_idx}: {e}")

                # Commit
                conn.commit()

                # 8. Verificar estrutura criada
                print("\n8️⃣ Verificando estrutura da tabela tbl_cliente...")
                cursor.execute("""
                    SELECT 
                        column_name,
                        data_type,
                        character_maximum_length,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_name = 'tbl_cliente'
                    ORDER BY ordinal_position
                """)

                colunas = cursor.fetchall()

                print("\n   ┌──────────────────────────────┬──────────────┬─────────┬──────────┐")
                print("   │ COLUNA                       │ TIPO         │ TAMANHO │ NULLABLE │")
                print("   ├──────────────────────────────┼──────────────┼─────────┼──────────┤")

                for col in colunas:
                    coluna = str(col['column_name'])[:28].ljust(28)
                    tipo = str(col['data_type'])[:12].ljust(12)
                    tamanho = str(col['character_maximum_length'] or '-')[:7].ljust(7)
                    nullable = "SIM" if col['is_nullable'] == 'YES' else "NÃO"
                    print(f"   │ {coluna} │ {tipo} │ {tamanho} │ {nullable:8s} │")

                print("   └──────────────────────────────┴──────────────┴─────────┴──────────┘")

                # 9. Verificar FKs
                print("\n9️⃣ Verificando Foreign Keys...")
                cursor.execute("""
                    SELECT
                        tc.constraint_name,
                        tc.table_name,
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                        ON ccu.constraint_name = tc.constraint_name
                        AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND tc.table_name IN ('tbl_cliente', 'users')
                    ORDER BY tc.table_name, tc.constraint_name
                """)

                fks = cursor.fetchall()

                print("\n   Tabela: tbl_cliente")
                for fk in fks:
                    if fk['table_name'] == 'tbl_cliente':
                        print(f"   ✅ {fk['constraint_name']}")
                        print(f"      {fk['column_name']} -> {fk['foreign_table_name']}.{fk['foreign_column_name']}")

                print("\n   Tabela: users")
                for fk in fks:
                    if fk['table_name'] == 'users':
                        print(f"   ✅ {fk['constraint_name']}")
                        print(f"      {fk['column_name']} -> {fk['foreign_table_name']}.{fk['foreign_column_name']}")

                # 10. Contar registros
                print("\n🔟 Contando registros...")
                cursor.execute("SELECT COUNT(*) as total FROM tbl_cliente")
                total = cursor.fetchone()['total']
                print(f"   📊 Total de clientes: {total}")

            print("\n" + "=" * 70)
            print("✅ ESTRUTURA CRIADA COM SUCESSO!")
            print("=" * 70)

            print("\n📋 Resumo:")
            print("   ✅ Sequence cliente_id_seq criada")
            print("   ✅ Tabela tbl_cliente criada")
            print("   ✅ FK tbl_cliente -> aux_status_sincronismo")
            print("   ✅ FK tbl_cliente -> users (responsavel)")
            print("   ✅ Coluna id_cliente adicionada em users")
            print("   ✅ FK users -> tbl_cliente")
            print("   ✅ Índices criados")

            print("\n💡 Próximos passos:")
            print("   1. Inserir clientes:")
            print("      python insert_clientes.py")
            print("\n   2. Verificar estrutura:")
            print("      python verify_tbl_cliente.py")

            return True

        except Exception as e:
            conn.rollback()
            print(f"\n❌ Erro ao criar estrutura: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    print("\n🚀 Iniciando criação da estrutura...\n")
    sucesso = criar_estrutura()

    if sucesso:
        print("\n✅ Script executado com sucesso!")
        sys.exit(0)
    else:
        print("\n❌ Script falhou!")
        sys.exit(1)