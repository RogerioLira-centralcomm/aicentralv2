"""Página única — pitches, schema e geração no padrão do Comercial."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from .ai import chat_json
from .helpers import as_dict, as_list, text
from .logos import resolve_branding
from .share import share_payload
from .theme import compose_theme, hero_party

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
        "partners": ("serasa", "meta", "linkedin", "tiktok"),
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

ONE_PAGE_PROMPT = """Você redige uma página única de mídia para o cliente FINAL (anunciante), não para a agência.
Devolva APENAS JSON:

{
  "strategy": {"title": "Estratégia", "body": ""},
  "creative": {
    "title": "Criativo",
    "body": "",
    "channel": "",
    "surface": "ctv|portal|app|display",
    "image_prompt": "descrição visual do criativo funcionando no canal"
  },
  "market": {"title": "Mercado", "body": "", "stat": "", "stat_label": ""},
  "defense": {"title": "Defesa", "body": ""}
}

Regras:
- Foco no anunciante. Se o material for de agência, escolha um cliente final citado.
- O criativo precisa parecer inserido no canal (TV, portal, app), não um banner solto.
- Um dado de mercado simples. Sem inventar percentual sem rotular como premissa.
- Defesa curta: por que aquele canal interessa a esse anunciante.
- Sem agência como herói, sem CentralComm no texto, sem mencionar IA.
"""


def match_pitch(client: str, agency: str, briefing: str = "") -> dict | None:
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


def empty_one_page(meta: dict, branding: dict, theme: dict | None = None, share: dict | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    resolved = dict(branding or {})
    resolved["hero"] = hero_party(resolved)
    return {
        "schemaVersion": 3,
        "planMode": "one_page",
        "meta": {
            "title": meta.get("title") or "Página única",
            "client": meta.get("client"),
            "agency": meta.get("agency"),
            "campaign": meta.get("campaign"),
            "presenter": (resolved.get("presenter") or {}).get("id") or "centralcomm",
            "createdAt": now,
            "updatedAt": now,
        },
        "branding": resolved,
        "theme": theme or {},
        "share": share or {},
        "sections": [{"id": "one_page", "type": "one_page", "title": "Página única", "order": 1, "cards": []}],
    }


def _normalize_card(card: dict, index: int) -> dict:
    extra = {}
    for key in ("channel", "surface", "image_url", "image_prompt", "stat", "stat_label"):
        if card.get(key):
            extra[key] = text(card.get(key))
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
        plan["meta"].update(
            {key: incoming_meta[key] for key in ("title", "client", "agency", "campaign") if incoming_meta.get(key)}
        )
    return plan


def build_one_page(
    meta: dict,
    briefing: str,
    planejamento: str,
    campanha: dict,
    presenter_id: str,
    public_token: str = "",
) -> dict:
    client = text(meta.get("client") or campanha.get("cliente"))
    agency = text(meta.get("agency") or campanha.get("agencia"))
    pitch = match_pitch(client, agency, briefing)
    partners = list(pitch.get("partners") or []) if pitch else []
    branding = resolve_branding(client, agency, presenter_id, partners)
    presenter = branding["presenter"]
    if pitch:
        cards = cards_from_pitch(pitch)
        if not client:
            client = pitch["client"]
        if not agency:
            agency = pitch["agency"]
        branding = resolve_branding(client, agency, presenter_id, partners)
    else:
        parsed = chat_json(
            ONE_PAGE_PROMPT,
            json.dumps(
                {
                    "cliente": client,
                    "agencia": agency,
                    "presenter": presenter,
                    "briefing": briefing[:8000],
                    "planejamento": planejamento[:8000],
                    "campanha": campanha,
                },
                ensure_ascii=False,
            ),
            max_tokens=2500,
            temperature=0.25,
        )
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
