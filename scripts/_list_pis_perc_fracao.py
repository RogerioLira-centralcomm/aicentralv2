"""Lista PIs com campanhas cujo percentual está gravado em fração (0 < v <= 1)."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(".env")
from aicentralv2 import create_app

PERC_COLS = (
    "perc_margem_cc",
    "perc_tech_fee",
    "perc_com_vendas",
    "perc_pl_incentivos",
    "perc_impostos",
)


def _perc_em_fracao(val):
    from aicentralv2 import db as dbmod

    v = dbmod.parse_percentual_campanha_raw(val)
    return v is not None and 0 < v <= 1


def main():
    app = create_app()
    with app.app_context():
        from aicentralv2 import db as dbmod

        campanhas = dbmod.obter_campanhas_pi(None) or []
        afetados_por_pi = {}
        total_camps = 0

        for c in campanhas:
            if any(_perc_em_fracao(c.get(col)) for col in PERC_COLS):
                total_camps += 1
                id_pi = c.get("id_pi")
                if not id_pi:
                    continue
                bucket = afetados_por_pi.setdefault(
                    int(id_pi),
                    {"ids_camp": set(), "codigo_pi": c.get("codigo_pi"), "cliente": c.get("cliente_nome"), "titulo": c.get("titulo_pi")},
                )
                bucket["ids_camp"].add(c.get("id_campanha"))
                if c.get("codigo_pi"):
                    bucket["codigo_pi"] = c.get("codigo_pi")
                if c.get("cliente_nome"):
                    bucket["cliente"] = c.get("cliente_nome")
                if c.get("titulo_pi"):
                    bucket["titulo"] = c.get("titulo_pi")

        items = sorted(
            afetados_por_pi.items(),
            key=lambda x: (str(x[1].get("codigo_pi") or ""), x[0]),
        )

        print(f"PIs com campanha(s) com % em fracao (0<v<=1): {len(items)}\n")
        for id_pi, info in items:
            codigo = info.get("codigo_pi") or id_pi
            titulo = (info.get("titulo") or "")[:70]
            cliente = info.get("cliente") or ""
            qtd = len(info["ids_camp"])
            print(f"  {codigo} | id_pi={id_pi} | {cliente} | {qtd} camp(s) | {titulo}")

        print(f"\nTotal de campanhas ainda com algum % em fracao: {total_camps}")

        ja_reparados = []
        for c in campanhas:
            if not c.get("id_campanha"):
                continue
            vp = dbmod.parse_valor_monetario_para_float(c.get("valor_plataforma"))
            mcc = dbmod.parse_percentual_campanha_raw(c.get("perc_margem_cc"))
            val_m = dbmod.parse_valor_monetario_para_float(c.get("val_margem_cc"))
            if vp > 10000 and mcc and mcc > 1 and val_m and val_m < vp * 0.01:
                ja_reparados.append(c)

        if ja_reparados:
            print(f"\nPossivel subcalculo (VP alto, % ok, val_margem muito baixo): {len(ja_reparados)} campanhas")


if __name__ == "__main__":
    main()