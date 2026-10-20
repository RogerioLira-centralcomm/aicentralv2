"""Proposta pública em slides: conteúdo que cabe no slide e escolha entre apresentação e documento."""

from aicentralv2.smart_planner import routes
from aicentralv2.smart_planner.public_slides import LIMITS, build_slides, clip

LONG = "Uma frase longa sobre a campanha que explica o desafio com detalhes. " * 12

VIEW = {
    "title": "Coleção de Verão",
    "client": "Animale",
    "document_label": "Plano de mídia executivo",
    "cover_identity": {"campaign": "Coleção de Verão", "client": "Animale", "agency": "Agência X"},
    "facts": [("Anunciante", "Animale"), ("Objetivo", "Consideração"), ("Praça", "SP, RJ e BH"), ("Período", "nov a jan"), ("Verba", "R$ 400.000"), ("Público", "Mulheres")],
    "hero": {"creative_image": "/img.png"},
    "overview": LONG,
    "overview_support": "Apoio da tese.",
    "editorial_context": {
        "challenge": {"title": "Atenção curta", "body": LONG},
        "opportunity": {"title": "", "body": "Portais AB."},
        "journey": [{"title": f"Etapa {i}", "body": LONG} for i in range(6)],
        "outputs": [{"name": "Visitas", "description": "Qualificadas."}],
        "media": {"decision": "Concentrar na Rede de portais e sites"},
        "market": {"insight": "", "title": ""},
    },
    "audience": "Mulheres 25-44 AB.",
    "concept": "Explore o verão look por look",
    "concept_body": "Hotspots e Cards.",
    "has_approved_mix": True,
    "media": {
        "channels": [{"id": "dv360", "label": "Rede de portais e sites", "pct": 100, "role": LONG, "color": "#123"}],
        "months": [{"label": "nov", "amount": 100, "amount_label": "R$ 100"}, {"label": "dez", "amount": 200, "amount_label": "R$ 200"}],
    },
    "fronts": [
        {"tipo": "impacto", "label": "Impacto", "weight": 60.0, "text": LONG, "formats": ["Hotspots", "Cards"], "segment": "classes AB"},
        {"tipo": "remarketing", "label": "Remarketing", "weight": 40.0, "text": "Volta a falar.", "formats": ["DCO"], "segment": ""},
    ],
    "formats_by_channel": {"dv360": [{"nome": "Hotspots", "custo_agregado": True}, {"nome": "Billboard"}]},
    "aggregated_formats": ["Hotspots"],
    "network_sites": {"total": 11, "sites": [{"name": "Valor"}, {"name": "Exame"}], "criterios": {"segmento": "AB"}},
    "impact": {"rows": [{"label": "Rede", "invested": "R$ 400.000"}], "cards": [{"label": "Impressões", "value": "6,5 mi"}],
               "origin_label": "Estimativa de referência, em validação", "reach_note": "O alcance não soma."},
    "defense_groups": [{"title": "Por que", "items": [LONG] * 5}],
    "show_market": False,
    "executive": {"name": "Ana", "initials": "AN", "whatsapp_url": "https://wa.me/1"},
    "tem_completo": True,
    "full_plan_url": "/p/x/plano",
}


def test_slides_follow_the_client_conversation_and_drop_empty_ones():
    types = [slide["type"] for slide in build_slides(VIEW)]
    assert types == ["cover", "thesis", "context", "audience", "creative", "media", "formats", "impact", "defense", "contact"]
    assert [slide["index"] for slide in build_slides(VIEW)] == list(range(1, 11))
    minimal = build_slides({"title": "X", "cover_identity": {"campaign": "X"}})
    assert [slide["type"] for slide in minimal] == ["cover", "contact"]


def test_text_budgets_keep_every_slide_inside_the_canvas():
    slides = {slide["type"]: slide for slide in build_slides(VIEW)}
    assert len(slides["thesis"]["statement"]) <= LIMITS["statement"]
    assert all(len(block["body"]) <= LIMITS["block"] for block in slides["context"]["blocks"])
    assert len(slides["audience"]["steps"]) == 4 and all(len(s["body"]) <= LIMITS["step"] for s in slides["audience"]["steps"])
    assert len(slides["defense"]["groups"][0]["items"]) == 3
    assert all(len(item) <= LIMITS["item"] for item in slides["defense"]["groups"][0]["items"])
    assert len(slides["media"]["fronts"][0]["text"]) <= 170


def test_cover_shows_facts_without_repeating_the_client():
    cover = build_slides(VIEW)[0]
    assert [fact["label"] for fact in cover["facts"]] == ["Objetivo", "Praça", "Período", "Verba"]
    assert cover["client"] == "Animale" and cover["image"] == "/img.png"


def test_media_slide_uses_one_share_bar_and_one_bar_per_month():
    media = next(slide for slide in build_slides(VIEW) if slide["type"] == "media")
    assert media["share"] == [{"label": "Impacto", "pct": 60}, {"label": "Remarketing", "pct": 40}]
    assert [m["height"] for m in media["flight"]] == [50, 100]
    assert media["channels"] == []  # com frentes, os canais não repetem a mesma informação
    no_fronts = next(s for s in build_slides({**VIEW, "fronts": []}) if s["type"] == "media")
    assert no_fronts["share"] == [{"label": "Rede de portais e sites", "pct": 100}] and no_fronts["channels"]


def test_clip_cuts_on_a_whole_word():
    assert clip("palavra " * 30, 40).endswith("…") and len(clip("palavra " * 30, 40)) <= 40
    assert clip("curto", 40) == "curto"


def _render(monkeypatch, path, view):
    seen = {}

    def fake_render(template, **ctx):
        seen["template"] = template
        seen["ctx"] = ctx
        return "ok"

    monkeypatch.setattr(routes, "render_template", fake_render)
    from flask import Flask

    with Flask(__name__).test_request_context(path):
        routes._public_document_response(dict(view))
    return seen


def test_proposal_opens_as_slides_and_document_on_request(monkeypatch):
    view = {**VIEW, "document": "proposal", "document_url": "https://x/p/t/proposta"}
    slides = _render(monkeypatch, "/smart-planner/p/t/proposta", view)
    assert slides["template"] == "smart_planner/public_slides.html"
    assert slides["ctx"]["document_page_url"] == "https://x/p/t/proposta?formato=documento"
    assert slides["ctx"]["cover"]["type"] == "cover"
    doc = _render(monkeypatch, "/smart-planner/p/t/proposta?formato=documento", view)
    assert doc["template"] == "smart_planner/public_document.html"
    full = _render(monkeypatch, "/smart-planner/p/t/plano", {**view, "document": "full_plan"})
    assert full["template"] == "smart_planner/public_document.html"


def test_theme_colors_only_accept_hex(monkeypatch):
    view = {**VIEW, "document": "proposal", "document_url": "/p/t/proposta",
            "hero": {**VIEW["hero"], "theme_ink": "red;}body{display:none", "theme_accent": "#AbC123"}}
    seen = _render(monkeypatch, "/smart-planner/p/t/proposta", view)
    assert seen["ctx"]["slide_ink"] == "#14252d" and seen["ctx"]["slide_accent"] == "#AbC123"
