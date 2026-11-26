"""Repara composição financeira de todas as campanhas inconsistentes."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(".env")
from aicentralv2 import create_app


def main():
    app = create_app()
    with app.app_context():
        from aicentralv2 import db as dbmod

        antes = len(dbmod.listar_pis_composicao_campanha_inconsistente())
        print(f"PIs inconsistentes antes: {antes}")
        out = dbmod.reparar_composicao_financeira_todas_campanhas()
        depois = len(dbmod.listar_pis_composicao_campanha_inconsistente())
        print(f"Campanhas reparadas: {out.get('reparadas')}")
        print(f"PIs afetados: {out.get('pis_afetados')}")
        if out.get("detalhe_por_pi"):
            for row in out["detalhe_por_pi"]:
                print(f"  PI {row.get('codigo_pi_cc') or row.get('id_pi')}: camps {row.get('id_campanhas')}")
        print(f"PIs inconsistentes depois: {depois}")


if __name__ == "__main__":
    main()