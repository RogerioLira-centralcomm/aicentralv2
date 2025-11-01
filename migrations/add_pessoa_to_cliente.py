"""
Adiciona campo pessoa na tabela tbl_cliente
Execução: python add_pessoa_to_cliente.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aicentralv2 import create_app


def adicionar_campo_pessoa():
    """Adiciona campo pessoa na tabela tbl_cliente"""
    print("=" * 70)
    print("🏢 ADICIONANDO CAMPO: pessoa em tbl_cliente")
    print("=" * 70)

    app = create_app()

    with app.app_context():
        from aicentralv2 import db
        conn = db.get_db()

        try:
            with conn.cursor() as cursor:
                # 1. Adicionar campo pessoa
                print("\n1️⃣ Adicionando campo pessoa...")
                cursor.execute("""
                    ALTER TABLE public.tbl_cliente 
                    ADD COLUMN IF NOT EXISTS pessoa CHAR(1) DEFAULT 'J' NOT NULL 
                    CHECK (pessoa IN ('F', 'J'))
                """)
                print("   ✅ Campo pessoa adicionado!")

                # 2. Atualizar registros existentes
                print("\n2️⃣ Atualizando registros existentes...")
                cursor.execute("""
                    UPDATE public.tbl_cliente 
                    SET pessoa = 'J' 
                    WHERE pessoa IS NULL
                """)
                print("   ✅ Registros atualizados!")

                conn.commit()
                print("\n✅ Alterações realizadas com sucesso!")

        except Exception as e:
            conn.rollback()
            print(f"\n❌ Erro: {str(e)}")
            raise

        finally:
            db.close_db()


if __name__ == "__main__":
    adicionar_campo_pessoa()