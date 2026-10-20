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
    assert len(slides["thesis"]["statement"]) <= 340  # sem manchete, a frase entra inteira até 340
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
    # Um canal só não vira barra de 100%: o slide mostra o canal, a leitura da verba e o voo.
    assert no_fronts["layout"] == "solo" and no_fronts["share"] == [] and no_fronts["channels"] == []
    assert no_fronts["solo"]["label"] == "Rede de portais e sites"
    assert no_fronts["flight_unit"] == "mês" and no_fronts["reading"]["stats"][0]["label"] == "Investimento"


def test_weekly_flight_is_read_as_weeks_and_ramp_is_named():
    from aicentralv2.smart_planner.public_slides import _flight_reading

    weeks = [{"label": f"S{i} · {d}", "amount": a} for i, (d, a) in enumerate(zip(["24/9", "1/10", "8/10", "15/10", "22/10"], [10754, 16864, 20819, 24231, 27332]), 1)]
    reading = _flight_reading({"media": {"months": weeks}})
    assert reading["unit"] == "semana"
    assert "semana a semana" in reading["shape"]
    assert reading["stats"][1]["label"] == "Em 5 semanas"


def test_thesis_uses_the_short_title_as_headline():
    view = {**VIEW, "overview": "Quando o tema é proteção do orçamento diante da influência das propagandas, a oportunidade está em vídeo.", "overview_title": "Educação financeira onde a atenção está"}
    thesis = next(s for s in build_slides(view) if s["type"] == "thesis")
    assert thesis["headline"] == "Educação financeira onde a atenção está"
    assert thesis["statement"].startswith("Quando o tema")
    generic = next(s for s in build_slides({**view, "overview_title": "Tese central"}) if s["type"] == "thesis")
    assert generic["headline"] == ""


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


def test_presenter_notes_keep_the_full_text_the_slide_summarized():
    slides = {slide["type"]: slide for slide in build_slides(VIEW)}
    assert slides["thesis"]["notes"][0] == VIEW["overview"].strip()  # o slide corta, a nota não
    assert len(slides["thesis"]["statement"]) < len(slides["thesis"]["notes"][0])
    assert any(note.startswith("Etapa 5:") for note in slides["audience"]["notes"])  # etapa que não coube no slide
    assert slides["cover"]["notes"] == [] and slides["contact"]["notes"] == []
    assert all(len(slide["notes"]) <= 12 for slide in slides.values())


def test_mockups_pick_one_screen_per_channel_kind_with_the_creative():
    from aicentralv2.smart_planner.mockups import mockups_for

    view = {"media": {"channels": [
        {"id": "dv360", "label": "Rede de portais e sites", "pct": 60, "group": "programmatic"},
        {"id": "netflix", "label": "Netflix", "pct": 40, "group": "ctv"},
        {"id": "ooh", "label": "OOH", "pct": 10, "group": "ooh"},
    ]}, "network_sites": {"sites": [{"name": "Valor Econômico"}, {"name": "G1"}]}}
    mocks = mockups_for(view, "/static/x.png")
    assert [m["kind"] for m in mocks] == ["portal", "tv"]
    assert mocks[0]["label"] == "G1" and mocks[0]["logo"]  # o maior portal com logo vira a tela
    assert all(m["image"] == "/static/x.png" for m in mocks)
    assert mockups_for(view, "") == []


def test_whatsapp_message_carries_the_plan_link(monkeypatch):
    from aicentralv2.smart_planner import public_view as pv

    monkeypatch.setattr(pv, "obter_contato_por_email", lambda email: {"nome_completo": "Ana Souza", "telefone": "11999998888"})
    monkeypatch.setattr(pv, "normalizar_telefone_whatsapp", lambda phone: "5511999998888")
    contact = pv._executive_contact({"user_email": "a@b.c", "dados_detectados": {}}, "Verão", link="https://x/p/T/proposta", client="Animale")
    assert contact["first_name"] == "Ana"
    assert "https://x/p/T/proposta" in contact["whatsapp_message"] and "Animale" in contact["whatsapp_message"]
    assert contact["whatsapp_message"].endswith("tenho uma dúvida:")


def test_unweighted_fronts_on_one_channel_keep_the_fronts_layout():
    view = {**VIEW, "fronts": [{**f, "weight": None} for f in VIEW["fronts"]]}
    media = next(s for s in build_slides(view) if s["type"] == "media")
    assert media["layout"] == "fronts" and len(media["fronts"]) == 2
