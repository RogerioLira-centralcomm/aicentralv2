"""Processador de planejamento — contrato de analyze.php."""

from __future__ import annotations

from .ai import chat_text
from .brand import brand_prompt_block
from .cost import bound_session
from .catalog import CHANNEL_CATALOG, PLAN_MODES, channel_label
from .helpers import as_dict, as_list, normalize_markdown, plan_mode_of, text
from .places_bridge import places_prompt_block, snapshot_places
from .materials import apoio_block
from .mix import progress_calendar
from .pace import budget_shares, campaign_pace, format_money
from .repository import get_by_token, merge_dados, update_session


PLAN_PROMPT = """Você é planejador de mídia sênior no Brasil. Escreve um planejamento executável, white-label.

Verdade do material:
- Verba, canais, % e voo mensal da configuração da campanha são lei. Feche a tabela de mix com esses R$.
- Sem dado: "A definir" ou "Premissa:". Nunca invente prazo de produção, CPM, impressão ou responsável.
- Sem agência, consultoria, ferramenta ou menção a IA.

Estrutura obrigatória (##):

## Capa
Campanha, anunciante, objetivo e período — copiar da configuração. Só inclua investimento se houver verba confirmada.

## Visão Geral
Um parágrafo, máximo 4 linhas.

## Objetivos e KPIs
SMART. Meta sem lastro vira Premissa.

## Território e Praça
Abrangência do mix. Sem praça: "Praça a definir pelo anunciante".
Se houver Places confirmados: um bloco por place e ponto, com o próprio raio e o próprio reach. Raios não se somam. App só os listados. Venue não entra como texto solto de praça.

## Inteligência de Audiência
Comportamento, hábitos de mídia, jornada e gatilhos do briefing.

## Modelagem e Segmentação
Tabela: Segmento | Perfil | Universo Praça | % Estimado | Impacto Esperado | Prioridade

## Estratégia e Mix
Tabela: Canal | % | R$ | Papel | Justificativa, somente quando a verba estiver confirmada.
Sem verba confirmada, apresente o papel estratégico e marque valores como "A validar", sem mencionar investimento.

## Números e Performance
Tabela: Canal | Impressões | Alcance | KPI Principal | Meta
Sem CPM. Volume sem fonte = Premissa.

## Direção Criativa
Formatos e mensagem por canal. Sem cronograma de produção.

## Fases do Voo
Tabela: Fase | Período | Canais Ativos | Objetivo da Fase
Use as colunas mensais da configuração. Sem período, não invente semanas.

## Premissas
Taxas, benchmarks e dependências.

## Próximos Passos
Máximo 5. Responsável: "A definir".
"""

IMPROVE_PROMPT = """Você aprofunda um rascunho de planejamento já escrito.
Devolva o documento inteiro em markdown — sem comentários.
Feche números somente quando houver verba confirmada e respeite o voo mensal da configuração.
Corte repetição. Não invente o que o briefing não trouxe. Sem agência, sem IA.
"""

FINAL_PROMPT = """Você fecha a versão final do planejamento de mídia.
Esta é a 3ª passagem — o documento que o anunciante lê.
Devolva o markdown inteiro, limpo, sem comentários.
Confira: mix soma a verba quando ela existir; voo respeita as colunas; KPI sem lastro está como Premissa.
Corte jargão e seção oca. Não invente. Sem agência, sem IA.
"""

MARKET_PROMPT = """Você é analista de mercado de mídia no Brasil.
Até 8 bullets: categoria, concorrência típica, consumo de mídia, praça e risco comercial.
Para cada número, informe fonte e data. Sem fonte, escreva "Premissa — a validar" e não invente audiência.
Não transforme membros cadastrados, alcance de anúncio ou usuários de uma plataforma em pessoas impactadas sem explicar a diferença.
Quando não houver demografia confiável, escreva "Demografia: a validar".
Sem agência, sem ferramenta, sem inventar audiência.
"""


def _brand_block(brand: dict) -> str:
    payload = brand_prompt_block(brand)
    if not payload:
        return ""
    lines = ["\n\n## Identidade da marca (Modelagem)"]
    for key, value in payload.items():
        if not value:
            continue
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if item)
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _campaign_block(campanha: dict) -> str:
    if not campanha:
        return ""
    canais = campanha.get("canais") or []
    labels = [channel_label(key) for key in canais]
    lines = [
        "\n\n## Configuração da campanha",
        f"- Canais: {', '.join(labels) or 'a definir'}",
        f"- Praça: {campanha.get('praca') or 'a definir'} {campanha.get('praca_detalhe') or ''}".rstrip(),
    ]
    places_note = places_prompt_block(snapshot_places(campanha.get("places")))
    if places_note:
        lines.append(places_note)
    lines += [
        f"- Período: {campanha.get('periodo') or 'a definir'}",
        f"- Objetivo: {campanha.get('objetivo') or 'a definir'}",
    ]
    if campanha.get("verba"):
        lines.insert(-2, f"- Verba confirmada: {campanha.get('verba')}")
    mix = campanha.get("mix") if isinstance(campanha.get("mix"), dict) else {}
    if mix.get("method"):
        lines.append(f"- Método de mix: {mix.get('method')}")
    split = campanha.get("canais_verba") if isinstance(campanha.get("canais_verba"), dict) else {}
    shares = budget_shares(split) if split else {}
    if canais:
        lines.append("- Catálogo:")
        for key in canais:
            meta = CHANNEL_CATALOG.get(key) or {}
            valor = split.get(key)
            share = shares.get(key)
            extra = ""
            if valor:
                extra = f" · {format_money(int(valor or 0))}"
                if share:
                    extra += f" ({share:g}%)"
            lines.append(f"  - {meta.get('label', key)}: {meta.get('desc', '')}{extra}")
    pace = campaign_pace(campanha)
    if pace.get("alocacao"):
        lines.append("- Voo mensal (menor no começo, maior no meio e no fim):")
        for key, label in zip(pace.get("chaves") or [], pace.get("rotulos") or []):
            lines.append(f"  - {label}: {format_money(int((pace['alocacao'] or {}).get(key) or 0))}")
        if pace.get("como"):
            lines.append(f"- Ritmo: {pace['como']}")
        calendar = progress_calendar(
            canais,
            text(campanha.get("objetivo")),
            text(mix.get("method")),
            pace,
            mix,
        )
        if calendar.get("progress") and calendar.get("rows"):
            lines.append("- Mídia progressiva (aprende no começo, converte no fim):")
            for row in calendar["rows"]:
                cells = ", ".join(
                    f"{label} {cell.get('pct')}%"
                    for label, cell in zip(calendar.get("labels") or [], row.get("cells") or [])
                )
                if cells:
                    lines.append(f"  - {row.get('label')}: {cells}")
    return "\n".join(lines)


def _folha_block(folha: dict) -> str:
    from .canvas import folha_text
    body = folha_text(folha)
    if not body:
        return ""
    return "\n\n## Página única (tese já escrita)\nUse esta folha como base. Aprofunde, não contradiga.\n" + body


def _pack(
    briefing: str,
    campanha: dict,
    brand: dict | None = None,
    lastro: str = "",
    folha: dict | None = None,
    apoio: str = "",
) -> str:
    return (
        briefing[:28000]
        + _campaign_block(campanha)
        + _brand_block(brand)
        + _folha_block(folha or {})
        + (apoio or "")
        + (f"\n\n## Dados de mercado\n{lastro}" if lastro else "")
    )


def research_market(briefing: str, campanha: dict, brand: dict | None = None, apoio: str = "") -> str:
    raw = chat_text(
        MARKET_PROMPT,
        briefing[:18000] + _campaign_block(campanha) + _brand_block(brand) + (apoio or ""),
        role="market",
    )
    return normalize_markdown(raw)


def generate_plan(
    briefing: str,
    campanha: dict,
    lastro: str = "",
    brand: dict | None = None,
    folha: dict | None = None,
    apoio: str = "",
) -> str:
    raw = chat_text(
        PLAN_PROMPT,
        "Passagem 1 — rascunho. Cubra todas as seções com o material abaixo.\n\n"
        + _pack(briefing, campanha, brand, lastro, folha, apoio),
        role="draft",
        timeout=120,
    )
    if not raw:
        raise ValueError("O planejamento voltou vazio. Tente gerar novamente.")
    return normalize_markdown(raw)


def improve_plan(
    document: str,
    briefing: str,
    campanha: dict,
    brand: dict | None = None,
    apoio: str = "",
) -> str:
    raw = chat_text(
        IMPROVE_PROMPT,
        "Passagem 2 — aprofunde este rascunho.\n\n"
        + _pack(briefing[:12000], campanha, brand, apoio=apoio)
        + "\n\n## Rascunho\n"
        + document[:28000],
        role="improve",
        timeout=120,
    )
    return normalize_markdown(raw or document)


def finalize_plan(
    document: str,
    briefing: str,
    campanha: dict,
    brand: dict | None = None,
    apoio: str = "",
) -> str:
    raw = chat_text(
        FINAL_PROMPT,
        "Passagem 3 — versão final.\n\n"
        + _pack(briefing[:12000], campanha, brand, apoio=apoio)
        + "\n\n## Documento\n"
        + document[:28000],
        role="final",
        timeout=120,
    )
    return normalize_markdown(raw or document)


def review_plan(document: str, briefing: str, campanha: dict, brand: dict | None = None) -> str:
    return finalize_plan(document, briefing, campanha, brand)


def run_generation(token: str, mode: str | None = None) -> dict:
    from .generator import run_generation as run_skill_pipeline
    return run_skill_pipeline(token, mode)


def start_generation(token: str, mode: str | None = None) -> dict:
    from .generator import start_generation as start_skill_pipeline
    return start_skill_pipeline(token, mode)
