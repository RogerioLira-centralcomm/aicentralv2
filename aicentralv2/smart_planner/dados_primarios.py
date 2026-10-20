"""Dados primários do cliente: de onde vêm as audiências próprias e para que o plano as usa.

Dado primário é o que o próprio anunciante fornece: lista de clientes do CRM, visitantes do site
(pixel), usuários do app, base de leads, compradores. O plano usa esses dados para remarketing
(voltar a falar com quem já conhece a marca), lookalike (achar pessoas parecidas) e exclusão (não
gastar verba com quem já é cliente). Sem fonte confirmada, o plano não promete nenhum desses usos.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .helpers import as_dict, as_list, text

FONTES = {
    "crm": {"label": "Lista de clientes (CRM)", "hint": "E-mails ou telefones de clientes, enviados com hash."},
    "pixel": {"label": "Visitantes do site (pixel)", "hint": "Quem visitou páginas do site, pela tag instalada."},
    "app": {"label": "Usuários do app", "hint": "Base de usuários ativos ou inativos do aplicativo."},
    "leads": {"label": "Base de leads", "hint": "Cadastros de formulários e campanhas anteriores."},
    "compradores": {"label": "Compradores", "hint": "Quem já comprou no e-commerce ou na loja."},
    "interacoes": {"label": "Quem interagiu com a campanha", "hint": "Quem clicou ou interagiu com os anúncios desta campanha."},
}

USOS = {
    "remarketing": {"label": "Remarketing", "hint": "Voltar a falar com quem já conhece a marca."},
    "lookalike": {"label": "Lookalike", "hint": "Encontrar pessoas parecidas com a base do cliente."},
    "exclusao": {"label": "Excluir quem já é cliente", "hint": "Não gastar verba com quem já comprou."},
}

# A campanha só gera essa audiência depois de rodar; não serve para lookalike nem exclusão.
CAMPAIGN_ONLY = {"interacoes"}

ALIASES = {
    "crm": "crm", "lista de clientes": "crm", "base de clientes": "crm", "clientes": "crm", "customer match": "crm",
    "pixel": "pixel", "site": "pixel", "visitantes": "pixel", "visitantes do site": "pixel", "tag": "pixel",
    "app": "app", "aplicativo": "app", "usuarios do app": "app",
    "leads": "leads", "base de leads": "leads", "cadastros": "leads",
    "compradores": "compradores", "compras": "compradores", "e-commerce": "compradores", "ecommerce": "compradores",
    "interacoes": "interacoes", "interacao": "interacoes", "quem interagiu": "interacoes", "engajados": "interacoes",
    "remarketing": "remarketing", "retargeting": "remarketing", "retomada": "remarketing",
    "lookalike": "lookalike", "semelhantes": "lookalike", "publicos semelhantes": "lookalike", "look-alike": "lookalike",
    "exclusao": "exclusao", "excluir clientes": "exclusao", "excluir": "exclusao", "supressao": "exclusao",
}


def _fold(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", text(value).lower())
    return re.sub(r"\s+", " ", "".join(ch for ch in raw if not unicodedata.combining(ch))).strip()


def _pick(values: Any, allowed: dict) -> list[str]:
    out: list[str] = []
    for value in as_list(values) if not isinstance(values, str) else [values]:
        key = ALIASES.get(_fold(value), _fold(value))
        if key in allowed and key not in out:
            out.append(key)
    return [key for key in allowed if key in out]


def normalize(raw: Any) -> dict:
    """Fontes e usos válidos; uso sem fonte que o sustente sai."""
    data = as_dict(raw)
    fontes = _pick(data.get("fontes"), FONTES)
    usos = _pick(data.get("usos"), USOS)
    own = [key for key in fontes if key not in CAMPAIGN_ONLY]
    if not fontes:
        usos = []
    elif not own:
        # Só a interação com a campanha: dá para fazer remarketing, não lookalike nem exclusão.
        usos = [key for key in usos if key == "remarketing"]
    note = text(data.get("observacao"))[:280]
    if not fontes and not note:
        return {}
    return {"fontes": fontes, "usos": usos, "observacao": note}


def labels(keys: list[str], table: dict) -> list[str]:
    return [table[key]["label"] for key in keys if key in table]


def problems(dados: dict, taticas: list[dict]) -> list[str]:
    """Avisos da revisão: remarketing sem audiência de onde partir, uso sem fonte."""
    data = normalize(dados)
    has_remarketing_front = any(text(as_dict(row).get("tipo")) == "remarketing" for row in as_list(taticas))
    out = []
    if has_remarketing_front and not data.get("fontes"):
        out.append("A frente de remarketing precisa de uma audiência: marque de onde ela vem (pixel do site, CRM ou quem interagiu com a campanha).")
    if "remarketing" in as_list(data.get("usos")) and not has_remarketing_front:
        out.append("Os dados vão para remarketing, mas o plano não tem a frente de remarketing nas táticas.")
    if data.get("fontes") and not data.get("usos"):
        out.append("Diga para que os dados do cliente serão usados: remarketing, lookalike ou exclusão.")
    return out


def for_prompt(raw: Any) -> dict | None:
    data = normalize(raw)
    if not data.get("fontes"):
        return None
    return {
        "fontes": labels(data["fontes"], FONTES),
        "usos": labels(data["usos"], USOS),
        "observacao": data.get("observacao") or "",
        "regra": "Dados fornecidos pelo cliente. Cite só estas fontes e usos; não prometa tamanho de base, taxa de match nem resultado.",
    }


def public_view(raw: Any) -> dict:
    """Bloco da apresentação: o que o cliente fornece e como o plano usa."""
    data = normalize(raw)
    if not data.get("fontes"):
        return {}
    return {
        "sources": [{"id": key, "label": FONTES[key]["label"], "hint": FONTES[key]["hint"]} for key in data["fontes"]],
        "uses": [{"id": key, "label": USOS[key]["label"], "hint": USOS[key]["hint"]} for key in data["usos"]],
        "note": data.get("observacao") or "",
    }


def spec_for_js() -> dict:
    return {
        "fontes": [{"id": key, **meta} for key, meta in FONTES.items()],
        "usos": [{"id": key, **meta} for key, meta in USOS.items()],
        "campaignOnly": sorted(CAMPAIGN_ONLY),
    }
