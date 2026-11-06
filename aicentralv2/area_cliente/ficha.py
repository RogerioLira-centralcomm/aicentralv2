"""Ficha completa de um item do Descobrir, na mesma organização do Cadu Planner.

Lê as mesmas fichas do Planner (catalog.channel_profile, audience_profile,
format_profile e portals.detail) e devolve uma estrutura neutra que o Jinja da
Área do Cliente desenha: faixa com imagem, números, destaques, índice de
sessões, sessões e itens parecidos. Regra da área: nada de preço, investimento,
CPA ou tamanho de mercado em reais. Dados técnicos de portal (ads.txt, sinais
de programática) ficam de fora, como no Planner.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from werkzeug.exceptions import BadRequest, NotFound

_VAZIOS = re.compile(r"^(n[ãa]o informado\.?|dados n[ãa]o dispon[íi]veis\.?|n/?d|-|—|none|null)$", re.I)
METRICA_MAX = 28  # número de faixa é número; frase longa vira nota sobre o método

# Audiência: grupos e campos que o cliente não vê (custos) ou que já aparecem em outro lugar.
_AUDIENCIA_FORA = {"cpa_estimado_min", "cpa_estimado_max", "tamanho_mercado_brl", "descricao_ia", "storytelling"}
_AUDIENCIA_JA_MOSTRADO = {"publico_estimado", "publico_numero", "descricao", "descricao_curta"}
_AUDIENCIA_LISTAS = {"tags", "interesses_correlatos", "momentos_chave", "categorias_alto_desempenho", "diferenciais_competitivos"}
_GRUPO_PERFIL = "Público, perfil e comportamento"
_GRUPO_DEMOGRAFIA = "Demografia e dispositivos"
_GRUPO_NARRATIVA = "Narrativa e aplicação"
_GRUPO_INDICADORES = "Indicadores estimados"

_PORTE = {"grande": "Grande porte", "medio": "Médio porte", "pequeno": "Pequeno porte", "nicho": "Nicho local"}
_GENERO = {"masculino": "Público mais masculino", "feminino": "Público mais feminino",
           "equilibrado": "Público equilibrado entre homens e mulheres"}
_PORTAL_COMERCIAL = (("modelos_de_negocio_declarados", "Formatos de publicidade que o portal vende"),
                     ("caracteristicas_declaradas", "Linha editorial e seções"))

_PAPEL_ICONE = ((r"captur|busca", "search"), (r"alcance|cobertura", "broadcast"), (r"frequ|contexto", "activity"),
                (r"complement|conex|ativa", "flow"), (r"convers|venda|perform", "target"))
_ESTRATEGIA_ICONE = ((r"capital|prac|praç|cidade|regi|geogr|local|bairro", "pin"), (r"hor[aá]r|per[ií]odo|temporal|dia|sazon|moment", "clock"),
                     (r"classe|ticket|pre[cç]o|renda|cupom|oferta", "tag"), (r"interess|comport|afinid|perfil|p[uú]blico|audi[eê]ncia|demogr", "users"),
                     (r"retarget|remarket|conver|a[cç][aã]o", "target"))


# ---------- utilidades ----------

def tem(valor) -> bool:
    if valor is None or valor == "" or valor == [] or valor == {}:
        return False
    if isinstance(valor, str) and _VAZIOS.match(valor.strip()):
        return False
    return True


def _arrumar(valor):
    """"ultra_segmentado" → "Ultra segmentado"; texto livre fica como está."""
    if isinstance(valor, str) and re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)+", valor):
        texto = valor.replace("_", " ")
        return texto[:1].upper() + texto[1:]
    return valor


def _maiuscula(valor):
    texto = str(valor or "").strip()
    return texto[:1].upper() + texto[1:] if texto else ""


def _texto_lista(valor) -> str:
    if isinstance(valor, list):
        partes = [(i.get("nome") or i.get("name") or i.get("label") or "") if isinstance(i, dict) else str(i or "") for i in valor]
        return ", ".join(p for p in partes if p)
    return "" if valor is None else str(valor)


def dividir(valor) -> list[str]:
    """Lista curta a partir de lista ou de texto "a, B; c" (vírgula seguida de maiúscula separa)."""
    if isinstance(valor, list):
        itens = [(i.get("nome") or i.get("name") or i.get("label") or "") if isinstance(i, dict) else str(i or "") for i in valor]
        return [str(_arrumar(i)).strip() for i in itens if str(i).strip()]
    texto = str(valor or "").strip()
    if not texto:
        return []
    partes = [p.strip() for p in re.split(r"\s*[;\n•]\s*|,\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9])", texto) if p.strip()]
    return partes if len(partes) > 1 else [texto]


def _dividir_parenteses(valor) -> list[str]:
    """"A, B (x, y), C" → ["A", "B (x, y)", "C"]: vírgula dentro de parênteses não separa."""
    partes, nivel, atual = [], 0, ""
    for ch in str(valor or ""):
        if ch == "(":
            nivel += 1
        if ch == ")":
            nivel = max(0, nivel - 1)
        if ch == "," and nivel == 0:
            partes.append(atual.strip())
            atual = ""
        else:
            atual += ch
    partes.append(atual.strip())
    return [p for p in partes if p]


def _pct(valor):
    if isinstance(valor, (int, float)) or re.fullmatch(r"\s*\d+([.,]\d+)?\s*", str(valor or "")):
        if not tem(valor):
            return None
        return f"{str(valor).strip().replace('.', ',')}%"
    return valor if tem(valor) else None


def _data(valor) -> str:
    if not valor:
        return ""
    if isinstance(valor, (date, datetime)):
        d = valor
    else:
        try:
            d = datetime.fromisoformat(str(valor).replace("Z", "+00:00")[:25])
        except ValueError:
            return str(valor)
    return d.strftime("%d/%m/%Y")


def _numero(valor) -> str:
    try:
        return f"{int(float(valor)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(valor)


def _icone(regras, texto, padrao):
    for padrao_re, nome in regras:
        if re.search(padrao_re, texto or "", re.I):
            return nome
    return padrao


def _fatos(pares):
    return [{"rotulo": r, "valor": _arrumar(v) if isinstance(v, str) else v} for r, v in pares if tem(v)]


def _tamanho(texto):
    """"300x250 (1:1.2)" → (300, 250); proporções soltas ("16:9") não contam."""
    m = re.search(r"(\d{2,4})\s*[x×]\s*(\d{2,4})", str(texto or ""), re.I)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _quadro(dimensoes) -> dict | None:
    """Caixa de proporção para a miniatura de um formato (largura fixa, altura proporcional)."""
    t = _tamanho(dimensoes)
    if not t:
        return None
    w, h = t
    return {"w": w, "h": h, "proporcao": f"{w} / {h}", "rotulo": f"{w}×{h}"}


def _metricas(itens):
    """Separa números de faixa (curtos) de notas longas sobre o método."""
    cheias = [i for i in itens if tem(i.get("valor"))]
    faixa = [i for i in cheias if not isinstance(i["valor"], str) or len(i["valor"].strip()) <= METRICA_MAX][:6]
    notas = [i for i in cheias if i not in faixa and isinstance(i["valor"], str) and len(i["valor"].strip()) > METRICA_MAX]
    return faixa, notas


def _sessao(id_, titulo, tipo, dados, dica="", contagem=None, larga=False):
    return {"id": id_, "titulo": titulo, "tipo": tipo, "dados": dados, "dica": dica, "contagem": contagem, "larga": larga}


def _montar(*, secao, item_id, nome, logo, eyebrow, descricao, imagens, ilustrativo=False, metricas=(),
            destaques=(), fonte_nota="", sessoes=(), relacionados=None):
    faixa, notas = _metricas(list(metricas))
    imagens = [u for i, u in enumerate(imagens) if u and u not in imagens[:i]]
    sessoes = [s for s in sessoes if s]
    extras = imagens[1:]
    if extras:
        sessoes.append(_sessao("fotos", "Fotos", "galeria", [{"url": u, "legenda": ""} for u in extras[:12]],
                               contagem=len(extras[:12]), larga=True))
    return {
        "secao": secao, "id": item_id, "nome": nome or "", "logo": logo or "", "eyebrow": eyebrow or "",
        "descricao": (descricao or "").strip(), "banner": imagens[0] if imagens else "", "ilustrativo": bool(ilustrativo),
        "metricas": faixa, "notas": notas,
        "destaques": [{"titulo": t, "texto": str(x).strip()} for t, x in destaques if tem(x)], "fonte_nota": fonte_nota,
        "sessoes": sessoes, "relacionados": relacionados if relacionados and relacionados.get("itens") else None,
    }


# ---------- canais ----------

def _canal(item_id):
    from ..cadu_planner import catalog
    c = catalog.channel_profile(item_id)
    formatos = c.get("formats") or []
    anuncios = c.get("ad_examples") or []
    conceitos = [x for x in c.get("concepts") or [] if x.get("image_url")]
    noticias = c.get("news") or []
    audiencias = c.get("audiences") or []
    papeis = c.get("roles") or []
    estrategias = [x for x in (c.get("segmentacoes") if isinstance(c.get("segmentacoes"), list) else []) if isinstance(x, dict) and x.get("nome")]
    segmentacao = []
    for chave, valor in (c.get("segmentacao") or {}).items() if isinstance(c.get("segmentacao"), dict) else []:
        if isinstance(valor, dict):
            titulo = valor.get("nome") or valor.get("name") or chave
            opcoes = valor.get("opcoes") or valor.get("options") or valor.get("valores") or _texto_lista(list(valor.values()))
        else:
            titulo, opcoes = chave, valor
        if tem(opcoes) and isinstance(titulo, str) and not titulo.isdigit():
            segmentacao.append({"titulo": _maiuscula(titulo), "itens": dividir(opcoes)})
    fontes_metricas = c.get("fontes_metricas") if isinstance(c.get("fontes_metricas"), dict) else {}
    fontes_formatos = [u for u in ((fontes_metricas.get("formatos") or {}).get("fontes") or []) if re.match(r"^https?://", str(u))]
    alcance_fonte = fontes_metricas.get("alcance") or {}
    perfil_fonte = fontes_metricas.get("perfil") or {}

    reais = [a.get("image_url") for a in anuncios if a.get("image_url")]
    lidera_anuncios = bool(c.get("hero_illustrative")) and bool(reais)
    imagens = (reais if lidera_anuncios else []) + [c.get("hero_image_url")] + [g.get("url") for g in c.get("gallery") or []]

    tipo = str(c.get("tipo") or "")
    tipo = tipo.upper() if len(tipo) <= 3 else _maiuscula(tipo)
    ficha = _fatos([("Categoria", c.get("categoria")), ("Tipo", tipo),
                    ("Alcance", " ".join(x for x in (str(c.get("alcance") or ""), f"({alcance_fonte['ano']})" if alcance_fonte.get("ano") else "") if x)),
                    ("Formatos", f"{len(formatos)} {'formato' if len(formatos) == 1 else 'formatos'}" if formatos else None)])
    compra = _fatos([("Modelo de compra", _texto_lista(c.get("modelo_compra"))), ("Mensuração", _texto_lista(c.get("medicao"))),
                     ("Brand safety", _texto_lista(c.get("brand_safety")))])
    produtos = dividir(c.get("produtos")) if isinstance(c.get("produtos"), list) else []
    if not produtos and tem(c.get("produtos")):
        compra.append({"rotulo": "Produtos", "valor": str(c.get("produtos"))})

    sessoes = [
        _sessao("ficha", "Ficha técnica", "fatos", ficha, "Os dados essenciais para decidir, num só lugar.") if ficha else None,
        _sessao("papel", "Papel no plano", "papeis",
                [{"titulo": p.get("role"), "texto": p.get("description"), "icone": _icone(_PAPEL_ICONE, p.get("role"), "compass")} for p in papeis],
                "Como este canal costuma trabalhar num plano. A Centralcomm ajusta por campanha.") if papeis else None,
        _sessao("formatos", "Formatos", "formatos",
                [{"secao": "formatos", "id": f["id"], "nome": f.get("name"), "texto": f.get("description") or "",
                  "tipo": _arrumar(f.get("format_type") or ""), "quadro": _quadro(f.get("dimensions")), "dimensoes": f.get("dimensions") or ""}
                 for f in formatos],
                "Escolha o formato ideal para o seu objetivo.", len(formatos), True) if formatos else None,
        _sessao("audiencias", "Audiências neste canal", "audiencias",
                [{"secao": "audiencias", "id": a["id"], "nome": a.get("name"),
                  "texto": " · ".join(x for x in (a.get("category"), _tamanho_publico(a.get("audience"))) if x)} for a in audiencias],
                "Segmente por interesses, comportamentos e contextos.", len(audiencias), True) if audiencias else None,
        _sessao("anuncios", "Anúncios neste canal", "anuncios",
                [{"url": x["image_url"], "titulo": x.get("title") or "", "formato": x.get("format") or "", "texto": x.get("description") or ""} for x in conceitos],
                "Simulações de como a marca apareceria, em cada formato. Demonstrações, não campanhas reais.", len(conceitos), True) if conceitos else None,
        _sessao("exemplos", "Exemplos", "galeria",
                [{"url": a["image_url"], "legenda": a.get("title") or a.get("source_domain") or ""} for a in anuncios if a.get("image_url")],
                contagem=len(reais), larga=True) if reais else None,
        _sessao("diferenciais", "Diferenciais", "tags", dividir(c.get("diferenciais"))) if tem(c.get("diferenciais")) else None,
        _sessao("publico", "Quem está no canal", "demografia", _demografia_canal(c.get("demografia"))) if _demografia_canal(c.get("demografia")) else None,
        _sessao("compra", "Como comprar", "compra",
                {"fatos": compra, "produtos": produtos,
                 "fontes": [{"url": u, "host": re.sub(r"^www\.", "", re.sub(r"^https?://([^/]+).*$", r"\1", u))} for u in fontes_formatos],
                 "segmentacao": segmentacao}) if (compra or produtos or segmentacao or fontes_formatos) else None,
        _sessao("estrategias", "Quando usar cada segmentação", "estrategias",
                [{"titulo": e.get("nome"), "quando": e.get("quando") or "", "exemplo": e.get("exemplo") or "",
                  "icone": _icone(_ESTRATEGIA_ICONE, e.get("nome"), "sparkles")} for e in estrategias],
                contagem=len(estrategias), larga=True) if estrategias else None,
        _sessao("novidades", "Novidades", "noticias",
                [{"titulo": n.get("titulo"), "url": n.get("fonte_url") or "", "resumo": n.get("resumo") or "",
                  "meta": " · ".join(x for x in (n.get("fonte"), _data(n.get("data_publicacao"))) if x)} for n in noticias],
                contagem=len(noticias)) if noticias else None,
    ]
    relacionados = {"titulo": "Canais parecidos", "itens": [
        {"secao": "canais", "id": r["id"], "nome": r.get("name"), "sub": r.get("alcance") or r.get("category") or "",
         "logo": r.get("logo_url") or "", "imagem": r.get("image_url") or ""} for r in c.get("related") or []]}
    return _montar(
        secao="canais", item_id=c.get("id") or item_id, nome=c.get("name"), logo=c.get("logo_url"),
        eyebrow=" · ".join(x for x in (c.get("categoria"), tipo) if x) or "Canal",
        descricao=c.get("description") or c.get("descricao"), imagens=imagens,
        ilustrativo=bool(c.get("hero_illustrative")) and not lidera_anuncios,
        metricas=[{"rotulo": "Alcance", "valor": c.get("alcance"), "dica": "Declarado pelo canal"},
                  {"rotulo": "Usuários únicos", "valor": c.get("usuarios_unicos")},
                  {"rotulo": "Tempo médio", "valor": c.get("tempo_medio")},
                  {"rotulo": "Viewability", "valor": _pct(c.get("viewability"))},
                  {"rotulo": "Taxa de conclusão", "valor": _pct(c.get("completion_rate"))},
                  {"rotulo": "Engajamento", "valor": _pct(c.get("taxa_engajamento"))}],
        destaques=[("Quem você alcança", c.get("perfil_audiencia")), ("Melhor uso", c.get("melhor_uso"))],
        fonte_nota=f"Resumo de fontes públicas, pesquisado em {_data(perfil_fonte['pesquisado_em'])}." if perfil_fonte.get("pesquisado_em") else "",
        sessoes=sessoes, relacionados=relacionados)


def _tamanho_publico(valor):
    texto = str(valor or "").strip()
    return f"{texto} de pessoas" if re.match(r"^[+≈~]?\d", texto) else texto


def _num(valor):
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str) and re.fullmatch(r"\s*\d+([.,]\d+)?\s*%?\s*", valor):
        return float(valor.replace("%", "").replace(",", ".").strip())
    return None


def _chave_bonita(chave):
    chave = str(chave)
    if len(chave) <= 2:
        return chave.upper()
    chave = re.sub(r"^(\d+)_(\d+)$", r"\1–\2", chave)
    chave = re.sub(r"^(\d+)_plus$", r"\1+", chave)
    return _maiuscula(chave.replace("_", " "))


def _barras(pares):
    return [{"rotulo": r, "pct": max(0.0, min(100.0, v)), "valor": f"{v:g}%"} for r, v in pares]


def _demografia_canal(valor) -> list[dict]:
    """{homens: 52, faixas: {18_24: 28}} → grupos de barras (Gênero e um por subgrupo)."""
    if not isinstance(valor, dict):
        return []
    grupos = []
    planos = [(_chave_bonita(k), _num(v)) for k, v in valor.items() if _num(v) is not None]
    if planos:
        grupos.append({"titulo": "Gênero", "barras": _barras(planos)})
    for k, v in valor.items():
        if isinstance(v, dict):
            linhas = [(_chave_bonita(a), _num(b)) for a, b in v.items() if _num(b) is not None]
            if linhas:
                grupos.append({"titulo": _chave_bonita(k), "barras": _barras(linhas)})
    return grupos


# ---------- formatos e interativos ----------

def _formato(secao, item_id):
    from ..cadu_planner import catalog
    f = catalog.format_profile(secao, item_id)
    interativo = secao == "interativos"
    canais = f.get("channels") or []
    tamanhos = [t for t in re.split(r"\s*[|,;]\s*", str(f.get("dimensions") or "")) if t]
    quadros = [q for q in (_quadro(t) | {"extra": re.sub(r"[()]", "", re.sub(r"^\s*\d+\s*[x×]\s*\d+\s*(px)?", "", t, flags=re.I)).strip()}
                           if _quadro(t) else None for t in tamanhos) if q]
    if quadros:
        alto = max(q["h"] for q in quadros)
        largo = max(q["w"] for q in quadros)
        escala = min(180 / alto, 320 / largo)
        for q in quadros:
            q["px_w"], q["px_h"] = max(12, round(q["w"] * escala)), max(12, round(q["h"] * escala))
    links = [(u, r) for u, r in ((f.get("creative_url"), "Ver a experiência funcionando" if interativo else "Abrir demonstração"),
                                  (f.get("gallery_url"), "Ver galeria de exemplos")) if u]
    sessoes = [
        _sessao("tamanhos", "Tamanhos em escala", "tamanhos", quadros,
                "Todos desenhados na mesma escala, para comparar o espaço de cada peça.", larga=True) if quadros else None,
        _sessao("especificacoes", "Especificações", "specs",
                {"fatos": _fatos([("Tipo", _maiuscula(f.get("format_type"))), ("Dimensões", None if len(tamanhos) > 1 else f.get("dimensions")),
                                  ("Arquivos aceitos", _texto_lista(f.get("files"))), ("Categoria criativa", _maiuscula(f.get("creative_category")))]),
                 "links": [{"url": u, "rotulo": r} for u, r in links]}),
        _sessao("onde", "Onde usar", "trilho",
                [{"secao": "canais", "id": c["id"], "nome": c.get("name"), "sub": c.get("category") or "", "logo": c.get("logo_path") or ""} for c in canais],
                "" if canais else "Os canais compatíveis ainda não foram ligados a este formato.", len(canais), True),
        _sessao("mercados", "Mercados e segmentos", "grupos_tags",
                [g for g in ({"titulo": "Mercados", "itens": dividir(f.get("markets"))}, {"titulo": "Segmentos", "itens": dividir(f.get("segments"))}) if g["itens"]])
        if (tem(f.get("markets")) or tem(f.get("segments"))) else None,
    ]
    return _montar(
        secao=secao, item_id=f.get("id") or item_id, nome=f.get("name"), logo=f.get("platform_logo"),
        eyebrow="Formato interativo" if interativo else (_maiuscula(f.get("creative_category")) or "Formato"),
        descricao=f.get("description"), imagens=[f.get("image_url")],
        metricas=[{"rotulo": "Finalidade", "valor": f.get("purpose")},
                  {"rotulo": "Tamanhos", "valor": f"{len(tamanhos)} opções" if len(tamanhos) > 1 else f.get("dimensions")},
                  {"rotulo": "Canais compatíveis", "valor": len(canais) or None}],
        sessoes=sessoes) | {"banner_contain": True}


# ---------- audiências ----------

def _campos(grupo):
    return [c for c in (grupo or {}).get("fields") or []
            if c.get("variable") not in _AUDIENCIA_JA_MOSTRADO and c.get("variable") not in _AUDIENCIA_FORA
            and " IA" not in f" {c.get('label') or ''}" and tem(c.get("value"))]


def _narrativa(grupo):
    campos = _campos(grupo)
    listas = [c for c in campos if c.get("variable") in _AUDIENCIA_LISTAS]
    longos = [c for c in campos if c not in listas and len(str(c.get("value"))) > 90]
    curtos = [c for c in campos if c not in listas and c not in longos]
    return {"cartoes": [{"titulo": c.get("label"), "texto": str(c.get("value")).strip()} for c in longos],
            "listas": [{"titulo": c.get("label"), "itens": dividir(c.get("value"))} for c in listas],
            "fatos": _fatos([(c.get("label"), str(c.get("value"))) for c in curtos])}


def _demografia_audiencia(grupo) -> list[dict]:
    linhas = [(c.get("variable") or "", c.get("label") or "", _num(str(c.get("value")).replace(",", ".")))
              for c in (grupo or {}).get("fields") or []]
    linhas = [x for x in linhas if x[2] is not None]
    saida = []
    for titulo, prefixo in (("Gênero", "demografia_"), ("Idade", "idade_"), ("Dispositivos", "dispositivo_")):
        itens = [(rotulo, valor) for var, rotulo, valor in linhas if var.startswith(prefixo)]
        if any(v > 0 for _, v in itens):  # tudo zero é "não medido", não "ninguém"
            saida.append({"titulo": titulo, "barras": _barras(itens)})
    return saida


def _audiencia(item_id):
    from ..cadu_planner import catalog
    a = catalog.audience_profile(item_id)
    grupos = {g.get("title"): g for g in a.get("data_groups") or []}
    campo = lambda var: next((c.get("value") for g in a.get("data_groups") or [] for c in g.get("fields") or [] if c.get("variable") == var), None)
    perfil, uso = _narrativa(grupos.get(_GRUPO_PERFIL)), _narrativa(grupos.get(_GRUPO_NARRATIVA))
    demografia = _demografia_audiencia(grupos.get(_GRUPO_DEMOGRAFIA))
    canal = a.get("channel_ref")
    formatos = a.get("channel_formats") or []
    cheio = lambda n: bool(n["cartoes"] or n["listas"] or n["fatos"])
    sessoes = [
        _sessao("perfil", "Quem são", "narrativa", perfil) if cheio(perfil) else None,
        _sessao("demografia", "Demografia", "demografia", demografia) if demografia else None,
        _sessao("uso", "Como usar no plano", "narrativa", uso) if cheio(uso) else None,
        _sessao("onde", "Onde comprar", "trilho",
                [{"secao": "canais", "id": canal["id"], "nome": canal.get("name"), "sub": canal.get("category") or "", "logo": canal.get("logo") or ""}],
                "O canal em que esta audiência é ativada.") if canal else None,
        _sessao("formatos", "Formatos para ativar", "formatos",
                [{"secao": "formatos", "id": f["id"], "nome": f.get("name"), "texto": "", "tipo": _arrumar(f.get("format_type") or ""),
                  "quadro": _quadro(f.get("dimensions")), "dimensoes": f.get("dimensions") or ""} for f in formatos],
                "Peças que este canal aceita para alcançar o público.", len(formatos), True) if formatos else None,
    ]
    relacionados = {"titulo": "Audiências parecidas", "itens": [
        {"secao": "audiencias", "id": r["id"], "nome": r.get("name"), "sub": " · ".join(x for x in (r.get("platform"), r.get("audience")) if x),
         "logo": r.get("platform_logo") or "", "imagem": ""} for r in a.get("related") or []]}
    return _montar(
        secao="audiencias", item_id=a.get("id") or item_id, nome=a.get("name"), logo=a.get("platform_logo"),
        eyebrow=" · ".join(x for x in (a.get("category"), a.get("subcategory")) if x) or "Audiência",
        descricao=a.get("description"), imagens=[a.get("image_url")],
        metricas=[{"rotulo": "Público estimado", "valor": a.get("audience")},
                  {"rotulo": "Onde comprar", "valor": a.get("channel") or "Portais e programática"},
                  {"rotulo": "CTR médio", "valor": campo("ctr_medio_estimado"), "dica": "Estimativa", "estimativa": True},
                  {"rotulo": "Conversão", "valor": campo("taxa_conversao_estimada"), "dica": "Estimativa", "estimativa": True},
                  {"rotulo": "Alcance incremental", "valor": campo("alcance_incremental")}],
        sessoes=sessoes, relacionados=relacionados)


# ---------- portais ----------

def _portal(item_id):
    from ..cadu_planner import portals
    p = portals.detail(item_id)
    atributos = [a for a in p.get("public_attributes") or [] if isinstance(a, dict) and a.get("atributo") != "status_curadoria"]
    atributo = lambda chave: next((a.get("valor") for a in atributos if str(a.get("atributo") or "").lower() == chave), None)
    comercial = [{"titulo": r, "itens": _dividir_parenteses(atributo(k))} for k, r in _PORTAL_COMERCIAL if _dividir_parenteses(atributo(k))]
    demo = p.get("demographics") if isinstance(p.get("demographics"), dict) else None
    lugar = str(atributo("localizacao") or "").strip()
    editorias = p.get("site_sections") if isinstance(p.get("site_sections"), list) else []
    selo = "Top 10 nacional" if 1 <= int(p.get("featured_rank") or 0) <= 10 else (f"Top 10 · {p.get('uf')}" if p.get("uf_top") else "")
    cobertura = "Nacional" if p.get("scope") == "nacional_premium" else " · ".join(x for x in (lugar.split("·")[0].strip(), p.get("uf")) if x)
    formatos_brutos = ((p.get("formats") or {}).get("own") or []) + ((p.get("formats") or {}).get("observed") or [])
    formatos, vistos = [], set()
    for f in formatos_brutos:
        chave = f.get("id") or f.get("label") or f.get("nome")
        if chave in vistos:
            continue
        vistos.add(chave)
        dim = re.split(r"\s*[|;]\s*", str(f.get("size") or f.get("dimensoes") or ""))[0]
        formatos.append({"secao": "formatos" if f.get("id") else "", "id": f.get("id"), "nome": f.get("nome") or f.get("label"),
                         "texto": "", "tipo": _arrumar(f.get("tipo") or ""), "quadro": _quadro(dim), "dimensoes": dim})
    exemplos = [e for e in p.get("ad_examples") or [] if isinstance(e, dict) and e.get("url")]
    publico = ""
    if demo:
        partes = [_GENERO.get(demo.get("genero")), demo.get("idade_dominante") and f"faixa predominante de {demo['idade_dominante']} anos",
                  demo.get("classe") and f"classe {demo['classe']}"]
        publico = ", ".join(x for x in partes if x)
    herdado = p.get("popularity_source") == "tranco_parent"
    rank = p.get("popularity_rank")
    sessoes = [
        _sessao("formatos", "Formatos de anúncio", "formatos", formatos,
                "Conheça os formatos e veja as especificações para sua campanha.", len(formatos), True) if formatos else None,
        _sessao("demografia", "Perfil do público", "fatos",
                _fatos([("Gênero", _GENERO.get(demo.get("genero"))),
                        ("Faixa etária predominante", demo.get("idade_dominante") and f"{demo['idade_dominante']} anos"),
                        ("Classe social predominante", demo.get("classe") and f"Classe {demo['classe']}"),
                        ("Região", " · ".join(x for x in (demo.get("regiao"), demo.get("uf")) if x) or None)]),
                f"Estimado pela categoria editorial{' e pela região' if demo.get('regiao') else ''}; confiança {demo.get('confianca') or 'baixa'}. "
                "Não é medição do portal.") if demo else None,
        _sessao("editorias", "Editorias e seções", "tags", [str(e) for e in editorias],
                "Onde o anunciante pode se associar a conteúdo.", len(editorias)) if editorias else None,
        _sessao("comercial", "Perfil comercial", "grupos_tags", comercial, "O que o portal declara vender e sobre o que escreve.") if comercial else None,
        _sessao("sobre", "Sobre o portal", "fatos", _fatos([
            ("Cobertura", lugar or None), ("Domínio", p.get("domain")), ("Categoria", p.get("category")),
            ("Escopo", "Premium nacional" if p.get("scope") == "nacional_premium" else (f"Regional · {p['uf']}" if p.get("uf") else None)),
            ("Período da audiência", p.get("audience_period")), ("Audiência conferida em", _data(p.get("audience_checked_at")))])),
        _sessao("exemplos", "Fotos", "galeria",
                [{"url": e["url"], "legenda": " · ".join(x for x in (p.get("name"), e.get("format"), str(e.get("size") or "").replace("x", "×"),
                                                                      e.get("brand"), "Simulação ilustrativa") if x)} for e in exemplos],
                "Simulações ilustrativas de anúncios por formato. As marcas são exemplos de aplicação.", len(exemplos), True) if exemplos else None,
    ]
    return _montar(
        secao="portais", item_id=p.get("id") or item_id, nome=p.get("name") or p.get("domain"),
        logo=p.get("favicon_url") or (f"https://{p['domain']}/favicon.ico" if p.get("domain") else ""),
        eyebrow=" · ".join(x for x in (selo, p.get("category")) if x), descricao=p.get("description"),
        imagens=[p.get("thumb_url")], ilustrativo=bool(p.get("thumb_url")),
        destaques=[("Formatos de anúncio", (", ".join(f["nome"] for f in formatos[:4] if f["nome"]) + (" e outros." if len(formatos) > 4 else "."))
                    if formatos else ""),
                   ("Quem lê (estimado)", f"{_maiuscula(publico)}." if publico else "")],
        metricas=[{"rotulo": "Porte", "valor": _PORTE.get(p.get("traffic_tier")),
                   "dica": (f"Estimativa pelo ranking público Tranco: #{_numero(rank)}{' (do site principal)' if herdado else ''}"
                            if rank else "Estimativa: fora do ranking público Tranco")},
                  {"rotulo": "Formatos", "valor": _numero(len(formatos)) if formatos else None},
                  {"rotulo": "Editorias", "valor": _numero(len(editorias)) if editorias else None},
                  {"rotulo": "Cobertura", "valor": cobertura or None},
                  {"rotulo": "Audiência pública", "valor": p.get("audience_estimate"), "fonte": p.get("audience_source_url") or ""},
                  {"rotulo": "Acessos por mês", "valor": _numero(p["monthly_visits"]) if float(p.get("monthly_visits") or 0) > 0 else None,
                   "fonte": p.get("metrics_source_url") or ""},
                  {"rotulo": "Tempo médio na página",
                   "valor": f"{int(float(p['avg_time_seconds']) // 60)}min {round(float(p['avg_time_seconds']) % 60):02d}s"
                   if float(p.get("avg_time_seconds") or 0) > 0 else None}],
        sessoes=sessoes)


def montar(secao: str, item_id) -> dict:
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        raise NotFound()
    try:
        if secao == "canais":
            return _canal(item_id)
        if secao in ("formatos", "interativos"):
            return _formato(secao, item_id)
        if secao == "audiencias":
            return _audiencia(item_id)
        if secao == "portais":
            return _portal(item_id)
    except (BadRequest, LookupError):
        raise NotFound()
    raise NotFound()
