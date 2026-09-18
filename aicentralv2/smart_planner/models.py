"""Família GPT-5 do Smart Planner: papéis, sampling e prévia de custo.

Padrão CentralX: nano para extração barata, mini para estrutura,
gpt-5.4 para redigir e fechar a 3ª passagem — a versão final.
"""

from __future__ import annotations

import os
from typing import Any

from ..creative_modeling_fx import usd_brl_rate
from .cost import format_brl
from .helpers import plan_mode_of, text


def _env(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip() or default


ROLES = {
    "extract": {
        "label": "Extrair campos",
        "model": _env("SMART_PLANNER_EXTRACT_MODEL", "openai/gpt-5-mini"),
        "temperature": 0.1,
        "top_k": 20,
        "max_tokens": 4000,
        "usd": 0.012,
    },
    "narrative": {
        "label": "Redigir briefing",
        "model": _env("SMART_PLANNER_NARRATIVE_MODEL", "openai/gpt-5-mini"),
        "temperature": 0.2,
        "top_k": 30,
        "max_tokens": 6000,
        "usd": 0.018,
    },
    "digest": {
        "label": "Resumir referência",
        "model": _env("SMART_PLANNER_DIGEST_MODEL", "openai/gpt-5-nano"),
        "temperature": 0.15,
        "top_k": 20,
        "max_tokens": 700,
        "usd": 0.004,
    },
    "review": {
        "label": "Revisar referência",
        "model": _env("SMART_PLANNER_REVIEW_MODEL", "openai/gpt-5-mini"),
        "temperature": 0.1,
        "top_k": 20,
        "max_tokens": 2000,
        "usd": 0.012,
    },
    "vision": {
        "label": "Ler imagem",
        "model": _env("SMART_PLANNER_VISION_MODEL", "openai/gpt-5-mini"),
        "temperature": 0.1,
        "top_k": 20,
        "max_tokens": 1800,
        "usd": 0.015,
    },
    "market": {
        "label": "Mercado",
        "model": _env("SMART_PLANNER_MARKET_MODEL", "openai/gpt-5-mini"),
        "temperature": 0.2,
        "top_k": 30,
        "max_tokens": 2500,
        "usd": 0.02,
    },
    "draft": {
        "label": "Passagem 1 · rascunho",
        "model": _env("SMART_PLANNER_DRAFT_MODEL", "openai/gpt-5-mini"),
        "temperature": 0.3,
        "top_k": 40,
        "max_tokens": 8000,
        "usd": 0.06,
    },
    "improve": {
        "label": "Passagem 2 · aprofundar",
        "model": _env("SMART_PLANNER_IMPROVE_MODEL", "openai/gpt-5.4"),
        "temperature": 0.2,
        "top_k": 30,
        "max_tokens": 8000,
        "usd": 0.14,
    },
    "final": {
        "label": "Passagem 3 · versão final",
        "model": _env("SMART_PLANNER_FINAL_MODEL", "openai/gpt-5.4"),
        "temperature": 0.1,
        "top_k": 20,
        "max_tokens": 8000,
        "usd": 0.14,
    },
    "compose": {
        "label": "Montar quadro",
        "model": _env("SMART_PLANNER_COMPOSE_MODEL", "openai/gpt-5-mini"),
        "temperature": 0.15,
        "top_k": 25,
        "max_tokens": 5000,
        "usd": 0.04,
    },
    "sheet": {
        "label": "Página única · defesa comercial",
        "model": _env("SMART_PLANNER_SHEET_MODEL", "openai/gpt-5.4"),
        "temperature": 0.2,
        "top_k": 30,
        "max_tokens": 6000,
        "usd": 0.08,
    },
}

IMAGE_USD = 0.05

ONE_PAGE_SECTIONS = (
    {
        "id": "strategy",
        "title": "Estratégia",
        "needs": "Recomendação em até duas frases: o que fazer e o peso do mix, só com o que o briefing e o voo trouxeram.",
    },
    {
        "id": "creative",
        "title": "Criativo no canal",
        "needs": "Canal, superfície e um criativo funcionando na tela — não um banner solto. Prompt de imagem para o GPT Image 2.",
    },
    {
        "id": "market",
        "title": "Dado de mercado",
        "needs": "Um número ou palavra de decisão com rótulo. Percentual só se o briefing ou a pesquisa trouxer; senão, Premissa.",
    },
    {
        "id": "defense",
        "title": "Defesa",
        "needs": "Por que este mix, agora, para este anunciante. Fecha a reunião.",
    },
)

COMPLETO_SECTIONS = (
    {"id": "capa", "title": "Capa", "needs": "Campanha, cliente, objetivo, período e investimento — copiar do briefing/mix."},
    {"id": "visao", "title": "Visão Geral", "needs": "Um parágrafo, no máximo quatro linhas, sem jargão."},
    {"id": "kpis", "title": "Objetivos e KPIs", "needs": "SMART. Meta só com lastro; senão Premissa."},
    {"id": "praca", "title": "Território e Praça", "needs": "Abrangência do mix. Sem praça: a definir pelo anunciante."},
    {"id": "audiencia", "title": "Inteligência de Audiência", "needs": "Comportamento, mídia, jornada e gatilhos do briefing."},
    {"id": "segmentacao", "title": "Modelagem e Segmentação", "needs": "Tabela Segmento | Perfil | Universo | % | Impacto | Prioridade."},
    {"id": "mix", "title": "Estratégia e Mix", "needs": "Tabela Canal | % | R$ | Papel | Justificativa. Fechar com a verba do voo."},
    {"id": "numeros", "title": "Números e Performance", "needs": "Impressões/alcance só como Premissa. Sem CPM."},
    {"id": "criativo", "title": "Direção Criativa", "needs": "Formatos e mensagem por canal. Sem cronograma de produção."},
    {"id": "voo", "title": "Fases do Voo", "needs": "Usar as colunas mensais do Gantt. Sem período, não inventar semanas."},
    {"id": "premissas", "title": "Premissas", "needs": "Taxas, benchmarks e dependências rotuladas."},
    {"id": "passos", "title": "Próximos Passos", "needs": "Até 5 ações. Responsável: A definir."},
)

COMPLETO_BOARD = (
    {"id": "context", "title": "Contexto", "needs": "2–3 cards: resumo, audiência, restrições."},
    {"id": "strategy", "title": "Estratégia", "needs": "2–3 cards. O primeiro é a recomendação em uma frase."},
    {"id": "media", "title": "Plano de Mídia", "needs": "2–3 cards: mix, alocação, voo mensal."},
    {"id": "execution", "title": "Execução", "needs": "2–3 cards: criativo, próximos passos, dependências."},
)


def resolve_role(role: str) -> dict:
    spec = dict(ROLES.get(role) or ROLES["draft"])
    override = text(os.getenv("SMART_PLANNER_MODEL"))
    if override and role in {"draft", "improve", "final", "sheet", "compose"}:
        spec["model"] = override
    return spec


def generation_map(mode: str) -> dict:
    mode = (mode or "").strip().lower()
    if mode == "one_page":
        return {
            "mode": "one_page",
            "label": "Página única",
            "document": "Uma folha para o anunciante.",
            "passes": (
                {"n": 1, "role": "final", "title": "Núcleo estratégico canônico"},
                {"n": 2, "role": "sheet", "title": "Página única e defesa comercial"},
            ),
            "sections": list(ONE_PAGE_SECTIONS),
            "board": [],
            "extras": ("Fundo do mercado", "Criativo no canal"),
        }
    return {
        "mode": "completo",
        "label": "Plano completo",
        "document": "Documento operacional e quadro das quatro seções.",
        "passes": (
            {"n": 1, "role": "final", "title": "Núcleo e página única"},
            {"n": 2, "role": "final", "title": "Estratégia, mídia e execução"},
            {"n": 3, "role": "compose", "title": "Quadro fiel ao núcleo"},
        ),
        "sections": list(COMPLETO_SECTIONS),
        "board": list(COMPLETO_BOARD),
        "extras": (),
    }


def preview_steps(mode: str) -> list[dict]:
    mode = (mode or "").strip().lower()
    steps = [ROLES["final"], ROLES["sheet"]]
    if mode != "one_page":
        steps.extend([ROLES["final"], ROLES["final"], ROLES["compose"]])
    return [
        {
            "label": item["label"],
            "model": item["model"],
            "usd": item["usd"],
        }
        for item in steps
    ]


def preview_cost(mode: str, dados: dict | None = None) -> dict:
    steps = preview_steps(mode)
    usd = sum(float(item["usd"]) for item in steps)
    rate, source = usd_brl_rate()
    brl = round(usd * float(rate or 0), 2)
    spent = None
    if isinstance(dados, dict):
        from .cost import cost_from_dados
        spent = cost_from_dados(dados)
    return {
        "mode": plan_mode_of(dados or {}, fallback=mode),
        "usd": round(usd, 3),
        "brl": brl,
        "label": format_brl(brl, usd=usd),
        "rate": rate,
        "source": source,
        "steps": steps,
        "spent": spent,
        "note": "Estimativa interna da geração em reais, sem margem comercial e fora do consumo de créditos.",
    }


def role_payload(role: str) -> dict[str, Any]:
    spec = resolve_role(role)
    return {
        "role": role,
        "label": spec["label"],
        "model": spec["model"],
        "temperature": spec["temperature"],
        "top_k": spec["top_k"],
        "max_tokens": spec["max_tokens"],
    }
