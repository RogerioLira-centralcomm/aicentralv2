"""Descobrir: as vitrines do Cadu Planner dentro da Área do Cliente.

Lê o mesmo catálogo do Planner (canais, formatos, interativos, audiências e
portais). Places e Radar ficam de fora: Radar é do Cadu (marca e projeto).
Regra da área: nada de preço, investimento mínimo, CPA ou valor de mercado.
O cliente pode separar itens para mandar junto com o briefing.
"""

from __future__ import annotations

from werkzeug.exceptions import BadRequest, NotFound

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
LIMITE_SELECAO = 30

# Fatias de audiência que não aparecem para o cliente (custos e preços).
_AUDIENCIA_GRUPOS_FORA = {"Indicadores estimados"}
_AUDIENCIA_VARIAVEIS_FORA = {"cpa_estimado_min", "cpa_estimado_max", "tamanho_mercado_brl"}


def _repo():
    from ..cadu_family import repository
    return repository


def _texto(valor, limite=400):
    texto = " ".join(str(valor or "").split())
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def _pct(valor):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return f"{numero:.0f}%" if numero > 1 else f"{numero * 100:.0f}%"


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
    return {
        "cartoes": [_cartao(secao, r) for r in registros],
        "total": total, "pagina": min(pagina, paginas), "paginas": paginas,
        "categorias": categorias[:60], "busca": busca, "categoria": categoria,
    }


def resumo_secoes() -> list[dict]:
    """Contagem por vitrine para a página inicial do Descobrir."""
    saida = []
    for secao, (titulo, icone, texto) in SECOES.items():
        try:
            total = listar(secao)["total"]
        except Exception:
            total = None
        saida.append({"id": secao, "titulo": titulo, "icone": icone, "texto": texto, "total": total})
    return saida


def _fatos(pares):
    return [{"rotulo": r, "valor": _texto(v, 300)} for r, v in pares if v not in (None, "", [], {})]


def detalhe(secao: str, item_id) -> dict:
    """Página de um item, só com campos que o cliente pode ver."""
    if secao not in SECOES:
        raise NotFound()
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        raise NotFound()
    from ..cadu_planner import catalog
    try:
        if secao == "canais":
            from ..cadu_planner import channels
            c = channels.detail(item_id)
            listas = c.get("diferenciais") if isinstance(c.get("diferenciais"), list) else []
            return {"id": item_id, "nome": c.get("name"), "descricao": c.get("descricao") or "",
                    "imagem": c.get("hero_image_url") or "", "logo": c.get("logo_url") or "",
                    "subtitulo": c.get("categoria") or "",
                    "fatos": _fatos([("Alcance", c.get("alcance")), ("Usuários únicos", c.get("usuarios_unicos")),
                                     ("Tempo médio", c.get("tempo_medio")), ("Viewability", _pct(c.get("viewability"))),
                                     ("Taxa de conclusão", _pct(c.get("completion_rate"))), ("Melhor uso", c.get("melhor_uso"))]),
                    "grupos": [{"titulo": "Diferenciais", "itens": [{"rotulo": "", "valor": _texto(d, 200)} for d in listas[:8]]}] if listas else []}
        if secao in ("formatos", "interativos"):
            f = catalog.detail(secao, item_id)
            return {"id": item_id, "nome": f.get("name"), "descricao": f.get("description") or "",
                    "imagem": f.get("image_url") or "", "logo": "", "subtitulo": f.get("purpose") or "",
                    "fatos": _fatos([("Plataforma", f.get("plataforma_slug", "").replace("_", " ").title() if f.get("plataforma_slug") else None),
                                     ("Objetivo", f.get("purpose")), ("Tipo", f.get("format_type")),
                                     ("Dimensões", f.get("dimensions")), ("Arquivos", f.get("files"))]),
                    "grupos": []}
        if secao == "audiencias":
            a = catalog.client_detail("audiencias", item_id)
            grupos, vistos = [], {_texto(a.get("description"), 80)}
            for g in a.get("data_groups") or []:
                if g.get("title") in _AUDIENCIA_GRUPOS_FORA:
                    continue
                itens = []
                for f in g.get("fields") or []:
                    rotulo = str(f.get("label") or "")
                    if (f.get("variable") in _AUDIENCIA_VARIAVEIS_FORA or f.get("variable") in ("descricao", "descricao_curta")
                            or " IA" in f" {rotulo}" or "storytelling" in rotulo.lower()):
                        continue
                    chave = _texto(f.get("value"), 80)  # textos longos repetidos em vários campos aparecem uma vez
                    if len(chave) >= 40:
                        if chave in vistos:
                            continue
                        vistos.add(chave)
                    itens.append({"rotulo": rotulo, "valor": _texto(f.get("value"), 300)})
                if itens:
                    grupos.append({"titulo": g.get("title"), "itens": itens[:12]})
            return {"id": item_id, "nome": a.get("name"), "descricao": a.get("description") or "",
                    "imagem": a.get("image_url") or "", "logo": "", "subtitulo": " · ".join(x for x in (a.get("channel"), a.get("category")) if x),
                    "fatos": _fatos([("Público estimado", a.get("audience")), ("Subcategoria", a.get("subcategory"))]),
                    "grupos": grupos}
        from ..cadu_planner import portals
        encontrados = portals.records([item_id])
        if not encontrados:
            raise NotFound()
        p = encontrados[0]
        formatos = [str(f.get("format")) for f in p.get("ad_formats") or [] if isinstance(f, dict) and f.get("format")]
        return {"id": item_id, "nome": p.get("name") or p.get("domain"), "descricao": p.get("description") or "",
                "imagem": "", "logo": p.get("favicon_url") or "", "subtitulo": p.get("domain") or "",
                "fatos": _fatos([("Categoria", p.get("category")), ("Abrangência", p.get("scope")), ("UF", p.get("uf")),
                                 ("Porte de tráfego", p.get("traffic_tier")), ("Visitas mensais", p.get("monthly_visits")),
                                 ("Formatos de anúncio", ", ".join(dict.fromkeys(formatos)) if formatos else None)]),
                "grupos": []}
    except BadRequest:
        raise NotFound()


# ---------- Seleção para o briefing (fica na sessão) ----------

def selecao(sess) -> list[dict]:
    itens = sess.get("area_cliente_descobrir") or []
    return [i for i in itens if isinstance(i, dict) and i.get("secao") in SECOES][:LIMITE_SELECAO]


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
        restantes.append({"secao": secao, "id": item_id, "nome": _texto(nome, 120) or TIPO_ROTULO[secao],
                          "tipo": TIPO_ROTULO[secao]})
    sess["area_cliente_descobrir"] = restantes
    return incluido


def selecionados(sess) -> set:
    return {(i["secao"], i["id"]) for i in selecao(sess)}


def texto_selecao(itens) -> str:
    if not itens:
        return ""
    return "Itens escolhidos no Descobrir:\n" + "\n".join(f"- {i['tipo']}: {i['nome']}" for i in itens)
