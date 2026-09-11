"""Catálogo comercial de canais para o CRM v3.

Lê `cadu_canais` e `cadu_formatos` quando a base responde. Se o banco
não estiver no request (testes, mock), devolve o fallback com os mesmos
campos que a sidebar e o gerador esperam.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


CANAIS_MIDIA = (
    "Netflix", "Spotify", "Serasa", "Disney", "HBO", "Amazon",
    "iFood", "Uber", "99", "Logan", "Interativos",
)

SERASA_KIT_2027 = {
    "titulo": "Serasa Ads e Centralcomm — 2027",
    "tipo": "apresentacao",
    "url": (
        "https://docs.google.com/presentation/d/"
        "1FU_nO_iHRGIOG4qW2XG3iuaNZyrjlqOJ_XqDiT5ILzI/edit"
    ),
    "fatos": [
        "Parceria exclusiva MG e RJ",
        "+100M CPFs 18+ cadastrados",
        "+10,2M CNPJs totais médios/mês",
        "+500 segmentações 1st e 3rd party",
        "Score, histórico de pagador, intenção de compra, renda presumida",
    ],
    "cortes": [
        "Imóveis RJ, score 500+, classe ABC, 30 dias: ECS 190.970 / Meta 1.514.181 / TikTok 58.035",
        "Automotivo RJ, score 500+, ABC: ECS 426.770 / Meta 4.061.559 / TikTok 102.218",
        "Viajantes RJ, score 500+, ABC: ECS 502.190 / Meta 1.211.725 / TikTok 40.296",
        "Nação do Futebol RJ: ECS 253.591 / Meta 1.423.062 / TikTok 71.435",
    ],
}

INTERATIVOS_FALLBACK = [
    {"nome": "Cube", "taxa": "3-6%", "tempo": "15-30s", "melhor_para": "storytelling, produto", "extra": "4x vs display"},
    {"nome": "Scratch", "taxa": "5-10%", "tempo": "10-20s", "melhor_para": "cupom, gamificação", "extra": "6x vs display"},
    {"nome": "Hot Spots", "taxa": "3-6%", "tempo": "15-30s", "melhor_para": "imóveis, decoração", "extra": ""},
    {"nome": "360° Viewer", "taxa": "4-7%", "tempo": "20-40s", "melhor_para": "imóveis, turismo", "extra": "5x vs display"},
    {"nome": "Poll / Quiz", "taxa": "6-12%", "tempo": "15-30s", "melhor_para": "first-party data", "extra": "8x vs display"},
    {"nome": "Countdown", "taxa": "2-4%", "tempo": "5-10s", "melhor_para": "lançamentos", "extra": ""},
    {"nome": "Video Interactive", "taxa": "4-8%", "tempo": "20-45s", "melhor_para": "demo", "extra": "5x vs display"},
]


_CATALOG_PATH = Path(__file__).with_name("crm_v3_canais_catalog.json")
_LOGOS_DIR = Path(__file__).resolve().parent / "static" / "images" / "canais"
_VIEWERS_DIR = "/static/images/creative-viewers"
_CANAIS_DIR = "/static/images/canais"

_LOCAL_LOGOS = {
    "netflix": f"{_VIEWERS_DIR}/netflix.png",
    "disney-plus": f"{_VIEWERS_DIR}/disney-plus.png",
    "hbo-max": f"{_VIEWERS_DIR}/hbo-max.png",
    "prime-video": f"{_VIEWERS_DIR}/prime-video.svg",
    "g1-globo": f"{_VIEWERS_DIR}/g1.svg",
    "youtube": f"{_VIEWERS_DIR}/youtube.svg",
    "instagram": f"{_VIEWERS_DIR}/instagram.svg",
    "tiktok": f"{_VIEWERS_DIR}/tiktok.svg",
    "linkedin": f"{_VIEWERS_DIR}/linkedin.svg",
    "cnn-brasil": f"{_VIEWERS_DIR}/cnn-brasil.svg",
    "sbt": f"{_VIEWERS_DIR}/sbt-news.svg",
}
_LOGO_ALIAS = {
    "experian-dmp": "experian-portal",
}


def _index_canais_logos() -> Dict[str, str]:
    mapping = dict(_LOCAL_LOGOS)
    if _LOGOS_DIR.is_dir():
        for path in sorted(_LOGOS_DIR.iterdir()):
            if path.suffix.lower() in {".png", ".svg", ".jpg", ".jpeg", ".webp"}:
                mapping[path.stem] = f"{_CANAIS_DIR}/{path.name}"
    for slug, alvo in _LOGO_ALIAS.items():
        if alvo in mapping:
            mapping[slug] = mapping[alvo]
    return mapping


_RESOLVED_LOGOS = _index_canais_logos()


def _resolver_logo(slug: str, logo_path: str = "") -> str:
    return _RESOLVED_LOGOS.get(slug or "") or (logo_path or "")


def _aplicar_kit(item: Dict[str, Any]) -> Dict[str, Any]:
    item["logo"] = _resolver_logo(item.get("slug") or "", item.get("logo") or "")
    if _eh_serasa(item):
        item["beneficios"] = list(SERASA_KIT_2027["fatos"])
        item["diferenciais"] = (
            list(item.get("diferenciais") or [])[:2] + SERASA_KIT_2027["cortes"]
        )
        item["arquivos"] = [_arquivo_serasa()]
        item["alcance"] = item.get("alcance") or "+100M CPFs 18+"
    return item


def _fallback_canais() -> List[Dict[str, Any]]:
    try:
        bruto = json.loads(_CATALOG_PATH.read_text())
    except Exception:
        bruto = []
    canais = []
    for row in bruto:
        item = _canal(
            row.get("slug") or "",
            row.get("nome") or "",
            row.get("categoria") or "",
            row.get("tipo") or "",
            alcance=row.get("alcance") or "",
            viewability=row.get("viewability"),
            minimo=row.get("investimento_minimo") or "",
            beneficios=row.get("beneficios") or [],
            diferenciais=row.get("diferenciais") or [],
            logo=row.get("logo_path") or "",
            cor=row.get("cor") or "",
            descricao=row.get("descricao") or "",
        )
        canais.append(_aplicar_kit(item))
    if not any(c.get("slug") == "interativos" for c in canais):
        canais.append(_aplicar_kit(_canal(
            "interativos", "Interativos", "Formatos", "interativo",
            alcance="Add-on rich media em programática e portais",
            beneficios=["Taxa de engajamento 2–12% conforme formato", "Tempo de interação 5–45s"],
            diferenciais=["Hot Spots e 360° para imóveis", "Poll/Quiz até 8x vs display"],
            formatos=list(INTERATIVOS_FALLBACK),
        )))
    if canais:
        return canais
    return [_aplicar_kit(item) for item in _fallback_canais_minimo()]


def _fallback_canais_minimo() -> List[Dict[str, Any]]:
    return [
        _canal(
            "netflix", "Netflix", "CTV / Streaming", "ctv",
            alcance="+20M assinantes BR", viewability=99, minimo="R$ 50.000",
            beneficios=["Viewability 99%", "Completion 97%", "2h/dia de consumo"],
            diferenciais=["Ambiente premium sem skip", "CTV com atenção alta"],
            cor="#E50914",
        ),
        _canal(
            "spotify", "Spotify", "Streaming de Áudio", "audio",
            alcance="+50M ouvintes", viewability=98, minimo="R$ 15.000",
            beneficios=["45 min/dia", "Completion 95%"],
            diferenciais=["Áudio com intenção de escuta"],
            cor="#1DB954",
        ),
        _canal(
            "serasa", "Serasa", "Dados e portal", "data",
            alcance="+100M CPFs 18+", viewability=85, minimo="R$ 10.000",
            beneficios=SERASA_KIT_2027["fatos"],
            diferenciais=["Intenção real de compra, não só interesse"] + SERASA_KIT_2027["cortes"],
            arquivos=[_arquivo_serasa()],
            cor="#7C3AED",
        ),
        _canal(
            "disney-plus", "Disney+", "CTV / Streaming", "ctv",
            alcance="+15M assinantes BR", viewability=98, minimo="R$ 40.000",
            beneficios=["Completion 96%"],
            diferenciais=["Família e franquias"],
            cor="#113CCF",
        ),
        _canal(
            "hbo-max", "Max (HBO)", "CTV / Streaming", "ctv",
            alcance="+10M assinantes BR", viewability=98, minimo="R$ 45.000",
            beneficios=["Completion 95%"],
            diferenciais=["Premium adulto"],
            cor="#7B2CBF",
        ),
        _canal(
            "prime-video", "Prime Video", "CTV / Streaming", "ctv",
            alcance="+12M assinantes BR", viewability=97, minimo="R$ 35.000",
            beneficios=["Completion 94%"],
            diferenciais=["Shoppable com dados Amazon"],
            cor="#00A8E1",
        ),
        _canal(
            "g1-globo", "G1 / Globo.com", "Portais Premium", "portal",
            alcance="+150M pageviews/mês", viewability=72, minimo="R$ 10.000",
            beneficios=["80M UU"],
            diferenciais=["Contexto editorial"],
            cor="#C4170C",
        ),
        _canal(
            "interativos", "Interativos", "Formatos", "interativo",
            alcance="Add-on rich media em programática e portais",
            viewability=None, minimo="",
            beneficios=["Taxa de engajamento 2–12% conforme formato", "Tempo de interação 5–45s"],
            diferenciais=["Hot Spots e 360° para imóveis", "Poll/Quiz até 8x vs display"],
            formatos=list(INTERATIVOS_FALLBACK),
            cor="#0F766E",
        ),
    ]


def _canal(
    slug, nome, categoria, tipo, alcance="", viewability=None, minimo="",
    beneficios=None, diferenciais=None, arquivos=None, formatos=None, cor="",
    logo="", descricao="",
):
    return {
        "slug": slug,
        "nome": nome,
        "categoria": categoria,
        "tipo": tipo,
        "alcance": alcance or "",
        "viewability": viewability,
        "investimento_minimo": minimo or "",
        "beneficios": beneficios or [],
        "diferenciais": diferenciais or [],
        "arquivos": arquivos or [],
        "formatos": formatos or [],
        "cor": cor or "",
        "logo": logo or "",
        "descricao": descricao or "",
        "inicial": (nome[:1] or "?").upper(),
    }


def _arquivo_serasa():
    return {
        "titulo": SERASA_KIT_2027["titulo"],
        "tipo": SERASA_KIT_2027["tipo"],
        "url": SERASA_KIT_2027["url"],
    }


def _query_db_canais() -> Optional[List[Dict[str, Any]]]:
    try:
        from flask import current_app, has_app_context
        if has_app_context() and current_app.config.get("TESTING"):
            return None
        from .db import get_db
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT slug, nome, categoria, tipo, alcance, viewability,
                       investimento_minimo, formatos_resumo, diferenciais,
                       logo_path, cor, descricao
                FROM cadu_canais
                WHERE is_active IS TRUE
                ORDER BY ordem NULLS LAST, nome
                """
            )
            rows = cur.fetchall() or []
    except Exception:
        return None
    if not rows:
        return None
    canais = []
    for row in rows:
        slug = (row.get("slug") or "").strip()
        nome = (row.get("nome") or "").strip()
        if not nome:
            continue
        item = _canal(
            slug or _slugify(nome),
            nome,
            row.get("categoria") or "",
            row.get("tipo") or "",
            alcance=row.get("alcance") or "",
            viewability=row.get("viewability"),
            minimo=row.get("investimento_minimo") or "",
            beneficios=_lista(row.get("formatos_resumo")),
            diferenciais=_lista(row.get("diferenciais")),
            logo=row.get("logo_path") or "",
            cor=row.get("cor") or "",
            descricao=row.get("descricao") or "",
        )
        canais.append(_aplicar_kit(item))
    if not any(c["slug"] == "interativos" for c in canais):
        canais.append(_aplicar_kit(_canal_interativos_db()))
    return canais


def _canal_interativos_db() -> Dict[str, Any]:
    formatos = list(INTERATIVOS_FALLBACK)
    try:
        from .db import get_db
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT nome, taxa_engajamento, tempo_interacao, melhor_para,
                       dados_extras
                FROM cadu_formatos
                WHERE is_interativo IS TRUE AND is_active IS TRUE
                ORDER BY ordem NULLS LAST, nome
                """
            )
            rows = cur.fetchall() or []
        if rows:
            formatos = []
            for row in rows:
                extras = row.get("dados_extras") or {}
                if not isinstance(extras, dict):
                    extras = {}
                formatos.append({
                    "nome": row.get("nome") or "",
                    "taxa": row.get("taxa_engajamento") or "",
                    "tempo": row.get("tempo_interacao") or "",
                    "melhor_para": row.get("melhor_para") or "",
                    "extra": extras.get("engagementMultiplier") or "",
                })
    except Exception:
        pass
    canal = _canal(
        "interativos", "Interativos", "Formatos", "interativo",
        alcance="Add-on rich media em programática e portais",
        beneficios=["Engajamento medido por formato", "Tempo de interação 5–45s"],
        diferenciais=["Hot Spots e 360° para imóveis"],
        formatos=formatos,
        cor="#0F766E",
    )
    return canal


def _lista(valor) -> List[str]:
    if not valor:
        return []
    if isinstance(valor, list):
        return [str(item).strip() for item in valor if str(item).strip()]
    return [str(valor).strip()]


def _slugify(nome: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in nome).strip("-")


def _eh_serasa(canal: Dict[str, Any]) -> bool:
    blob = f"{canal.get('slug') or ''} {canal.get('nome') or ''}".lower()
    return "serasa" in blob or "experian" in blob


def listar_canais() -> List[Dict[str, Any]]:
    return _query_db_canais() or _fallback_canais()


def nomes_canais() -> List[str]:
    nomes = [item["nome"] for item in listar_canais() if item.get("nome")]
    for extra in CANAIS_MIDIA:
        if extra not in nomes:
            nomes.append(extra)
    return nomes


def resolver_canal(nome: str) -> Optional[Dict[str, Any]]:
    alvo = (nome or "").strip().casefold()
    if not alvo:
        return None
    canais = listar_canais()
    for item in canais:
        if (item.get("nome") or "").casefold() == alvo:
            return item
        if (item.get("slug") or "").casefold() == alvo:
            return item
    for item in canais:
        nome_item = (item.get("nome") or "").casefold()
        slug = (item.get("slug") or "").casefold()
        if alvo in nome_item or nome_item in alvo or alvo in slug:
            return item
    if "interativ" in alvo:
        return next((item for item in canais if item.get("slug") == "interativos"), None)
    return None


def inferir_canal(titulo: str, atual: str = "") -> str:
    if (atual or "").strip():
        encontrado = resolver_canal(atual)
        return encontrado["nome"] if encontrado else atual.strip()
    texto = (titulo or "").casefold()
    if "interativ" in texto:
        return "Interativos"
    for nome in nomes_canais():
        if nome and nome.casefold() in texto:
            return nome
    return ""


def ficha_canal_texto(nome: str, registro: str = "") -> str:
    canal = resolver_canal(nome)
    if not canal:
        return ""
    linhas = [
        f"FICHA TÉCNICA — {canal['nome']}",
        "Amarre estes números ao registro. Não troque o assunto da atividade pelo nome do canal.",
        "Use somente estes números. Sem número aqui, não escreva 'métrica'.",
    ]
    if canal.get("alcance"):
        linhas.append(f"Alcance: {canal['alcance']}")
    if canal.get("viewability") is not None:
        linhas.append(f"Viewability: {canal['viewability']}%")
    if canal.get("investimento_minimo"):
        linhas.append(f"Investimento mínimo: {canal['investimento_minimo']}")
    if canal.get("beneficios"):
        linhas.append("Números e benefícios: " + "; ".join(canal["beneficios"][:6]))
    if canal.get("diferenciais"):
        linhas.append("Diferenciais: " + "; ".join(canal["diferenciais"][:6]))
    formatos = _formatos_para_registro(canal.get("formatos") or [], registro)
    if formatos:
        blocos = []
        for item in formatos[:5]:
            pedaco = item["nome"]
            if item.get("taxa"):
                pedaco += f" {item['taxa']}"
            if item.get("tempo"):
                pedaco += f" / {item['tempo']}"
            if item.get("extra"):
                pedaco += f" ({item['extra']})"
            if item.get("melhor_para"):
                pedaco += f" — {item['melhor_para']}"
            blocos.append(pedaco)
        linhas.append("Formatos: " + " | ".join(blocos))
    arquivos = canal.get("arquivos") or []
    if arquivos:
        linhas.append(
            "Material de venda: "
            + "; ".join(item.get("titulo") or item.get("url") or "" for item in arquivos[:3])
        )
    return "\n".join(linhas)


def _formatos_para_registro(formatos: List[Dict[str, Any]], registro: str) -> List[Dict[str, Any]]:
    if not formatos:
        return []
    texto = (registro or "").casefold()
    if any(palavra in texto for palavra in ("imob", "lançament", "lancament")):
        prioridade = ("hot spots", "360", "countdown", "cube", "scratch")
        ordenados = sorted(
            formatos,
            key=lambda item: next(
                (idx for idx, chave in enumerate(prioridade) if chave in (item.get("nome") or "").casefold()),
                99,
            ),
        )
        return ordenados
    return formatos


def canal_publico(canal: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "slug": canal.get("slug") or "",
        "nome": canal.get("nome") or "",
        "categoria": canal.get("categoria") or "",
        "tipo": canal.get("tipo") or "",
        "alcance": canal.get("alcance") or "",
        "viewability": canal.get("viewability"),
        "investimento_minimo": canal.get("investimento_minimo") or "",
        "beneficios": canal.get("beneficios") or [],
        "diferenciais": canal.get("diferenciais") or [],
        "arquivos": canal.get("arquivos") or [],
        "formatos": canal.get("formatos") or [],
        "cor": canal.get("cor") or "",
        "logo": canal.get("logo") or "",
        "descricao": canal.get("descricao") or "",
        "inicial": canal.get("inicial") or (canal.get("nome") or "?")[:1].upper(),
    }
