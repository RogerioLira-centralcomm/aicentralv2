"""Lista PIs com campanhas cujo %/R$ não batem com VP × (%÷100). Uso: diagnóstico manual."""
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

        rows = dbmod.listar_pis_composicao_campanha_inconsistente()
        print(f"PIs com composição inconsistente: {len(rows)}\n")
        for r in rows:
            codigo = r.get("codigo_pi_cc") or r.get("id_pi")
            sub = r.get("sub_status") or r.get("id_sub_status_pi")
            cliente = r.get("cliente_nome") or ""
            titulo = (r.get("titulo_pi") or "")[:60]
            q = r.get("qtd_campanhas_inconsistentes", r.get("qtd_campanhas"))
            print(
                f"  {codigo} | id_pi={r['id_pi']} | {sub} | {cliente} | "
                f"{q} camp(s) | {titulo}"
            )


if __name__ == "__main__":
    main()