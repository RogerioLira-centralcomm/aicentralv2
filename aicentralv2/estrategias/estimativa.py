"""Estimativa de resultado de uma estratégia para uma verba e um conjunto de praças.

Sempre em faixa (mínimo e máximo), a partir de benchmarks de mercado por canal
(CPM ou CPC e CTR) e de taxas de conversão por destino. Os benchmarks são
editáveis no admin (tabela cadu_estrategias_parametros); sem a tabela valem os
padrões daqui. A população das praças limita o alcance: verba alta em praça
pequena vira frequência, não alcance.
"""

from __future__ import annotations

import logging
import time
from copy import deepcopy

from . import catalogo, pracas

log = logging.getLogger(__name__)

# modelo, custo (R$ por mil impressões ou por clique) mín e máx, CTR mín e máx (fração).
BENCHMARKS = {
    "google-search": ("cpc", 1.5, 4.5, 0.04, 0.08),
    "google-pmax": ("cpc", 0.8, 2.5, 0.01, 0.02),
    "google-demand-gen": ("cpm", 8, 18, 0.006, 0.012),
    "google-app": ("cpc", 0.6, 1.8, 0.01, 0.025),
    "meta-ads": ("cpm", 10, 25, 0.008, 0.016),
    "youtube": ("cpm", 12, 30, 0.003, 0.007),
    "tiktok": ("cpm", 8, 20, 0.006, 0.012),
    "kwai": ("cpm", 4, 10, 0.008, 0.015),
    "linkedin": ("cpm", 90, 180, 0.004, 0.008),
    "twitch": ("cpm", 25, 50, 0.002, 0.005),
    "spotify": ("cpm", 25, 45, 0.002, 0.005),
    "deezer": ("cpm", 20, 40, 0.002, 0.004),
    "amazon-music": ("cpm", 25, 45, 0.002, 0.004),
    "podcast-ads": ("cpm", 40, 80, 0.001, 0.003),
    "netflix": ("cpm", 90, 140, 0.0005, 0.0015),
    "globoplay": ("cpm", 60, 110, 0.0005, 0.0015),
    "prime-video": ("cpm", 60, 110, 0.0005, 0.0015),
    "disney-plus": ("cpm", 60, 110, 0.0005, 0.0015),
    "hbo-max": ("cpm", 60, 110, 0.0005, 0.0015),
    "paramount-plus": ("cpm", 50, 90, 0.0005, 0.0015),
    "samsung-tv-plus": ("cpm", 35, 60, 0.0005, 0.0015),
    "eletromidia": ("cpm", 15, 35, 0.0, 0.0),
    "uber": ("cpm", 40, 80, 0.003, 0.008),
    "99": ("cpm", 20, 40, 0.003, 0.008),
    "ifood": ("cpm", 25, 50, 0.008, 0.02),
    "g1-globo": ("cpm", 25, 50, 0.0015, 0.004),
    "uol": ("cpm", 12, 30, 0.0015, 0.004),
    "r7": ("cpm", 12, 28, 0.0015, 0.004),
    "sbt": ("cpm", 12, 30, 0.0015, 0.004),
    "cnn-brasil": ("cpm", 25, 45, 0.0015, 0.004),
    "infomoney": ("cpm", 30, 60, 0.002, 0.005),
    "ge-globo-esporte": ("cpm", 20, 40, 0.0015, 0.004),
    "tudogostoso": ("cpm", 20, 40, 0.002, 0.005),
    "techtudo": ("cpm", 20, 40, 0.002, 0.005),
    "experian-portal": ("cpm", 20, 40, 0.002, 0.005),
    "google-dv360": ("cpm", 8, 20, 0.001, 0.003),
    "logan": ("cpm", 12, 25, 0.002, 0.005),
    "experian-dmp": ("cpm", 10, 20, 0.0015, 0.003),
    "amazon-ads": ("cpc", 1.0, 3.0, 0.004, 0.008),
    "interativos": ("cpm", 30, 60, 0.01, 0.03),
}
PADRAO_CANAL_SEM_BENCH = ("cpm", 15, 35, 0.002, 0.006)

# Destino: (nome do resultado, taxa mín e máx sobre os cliques que contam).
CONVERSAO = {
    "formulario": ("leads", 0.07, 0.14),
    "landing": ("leads", 0.02, 0.06),
    "whatsapp": ("conversas iniciadas", 0.12, 0.25),
    "site": ("conversões no site", 0.02, 0.05),
    "site-vendas": ("vendas", 0.008, 0.02),
    "site-visitas": ("visitas ao site", 0.55, 0.8),
    "app": ("instalações", 0.15, 0.35),
    "loja": ("visitas à loja", 0.03, 0.08),
    "marketplace": ("pedidos", 0.03, 0.08),
}
# Clique de canal de topo ajuda, mas converte menos que o de busca e remarketing.
PESO_CLIQUE = {"Conversão": 1.0, "Remarketing": 1.0, "Consideração": 0.5, "Alcance": 0.3, "Dados": 0.3}
FREQUENCIA = (2.5, 4.5)       # impressões por pessoa no período
ALCANCAVEL = 0.75             # parte da população com acesso a mídia digital
TETO_COBERTURA = 0.6          # alcance máximo realista sobre os alcançáveis
# Os extremos dos benchmarks somados viram faixas largas demais; a faixa mostrada usa os percentis 30 e 70.
QUANTIS = (0.3, 0.7)
FREQ_ALERTA = 6               # acima disso a mesma pessoa vê demais e o anúncio cansa

_CACHE = {"em": 0.0, "valor": None}


def parametros() -> dict:
    """Benchmarks e conversões: padrões daqui com o que o admin gravou por cima."""
    if _CACHE["valor"] is not None and time.monotonic() - _CACHE["em"] < 60:
        return _CACHE["valor"]
    bench = {k: list(v) for k, v in BENCHMARKS.items()}
    conv = {k: list(v) for k, v in CONVERSAO.items()}
    try:
        from ..db import get_db
        with get_db().cursor() as cur:
            cur.execute("SELECT to_regclass('public.cadu_estrategias_parametros') AS t")
            r = cur.fetchone()
            if r and r["t"]:
                cur.execute("SELECT chave, valor FROM cadu_estrategias_parametros WHERE chave IN ('benchmarks', 'conversao')")
                for linha in cur.fetchall():
                    alvo = bench if linha["chave"] == "benchmarks" else conv
                    for k, v in (linha["valor"] or {}).items():
                        if isinstance(v, list) and len(v) == len(alvo.get(k, v)):
                            alvo[k] = v
    except Exception:
        log.exception("estrategias: parâmetros de estimativa indisponíveis; usando padrões")
    valor = {"benchmarks": bench, "conversao": conv}
    _CACHE.update(em=time.monotonic(), valor=valor)
    return valor


def limpar_cache():
    _CACHE.update(em=0.0, valor=None)


def _chave_conversao(e: dict) -> str:
    destino = (e.get("conversao") or {}).get("destino") or "site"
    if destino == "site":
        if e.get("objetivo") in ("vendas-online", "retencao"):
            return "site-vendas"
        if e.get("objetivo") in ("reconhecimento", "lancamento"):
            return "site-visitas"
    return destino


def _redondo(n: float) -> int:
    """Dois algarismos significativos: 1.234.567 -> 1.200.000."""
    n = int(round(n))
    if n < 100:
        return n
    casas = len(str(n)) - 2
    return int(round(n / 10 ** casas) * 10 ** casas)


def numero(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".replace(".", ",").replace(",0", "") + " mi"
    if n >= 10_000:
        return f"{round(n / 1_000):,}".replace(",", ".") + " mil"
    return f"{n:,}".replace(",", ".")


def faixa_txt(a: int, b: int) -> str:
    a, b = _redondo(a), _redondo(b)
    return numero(a) if a == b else f"{numero(a)} a {numero(b)}"


def _q(lo, hi, k):
    """Ponto entre o pior e o melhor caso. k=0 pior (custo alto, taxa baixa)."""
    return lo + (hi - lo) * QUANTIS[k]


def simular(e: dict, verba: int, ids_pracas=None, params: dict | None = None, nomes: dict | None = None) -> dict:
    params = params or parametros()
    praca = pracas.resolver(ids_pracas)
    f = praca["fator_custo"]
    d = catalogo.divisao(e.get("canais") or [], int(verba))
    papeis = {c["slug"]: c.get("papel") for c in e.get("canais") or []}
    linhas = []
    imp = [0.0, 0.0]
    cli = [0.0, 0.0]
    cli_conv = [0.0, 0.0]
    for l in d["linhas"]:
        modelo, cmin, cmax, tmin, tmax = params["benchmarks"].get(l["slug"], PADRAO_CANAL_SEM_BENCH)
        v = l["valor"]
        custo_ = [_q(cmax, cmin, 0), _q(cmax, cmin, 1)]  # pior caso = custo mais alto
        ctr = [_q(tmin, tmax, 0), _q(tmin, tmax, 1)]
        if modelo == "cpc":
            c = [v / (custo_[0] * f), v / (custo_[1] * f)]
            i = [c[0] / ctr[1] if ctr[1] else 0, c[1] / ctr[0] if ctr[0] else 0]
        else:
            i = [v / (custo_[0] * f) * 1000, v / (custo_[1] * f) * 1000]
            c = [i[0] * ctr[0], i[1] * ctr[1]]
        peso = PESO_CLIQUE.get(papeis.get(l["slug"]), 0.5)
        for k in (0, 1):
            imp[k] += i[k]
            cli[k] += c[k]
            cli_conv[k] += c[k] * peso
        linhas.append({"slug": l["slug"], "valor": v, "impressoes": faixa_txt(*i), "cliques": faixa_txt(*c) if c[1] >= 1 else "—"})

    alcancaveis = praca["pop"] * ALCANCAVEL
    teto = alcancaveis * TETO_COBERTURA
    alc = [imp[0] / FREQUENCIA[1], imp[1] / FREQUENCIA[0]]
    saturado = alc[1] > teto
    if saturado:
        alc = [min(alc[0], teto * 0.8), teto]
    freq = sorted([imp[0] / alc[0] if alc[0] else 0, imp[1] / alc[1] if alc[1] else 0])
    saturado = saturado and freq[1] >= FREQ_ALERTA
    nome_res, rmin, rmax = params["conversao"].get(_chave_conversao(e), CONVERSAO["site"])
    res = [cli_conv[0] * _q(rmin, rmax, 0), cli_conv[1] * _q(rmin, rmax, 1)]
    custo = [verba / res[1] if res[1] >= 1 else 0, verba / res[0] if res[0] >= 1 else 0]

    avisos = []
    if saturado:
        avisos.append(f"A verba é alta para o tamanho das praças: o alcance chega perto do teto e a frequência sobe "
                      f"para cerca de {freq[0]:.0f} a {freq[1]:.0f} vezes por pessoa no período. Vale incluir mais praças ou reduzir a verba.")
    if verba < catalogo.faixa_inicial(e.get("verba_minima") or 0):
        avisos.append("Verba abaixo da mínima desta estratégia.")
    if d["fora"]:
        avisos.append(f"Nesta verba ficam de fora: {', '.join((nomes or {}).get(s, s) for s in d['fora'])}.")
    pct_alcance = [100 * a / alcancaveis if alcancaveis else 0 for a in alc]
    return {
        "verba": int(verba), "verba_txt": catalogo.brl(verba), "praca": praca, "pop_txt": pracas.pessoas(praca["pop"]),
        "impressoes": faixa_txt(*imp), "alcance": faixa_txt(*alc), "cliques": faixa_txt(*cli),
        "alcance_pct": ("menos de 1%" if pct_alcance[1] < 1 else f"{max(pct_alcance[0], 1):.0f}% a {pct_alcance[1]:.0f}%"),
        "frequencia": f"{freq[0]:.1f} a {freq[1]:.1f}".replace(".", ","),
        "resultado_nome": nome_res, "resultado": faixa_txt(*res) if res[1] >= 1 else "—",
        "custo_resultado": (f"{catalogo.brl(custo[0])} a {catalogo.brl(custo[1])}" if custo[0] and custo[1] else ""),
        "linhas": linhas, "avisos": avisos, "saturado": saturado,
        "_numeros": {"imp": imp, "alc": alc, "cli": cli, "res": res},
    }


def padroes() -> dict:
    return {"benchmarks": deepcopy({k: list(v) for k, v in BENCHMARKS.items()}),
            "conversao": deepcopy({k: list(v) for k, v in CONVERSAO.items()})}


ROTULO_CONVERSAO = {
    "formulario": "Formulário nativo", "landing": "Landing page", "whatsapp": "WhatsApp",
    "site": "Site (geral)", "site-vendas": "Site com vendas (e-commerce)", "site-visitas": "Site (só visitas)",
    "app": "App", "loja": "Loja física", "marketplace": "Marketplace",
}


def validar_parametros(bruto: dict) -> dict:
    """Confere o que veio do admin. Levanta ValueError com a mensagem para a tela."""
    bruto = bruto if isinstance(bruto, dict) else {}
    bench = {}
    for slug, v in (bruto.get("benchmarks") or {}).items():
        if slug not in BENCHMARKS or not isinstance(v, list) or len(v) != 5:
            raise ValueError(f"Benchmark inválido: {slug}.")
        modelo = v[0]
        if modelo not in ("cpm", "cpc"):
            raise ValueError(f"{slug}: modelo precisa ser CPM ou CPC.")
        try:
            cmin, cmax, tmin, tmax = (float(x) for x in v[1:])
        except (TypeError, ValueError):
            raise ValueError(f"{slug}: use números.")
        if not (0 < cmin <= cmax <= 5000):
            raise ValueError(f"{slug}: custo mínimo precisa ser maior que zero e até o máximo.")
        if not (0 <= tmin <= tmax <= 1):
            raise ValueError(f"{slug}: CTR entre 0% e 100%, mínimo até o máximo.")
        bench[slug] = [modelo, cmin, cmax, tmin, tmax]
    conv = {}
    for chave, v in (bruto.get("conversao") or {}).items():
        if chave not in CONVERSAO or not isinstance(v, list) or len(v) != 3:
            raise ValueError(f"Conversão inválida: {chave}.")
        nome = " ".join(str(v[0] or "").split())[:40]
        try:
            rmin, rmax = float(v[1]), float(v[2])
        except (TypeError, ValueError):
            raise ValueError(f"{chave}: use números.")
        if not nome or not (0 < rmin <= rmax <= 1):
            raise ValueError(f"{chave}: nome e taxa entre 0% e 100%, mínimo até o máximo.")
        conv[chave] = [nome, rmin, rmax]
    return {"benchmarks": bench, "conversao": conv}
