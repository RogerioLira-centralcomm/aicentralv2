"""Praças para a simulação: Brasil, estados, capitais e cidades do interior com 200 mil+ habitantes.

População do IBGE (Censo 2022, tabela 4709), gravada em pracas_ibge2022.json.
Ids: "BR" (Brasil), "UF-SP" (estado inteiro), código IBGE de 7 dígitos (cidade).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ARQUIVO = Path(__file__).with_name("pracas_ibge2022.json")
MAX_PRACAS = 60

# Custo de mídia relativo à média nacional: capital disputa mais leilão, interior menos.
FATOR_CUSTO = {"capital": 1.15, "interior": 0.92, "estado": 1.0, "brasil": 1.0}

PRESETS = (
    ("brasil", "Brasil inteiro"),
    ("capitais", "Todas as capitais"),
    ("capitais-sudeste", "Capitais do Sudeste"),
    ("capitais-nordeste", "Capitais do Nordeste"),
    ("capitais-sul", "Capitais do Sul"),
    ("interior-sp", "Interior de SP"),
)


@lru_cache(maxsize=1)
def base() -> dict:
    dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    itens = {"BR": {"id": "BR", "nome": "Brasil", "uf": "", "regiao": "", "pop": dados["brasil"], "tipo": "brasil"}}
    for e in dados["estados"]:
        itens[f"UF-{e['uf']}"] = {"id": f"UF-{e['uf']}", "nome": f"{e['nome']} (estado)", "uf": e["uf"], "regiao": e["regiao"],
                                  "pop": e["pop"], "tipo": "estado"}
    for c in dados["cidades"]:
        itens[c["id"]] = {"id": c["id"], "nome": f"{c['nome']} - {c['uf']}", "uf": c["uf"], "regiao": c["regiao"],
                          "pop": c["pop"], "tipo": "capital" if c["capital"] else "interior"}
    return {"fonte": dados["fonte"], "brasil": dados["brasil"], "itens": itens}


def lista() -> list[dict]:
    """Para o seletor: Brasil, capitais, interior e estados, maiores primeiro dentro de cada grupo."""
    ordem = {"brasil": 0, "capital": 1, "interior": 2, "estado": 3}
    return sorted(base()["itens"].values(), key=lambda i: (ordem[i["tipo"]], -i["pop"]))


def preset(chave: str) -> list[str]:
    itens = base()["itens"].values()
    regiao = {"capitais-sudeste": "Sudeste", "capitais-nordeste": "Nordeste", "capitais-sul": "Sul"}
    if chave == "brasil":
        return ["BR"]
    if chave == "capitais":
        return [i["id"] for i in itens if i["tipo"] == "capital"]
    if chave in regiao:
        return [i["id"] for i in itens if i["tipo"] == "capital" and i["regiao"] == regiao[chave]]
    if chave == "interior-sp":
        return [i["id"] for i in itens if i["tipo"] == "interior" and i["uf"] == "SP"]
    return []


def resolver(ids) -> dict:
    """Praças escolhidas, sem contar duas vezes: Brasil engole tudo; estado engole as cidades dele.

    Sem praça escolhida vale Brasil. Devolve itens, população total, % do Brasil,
    fator de custo ponderado pela população e um resumo para o briefing.
    """
    itens = base()["itens"]
    vistos, escolhidos = set(), []
    for i in ids or []:
        i = str(i).strip()
        if i in itens and i not in vistos:
            vistos.add(i)
            escolhidos.append(itens[i])
    escolhidos = escolhidos[:MAX_PRACAS]
    if not escolhidos or any(e["tipo"] == "brasil" for e in escolhidos):
        escolhidos = [itens["BR"]]
    else:
        ufs = {e["uf"] for e in escolhidos if e["tipo"] == "estado"}
        escolhidos = [e for e in escolhidos if e["tipo"] == "estado" or e["uf"] not in ufs]
    pop = sum(e["pop"] for e in escolhidos)
    fator = sum(e["pop"] * FATOR_CUSTO[e["tipo"]] for e in escolhidos) / pop if pop else 1.0
    nomes = [e["nome"] for e in escolhidos]
    resumo = nomes[0] if len(nomes) == 1 else (", ".join(nomes[:3]) + (f" e mais {len(nomes) - 3}" if len(nomes) > 3 else ""))
    return {"itens": escolhidos, "ids": [e["id"] for e in escolhidos], "pop": pop,
            "pct_brasil": round(100 * pop / base()["brasil"], 1), "fator_custo": round(fator, 3),
            "capitais": sum(e["tipo"] == "capital" for e in escolhidos),
            "interior": sum(e["tipo"] == "interior" for e in escolhidos), "resumo": resumo,
            "nacional": escolhidos[0]["tipo"] == "brasil"}


def pessoas(n: int) -> str:
    """11,5 milhões / 698 mil / 203,1 milhões."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".replace(".", ",") + (" milhão" if n < 2_000_000 else " milhões")
    if n >= 1_000:
        return f"{round(n / 1_000):,}".replace(",", ".") + " mil"
    return str(n)
