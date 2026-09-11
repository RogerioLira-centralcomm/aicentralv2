"""Processador de planejamento — contrato de analyze.php."""

from __future__ import annotations

from .ai import chat_text
from .catalog import CHANNEL_CATALOG, channel_label
from .helpers import as_dict, normalize_markdown, text
from .repository import get_by_token, merge_dados


PLAN_PROMPT = """Você é planejador de mídia sênior especializado em inteligência de mídia e modelagem de audiências no Brasil.

Sua tarefa é criar um PLANEJAMENTO DE MÍDIA executável e detalhado que sirva como guia operacional e documento de alinhamento.

IMPORTANTE:
- NÃO mencione nenhuma agência, consultoria ou empresa específica
- Documento white-label
- NÃO invente prazos, datas de produção ou cronograma de criativos
- Use "A definir" para responsáveis

ESTRUTURA (use ## para cada seção):

## Capa
Nome da campanha, cliente/marca, objetivo, período (ou "Período a definir") e investimento.

## Visão Geral
Um parágrafo, máximo 4 linhas.

## Objetivos e KPIs
Objetivos SMART com KPI e meta. Premissas rotuladas como "Premissa:".

## Território e Praça
Abrangência, perfil e leitura de mercado. Sem dado: "Praça a definir pelo anunciante".

## Inteligência de Audiência
Comportamentos, hábitos de mídia, jornada e gatilhos.

## Modelagem e Segmentação
Tabela: Segmento | Perfil | Universo Praça | % Estimado | Impacto Esperado | Prioridade

## Estratégia e Mix
Tabela: Canal | % | R$ | Papel | Justificativa
Justificativa específica (público + comportamento + segmentação).

## Números e Performance
Tabela: Canal | Impressões | Alcance | KPI Principal | Meta
NÃO inclua CPM.

## Direção Criativa
Formatos, mensagem e variações por canal. Sem cronograma de produção.

## Fases do Voo
Tabela: Fase | Período | Canais Ativos | Objetivo da Fase
Sem período informado: não invente semanas.

## Premissas
Taxas assumidas, benchmarks e dependências.

## Próximos Passos
Máximo 5 ações. Responsável: "A definir".
"""

REVIEW_PROMPT = """Você revisa um planejamento de mídia já escrito.
Devolva o documento revisado inteiro em markdown — nunca comentários sobre ele.
Corrija números que não fecham com a verba, promessas sem lastro e seções repetidas.
Não invente dado que o briefing não trouxe. Não mencione agência nem IA.
"""

MARKET_PROMPT = """Você é analista de mercado de mídia no Brasil.
Com base no briefing, escreva insights curtos e úteis (máximo 8 bullets) sobre:
categoria, concorrência típica, consumo de mídia do público e riscos de verba.
Não invente números sem rotular como premissa. Sem agência, sem ferramenta.
"""


def _campaign_block(campanha: dict) -> str:
    if not campanha:
        return ""
    canais = campanha.get("canais") or []
    labels = [channel_label(key) for key in canais]
    lines = [
        "\n\n## Configuração da campanha",
        f"- Canais: {', '.join(labels) or 'a definir'}",
        f"- Praça: {campanha.get('praca') or 'a definir'} {campanha.get('praca_detalhe') or ''}".rstrip(),
        f"- Verba: {campanha.get('verba') or 'a definir'}",
        f"- Período: {campanha.get('periodo') or 'a definir'}",
        f"- Objetivo: {campanha.get('objetivo') or 'a definir'}",
    ]
    if canais:
        lines.append("- Catálogo:")
        for key in canais:
            meta = CHANNEL_CATALOG.get(key) or {}
            lines.append(f"  - {meta.get('label', key)}: {meta.get('desc', '')}")
    return "\n".join(lines)


def research_market(briefing: str, campanha: dict) -> str:
    raw = chat_text(
        MARKET_PROMPT,
        briefing[:18000] + _campaign_block(campanha),
        max_tokens=2500,
        temperature=0.3,
    )
    return normalize_markdown(raw)


def generate_plan(briefing: str, campanha: dict, lastro: str = "") -> str:
    raw = chat_text(
        PLAN_PROMPT,
        "Monte o planejamento de mídia com base neste briefing:\n\n"
        + briefing[:28000]
        + _campaign_block(campanha)
        + (f"\n\n## Dados de mercado\n{lastro}" if lastro else ""),
        max_tokens=8000,
        temperature=0.35,
        timeout=90,
    )
    if not raw:
        raise ValueError("O planejamento voltou vazio. Tente gerar novamente.")
    return normalize_markdown(raw)


def review_plan(document: str, briefing: str, campanha: dict) -> str:
    raw = chat_text(
        REVIEW_PROMPT,
        "Briefing:\n"
        + briefing[:12000]
        + _campaign_block(campanha)
        + "\n\nDocumento a revisar:\n"
        + document[:28000],
        max_tokens=8000,
        temperature=0.15,
        timeout=90,
    )
    return normalize_markdown(raw or document)


def run_generation(token: str) -> dict:
    row = get_by_token(token)
    if not row:
        raise ValueError("Plano não encontrado.")
    briefing = text(row.get("briefing_melhorado") or row.get("briefing_compilado"))
    if not briefing:
        raise ValueError("Processe o briefing antes de gerar o plano.")
    dados = as_dict(row.get("dados_detectados"))
    campanha = dados.get("campanha") if isinstance(dados.get("campanha"), dict) else {}
    market = research_market(briefing, campanha)
    plan = generate_plan(briefing, campanha, market)
    reviewed = review_plan(plan, briefing, campanha)
    merge_dados(token, {
        "mercado": market,
        "planejamento": reviewed,
        "planejamento_rascunho": plan,
    })
    return {
        "mercado": market,
        "planejamento": reviewed,
    }
