"""
Sincroniza os contatos do Leads v3 e do CRM v3 com as listas da Brevo.

Por padrão só mostra a prévia (o que entraria e sairia de cada lista).
Use --apply para gravar na Brevo. O banco é só lido.

    .venv/bin/python scripts/brevo_sincronizar_contatos.py
    .venv/bin/python scripts/brevo_sincronizar_contatos.py --apply
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import psycopg  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="grava na Brevo (sem isso, só prévia)")
    args = parser.parse_args()

    from aicentralv2 import create_app, db as db_mod
    from aicentralv2.services.brevo_contatos_sync import LISTAS_EXECUTIVO, sincronizar, tamanhos_das_listas
    from aicentralv2.services.brevo_service import LISTA_USUARIOS_ATIVOS, BrevoService

    app = create_app()
    with app.app_context():
        service = BrevoService()
        listas = sorted(LISTAS_EXECUTIVO | {LISTA_USUARIOS_ATIVOS})
        antes = tamanhos_das_listas(service, listas)
        with psycopg.connect(**db_mod.get_db_config()) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                resultado = sincronizar(cur, service, aplicar=args.apply)
        saida = {"listas_antes": antes, **resultado}
        if args.apply:
            saida["listas_depois"] = tamanhos_das_listas(service, listas)
        print(json.dumps(saida, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
