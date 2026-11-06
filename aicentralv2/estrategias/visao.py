"""Monta a estratégia para tela: nomes e logos dos canais, faixas de verba,
fluxo com logos, peças agregadas e imagens (arquivos estáticos por slug)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from . import catalogo

log = logging.getLogger(__name__)

IMAGENS = (
    ("conceito", "Visão da estratégia"),
    ("criativo-topo", "Criativo modelo: descoberta"),
    ("criativo-conversao", "Criativo modelo: conversão"),
    ("apoio", "Momento do público"),
)
_CACHE = {"em": 0.0, "canais": {}}
_TTL = 300


def canais_catalogo() -> dict:
    """slug -> {nome, logo, categoria} dos canais ativos do Planner, mais os extras."""
    if time.monotonic() - _CACHE["em"] < _TTL and _CACHE["canais"]:
        return _CACHE["canais"]
    mapa, ok = {}, False
    try:
        from ..cadu_planner.channels import _channel_logo  # logo curado; o /assets_images gravado não é servido
        from ..db import get_db
        with get_db().cursor() as cur:
            cur.execute("SELECT slug, nome, logo_path, categoria FROM cadu_canais WHERE is_active ORDER BY ordem, nome")
            for r in cur.fetchall():
                logo = _channel_logo(str(r["slug"]).lower(), r.get("logo_path")) or ""
                mapa[r["slug"]] = {"nome": r["nome"], "logo": logo, "categoria": r.get("categoria") or ""}
        ok = True
    except Exception:
        log.exception("estrategias: canais do catálogo indisponíveis")
        _rollback()
    mapa.pop("waze", None)
    for slug, extra in catalogo.CANAIS_EXTRAS.items():
        mapa.setdefault(slug, dict(extra))
    if ok:  # falha não fica em cache: a próxima requisição tenta de novo
        _CACHE.update(em=time.monotonic(), canais=mapa)
    return mapa


def _rollback():
    """Consulta que falhou deixa a transação abortada; desfaz para o resto da requisição seguir."""
    try:
        from ..db import get_db
        get_db().rollback()
    except Exception:
        pass


def slugs_validos() -> set[str]:
    return set(canais_catalogo())


def no(slug: str, canais: dict | None = None) -> dict:
    canais = canais if canais is not None else canais_catalogo()
    if slug in catalogo.NOS_FLUXO:
        n = catalogo.NOS_FLUXO[slug]
        return {"slug": slug, "nome": n["nome"], "logo": n.get("logo", ""), "icone": n["icone"], "tipo": "destino" if slug != "crm" else "dados"}
    c = canais.get(slug) or {}
    return {"slug": slug, "nome": c.get("nome") or slug, "logo": c.get("logo") or "", "icone": "broadcast", "tipo": "canal"}


def _static_root() -> Path:
    return Path(__file__).resolve().parents[1] / "static" / "images" / "estrategias"


def imagens(slug: str) -> list[dict]:
    pasta = _static_root() / slug
    saida = []
    for nome, legenda in IMAGENS:
        arq = pasta / f"{nome}.webp"
        if arq.is_file():
            saida.append({"url": f"/static/images/estrategias/{slug}/{nome}.webp?v={int(arq.stat().st_mtime)}",
                          "legenda": legenda, "tipo": nome})
    return saida


def cartao(e: dict, canais: dict | None = None) -> dict:
    canais = canais if canais is not None else canais_catalogo()
    pagos = [c for c in e.get("canais") or [] if catalogo.recebe_verba(c)]
    imgs = imagens(e["slug"])
    return {"id": e["id"], "slug": e["slug"], "nome": e["nome"], "resumo": e.get("resumo") or "",
            "objetivo": catalogo.OBJETIVOS.get(e.get("objetivo"), ""), "objetivo_id": e.get("objetivo"),
            "verba_minima": e["verba_minima"], "verba_rotulo": "A partir de " + catalogo.brl_curto(e["verba_minima"]),
            "canais": [no(c["slug"], canais) for c in pagos],
            "remarketing": bool((e.get("remarketing") or {}).get("usa")),
            "lista_clientes": bool((e.get("lista_clientes") or {}).get("usa")),
            "precisa_link": bool((e.get("conversao") or {}).get("precisa_link")),
            "imagem": imgs[0]["url"] if imgs else ""}


def _e(nomes: list[str]) -> str:
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]


def escala_texto(lista_canais: list[dict], verba_minima: int, canais: dict | None = None) -> str:
    """Frase com o que entra em cada faixa, tirada do próprio cálculo de divisão."""
    entra = catalogo.entra_a_partir(lista_canais, verba_minima)
    if not entra:
        return ""
    por_faixa = {}
    for slug, faixa in entra.items():
        por_faixa.setdefault(faixa, []).append(no(slug, canais)["nome"])
    faixas = sorted(por_faixa)
    partes = [f"Com {catalogo.brl_curto(faixas[0])}: {_e(por_faixa[faixas[0]])}."]
    for f in faixas[1:]:
        partes.append(f"A partir de {catalogo.brl_curto(f)} entra{'m' if len(por_faixa[f]) > 1 else ''} {_e(por_faixa[f])}.")
    fora = [c for c in lista_canais if catalogo.recebe_verba(c) and c["slug"] not in entra]
    if fora:
        partes.append(f"{_e([no(c['slug'], canais)['nome'] for c in fora])} só com verba acima de {catalogo.brl_curto(catalogo.FAIXAS[-1])}.")
    return " ".join(partes)


def completa(e: dict) -> dict:
    """Tudo o que a ficha mostra."""
    canais = canais_catalogo()
    base = cartao(e, canais)
    lista_canais = e.get("canais") or []
    tabela = catalogo.tabela_faixas(lista_canais, e["verba_minima"])
    for f in tabela:
        f["rotulo"] = catalogo.brl_curto(f["verba"])
        f["verba_txt"] = catalogo.brl(f["verba"])
        for l in f["linhas"]:
            l.update(no(l["slug"], canais))
            l["valor_txt"] = catalogo.brl(l["valor"])
        f["fora_nomes"] = [no(s, canais)["nome"] for s in f["fora"]]
    entra = catalogo.entra_a_partir(lista_canais, e["verba_minima"])
    detalhes = []
    for c in lista_canais:
        if not catalogo.recebe_verba(c):
            continue
        d = no(c["slug"], canais)
        d.update({"papel": c.get("papel"), "formatos": c.get("formatos") or [], "otimizacoes": c.get("otimizacoes") or [],
                  "essencial": c.get("essencial"), "nota": c.get("nota") or "",
                  "entra": catalogo.brl_curto(entra[c["slug"]]) if c["slug"] in entra else ""})
        detalhes.append(d)
    fluxo = [{"titulo": et["titulo"], "descricao": et.get("descricao") or "", "nos": [no(s, canais) for s in et.get("nos") or []]}
             for et in e.get("fluxo") or []]
    criativos = [{**p, "nos": [no(s, canais) for s in p.get("canais") or []]} for p in e.get("criativos") or []]
    kpis = e.get("kpis") or []
    conv = dict(e.get("conversao") or {})
    conv["destino_nome"] = catalogo.DESTINOS.get(conv.get("destino"), "")
    inicial = catalogo.faixa_inicial(e["verba_minima"])
    base.update({"escala": escala_texto(lista_canais, e["verba_minima"], canais)})
    base.update({
        "descricao": e.get("descricao") or "", "duracao": e.get("duracao") or "", "publico": e.get("publico") or "",
        "como_escala": e.get("como_escala") or "", "faixas": tabela, "faixa_inicial": inicial,
        "canais_detalhe": detalhes, "fluxo": fluxo, "criativos": criativos,
        "total_pecas": sum(int(p.get("quantidade") or 1) for p in criativos),
        "kpis_principais": [k for k in kpis if k.get("principal")], "kpis_apoio": [k for k in kpis if not k.get("principal")],
        "conversao": conv, "remarketing_info": e.get("remarketing") or {}, "lista_info": e.get("lista_clientes") or {},
        "otimizacoes": e.get("otimizacoes") or [], "imagens": imagens(e["slug"]),
        "efeitos": e.get("efeitos") or [], "pracas_seletor": pracas_seletor(),
    })
    return base


def simulacao(e: dict, verba: int, ids_pracas: list[str]) -> dict:
    """Divisão da verba e estimativa de resultado para a verba e as praças escolhidas."""
    from . import estimativa
    canais = canais_catalogo()
    nomes = {s: no(s, canais)["nome"] for s in [c["slug"] for c in e.get("canais") or []]}
    sim = estimativa.simular(e, verba, ids_pracas, nomes=nomes)
    papeis = {c["slug"]: c.get("papel") for c in e.get("canais") or []}
    for l in sim["linhas"]:
        l.update(no(l["slug"], canais))
        l["papel"] = papeis.get(l["slug"], "")
        l["valor_txt"] = catalogo.brl(l["valor"])
        l["pct"] = round(100 * l["valor"] / verba, 1) if verba else 0
    sim.pop("_numeros", None)
    inicial = catalogo.faixa_inicial(e["verba_minima"])
    sim.update({"id": e["id"], "faixas": [{"verba": f, "rotulo": catalogo.brl_curto(f), "disponivel": f >= inicial}
                                         for f in catalogo.FAIXAS],
                "ids_txt": ",".join(sim["praca"]["ids"]) if not sim["praca"]["nacional"] else ""})
    return sim


def pracas_seletor() -> dict:
    """Lista enxuta para o seletor de praças da ficha (vai como JSON na página)."""
    from . import pracas
    return {"itens": [{"id": i["id"], "nome": i["nome"], "pop": i["pop"], "tipo": i["tipo"]} for i in pracas.lista()],
            "presets": [{"chave": k, "rotulo": r, "ids": pracas.preset(k)} for k, r in pracas.PRESETS],
            "fonte": pracas.base()["fonte"]}
