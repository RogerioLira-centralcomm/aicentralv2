"""
Adiciona relação com cargo na tabela de contatos
"""
from aicentralv2.db import get_db

def add_cargo_to_contatos():
    """Adiciona coluna de cargo na tabela de contatos"""
    conn = get_db()
    with conn.cursor() as cur:
        # Verifica se a coluna já existe
        cur.execute("""
            SELECT EXISTS (
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'tbl_contato_cliente' 
                AND column_name = 'pk_id_tbl_cargo'
            );
        """)
        column_exists = cur.fetchone()[0]
        
        if not column_exists:
            # Adiciona a coluna e a chave estrangeira
            cur.execute("""
                ALTER TABLE tbl_contato_cliente 
                ADD COLUMN pk_id_tbl_cargo INTEGER,
                ADD CONSTRAINT fk_cargo_contato 
                FOREIGN KEY (pk_id_tbl_cargo) 
                REFERENCES tbl_cargo_contato(id_cargo_contato);
                
                COMMENT ON COLUMN tbl_contato_cliente.pk_id_tbl_cargo IS 'ID do cargo do contato';
            """)
            print("Coluna pk_id_tbl_cargo adicionada com sucesso!")
            conn.commit()
        else:
            print("Coluna pk_id_tbl_cargo já existe.")

if __name__ == '__main__':
    add_cargo_to_contatos()