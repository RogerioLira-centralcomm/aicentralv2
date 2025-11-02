"""
Adiciona relacionamento entre tbl_cliente e aux_agencia
Execução: python add_agencia_to_cliente.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aicentralv2 import create_app


def adicionar_campo_agencia():
    """Adiciona campo pk_id_aux_agencia na tabela tbl_cliente"""
    print("=" * 70)
    print("🏢 ADICIONANDO CAMPO: pk_id_aux_agencia em tbl_cliente")
    print("=" * 70)

    app = create_app()

    with app.app_context():
        from aicentralv2 import db
        conn = db.get_db()

        try:
            with conn.cursor() as cursor:
                # 1. Adicionar campo pk_id_aux_agencia
                print("\n1️⃣ Adicionando campo pk_id_aux_agencia...")
                cursor.execute("""
                    ALTER TABLE public.tbl_cliente 
                    ADD COLUMN IF NOT EXISTS pk_id_aux_agencia INTEGER
                """)
                print("   ✅ Campo pk_id_aux_agencia adicionado!")

                # 2. Adicionar foreign key
                print("\n2️⃣ Adicionando foreign key para aux_agencia...")
                cursor.execute("""
                    ALTER TABLE public.tbl_cliente
                    ADD CONSTRAINT fk_cliente_agencia
                    FOREIGN KEY (pk_id_aux_agencia)
                    REFERENCES public.aux_agencia(id_aux_agencia)
                    ON UPDATE NO ACTION
                    ON DELETE NO ACTION
                """)
                print("   ✅ Foreign key adicionada!")

                # 3. Adicionar índice
                print("\n3️⃣ Criando índice...")
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cliente_agencia
                    ON public.tbl_cliente(pk_id_aux_agencia)
                """)
                print("   ✅ Índice criado!")

                conn.commit()
                print("\n✅ Alterações realizadas com sucesso!")

        except Exception as e:
            conn.rollback()
            print(f"\n❌ Erro: {str(e)}")
            raise

        finally:
            db.close_db()


if __name__ == "__main__":
    adicionar_campo_agencia()