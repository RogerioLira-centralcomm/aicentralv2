#!/usr/bin/env python
"""Remove a unicidade de crm_client_id antes das demais migrations da modelagem."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cx_clients_crm import connect, liberar_crm_client_id, validar_crm_client_id


def main():
    conn = connect()
    try:
        with conn.cursor() as cursor:
            liberar_crm_client_id(cursor)
            validar_crm_client_id(cursor, exigir_tabela=False)
        conn.commit()
        print("Índice de crm_client_id liberado para marcas compartilhadas.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
