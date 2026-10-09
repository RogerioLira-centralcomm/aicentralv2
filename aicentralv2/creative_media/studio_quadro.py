"""Quadro do Studio: quebra um pedido com várias peças (plano, briefing colado) em uma lista revisável.

O modelo só separa e organiza o que o pedido já diz; não inventa peças nem textos. O que vale para todas as peças vira
``rules`` (regras da série); o que é de uma peça só fica no ``prompt`` dela.
"""
from __future__ import annotations

import json
import os

DECOMPOSE_MODEL = os.getenv("CREATIVE_STUDIO_DECOMPOSE_MODEL", "anthropic/claude-haiku-4.5")
TYPES = ("anuncio", "ilustracao_interface", "ilustracao", "landing_vendas", "landing_institucional", "site", "post")
FORMATS = {
    "feed-4x5": "feed vertical 4:5 (Instagram/Facebook)", "feed-1x1": "feed quadrado 1:1", "story-9x16": "story/reels 9:16",
    "linkedin-landscape": "LinkedIn paisagem 1200x627", "iab-medium": "display 300x250", "iab-billboard": "billboard 970x250",
    "landscape-16x9": "paisagem 16:9", "page-desktop": "tela de página/site desktop", "page-mobile": "tela de página/site mobile",
    "illustration-1x1": "ilustração quadrada (ícone de set)",
    "spot-3x2": "ilustração de interface 3:2 (spot ao lado de card ou seção)", "spot-1x1": "ilustração de interface quadrada",
}
MAX_PIECES = 24

SYSTEM = (
    "Você organiza pedidos de criação de um estúdio de marca. Recebe um texto que pode ser uma ideia solta ou um plano com "
    "várias peças. Devolva SÓ JSON no formato:\n"
    '{"type": "<tipo>", "title": "<nome curto da série>", "rules": "<o que vale para todas as peças>", '
    '"pieces": [{"title": "<nome curto da peça>", "format": "<chave do formato>", "prompt": "<pedido desta peça>"}]}\n'
    "Regras:\n"
    "- Uma peça por item que o texto pede. Se o texto pede 3 banners, são 3 peças. Não invente peças que o texto não pede.\n"
    "- Telas de site ou dobras de landing são peças separadas quando o texto as lista.\n"
    "- Informação que vale para todas (campanha, oferta, público, tom, cores, prazo) vai em rules, não repetida em cada peça.\n"
    "- O prompt da peça leva só o que é dela (mensagem, cena, detalhe pedido). Mantenha textos, números e preços exatamente "
    "como estão no pedido.\n"
    "- format: escolha a chave mais próxima entre: " + "; ".join(f"{key} = {label}" for key, label in FORMATS.items()) + ".\n"
    "- type: um de " + ", ".join(TYPES) + ". Use o tipo informado pelo usuário, salvo se o texto claramente pedir outro.\n"
    "- Títulos e prompts em português.\n"
    "- Para type ilustracao_interface use format spot-3x2 (salvo pedido de outro formato) e não chame as peças de card: a peça é só "
    "a ilustração; descreva os objetos do agrupamento, nunca moldura, título ou texto."
)


def decompose(text, preferred_type="anuncio", *, completion):
    """Lista de peças do pedido. ``completion`` é a chamada ao modelo (injetada para cobrar e testar)."""
    text = " ".join(str(text or "").split()) if len(str(text or "")) < 400 else str(text or "").strip()
    if not text:
        raise ValueError("Escreva o pedido.")
    preferred = preferred_type if preferred_type in TYPES else "anuncio"
    result = completion(
        [{"role": "system", "content": SYSTEM},
         {"role": "user", "content": f"Tipo escolhido pelo usuário: {preferred}\n\nPedido:\n{text[:12000]}"}],
        model=DECOMPOSE_MODEL, max_tokens=3000, temperature=0.2, response_format={"type": "json_object"}, provider="openrouter",
    )
    from ..services.openrouter_service import message_text
    raw = message_text(result.get("message") or {})
    try:
        data = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
    except (ValueError, TypeError) as error:
        raise ValueError("Não foi possível separar as peças do pedido.") from error
    return normalize(data, preferred), result


def normalize(data, preferred):
    data = data if isinstance(data, dict) else {}
    kind = data.get("type") if data.get("type") in TYPES else preferred
    pieces = []
    for item in (data.get("pieces") or [])[:MAX_PIECES]:
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt") or "").strip()
        if not prompt:
            continue
        fmt = str(item.get("format") or "")
        pieces.append({"title": str(item.get("title") or f"Peça {len(pieces) + 1}").strip()[:80],
                       "format": fmt if fmt in FORMATS else "feed-4x5", "prompt": prompt[:2000]})
    return {"type": kind, "title": str(data.get("title") or "Nova série").strip()[:80],
            "rules": str(data.get("rules") or "").strip()[:1500], "pieces": pieces}


# Tipo de criação do Quadro → papel do ativo na biblioteca da marca.
PUBLISH_ROLES = {"ilustracao": "icon", "ilustracao_interface": "illustration"}


def publish_role(kind):
    return PUBLISH_ROLES.get(str(kind or ""), "creative")


def resolve_generated_file(url, modeling):
    """Arquivo local de uma peça do Studio (criação ou edição). Só caminhos gerados pelo próprio Studio."""
    from pathlib import Path
    clean = url.split("?", 1)[0]
    if ".." in clean:
        raise ValueError("Endereço de peça inválido.")
    if clean.startswith("/static/uploads/creative_generated/"):
        path = Path(__file__).resolve().parents[1] / clean.lstrip("/")
    elif "/format-lab/swap/still/" in clean:
        path = Path(modeling.serve_format_lab_swap_still(clean.rsplit("/", 1)[1]))
    else:
        raise ValueError("Só peças criadas no Studio podem ir para a biblioteca da marca.")
    if not path.is_file():
        raise ValueError("O arquivo desta peça não foi encontrado.")
    return path
