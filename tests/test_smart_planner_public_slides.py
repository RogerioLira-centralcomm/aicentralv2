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


def test_showcase_puts_the_creative_in_each_channel_layout():
    from aicentralv2.smart_planner.mockups import showcase_for

    view = {"media": {"channels": [
        {"id": "netflix", "label": "Netflix", "pct": 40, "group": "ctv"},
        {"id": "uber", "label": "Uber", "pct": 20, "group": "apps"},
        {"id": "tiktok", "label": "TikTok", "pct": 15, "group": "social"},
        {"id": "spotify", "label": "Spotify", "pct": 15, "group": "audio"},
        {"id": "ooh", "label": "OOH", "pct": 10, "group": "ooh"},
    ]}}
    screens = showcase_for(view, "/static/c.png")
    assert [s["kind"] for s in screens] == ["tv", "app", "vertical", "audio"]
    assert all(s["placement"] for s in screens)
    slides = build_slides({**view, "title": "P", "hero": {"creative_image": "/static/c.png", "has_generated_visual": True}})
    assert any(s["type"] == "showcase" for s in slides)
    assert not any(s["type"] == "showcase" for s in build_slides({**view, "title": "P"}))


def test_variants_follow_the_channels_and_fill_each_screen():
    from aicentralv2.smart_planner.mockups import showcase_for, variants_needed

    assert variants_needed([{"id": "netflix", "group": "ctv"}]) == []
    assert variants_needed(["tiktok"]) == ["vertical"]
    assert variants_needed([{"id": "meta", "group": "social"}]) == ["vertical", "square"]
    assert variants_needed([{"id": "dv360", "group": "programmatic"}]) == ["square"]
    view = {
        "hero": {"creative_variants": {"vertical": "/static/v.png", "square": "/static/q.png"}},
        "media": {"channels": [
            {"id": "tiktok", "label": "TikTok", "pct": 40},
            {"id": "meta", "label": "Meta", "pct": 30, "group": "social"},
            {"id": "netflix", "label": "Netflix", "pct": 20, "group": "ctv"},
            {"id": "dv360", "label": "Portais", "pct": 10, "group": "programmatic"},
        ]},
    }
    images = {s["channel"]: (s["image"], s["square"]) for s in showcase_for(view, "/static/c.png")}
    assert images["TikTok"][0] == "/static/v.png"
    assert images["Meta"][0] == "/static/q.png"
    assert images["Netflix"][0] == "/static/c.png"
    assert images["Portais"] == ("/static/c.png", "/static/q.png")


def test_variants_are_dropped_when_another_art_is_shown():
    from aicentralv2.smart_planner.public_view import _creative_variants

    card = {"image_url": "/static/a.png", "variants": {"vertical": "/static/v.png"}}
    assert _creative_variants(card, "/static/a.png") == {"vertical": "/static/v.png"}
    assert _creative_variants(card, "/static/outra.png") == {}


def test_regenerate_creative_renders_only_the_variants_the_plan_uses(monkeypatch):
    from aicentralv2.smart_planner import images

    calls = []
    monkeypatch.setattr(images, "_render", lambda prompt, stem, aspect_ratio, references=None: calls.append(aspect_ratio) or f"/static/{stem}.png")
    plan = {"meta": {"client": "Animale"}, "sections": [{"cards": [{"type": "creative"}]}]}
    images.regenerate_creative(plan, channels=[{"id": "netflix", "group": "ctv"}])
    assert calls == ["16:9"]
    calls.clear()

    def flaky(prompt, stem, aspect_ratio, references=None):
        calls.append(aspect_ratio)
        if aspect_ratio == "2:3":
            raise RuntimeError("provedor fora")
        return f"/static/{stem}.png"

    monkeypatch.setattr(images, "_render", flaky)
    images.regenerate_creative(plan, channels=["tiktok", {"id": "meta", "group": "social"}])
    card = plan["sections"][0]["cards"][0]
    assert calls[0] == "16:9" and sorted(calls[1:]) == ["1:1", "2:3"]
    assert card["variants"] == {"square": "/static/animale-creative-square.png"}


def test_studio_environment_keeps_only_safe_values():
    from aicentralv2.smart_planner.viewer_envs import _env

    env = _env({"slug": "netflix", "viewer_kind": "tv", "logo_asset_ref": "javascript:x",
                "palette": {"primary": "#E50914", "canvas": "red;background:url(x)"},
                "shell_spec": {"nav": ["Início", "Séries"], "sections": [{"title": "Em alta", "items": [{"image": "https://fora/x.svg"}, {"image": "/static/c.svg"}]}]}})
    assert env["palette"] == {"primary": "#E50914"}
    assert env["logo"] == "" and env["catalog"] == "/static/c.svg" and env["row_title"] == "Em alta"


def test_screens_use_the_studio_environment_and_name_real_sizes():
    from aicentralv2.smart_planner.mockups import showcase_for

    view = {
        "viewer_envs": {"netflix": {"slug": "netflix", "nav": ["Início"]}, "g1": {"slug": "g1", "nav": ["Brasil"]}},
        "network_sites": {"sites": [{"name": "Terra"}, {"name": "g1"}]},
        "media": {"channels": [
            {"id": "netflix", "label": "Netflix", "pct": 60, "group": "ctv"},
            {"id": "dv360", "label": "Portais", "pct": 30, "group": "programmatic"},
            {"id": "spotify", "label": "Spotify", "pct": 10, "group": "audio"},
        ]},
    }
    screens = {s["channel"]: s for s in showcase_for(view, "/static/c.png")}
    assert screens["Netflix"]["env"]["slug"] == "netflix"
    assert [f["size"] for f in screens["Netflix"]["formats"]] == ["1920×1080"]
    assert screens["Portais"]["label"] == "g1" and screens["Portais"]["env"]["slug"] == "g1"
    assert [f["name"] for f in screens["Portais"]["formats"]] == ["Billboard", "Retângulo médio"]
    assert screens["Spotify"]["env"] == {} and screens["Spotify"]["formats"] == []


def test_studio_environments_failure_rolls_back_and_waits(monkeypatch):
    from aicentralv2 import db
    from aicentralv2.smart_planner import viewer_envs

    calls = {"query": 0, "rollback": 0}

    class Broken:
        def cursor(self):
            calls["query"] += 1
            raise RuntimeError("tabela ausente")

    monkeypatch.setattr(db, "get_db", lambda: Broken())
    monkeypatch.setattr(db, "recuperar_transacao_falha", lambda: calls.__setitem__("rollback", calls["rollback"] + 1))
    monkeypatch.setattr(viewer_envs, "_CACHE", {"at": 0.0, "envs": {}})
    assert viewer_envs.load() == {} and viewer_envs.load() == {}
    assert calls == {"query": 1, "rollback": 1}


def _art_plan():
    return {"meta": {"client": "Animale"}, "sections": [{"cards": [{"type": "creative"}]}]}


def test_several_arts_in_parallel_only_the_chosen_one_gets_variants(monkeypatch):
    from aicentralv2.smart_planner import images

    calls = []

    def fake(prompt, stem, aspect_ratio, references=None):
        calls.append(aspect_ratio)
        return f"/static/uploads/smart_planner/{stem}-{len(calls)}.png"

    monkeypatch.setattr(images, "_render", fake)
    plan = images.regenerate_creative(_art_plan(), channels=[{"id": "meta_ads", "group": "social"}], count=3, shape="vertical")
    card = plan["sections"][0]["cards"][0]
    assert sorted(calls[:3]) == ["9:16"] * 3
    assert sorted(calls[3:]) == ["1:1"]  # vertical já é a forma da arte; falta só a quadrada
    assert len(card["images"]) == 3 and card["image_url"] == card["images"][0]["url"]
    assert card["shape"] == "vertical" and set(card["variants"]) == {"square"}
    assert plan["public_design"]["hero"]["asset_url"] == card["image_url"]

    other = card["images"][2]["url"]
    calls.clear()
    images.use_creative(plan, other, [{"id": "netflix", "group": "ctv"}])
    assert calls == ["16:9"] and card["image_url"] == other
    assert set(card["images"][2]["variants"]) == {"horizontal"}
    calls.clear()
    images.use_creative(plan, other, [{"id": "netflix", "group": "ctv"}])
    assert calls == []  # variações já feitas não são geradas de novo


def test_use_creative_rejects_art_outside_the_plan():
    import pytest
    from aicentralv2.smart_planner import images

    with pytest.raises(ValueError):
        images.use_creative(_art_plan(), "/static/uploads/smart_planner/outro-cliente.png", [])


def test_vertical_art_uses_its_horizontal_version_on_wide_screens():
    from aicentralv2.smart_planner.mockups import showcase_for, variants_needed

    assert variants_needed([{"id": "netflix", "group": "ctv"}], "vertical") == ["horizontal"]
    view = {"hero": {"creative_variants": {"horizontal": "/static/h.png"}},
            "media": {"channels": [{"id": "netflix", "label": "Netflix", "pct": 60, "group": "ctv"}, {"id": "tiktok", "label": "TikTok", "pct": 40}]}}
    images = {s["channel"]: s["image"] for s in showcase_for(view, "/static/v.png")}
    assert images == {"Netflix": "/static/h.png", "TikTok": "/static/v.png"}


def test_saving_the_editor_keeps_the_uploaded_logo():
    from aicentralv2.smart_planner.one_page import normalize_one_page

    logo = "/static/uploads/smart_planner/upload-ref-0-abc.png"
    plan = normalize_one_page({"visual_inputs": {"logo_url": logo}, "sections": []}, {"client": "Animale"},
                              {"client": {"logo_url": "/static/crm.png"}, "hero": {"name": "Animale"}})
    assert plan["branding"]["client"]["logo_url"] == logo and plan["branding"]["hero"]["logo_url"] == logo
    other = normalize_one_page({"visual_inputs": {"logo_url": "https://fora/x.png"}, "sections": []}, {}, {"client": {"logo_url": "/static/crm.png"}})
    assert other["branding"]["client"]["logo_url"] == "/static/crm.png"


def test_editor_gallery_lists_the_plan_arts_with_their_formats():
    from aicentralv2.smart_planner.editor import _gallery

    folha = {"sections": [{"cards": [{"type": "creative", "image_url": "/a.png", "images": [
        {"url": "/a.png", "shape": "vertical", "variants": {"horizontal": "/ah.png", "square": "/aq.png"}},
        {"url": "/b.png", "shape": "horizontal", "variants": {}},
    ]}]}]}
    items = _gallery(folha)
    assert [(i["label"], i["active"], i["formats"]) for i in items[:2]] == [
        ("Arte 1", True, ["9:16", "16:9", "1:1"]), ("Arte 2", False, ["16:9"])]


def test_saving_the_editor_keeps_the_arts_and_their_versions():
    from aicentralv2.smart_planner.one_page import normalize_one_page

    card = {"type": "creative", "image_url": "/a.png", "shape": "vertical", "variants": {"square": "/q.png", "x": "/bad.png"},
            "images": [{"url": "/a.png", "shape": "vertical", "variants": {"square": "/q.png"}}, {"url": ""}]}
    plan = normalize_one_page({"sections": [{"id": "one_page", "cards": [card]}]}, {}, {})
    saved = plan["sections"][0]["cards"][0]
    assert saved["shape"] == "vertical" and saved["variants"] == {"square": "/q.png"}
    assert saved["images"] == [{"url": "/a.png", "shape": "vertical", "variants": {"square": "/q.png"}, "model": ""}]


def test_old_art_from_another_client_cannot_be_used(tmp_path, monkeypatch):
    from aicentralv2.smart_planner import images

    monkeypatch.setattr(images, "_art_dir", lambda: str(tmp_path))
    (tmp_path / "animale-creative-aa11.png").write_bytes(b"x")
    (tmp_path / "caixa-creative-bb22.png").write_bytes(b"x")
    assert images.is_creative_file("/static/uploads/smart_planner/animale-creative-aa11.png", "animale")
    assert not images.is_creative_file("/static/uploads/smart_planner/caixa-creative-bb22.png", "animale")
    assert not images.is_creative_file("/static/uploads/smart_planner/animale-creative-square-cc33.png", "animale")
