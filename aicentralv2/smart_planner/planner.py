"""Processador de planejamento — contrato de analyze.php."""

from __future__ import annotations

from .ai import chat_text
from .brand import brand_prompt_block
from .cost import bound_session
from .catalog import CHANNEL_CATALOG, PLAN_MODES, channel_label
from .helpers import as_dict, as_list, normalize_markdown, plan_mode_of, text
from .places_bridge import places_prompt_block, snapshot_places
from .materials import apoio_block
from .pace import budget_shares, campaign_pace, format_money
from .repository import get_by_token, merge_dados, update_session


PLAN_PROMPT = """Você é planejador de mídia sênior no Brasil. Escreve um planejamento executável, white-label.
O documento é complementar à página única: acrescenta operação e critérios, sem reescrever a mesma decisão em cada capítulo.

Verdade do material:
- Verba total, canais, percentuais e voo mensal da configuração são lei. A tabela deve mostrar a divisão estratégica; não trate a divisão de OOH ou Places como cotação.
- Regra comercial: nunca gere preço, cotação, mínimo, compra, negociação, fornecedor, inventário, ponto, raio ou disponibilidade comercial para OOH ou Places. Use somente investimento total, divisão percentual, público, segmentação, papel estratégico e defesa do plano.
- Sem dado: omita a afirmação e registre somente a decisão pendente necessária. Nunca invente prazo de produção, CPM, impressão ou responsável.
- Sem agência, consultoria, ferramenta ou menção a IA.
- Cada fato deve ter uma única seção de propriedade. Nas demais, não repita.
- Parágrafos com no máximo 4 linhas; no máximo 5 bullets por seção; não preencha seção sem evidência.
- Não escreva prompt de imagem nem gere expressão visual. A imagem será decidida depois no editor.

Estrutura obrigatória (##):

## Capa
Campanha, anunciante, objetivo e período — copiar da configuração. Só inclua investimento se houver verba confirmada.

## Visão Geral
Um parágrafo, máximo 4 linhas. Não repetir a tabela de mix.

## Objetivos e KPIs
SMART. Só inclua metas com lastro; caso contrário, registre a necessidade de definição em Próximos Passos.

## Território e Praça
Abrangência do mix. Se a praça não estiver informada, registre a confirmação em Próximos Passos sem criar texto de preenchimento.
Se houver Places confirmados: cite apenas o ambiente/place e sua audiência consolidada. Apps e sites observados no catálogo podem ser usados como contexto de audiência digital, nunca como promessa de compra. Separe Places digital (apps e geolocalização) de Places OOH (presença física) somente se o catálogo trouxer esse sinal. Não cite preço, mínimo comercial, ponto, raio, fornecedor ou inventário. Venue não entra como texto solto de praça.

## Inteligência de Audiência
Comportamento, hábitos de mídia, jornada e gatilhos do briefing. Não repetir território ou segmentação.

## Modelagem e Segmentação
Tabela: Segmento | Perfil | Universo Praça | % Estimado | Impacto Esperado | Prioridade

## Estratégia e Mix
Tabela: Canal | % de divisão | Investimento do plano | Papel | Justificativa. O investimento é uma referência estratégica do plano, não uma cotação comercial.
Para OOH/Painéis, informe apenas o papel estratégico e a necessidade de planejamento de rede. Para Places, informe a divisão digital ou OOH apenas quando houver evidência no catálogo.

## Números e Performance
Tabela: Canal | Impressões | Alcance | KPI Principal | Meta
Sem CPM. Sem fonte, omita volume e registre a necessidade de uma referência de compra.

## Direção Criativa
Formatos e mensagem por canal. Sem cronograma de produção, prompt de imagem ou direção visual detalhada.

## Fases do Voo
Tabela: Fase | Período | Canais Ativos | Objetivo da Fase
Use as colunas mensais da configuração. Sem período, não invente semanas.

## Decisões pendentes
Liste somente decisões que bloqueiam aprovação ou compra. Não use o rótulo "Premissa" como preenchimento.

## Próximos Passos
Máximo 5. Escreva a ação e o responsável somente se estiverem informados; não invente responsável.
"""

IMPROVE_PROMPT = """Você edita um rascunho de planejamento já escrito.
Devolva o documento inteiro em markdown — sem comentários.
Feche números somente quando houver verba confirmada e respeite o voo mensal da configuração.
Corte repetição entre capítulos: cada fato deve aparecer uma única vez. Remova jargão e texto genérico. Não invente o que o briefing não trouxe. Sem agência, sem IA.
Remova prompts de imagem e direção visual detalhada.
"""

FINAL_PROMPT = """Você fecha a versão final do planejamento de mídia.
Esta é a 3ª passagem — o documento que o anunciante lê.
Devolva o markdown inteiro, limpo, sem comentários.
Confira: mix soma a verba quando ela existir e voo respeita as colunas. KPI sem fonte deve ser removido e virar decisão pendente.
Corte jargão, repetição e seção oca. Nenhum parágrafo com mais de 4 linhas. Não invente. Sem agência, sem IA.
A página única já contém a decisão executiva; este documento deve acrescentar operação, medição e aprovações, não duplicá-la.
"""

MARKET_PROMPT = """Você é analista de mercado de mídia no Brasil.
Até 8 bullets: categoria, concorrência típica, consumo de mídia, praça e risco comercial.
Para cada número, informe fonte e data. Sem fonte, omita o número e registre a necessidade de fonte; não invente audiência.
Não transforme membros cadastrados, alcance de anúncio ou usuários de uma plataforma em pessoas impactadas sem explicar a diferença.
Quando não houver demografia confiável, não crie uma frase de preenchimento.
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
            if valor and meta.get("group") not in {"ooh", "places"}:
                extra = f" · {format_money(int(valor or 0))}"
                if share:
                    extra += f" ({share:g}%)"
            elif share:
                extra = f" ({share:g}% da divisão estratégica)"
            lines.append(f"  - {meta.get('label', key)}: {meta.get('desc', '')}{extra}")
    pace = campaign_pace(campanha)
    if pace.get("alocacao"):
        lines.append("- Voo mensal (menor no começo, maior no meio e no fim):")
        for key, label in zip(pace.get("chaves") or [], pace.get("rotulos") or []):
            lines.append(f"  - {label}: {format_money(int((pace['alocacao'] or {}).get(key) or 0))}")
        if pace.get("como"):
            lines.append(f"- Ritmo: {pace['como']}")
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
