"""Repara composição financeira das campanhas de um PI (explícito). Ex.: python scripts/reparar_composicao_pi.py 8271"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(".env")
from aicentralv2 import create_app


def resolve_id_pi(dbmod, arg: str):
    arg = (arg or "").strip()
    if arg.isdigit() and len(arg) <= 6:
        row = dbmod.obter_cadu_pi_por_id(int(arg))
        if row:
            return int(row["id_pi"])
    conn = dbmod.get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id_pi FROM cadu_pi
            WHERE codigo_pi_cc::text = %s
               OR id_pi::text = %s
               OR REPLACE(codigo_pi_cc::text, ' ', '') = REPLACE(%s, ' ', '')
               OR codigo_pi_cc::text ILIKE %s
            ORDER BY id_pi DESC
            LIMIT 1
            """,
            (arg, arg, arg, f"%{arg}%"),
        )
        r = cur.fetchone()
        if r:
            return int(r["id_pi"])
    return None


def main():
    if len(sys.argv) < 2:
        print("Uso: reparar_composicao_pi.py <codigo_pi_cc ou id_pi>")
        sys.exit(1)
    app = create_app()
    with app.app_context():
        from aicentralv2 import db as dbmod

        id_pi = resolve_id_pi(dbmod, sys.argv[1].strip())
        if not id_pi:
            print("PI não encontrado:", sys.argv[1])
            sys.exit(1)
        out = dbmod.reparar_composicao_financeira_por_id_pi(id_pi)
        print(out)


if __name__ == "__main__":
    main()