"""Descobrir: as vitrines do Cadu Planner dentro da Área do Cliente.

Lê o mesmo catálogo do Planner (canais, formatos, interativos, audiências e
portais). Places e Radar ficam de fora: Radar é do Cadu (marca e projeto).
Regra da área: nada de preço, investimento mínimo, CPA ou valor de mercado.
O cliente pode separar itens para mandar junto com o briefing.
"""

from __future__ import annotations


from werkzeug.exceptions import NotFound

SECOES = {
    "estrategias": ("Estratégias", "flow", "Combinações de canais prontas por objetivo, com fluxo, verba por faixa, peças e indicadores."),
    "canais": ("Canais", "broadcast", "Onde a mídia roda: apps, plataformas, TV, áudio e OOH, com alcance e uso indicado."),
    "formatos": ("Formatos", "layout", "Os formatos de anúncio de cada plataforma, com objetivo e especificações."),
    "interativos": ("Formatos interativos", "sparkles", "Formatos com interação: jogos, carrosséis, quizzes e experiências ricas."),
    "audiencias": ("Audiências", "users", "Públicos prontos por interesse, perfil e comportamento, com tamanho estimado."),
    "portais": ("Portais", "globe", "Sites de notícia e conteúdo por categoria e região, com tráfego e formatos aceitos."),
}
TIPO_ROTULO = {"estrategias": "Estratégia", "canais": "Canal", "formatos": "Formato", "interativos": "Formato interativo",
               "audiencias": "Audiência", "portais": "Portal"}
POR_PAGINA = 24
LIMITE_SELECAO = 20  # a seleção fica no cookie de sessão (limite de ~4 KB)
NOME_MAX = 60
NOME_MAX_ESTRATEGIA = 110  # nome · verba · praças da simulação


def _repo():
    from ..cadu_family import repository
    return repository


def _texto(valor, limite=400):
    texto = " ".join(str(valor or "").split())
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def _cartao(secao, r) -> dict:
    """Formato único de cartão para as cinco vitrines: capa, selo da marca e textos."""
    if secao == "canais":
        meta = [r.get("category")] + ([f"{r['reach_figure']} {r.get('reach_unit') or ''}".strip()] if r.get("reach_figure") else [])
        return {"id": r["id"], "nome": r.get("name"), "descricao": _texto(r.get("description"), 180),
                "imagem": r.get("image_url") or "", "logo": r.get("logo_path") or "", "marca": r.get("name") or "",
                "meta": [m for m in meta if m]}
    if secao in ("formatos", "interativos"):
        from .ficha import _quadro
        meta = [r.get("purpose"), r.get("dimensions") if len(str(r.get("dimensions") or "")) <= 40 else None]
        return {"id": r["id"], "nome": r.get("name"), "descricao": _texto(r.get("description"), 140),
                "imagem": r.get("image_url") or "", "logo": r.get("platform_logo") or "", "marca": r.get("platform") or "",
                "quadro": _quadro(r.get("dimensions")), "familia": r.get("family") or "", "meta": [m for m in meta if m]}
    if secao == "audiencias":
        meta = [r.get("category"), r.get("audience")]
        return {"id": r["id"], "nome": r.get("name"), "descricao": _texto(r.get("description"), 180),
                "imagem": r.get("image_url") or "", "logo": r.get("platform_logo") or "", "marca": r.get("platform") or "",
                "meta": [m for m in meta if m]}
    meta = [r.get("category"), r.get("domain"), r.get("uf")]
    logo = r.get("favicon_url") or (f"https://{r['domain']}/favicon.ico" if r.get("domain") else "")
    return {"id": r["id"], "nome": r.get("name") or r.get("domain"), "descricao": _texto(r.get("description"), 180),
            "imagem": r.get("thumb_url") or "", "logo": logo, "marca": r.get("name") or r.get("domain") or "",
            "meta": [m for m in meta if m]}


# ---------- Estratégias (verba em R$: exceção pedida pelo usuário à regra de não mostrar preço) ----------

def vitrine_estrategias(busca: str = "", objetivo: str = "", verba: str = "") -> dict:
    """Cartões das estratégias ativas com filtro por objetivo e verba disponível."""
    from ..estrategias import catalogo, repositorio, visao
    busca, objetivo = (busca or "").strip()[:80].lower(), (objetivo or "").strip()
    try:
        teto = int(verba) if int(verba) in catalogo.FAIXAS else 0
    except (TypeError, ValueError):
        teto = 0
    todas, _ = repositorio.listar(somente_ativas=True)
    canais = visao.canais_catalogo()
    cartoes = []
    objetivos_usados = {}
    for e in todas:
        c = visao.cartao(e, canais)
        objetivos_usados[e["objetivo"]] = c["objetivo"]
        if objetivo and e["objetivo"] != objetivo:
            continue
        if teto and e["verba_minima"] > teto:
            continue
        texto = " ".join([c["nome"], c["resumo"], c["objetivo"]] + [n["nome"] for n in c["canais"]]).lower()
        if busca and busca not in texto:
            continue
        cartoes.append(c)
    return {"cartoes": cartoes, "total": len(cartoes), "busca": busca, "objetivo": objetivo, "verba": teto,
            "objetivos": [(k, v) for k, v in catalogo.OBJETIVOS.items() if k in objetivos_usados],
            "faixas": [(f, catalogo.brl_curto(f)) for f in catalogo.FAIXAS]}


def _estrategia(item_id) -> dict:
    from ..estrategias import repositorio
    try:
        e = repositorio.obter(int(item_id), somente_ativas=True)
    except (TypeError, ValueError):
        e = None
    if not e:
        raise NotFound()
    return e


def _verba_valida(e: dict, verba) -> int:
    from ..estrategias import catalogo
    inicial = catalogo.faixa_inicial(e["verba_minima"])
    try:
        verba = int(verba)
    except (TypeError, ValueError):
        return inicial
    return verba if verba in catalogo.FAIXAS and verba >= inicial else inicial


def _ids_pracas(texto) -> list[str]:
    return [p for p in str(texto or "").replace(" ", "").split(",") if p][:60]


def sugestoes_estrategias(plataformas_usadas, n: int = 3) -> dict:
    """Estratégias para a tela inicial, personalizadas pelas plataformas que o cliente já usa:
    primeiro as que combinam esses canais (o cliente já conhece) com outros novos; sem histórico,
    as primeiras do catálogo. Devolve os cartões e uma frase explicando a escolha."""
    from ..estrategias.catalogo import slug_url
    vitrine = vitrine_estrategias()
    usadas = [slug_url(x) for x in plataformas_usadas or [] if x]

    def combina(nome_canal: str) -> bool:
        canal = slug_url(nome_canal)
        return any(u and (u in canal or canal in u) for u in usadas)

    pontuados = []
    for ordem, c in enumerate(vitrine["cartoes"]):
        conhecidos = [x["nome"] for x in c["canais"] if combina(x["nome"])]
        novos = [x["nome"] for x in c["canais"] if not combina(x["nome"])]
        pontuados.append((-(len(conhecidos) * 2 + min(len(novos), 2)) if usadas else 0, ordem,
                          dict(c, conhecidos=conhecidos, novos=novos[:3])))
    itens = [c for _p, _o, c in sorted(pontuados, key=lambda t: (t[0], t[1]))][:n]
    if usadas and any(c["conhecidos"] for c in itens):
        nomes = list(dict.fromkeys(plataformas_usadas))[:3]
        motivo = "Combinam " + (", ".join(nomes[:-1]) + " e " + nomes[-1] if len(nomes) > 1 else nomes[0]) + \
                 ", que vocês já usam, com canais novos para ampliar o resultado."
    else:
        motivo = "Estratégias prontas para começar: canais, verba e peças já definidos."
    return {"itens": itens, "motivo": motivo}


def estrategia_por_url(endereco) -> dict:
    """Estratégia ativa pelo endereço legível (ou nome atual / slug interno); 404 se não houver."""
    from ..estrategias import repositorio
    e = repositorio.obter_por_url(endereco, somente_ativas=True)
    if not e:
        raise NotFound()
    return e


def detalhe_estrategia(item_id, verba=None, pracas=None, estrategia=None) -> dict:
    """Ficha completa com a simulação inicial (verba e praças da URL, se vierem)."""
    from ..estrategias import visao
    e = estrategia or _estrategia(item_id)
    item = visao.completa(e)
    item["sim"] = visao.simulacao(e, _verba_valida(e, verba), _ids_pracas(pracas))
    return item


def simulacao_estrategia(item_id, verba=None, pracas=None) -> dict:
    from ..estrategias import visao
    e = _estrategia(item_id)
    return visao.simulacao(e, _verba_valida(e, verba), _ids_pracas(pracas))


def nome_simulacao(item_id, verba=None, pracas=None) -> str:
    """Como a estratégia entra no briefing: nome, verba e praças, montado aqui (não confia no formulário)."""
    from ..estrategias import catalogo, pracas as mod_pracas
    e = _estrategia(item_id)
    praca = mod_pracas.resolver(_ids_pracas(pracas))
    return f"{e['nome']} · {catalogo.brl_curto(_verba_valida(e, verba))} · {praca['resumo']}"


# Vitrine de formatos: blocos por canal (padrão) ou por tipo; interativos por objetivo criativo.
VISOES_FORMATOS = {"canal": "Por canal", "tipo": "Por tipo"}


def vitrine_formatos(secao: str, busca: str = "", canal: str = "", visao: str = "canal") -> dict:
    """Formatos e interativos agrupados, sem paginação (o catálogo cabe numa página).

    canal filtra por plataforma (chips com logo); visao escolhe o agrupamento dos formatos.
    """
    if secao not in ("formatos", "interativos"):
        raise NotFound()
    busca, canal = (busca or "").strip()[:80], (canal or "").strip()[:100]
    visao = visao if visao in VISOES_FORMATOS else "canal"
    repo = _repo()
    todos = repo.catalog(secao, busca)
    base = repo.catalog(secao, "") if busca else todos
    chips = {}
    for r in base:
        nome = str(r.get("platform") or "")
        if nome:
            chip = chips.setdefault(nome, {"valor": nome, "logo": r.get("platform_logo") or "", "total": 0})
            chip["total"] += 1
    if canal:
        todos = [r for r in todos if r.get("platform") == canal]
    from .ficha import _maiuscula
    if secao == "interativos":
        chave, ordem = (lambda r: _maiuscula(r.get("creative_category") or "Outros")), None
        visao = "objetivo"
    elif visao == "tipo":
        chave = lambda r: r.get("family") or "Outros"
        ordem = {r.get("family") or "Outros": r.get("family_order") or 99 for r in todos}
    else:
        chave, ordem = (lambda r: r.get("platform") or "Outros"), None
    grupos = {}
    for r in todos:
        g = grupos.setdefault(chave(r), {"titulo": chave(r), "logo": r.get("platform_logo") if visao == "canal" else "",
                                         "cartoes": []})
        g["cartoes"].append(_cartao(secao, r))
    lista = sorted(grupos.values(), key=lambda g: (ordem.get(g["titulo"], 99) if ordem else -len(g["cartoes"]), g["titulo"]))
    return {"grupos": lista, "total": sum(len(g["cartoes"]) for g in lista), "busca": busca, "canal": canal, "visao": visao,
            "chips": sorted(chips.values(), key=lambda c: (-c["total"], c["valor"])) if secao == "formatos" or len(chips) > 1 else []}


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


def alternar(sess, secao: str, item_id, nome: str, atualizar: bool = False) -> bool:
    """Inclui ou tira um item da seleção. Devolve True se ficou incluído."""
    if secao not in SECOES:
        raise NotFound()
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        raise NotFound()
    itens = selecao(sess)
    chave = (secao, item_id)
    if atualizar and secao == "estrategias" and nome:
        # Estratégia já no briefing com outra simulação: atualiza em vez de tirar.
        atual = next((i for i in itens if (i["secao"], i["id"]) == chave), None)
        novo = _texto(nome, NOME_MAX_ESTRATEGIA)
        if atual and atual["nome"] != novo:
            atual["nome"] = novo
            sess["area_cliente_descobrir"] = [[i["secao"], i["id"], i["nome"]] for i in itens]
            return True
    restantes = [i for i in itens if (i["secao"], i["id"]) != chave]
    incluido = len(restantes) == len(itens)
    if incluido:
        if len(restantes) >= LIMITE_SELECAO:
            return False
        limite = NOME_MAX_ESTRATEGIA if secao == "estrategias" else NOME_MAX
        restantes.append({"secao": secao, "id": item_id, "nome": _texto(nome, limite) or TIPO_ROTULO[secao]})
    sess["area_cliente_descobrir"] = [[i["secao"], i["id"], i["nome"]] for i in restantes]
    return incluido


def selecionados(sess) -> set:
    return {(i["secao"], i["id"]) for i in selecao(sess)}


def texto_selecao(itens) -> str:
    if not itens:
        return ""
    return "Itens escolhidos no Descobrir:\n" + "\n".join(f"- {i['tipo']}: {i['nome']}" for i in itens)
