"""Página única — pitches, schema e geração no padrão do Comercial."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from .ai import chat_json
from .catalog import CHANNEL_CATALOG, CHANNEL_LOGOS
from .helpers import as_dict, as_list, text
from .logos import resolve_branding
from .mix import METHODS
from .pace import as_int, format_money
from .share import share_payload
from .theme import compose_theme, density_note_from_pace, hero_party

logger = logging.getLogger(__name__)

ONE_PAGE_TYPES = ("strategy", "creative", "market", "defense")
LEGACY_ONE_PAGE_TYPES = ("summary", "audience", "channel-mix", "allocation", "kpi-group")

STARTER_PITCHES = (
    {
        "id": "montana-grill",
        "client": "Montana Grill",
        "agency": "Desafio",
        "market_id": "food",
        "bg_url": "/static/images/smart_planner/bg-montana-food.png",
        "aliases": ("montana", "desafio"),
        "partners": ("prime_video",),
        "strategy": (
            "Universo Amazon: vídeo no Prime Video, banners no marketplace "
            "e retargeting com dados exclusivos da Amazon."
        ),
        "creative": {
            "title": "Criativo no Prime Video",
            "body": "Vídeo horizontal do Montana Grill na CTV, com QR para o cardápio ou reserva.",
            "channel": "prime_video",
            "surface": "ctv",
            "image_url": "/static/images/smart_planner/montana-grill-ctv.png",
            "image_prompt": (
                "Horizontal CTV living-room shot: a premium TV playing a Montana Grill "
                "steakhouse video ad on Amazon Prime Video, subtle QR code on the lower third, "
                "warm evening light, no agency logos."
            ),
        },
        "market": {
            "stat": "Atenção exclusiva",
            "stat_label": "CTV premium",
            "body": "Prime Video entrega contexto premium e atenção contínua — o anúncio compete com o conteúdo, não com o feed.",
        },
        "defense": (
            "Na Amazon alcançamos o público da marca com assertividade: relevância do Prime Video, "
            "contexto premium e atenção exclusiva. Os dados da própria Amazon reimpactam quem viu "
            "ou interagiu com o filme e com os banners do marketplace."
        ),
    },
    {
        "id": "bh-airport",
        "client": "BH Airport",
        "agency": "Filadélfia",
        "market_id": "travel",
        "bg_url": "/static/images/smart_planner/bg-bh-travel.png",
        "aliases": ("confins", "bh airport", "aeroporto", "filadélfia", "filadelfia"),
        "partners": ("logan",),
        "strategy": (
            "Mídia contextual em portal e app de linhas aéreas e viagens, com deal Logan, "
            "para quem pesquisa MG, passagens e viagem em família — e retargeting em seguida."
        ),
        "creative": {
            "title": "Criativo em viagem",
            "body": "Formato interativo no portal ou app de linhas aéreas: reserve a vaga do estacionamento pelo celular.",
            "channel": "portal",
            "surface": "portal",
            "image_url": "/static/images/smart_planner/bh-airport-portal.png",
            "image_prompt": (
                "Laptop showing an airline travel portal with a BH Airport Confins interactive "
                "ad to book parking online, clean Brazilian travel UI, no agency logos."
            ),
        },
        "market": {
            "stat": "Clique",
            "stat_label": "CTR de intenção",
            "body": "Quem está em app ou portal de passagem já está em jornada de viagem — o clique vende a reserva do estacionamento.",
        },
        "defense": (
            "A estrutura alcança quem de fato viaja por Confins e comunica a reserva de vaga "
            "pela internet, com CTR mais alto, dados premium de intenção e retargeting para reimpacto."
        ),
    },
    {
        "id": "bdmg",
        "client": "BDMG",
        "agency": "Perfil 252",
        "market_id": "finance",
        "bg_url": "/static/images/smart_planner/bg-bdmg-finance.png",
        "aliases": ("bdmg", "perfil 252"),
        "partners": ("serasa", "meta_ads", "linkedin", "tiktok"),
        "strategy": (
            "Serasa Ads no app e no portal, dados B2B e B2C exclusivos, e a mesma base "
            "nas redes da agência — com um interativo possível na campanha do banco."
        ),
        "creative": {
            "title": "Display no Serasa",
            "body": "Display IAB no app ou portal Serasa: abertura de conta ou crédito, com leitura B2B e B2C.",
            "channel": "serasa",
            "surface": "app",
            "image_url": "/static/images/smart_planner/bdmg-serasa-app.png",
            "image_prompt": (
                "Smartphone showing the Serasa app with a BDMG IAB display ad about credit "
                "or account opening, clean fintech UI, no agency logos."
            ),
        },
        "market": {
            "stat": "B2B + B2C",
            "stat_label": "Serasa Ads",
            "body": "O mesmo ambiente alcança pessoa física e jurídica com dado de crédito — e a base pode ir para Meta, LinkedIn e TikTok.",
        },
        "defense": (
            "Serasa Ads alcança o público certo do banco, PF ou PJ, para abertura de conta "
            "e facilidade de crédito. Os mesmos dados B2B e B2C alimentam a operação de redes "
            "sociais da agência do BDMG."
        ),
    },
    {
        "id": "minas-maquinas",
        "client": "Minas Máquinas",
        "agency": "StaloIn",
        "market_id": "agro",
        "bg_url": "/static/images/smart_planner/bg-minas-agro.png",
        "aliases": ("minas máquinas", "minas maquinas", "staloin"),
        "partners": ("serasa",),
        "strategy": (
            "Serasa Ads no app e no portal, dados B2B e B2C, mais interativo geolocal "
            "em portais de agro e construção perto das lojas."
        ),
        "creative": {
            "title": "Display Serasa + praça",
            "body": "Display IAB no Serasa e interativo em conteúdo de maquinário, em raio das lojas físicas.",
            "channel": "serasa",
            "surface": "display",
            "image_url": "/static/images/smart_planner/minas-maquinas-serasa.png",
            "image_prompt": (
                "Serasa web portal with a Minas Máquinas IAB display for agricultural machinery, "
                "plus a hint of a local store map, no agency logos."
            ),
        },
        "market": {
            "stat": "Raio da loja",
            "stat_label": "Interativo geolocal",
            "body": "Dado de crédito no Serasa mais conteúdo temático de agro e construção na praça da loja.",
        },
        "defense": (
            "Serasa Ads alcança PF e PJ com intenção de compra de máquinas. O interativo "
            "geolocal leva a mesma conversa para portais do setor, perto das lojas."
        ),
    },
)

ONE_PAGE_PROMPT = """Você redige uma página única de mídia para o anunciante, não para a agência.
Devolva APENAS JSON:

{
  "strategy": {"title": "Estratégia", "body": ""},
  "creative": {
    "title": "Criativo",
    "body": "",
    "channel": "",
    "surface": "ctv|portal|app|display|place",
    "image_prompt": "descrição visual do criativo funcionando no canal"
  },
  "visual_direction": {
    "persona_name": "nome curto da persona",
    "persona_description": "quem é, contexto e motivação, sem inventar dado demográfico",
    "place_scene": "lugar ou contexto visual confirmado no briefing; vazio se não houver",
    "persona_image_prompt": "foto editorial da persona em situação real, sem logo e sem texto",
    "place_image_prompt": "foto editorial do lugar ou contexto da campanha, sem logo e sem texto"
  },
  "audience_model": {
    "segments": [],
    "faixa_etaria": {"value": null, "status": "a_validar"},
    "genero": {"value": null, "status": "a_validar"},
    "classe_social": {"value": null, "status": "a_validar"},
    "regiao": "",
    "bairro": "",
    "universo_estimado": {"value": null, "unit": "pessoas", "status": "a_validar", "source": ""},
    "impacto_estimado": {"value": null, "unit": "pessoas", "status": "a_validar", "source": ""},
    "source_note": ""
  },
  "visual_data": [
    {"id": "universe", "label": "Universo demográfico", "value": "A validar", "status": "a_validar"},
    {"id": "impact", "label": "Impacto estimado", "value": "A validar", "status": "a_validar"}
  ],
  "market": {"title": "Mercado", "body": "", "stat": "", "stat_label": ""},
  "defense": {"title": "Defesa", "body": ""}
}

Regras:
- Foco no anunciante. Se o material for de agência, escolha o anunciante citado, não a agência.
- Não chame o anunciante de cliente. “Clientes da marca” é público.
- A tese é o desafio de mídia do anunciante, não o documento ou o planejamento.
- Se o nome for confidencial, não o escreva e não descreva a logo da marca.
- strategy.body é a recomendação executiva em até duas frases: o que fazer e o peso do mix.
- O criativo precisa parecer inserido no canal (TV, portal, app ou place), não um banner solto.
- Surface "place" só se Places for o canal de maior peso. Interativo = surface portal, nunca place.
- Se houver places confirmados, não reutilize pitch de aeroporto/portal. Cite apenas o ambiente e sua audiência consolidada; não cite ponto, raio ou app.
- market.stat é um número ou uma palavra de decisão (nunca um slogan). Sem inventar percentual sem rotular como premissa.
- defense.body fecha a reunião: por que este mix, agora, para este anunciante.
- Use os canais, os places e o voo da campanha quando existirem. Se a verba não foi informada, não cite verba, investimento, orçamento, valores ou estimativas no texto: estamos na primeira fase de venda.
- Modele uma persona visual concreta a partir apenas do público e do contexto confirmados. Não invente idade, renda, profissão ou comportamento como se fossem fatos.
- Quando houver praça, lugar ou cenário confirmado, descreva uma imagem de apoio desse lugar. Se não houver, deixe place_scene vazio e não invente um destino.
- Dados demográficos estimados devem trazer fonte, data e status. Sem fonte, mostre "A validar"; nunca preencha pessoas, idade, classe ou gênero por plausibilidade.
- visual_data é uma camada visual de leitura: use mostradores e barras apenas para números confirmados ou estimativas rotuladas. Não crie gráfico com número inventado.
- Sem agência como herói, sem CentralComm no texto, sem mencionar IA.
- Se houver identidade da marca (público, produto, tom), use como verdade. Não invente outro posicionamento.
"""

SHEET_IMPROVE = ONE_PAGE_PROMPT + "\nEsta é a passagem 2. Aprofunde o JSON abaixo sem mudar o schema. Feche o mix com a campanha."
SHEET_FINAL = ONE_PAGE_PROMPT + "\nEsta é a passagem 3 — a versão final da folha. Aperte o texto. Sem peça oca."


def _sheet_from_material(payload: dict) -> dict:
    material = json.dumps(payload, ensure_ascii=False)
    draft = chat_json(ONE_PAGE_PROMPT, "Passagem 1 — rascunho das quatro peças.\n\n" + material, role="draft")
    improved = chat_json(
        SHEET_IMPROVE,
        "Passagem 2.\n\nMaterial:\n" + material[:8000] + "\n\nRascunho:\n" + json.dumps(draft, ensure_ascii=False)[:8000],
        role="improve",
    )
    final = chat_json(
        SHEET_FINAL,
        "Passagem 3 — versão final.\n\nMaterial:\n" + material[:8000] + "\n\nDocumento:\n" + json.dumps(improved, ensure_ascii=False)[:8000],
        role="final",
    )
    return final if isinstance(final, dict) else (improved if isinstance(improved, dict) else draft)


def match_pitch(client: str, agency: str, briefing: str = "", places=None) -> dict | None:
    if as_list(places):
        return None
    hay = " ".join(part.lower() for part in (client, agency, briefing) if part)
    if not hay:
        return None
    for pitch in STARTER_PITCHES:
        names = (pitch["client"], pitch["agency"], *pitch.get("aliases", ()))
        if any(alias.lower() in hay for alias in names if alias):
            return pitch
    return None


def _card(type_id: str, title: str, body: str, extra: dict | None = None, index: int = 0) -> dict:
    card = {
        "id": f"{type_id}-{index}",
        "type": type_id,
        "title": text(title) or type_id,
        "body": text(body),
        "items": [],
    }
    if extra:
        card.update(extra)
    return card


def cards_from_pitch(pitch: dict) -> list[dict]:
    creative = as_dict(pitch.get("creative"))
    market = as_dict(pitch.get("market"))
    return [
        _card("strategy", "Estratégia", pitch.get("strategy"), index=0),
        _card(
            "creative",
            creative.get("title") or "Criativo",
            creative.get("body"),
            {
                "channel": text(creative.get("channel")),
                "surface": text(creative.get("surface") or "display"),
                "image_url": text(creative.get("image_url")),
                "image_prompt": text(creative.get("image_prompt")),
            },
            index=1,
        ),
        _card(
            "market",
            market.get("title") or "Mercado",
            market.get("body"),
            {"stat": text(market.get("stat")), "stat_label": text(market.get("stat_label"))},
            index=2,
        ),
        _card("defense", "Defesa", pitch.get("defense"), index=3),
    ]


def _method_label(method_id: str) -> str:
    key = text(method_id)
    for item in METHODS:
        if item["id"] == key:
            return text(item.get("label"))
    return key


def _audience_line(snapshot: dict) -> str:
    audiences = as_list((snapshot or {}).get("audiences"))
    if audiences:
        first = audiences[0]
        if isinstance(first, dict):
            return text(first.get("label") or first.get("name") or first.get("text"))
        return text(first)
    return text(as_dict((snapshot or {}).get("brand")).get("audience"))


def _role_map(roles) -> dict[str, str]:
    mapped = {}
    for item in as_list(roles):
        row = as_dict(item)
        channel = text(row.get("channel") or row.get("id")).strip().lower()
        role = text(row.get("role") or row.get("papel"))
        if channel and role:
            mapped[channel] = role
    return mapped


def channel_roles_for_one_page(snapshot: dict | None, roles=None) -> list[dict]:
    """Build the compact channel/ecosystem readout without creating a fifth card."""
    snap = as_dict(snapshot)
    role_map = _role_map(roles)
    rows = []
    for raw in as_list(snap.get("mix")):
        item = as_dict(raw)
        channel_id = text(item.get("id")).lower()
        label = text(item.get("label") or CHANNEL_CATALOG.get(channel_id, {}).get("label") or channel_id)
        if not label:
            continue
        meta = CHANNEL_CATALOG.get(channel_id, {})
        rows.append({
            "id": channel_id,
            "label": label,
            "logo": CHANNEL_LOGOS.get(channel_id, ""),
            "role": role_map.get(channel_id) or text(item.get("role")) or "Papel a definir",
            "status": "confirmed",
            "count": item.get("count") if item.get("count") not in (None, "") else None,
            "group": text(meta.get("group")),
        })
    if not rows:
        for channel_id, role in role_map.items():
            meta = CHANNEL_CATALOG.get(channel_id, {})
            rows.append({
                "id": channel_id,
                "label": text(meta.get("label") or channel_id),
                "logo": CHANNEL_LOGOS.get(channel_id, ""),
                "role": role,
                "status": "proposed",
                "count": None,
                "group": text(meta.get("group")),
            })
    portal_rows = [row for row in rows if row.get("group") == "portais"]
    if len(portal_rows) > 1:
        rows = [row for row in rows if row not in portal_rows]
        rows.append({
            "id": "display-network",
            "label": "Rede de portais",
            "logo": CHANNEL_LOGOS.get("dv360", ""),
            "role": "Cobertura contextual",
            "status": "confirmed" if all(row.get("status") == "confirmed" for row in portal_rows) else "proposed",
            "count": sum(row.get("count") or 0 for row in portal_rows) or None,
            "group": "portais",
        })
    return rows[:8]


def build_media_board(
    mix,
    *,
    method: str = "",
    pace=None,
    roles=None,
    calendar=None,
) -> dict:
    roles_by_channel = _role_map(roles)
    channels = []
    for row in as_list(mix):
        item = as_dict(row)
        cid = text(item.get("id"))
        label = text(item.get("label") or cid)
        if not cid and not label:
            continue
        role = (
            roles_by_channel.get(cid.lower())
            or roles_by_channel.get(label.lower())
            or text(item.get("role"))
        )
        amount = as_int(item.get("amount"))
        channels.append({
            "id": cid,
            "label": label,
            "pct": as_int(item.get("pct")),
            "amount": amount or None,
            "amount_label": text(item.get("amount_label")) or (format_money(amount) if amount else ""),
            "role": role,
        })
    channels.sort(key=lambda item: item.get("pct") or 0, reverse=True)
    pace_data = as_dict(pace)
    labels = [text(item) for item in as_list(pace_data.get("labels")) if text(item)]
    keys = [text(item) for item in as_list(pace_data.get("keys")) if text(item)]
    allocation = as_dict(pace_data.get("allocation"))
    months = []
    for index, label in enumerate(labels):
        key = keys[index] if index < len(keys) else str(index)
        amount = as_int(allocation.get(key) or allocation.get(str(index)))
        months.append({
            "label": label,
            "key": key,
            "amount": amount or None,
            "amount_label": format_money(amount) if amount else "",
        })
    board = {
        "method": text(method),
        "method_label": _method_label(method),
        "channels": channels,
    }
    if labels or text(pace_data.get("how")):
        board["pace"] = {
            "how": text(pace_data.get("how")),
            "labels": labels,
            "keys": keys,
            "allocation": allocation,
            "months": months,
        }
    cal = as_dict(calendar)
    if cal:
        board["calendar"] = cal
    return board


def enrich_meta(meta: dict, snapshot: dict | None = None, media: dict | None = None) -> dict:
    out = dict(meta or {})
    snap = as_dict(snapshot)
    board = as_dict(media)
    publico = _audience_line(snap)
    if publico:
        out["publico"] = publico
    budget = as_dict(snap.get("budget"))
    raw_budget = text(budget.get("raw") or out.get("budget"))
    base = text(budget.get("base") or out.get("budget_base") or "total")
    if raw_budget:
        folded = raw_budget.lower()
        if base == "mensal" and "mês" not in folded and "mes" not in folded:
            out["budget"] = raw_budget + " / mês"
        else:
            out["budget"] = raw_budget
        out["budget_base"] = base
    period = text(as_dict(snap.get("period")).get("raw"))
    if period:
        out["period"] = period
    ritmo = text(as_dict(snap.get("pace")).get("how") or as_dict(board.get("pace")).get("how"))
    if ritmo:
        out["ritmo"] = ritmo
    obj = text(as_dict(snap.get("objective")).get("label") or as_dict(snap.get("objective")).get("text"))
    if obj:
        out["objective"] = obj
    channels = as_list(board.get("channels")) or as_list(snap.get("mix"))
    method_label = text(board.get("method_label")) or _method_label(board.get("method") or snap.get("mix_method"))
    if channels:
        out["canais"] = f"{len(channels)} canais" + (f" · {method_label}" if method_label else "")
    if method_label:
        out["mix_method"] = method_label
    place_titles = [
        text(as_dict(item).get("title") or as_dict(item).get("slug"))
        for item in as_list(snap.get("places"))
        if text(as_dict(item).get("title") or as_dict(item).get("slug"))
    ]
    if place_titles:
        out["places"] = ", ".join(place_titles)
        if not text(out.get("market")):
            out["market"] = place_titles[0]
    return out


def cards_from_v2(page: dict, snapshot: dict | None = None) -> list[dict]:
    data = as_dict(page)
    thesis = as_dict(data.get("thesis"))
    rec = as_dict(data.get("recommendation"))
    challenge = as_dict(data.get("challenge"))
    creative = as_dict(data.get("creative_expression"))
    estimates = as_dict(data.get("result_estimates"))
    defense = as_dict(data.get("commercial_defense"))
    audience_model = as_dict(data.get("audience_model"))
    visual_data = as_list(data.get("visual_data"))
    channel_roles = channel_roles_for_one_page(snapshot, rec.get("channel_roles"))
    audience = text(rec.get("audience")) or _audience_line(as_dict(snapshot))
    strategy_bits = [
        text(thesis.get("statement")),
        text(rec.get("summary")),
        text(challenge.get("body") or audience),
    ]
    strategy_body = "\n\n".join(part for part in strategy_bits if part)
    defense_bits = list(as_list(defense.get("why_this_mix"))) or list(as_list(defense.get("why_this_plan")))
    if text(defense.get("closing_statement")):
        defense_bits.append(text(defense.get("closing_statement")))
    outputs = [
        text(as_dict(item).get("name") or item)
        for item in as_list(data.get("outputs"))
        if text(as_dict(item).get("name") or item)
    ]
    market_body = text(estimates.get("summary")) or "Estimativa ainda não disponível."
    if outputs:
        market_body = market_body + "\n\nOutputs: " + "; ".join(outputs[:4])
    return [
        _card("strategy", "Tese e briefing", strategy_body, index=0),
        _card(
            "creative",
            creative.get("headline") or "Criativo no canal",
            text(creative.get("supporting_text") or creative.get("cta")),
            {
                "channel": text(creative.get("channel")),
                "surface": text(creative.get("surface") or "display"),
                "image_prompt": text(creative.get("image_prompt")),
            },
            index=1,
        ),
        _card(
            "market",
            "Indicadores e outputs",
            market_body,
            {
                "stat": "Premissa" if estimates.get("status") != "available" else "Calculado",
                "stat_label": "Origem da estimativa",
                "audience_model": audience_model,
                "visual_data": visual_data,
                "channel_roles": channel_roles,
            },
            index=2,
        ),
        _card("defense", "Defesa comercial", "\n\n".join(part for part in defense_bits if part), index=3),
    ]


def assemble_from_v2(
    meta: dict,
    branding: dict,
    theme: dict | None,
    share: dict | None,
    page: dict,
    core: dict | None = None,
    snapshot_id: str = "",
    snapshot: dict | None = None,
    media: dict | None = None,
) -> dict:
    snap = as_dict(snapshot)
    rec = as_dict(as_dict(page).get("recommendation"))
    board = media or build_media_board(
        snap.get("mix"),
        method=text(snap.get("mix_method")),
        pace=snap.get("pace"),
        roles=rec.get("channel_roles"),
        calendar=snap.get("calendar"),
    )
    plan = empty_one_page(enrich_meta(meta, snap, board), branding, theme, share)
    plan["sections"][0]["cards"] = cards_from_v2(page, snap)
    plan["media"] = board
    plan["public_design"] = as_dict(as_dict(page).get("public_design")) or {
        "skin_id": text(as_dict(theme).get("id")) or "paper-editorial",
        "selection_mode": "auto",
        "brand_ref": text(as_dict(branding.get("client")).get("id")),
        "brand_revision": "",
        "tokens": {
            key: text(as_dict(theme).get(key))
            for key in ("paper", "ink", "accent")
            if text(as_dict(theme).get(key))
        },
        "hero": {"asset_url": text(as_dict(theme).get("bg_url")), "prompt": text(as_dict(theme).get("bg_prompt")), "status": "approved"},
        "agent_note": "Tema resolvido pelo mercado e pela identidade disponível.",
    }
    plan["executive_contact"] = as_dict(as_dict(page).get("executive_contact"))
    plan["asset_manifest"] = as_list(as_dict(page).get("asset_manifest"))
    if as_list(snap.get("places")):
        plan["places"] = as_list(snap.get("places"))
    plan["one_page_v2"] = page
    if core:
        plan["strategy_core"] = {
            "id": as_dict(core).get("id"),
            "thesis": as_dict(core).get("central_thesis"),
        }
    if snapshot_id or snap.get("snapshot_id"):
        plan["snapshot_id"] = snapshot_id or text(snap.get("snapshot_id"))
    return plan


def cards_from_ai(payload: dict) -> list[dict]:
    data = as_dict(payload)
    creative = as_dict(data.get("creative"))
    market = as_dict(data.get("market"))
    strategy = as_dict(data.get("strategy"))
    defense = as_dict(data.get("defense"))
    return [
        _card("strategy", strategy.get("title") or "Estratégia", strategy.get("body"), index=0),
        _card(
            "creative",
            creative.get("title") or "Criativo",
            creative.get("body"),
            {
                "channel": text(creative.get("channel")),
                "surface": text(creative.get("surface") or "display"),
                "image_url": text(creative.get("image_url")),
                "image_prompt": text(creative.get("image_prompt")),
            },
            index=1,
        ),
        _card(
            "market",
            market.get("title") or "Mercado",
            market.get("body"),
            {"stat": text(market.get("stat")), "stat_label": text(market.get("stat_label"))},
            index=2,
        ),
        _card("defense", defense.get("title") or "Defesa", defense.get("body"), index=3),
    ]


META_KEYS = (
    "title",
    "client",
    "agency",
    "campaign",
    "budget",
    "budget_base",
    "period",
    "market",
    "objective",
    "publico",
    "ritmo",
    "canais",
    "mix_method",
    "places",
)


def theme_for_snapshot(client: str, agency: str, briefing: str, snapshot: dict | None = None, pitch: dict | None = None) -> dict:
    snap = as_dict(snapshot)
    if as_list(snap.get("places")):
        pitch = None
    return compose_theme(
        client,
        agency,
        briefing,
        pitch,
        mix=snap.get("mix"),
        density_note=density_note_from_pace(snap.get("pace")),
    )


def empty_one_page(meta: dict, branding: dict, theme: dict | None = None, share: dict | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    resolved = dict(branding or {})
    resolved["hero"] = hero_party(resolved)
    incoming = as_dict(meta)
    visual_theme = as_dict(theme)
    return {
        "schemaVersion": 3,
        "planMode": "one_page",
        "meta": {
            "title": incoming.get("title") or "Página única",
            "client": incoming.get("client"),
            "agency": incoming.get("agency"),
            "campaign": incoming.get("campaign"),
            "budget": incoming.get("budget"),
            "budget_base": incoming.get("budget_base"),
            "period": incoming.get("period"),
            "market": incoming.get("market"),
            "objective": incoming.get("objective"),
            "publico": incoming.get("publico"),
            "ritmo": incoming.get("ritmo"),
            "canais": incoming.get("canais"),
            "mix_method": incoming.get("mix_method"),
            "places": incoming.get("places"),
            "presenter": incoming.get("presenter") or (resolved.get("presenter") or {}).get("id") or "centralcomm",
            "createdAt": now,
            "updatedAt": now,
        },
        "branding": resolved,
        "theme": visual_theme,
        "media": as_dict(incoming.get("media")) if incoming.get("media") else {},
        "share": share or {},
        "public_design": {
            "skin_id": text(visual_theme.get("id")) or "paper-editorial",
            "selection_mode": "auto",
            "brand_ref": text(as_dict(resolved.get("client")).get("id")),
            "brand_revision": "",
            "tokens": {key: text(visual_theme.get(key)) for key in ("paper", "ink", "accent") if text(visual_theme.get(key))},
            "hero": {
                "asset_url": text(visual_theme.get("bg_url")),
                "prompt": text(visual_theme.get("bg_prompt")),
                "status": "approved",
            },
            "agent_note": "Tema visual resolvido automaticamente a partir do contexto do plano.",
        },
        "asset_manifest": [],
        "executive_contact": {},
        "sections": [{"id": "one_page", "type": "one_page", "title": "Página única", "order": 1, "cards": []}],
    }


def _normalize_card(card: dict, index: int) -> dict:
    extra = {}
    for key in ("channel", "surface", "image_url", "image_prompt", "stat", "stat_label", "audience_model", "visual_data", "channel_roles"):
        if card.get(key):
            extra[key] = card.get(key) if key in {"audience_model", "visual_data", "channel_roles"} else text(card.get(key))
    return _card(
        text(card.get("type") or "strategy"),
        card.get("title"),
        card.get("body"),
        extra,
        index=index,
    )


def normalize_one_page(payload: dict, meta: dict, branding: dict) -> dict:
    incoming_plan = payload if isinstance(payload, dict) else {}
    plan = empty_one_page(
        meta,
        branding or as_dict(incoming_plan.get("branding")),
        as_dict(incoming_plan.get("theme")),
        as_dict(incoming_plan.get("share")),
    )
    incoming = as_list(incoming_plan.get("sections"))
    source = {}
    for section in incoming:
        if isinstance(section, dict) and text(section.get("id")) in {"one_page", ""}:
            source = section
            break
    if not source and incoming:
        source = incoming[0] if isinstance(incoming[0], dict) else {}
    cards = [_normalize_card(card, i) for i, card in enumerate(as_list(source.get("cards")))]
    allowed = set(ONE_PAGE_TYPES + LEGACY_ONE_PAGE_TYPES)
    cards = [card for card in cards if card["type"] in allowed][:6]
    plan["sections"][0]["cards"] = cards
    if isinstance(payload, dict):
        incoming_meta = as_dict(payload.get("meta"))
        plan["meta"].update({key: incoming_meta[key] for key in META_KEYS if incoming_meta.get(key)})
        media = as_dict(payload.get("media"))
        if media.get("channels") or media.get("method") or media.get("pace"):
            plan["media"] = media
        if payload.get("one_page_v2"):
            plan["one_page_v2"] = payload.get("one_page_v2")
        for key in ("public_design", "asset_manifest", "executive_contact", "audience_model", "visual_data", "visual_direction", "supporting_visuals"):
            if key in payload:
                plan[key] = payload.get(key)
    return plan


def build_one_page(
    meta: dict,
    briefing: str,
    planejamento: str,
    campanha: dict,
    presenter_id: str,
    public_token: str = "",
    brand: dict | None = None,
    cliente_id=None,
    agencia_id=None,
    apoio: str = "",
) -> dict:
    from .brand import brand_prompt_block

    client = text(meta.get("client") or campanha.get("cliente"))
    agency = text(meta.get("agency") or campanha.get("agencia"))
    pitch = match_pitch(client, agency, briefing, as_dict(campanha).get("places"))
    partners = list(pitch.get("partners") or []) if pitch else []
    branding = resolve_branding(
        client, agency, presenter_id, partners,
        cliente_id=cliente_id, agencia_id=agencia_id, brand=brand,
    )
    presenter = branding["presenter"]
    if pitch:
        cards = cards_from_pitch(pitch)
        if not client:
            client = pitch["client"]
        if not agency:
            agency = pitch["agency"]
        branding = resolve_branding(
            client, agency, presenter_id, partners,
            cliente_id=cliente_id, agencia_id=agencia_id, brand=brand,
        )
    else:
        parsed = _sheet_from_material({
            "cliente": client,
            "agencia": agency,
            "presenter": presenter,
            "marca": brand_prompt_block(brand),
            "briefing": briefing[:8000],
            "planejamento": planejamento[:8000],
            "campanha": campanha,
            "apoio": text(apoio)[:6000],
        })
        cards = cards_from_ai(parsed if isinstance(parsed, dict) else {})
    client = client or branding["client"]["name"]
    agency = agency or branding["agency"]["name"]
    meta = {
        **meta,
        "client": client,
        "agency": agency,
        "presenter": presenter["id"],
    }
    theme = compose_theme(client, agency, briefing, pitch)
    share = share_payload(public_token, client)
    plan = empty_one_page(meta, branding, theme, share)
    plan["sections"][0]["cards"] = cards
    if presenter["id"] != "centralcomm":
        _apply_principal_voice(plan, presenter)
    return plan


def _apply_principal_voice(plan: dict, presenter: dict) -> None:
    name = presenter.get("name") or ""
    if not name:
        return
    for card in plan["sections"][0]["cards"]:
        body = text(card.get("body"))
        if not body:
            continue
        body = body.replace("CentralComm", name).replace("Centralcomm", name)
        card["body"] = body
