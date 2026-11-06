"""Descobrir: as vitrines do Cadu Planner dentro da Área do Cliente.

Lê o mesmo catálogo do Planner (canais, formatos, interativos, audiências e
portais). Places e Radar ficam de fora: Radar é do Cadu (marca e projeto).
Regra da área: nada de preço, investimento mínimo, CPA ou valor de mercado.
O cliente pode separar itens para mandar junto com o briefing.
"""

from __future__ import annotations

import time

from werkzeug.exceptions import NotFound

SECOES = {
    "canais": ("Canais", "broadcast", "Onde a mídia roda: apps, plataformas, TV, áudio e OOH, com alcance e uso indicado."),
    "formatos": ("Formatos", "layout", "Os formatos de anúncio de cada plataforma, com objetivo e especificações."),
    "interativos": ("Formatos interativos", "sparkles", "Formatos com interação: jogos, carrosséis, quizzes e experiências ricas."),
    "audiencias": ("Audiências", "users", "Públicos prontos por interesse, perfil e comportamento, com tamanho estimado."),
    "portais": ("Portais", "globe", "Sites de notícia e conteúdo por categoria e região, com tráfego e formatos aceitos."),
}
TIPO_ROTULO = {"canais": "Canal", "formatos": "Formato", "interativos": "Formato interativo",
               "audiencias": "Audiência", "portais": "Portal"}
POR_PAGINA = 24
LIMITE_SELECAO = 20  # a seleção fica no cookie de sessão (limite de ~4 KB)
NOME_MAX = 60
_CACHE_RESUMO = {"em": 0.0, "dados": None}


def _repo():
    from ..cadu_family import repository
    return repository


def _texto(valor, limite=400):
    texto = " ".join(str(valor or "").split())
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def _cartao(secao, r) -> dict:
    """Formato único de cartão para as cinco vitrines."""
    if secao == "canais":
        meta = [r.get("category")] + ([f"{r['reach_figure']} {r.get('reach_unit') or ''}".strip()] if r.get("reach_figure") else [])
        return {"id": r["id"], "nome": r.get("name"), "descricao": _texto(r.get("description"), 180),
                "imagem": r.get("image_url") or "", "logo": r.get("logo_path") or "", "meta": [m for m in meta if m]}
    if secao in ("formatos", "interativos"):
        meta = [r.get("platform"), r.get("purpose"), r.get("dimensions")]
        return {"id": r["id"], "nome": r.get("name"), "descricao": _texto(r.get("description"), 180),
                "imagem": r.get("image_url") or "", "logo": r.get("platform_logo") or "", "meta": [m for m in meta if m]}
    if secao == "audiencias":
        meta = [r.get("platform"), r.get("category"), r.get("audience")]
        return {"id": r["id"], "nome": r.get("name"), "descricao": _texto(r.get("description"), 180),
                "imagem": r.get("image_url") or "", "logo": r.get("platform_logo") or "", "meta": [m for m in meta if m]}
    meta = [r.get("category"), r.get("domain"), r.get("uf")]
    return {"id": r["id"], "nome": r.get("name") or r.get("domain"), "descricao": _texto(r.get("description"), 180),
            "imagem": r.get("thumb_url") or "", "logo": r.get("favicon_url") or "", "meta": [m for m in meta if m]}


def listar(secao: str, busca: str = "", categoria: str = "", pagina: int = 1) -> dict:
    """Uma página da vitrine: cartões, categorias para filtro e paginação."""
    if secao not in SECOES:
        raise NotFound()
    busca, categoria = (busca or "").strip()[:80], (categoria or "").strip()[:100]
    pagina = max(1, int(pagina or 1))
    offset = (pagina - 1) * POR_PAGINA
    repo = _repo()
    if secao == "audiencias":
        dados = repo.audience_search(query=busca, category=categoria, limit=POR_PAGINA, offset=offset)
        registros, total = dados["records"], int(dados["total"])
        categorias = [f["value"] for f in (dados.get("facets") or {}).get("categories") or [] if f.get("value")]
    elif secao == "portais":
        from ..cadu_planner import portals
        dados = portals.catalog(busca, category=categoria, limit=POR_PAGINA, offset=offset)
        registros, total = dados["records"], int(dados["total"])
        categorias = sorted({r["category"] for r in repo.rows(
            "SELECT DISTINCT category FROM cadu_planner_portals WHERE active = TRUE AND category IS NOT NULL") if r["category"]})
    else:
        # Canais filtram por categoria; formatos e interativos, por plataforma.
        campo = "category" if secao == "canais" else "platform"
        todos = repo.catalog(secao, busca)
        categorias = sorted({str(r.get(campo) or "") for r in (repo.catalog(secao, "") if busca else todos)} - {""})
        if categoria:
            todos = [r for r in todos if r.get(campo) == categoria]
        if secao == "canais":
            from ..cadu_planner.channels import decorate_logos
            decorate_logos(todos)
        total = len(todos)
        registros = todos[offset: offset + POR_PAGINA]
    paginas = max(1, -(-total // POR_PAGINA))
    if pagina > paginas and total:
        return listar(secao, busca, categoria, paginas)
    return {
        "cartoes": [_cartao(secao, r) for r in registros],
        "total": total, "pagina": min(pagina, paginas), "paginas": paginas,
        "categorias": categorias[:60], "busca": busca, "categoria": categoria,
    }


def resumo_secoes() -> list[dict]:
    """Contagem por vitrine para a página inicial do Descobrir (cache de 10 minutos)."""
    if _CACHE_RESUMO["dados"] is not None and time.time() - _CACHE_RESUMO["em"] < 600:
        return _CACHE_RESUMO["dados"]
    saida = []
    for secao, (titulo, icone, texto) in SECOES.items():
        try:
            total = listar(secao)["total"]
        except Exception:
            total = None
        saida.append({"id": secao, "titulo": titulo, "icone": icone, "texto": texto, "total": total})
    if all(s["total"] is not None for s in saida):
        _CACHE_RESUMO.update(em=time.time(), dados=saida)
    return saida


def detalhe(secao: str, item_id) -> dict:
    """Ficha completa do item, na organização do Planner e sem custos (ver ficha.py)."""
    if secao not in SECOES:
        raise NotFound()
    from .ficha import montar
    return montar(secao, item_id)


# ---------- Seleção para o briefing (fica na sessão) ----------

def selecao(sess) -> list[dict]:
    """Itens separados, guardados compactos na sessão como [secao, id, nome]."""
    saida = []
    for i in sess.get("area_cliente_descobrir") or []:
        if isinstance(i, (list, tuple)) and len(i) == 3 and i[0] in SECOES:
            saida.append({"secao": i[0], "id": int(i[1]), "nome": i[2], "tipo": TIPO_ROTULO[i[0]]})
    return saida[:LIMITE_SELECAO]


def alternar(sess, secao: str, item_id, nome: str) -> bool:
    """Inclui ou tira um item da seleção. Devolve True se ficou incluído."""
    if secao not in SECOES:
        raise NotFound()
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        raise NotFound()
    itens = selecao(sess)
    chave = (secao, item_id)
    restantes = [i for i in itens if (i["secao"], i["id"]) != chave]
    incluido = len(restantes) == len(itens)
    if incluido:
        if len(restantes) >= LIMITE_SELECAO:
            return False
        restantes.append({"secao": secao, "id": item_id, "nome": _texto(nome, NOME_MAX) or TIPO_ROTULO[secao]})
    sess["area_cliente_descobrir"] = [[i["secao"], i["id"], i["nome"]] for i in restantes]
    return incluido


def selecionados(sess) -> set:
    return {(i["secao"], i["id"]) for i in selecao(sess)}


def texto_selecao(itens) -> str:
    if not itens:
        return ""
    return "Itens escolhidos no Descobrir:\n" + "\n".join(f"- {i['tipo']}: {i['nome']}" for i in itens)
