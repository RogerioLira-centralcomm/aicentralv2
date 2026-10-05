from pathlib import Path

from unittest.mock import patch

from flask import Flask, render_template, session

from aicentralv2.creative_media import studio


def test_create_screen_exposes_unified_visual_workspace():
    root = Path(__file__).resolve().parents[1]
    app = Flask(
        __name__,
        template_folder=str(root / "aicentralv2" / "templates"),
        static_folder=str(root / "aicentralv2" / "static"),
    )
    app.secret_key = "test"
    app.config.update(STUDIO_URL="https://studio.test")
    app.context_processor(lambda: {
        "product_url": lambda product, path="/": f"https://{product}.test{path}",
        "studio_url": lambda endpoint, **values: f"/{endpoint}",
    })
    with app.test_request_context("/criar", base_url="https://studio.test"):
        html = render_template("cadu_studio/create.html", mc_page="criar")

    assert 'id="mcCaduProject"' in html
    assert 'id="mcCaduBarClient"' in html
    assert ">Criar<" in html
    assert ">Editar<" in html
    assert ">Vídeos<" in html
    assert ">Biblioteca<" in html
    assert "Descreva o criativo que você quer criar" in html
    assert "Aprovar por mim" in html
    assert 'id="referenceRail"' in html
    assert 'id="deliveryPanel"' in html
    assert 'id="creationProgressTitle"' in html
    assert 'id="composerFeedback"' in html
    assert 'id="resultsView"' in html
    assert 'href="/static/css/cadu-studio-create-v2.css?v=46"' in html
    assert 'src="/static/js/cadu-studio-create-v2.js?v=45"' in html
    assert 'data-group="variations"><button class="is-selected" type="button">1</button><button type="button">2</button><button type="button">4</button>' in html
    assert "Inclui direção criativa e revisão final do prompt" in html
    assert "A peça gerada terá uma estrutura similar" in html
    assert "Formatos para Social" in html
    assert 'src="/static/js/cadu-studio-create-v2.js?v=45"' in html
    assert 'id="brandLogoDialog"' in html
    assert 'id="brandPaletteDialog"' in html
    assert 'aria-describedby="referencePreviewDescription"' in html
    assert 'id="creationProgressTime">7s' in html
    assert 'id="libraryContent"' in html
    assert 'id="studioSidebarProject"' in html
    assert 'aria-controls="libraryContent"' in html
    assert 'class="brand-identity-preview__actions"' in html


def test_create_v2_keeps_manual_review_and_progress_recoverable():
    root = Path(__file__).resolve().parents[1]
    template = (root / "aicentralv2" / "templates" / "cadu_studio" / "create.html").read_text(encoding="utf-8")
    source = (root / "aicentralv2" / "static" / "js" / "cadu-studio-create-v2.js").read_text(encoding="utf-8")
    styles = (root / "aicentralv2" / "static" / "css" / "cadu-studio-create-v2.css").read_text(encoding="utf-8")

    assert "Supermercados BH" not in template
    assert 'id="directionEditText"' in template
    assert "seedDirectionEditor(direction)" in source
    assert "approveDirectionSilently" not in source
    assert "returnToComposerAfterDiscard" in source
    assert "state.direction = null" in source
    assert "Finalizando a direção criativa." in source
    assert "window.clearInterval(generationTimer)" in source
    assert "max-height:none" in styles
    assert ".review-loading.creation-progress>.creation-progress__track" in styles
    assert 'grid-template-columns:repeat(3,minmax(0,1fr))' in styles
    assert '.studio-v2 .format-grid{grid-template-columns:repeat(2,minmax(0,1fr))' in styles
    assert '.results-grid[data-count="2"]' in styles
    assert 'margin-top:10px' in styles
    assert 'grid-template-columns:minmax(0,1fr) auto' in styles
    assert 'minimumVariationMs = 7000' in source
    assert 'creation-progress__mark' not in template
    assert 'Uma referência global define a direção de composição' in source
    assert 'const semanticRatioFor' in source
    assert 'state.originalPrompt' in source
    assert 'Requisitos obrigatórios do briefing original do usuário' in source
    assert 'const activeReferenceCount' in source
    assert 'imageCostTable' in source and 'referenceCount * 220' not in source
    assert '.reference-card .reference-check i' in styles
    assert 'height:100dvh' in styles
    assert '.reference-preview-frame{min-height:0;margin:0;padding:0;border:0' in styles
    assert "normalizePromptHex" in source
    assert "rgbToHex" in source
    assert "project_id: state.projectId, selected_logo_id: state.selectedLogoId, colors: paletteChoice" in source
    assert "brand-palette/suggest" in source
    assert "Cores da marca" in source
    assert "if (!isLogo)" in source
    assert '.brand-identity-preview:has(#brandIdentityLogo[hidden])>div' in styles
    assert '.brand-identity-preview__actions{display:flex!important' in styles


def test_quick_creation_uses_canonical_client_and_recovers_optional_history_failure():
    root = Path(__file__).resolve().parents[1]
    source = (root / "aicentralv2" / "creative_media" / "studio.py").read_text(encoding="utf-8")

    assert "modeling.repository.resolve_client_id(crm_client_id, 'crm')" in source
    assert "Studio quick image history claim unavailable" in source
    assert "history.connection.rollback()" in source


def test_project_brand_guard_rejects_a_project_not_linked_to_the_current_account():
    app = Flask(__name__)
    app.secret_key = "test"
    with app.test_request_context("/"):
        session["cliente_id"] = 91
        with patch("aicentralv2.creative_media.project_contexts.linked_project_contexts", return_value=[{"id": 7, "client_id": 12}]):
            studio._assert_project_brand_access("7", 12)
            try:
                studio._assert_project_brand_access("7", 13)
            except ValueError as error:
                assert str(error) == "Projeto não encontrado nesta marca."
            else:
                raise AssertionError("O projeto não pode ser usado com outra marca.")


def test_create_contract_binds_palette_and_image_to_the_project_context():
    source = (Path(__file__).resolve().parents[1] / "aicentralv2" / "creative_media" / "studio.py").read_text(encoding="utf-8")
    assert source.count("_assert_project_brand_access(project_id, client_id)") >= 2
    assert "_assert_project_brand_access(data.get('project_id'), client_id)" in source
    assert "brand-palette/suggest" in source
    assert "brand_identity_extraction" in source
    assert "select_brand_logo(" in source


def test_logo_palette_suggestion_uses_the_official_logo_and_rejects_unusable_colors():
    captured = {}

    def provider(messages, **kwargs):
        captured["messages"] = messages
        captured.update(kwargs)
        return {"model": "openai/gpt-5-nano", "message": {"content": '{"colors":["#7428C8","#FFFFFF","#20123A","invalid"]}'}, "usage": {"total_tokens": 120}}

    colors, result = studio._logo_palette_suggestion(
        {"logo_url": "https://studio.test/static/brands/nubank-logo.png", "assets": {"logo": []}},
        provider,
    )

    assert colors == ["#7428C8", "#FFFFFF", "#20123A"]
    assert result["model"] == "openai/gpt-5-nano"
    assert captured["model"] == "openai/gpt-5-nano"
    assert captured["messages"][1]["content"][1]["image_url"]["url"].endswith("nubank-logo.png")


def test_logo_identity_suggestion_keeps_typography_as_a_cautious_direction():
    def provider(_messages, **_kwargs):
        return {"message": {"content": '{"colors":["#7428C8","#FFFFFF","#20123A"],"fonts":[{"role":"display","classification":"sans geométrica","confidence":0.72}]}'}}

    identity, _ = studio._logo_identity_suggestion({"logo_url": "https://studio.test/logo.png"}, provider)

    assert identity["colors"][0] == "#7428C8"
    assert identity["fonts"] == [{"family": "", "classification": "sans geométrica", "role": "display", "source": "logo_analysis", "confidence": 0.72}]


def test_logo_identity_suggestion_accepts_a_monochrome_official_logo():
    def provider(_messages, **_kwargs):
        return {"message": {"content": '{"colors":["#111111"],"fonts":[]}'}}

    identity, _ = studio._logo_identity_suggestion({"logo_url": "https://studio.test/logo.png"}, provider)

    assert identity["colors"] == ["#111111"]


def test_global_feed_references_are_compact_webp_assets():
    root = Path(__file__).resolve().parents[1]
    reference_dir = root / "aicentralv2" / "static" / "images" / "cadu" / "studio" / "references" / "feed"
    references = sorted(reference_dir.glob("feed-mask-*.webp"))

    assert len(references) == 10
    assert not list(reference_dir.glob("feed-mask-*.png"))
    assert all(reference.stat().st_size < 100_000 for reference in references)


def test_square_300_references_are_compact_webp_assets():
    root = Path(__file__).resolve().parents[1]
    reference_dir = root / "aicentralv2" / "static" / "images" / "cadu" / "studio" / "references" / "square-300x300"
    references = sorted(reference_dir.glob("square-mask-*.webp"))

    assert len(references) == 6
    assert not list(reference_dir.glob("square-mask-*.png"))
    assert all(reference.stat().st_size < 100_000 for reference in references)


def test_iab_300x250_reference_is_a_compact_webp_asset():
    root = Path(__file__).resolve().parents[1]
    reference_dir = root / "aicentralv2" / "static" / "images" / "cadu" / "studio" / "references" / "iab-300x250"
    references = sorted(reference_dir.glob("iab-300x250-mask-*.webp"))

    assert len(references) == 1
    assert not list(reference_dir.glob("iab-300x250-mask-*.png"))
    assert all(reference.stat().st_size < 100_000 for reference in references)


def test_create_frontend_connects_persistent_session_lifecycle():
    root = Path(__file__).resolve().parents[1]
    source = (root / "aicentralv2" / "static" / "js" / "mc-studio-create.js").read_text(encoding="utf-8")

    assert "/format-lab/studio/sessions" in source
    assert "expected_revision:state.sessionRevision" in source
    assert "/accept`" in source
    assert "/handoff`" in source
    assert "/finalize`" in source
    assert "/continue`" in source
    assert "studio_session_id" in source
    assert "is-read-only" in source
    assert "/format-lab/studio/prompt/optimize" in source
    assert "original_prompt:state.originalPrompt" in source
    assert "optimized_prompt:state.optimizedPrompt" in source


def test_create_frontend_keeps_csrf_and_json_headers_when_request_options_are_spread():
    root = Path(__file__).resolve().parents[1]
    source = (root / "aicentralv2" / "static" / "js" / "mc-studio-create.js").read_text(encoding="utf-8")
    request_start = source.index("async function request(url, options = {}, retried = false)")
    request_body = source[request_start:source.index("    const payload", request_start)]

    assert request_body.index("...options,") < request_body.index("headers:")
    assert "'X-Trocr-CSRF-Token': csrf" in request_body
    assert "...(options.headers || {})" in request_body
    assert "setSaveStatus('Preparando criação…', true)" in source
    assert "title: 'Em andamento'" in source
    assert "/attach-project" in source
    assert "Conversa e decisões vinculadas ao projeto." in source


def test_studio_desks_keep_context_and_stage_controls_aligned():
    root = Path(__file__).resolve().parents[1]
    create_css = (root / "aicentralv2" / "static" / "css" / "cadu-studio-create.css").read_text(encoding="utf-8")
    frame_css = (root / "aicentralv2" / "static" / "css" / "cadu-studio-frame.css").read_text(encoding="utf-8")

    assert ".studio-workbar__center{position:absolute;left:50%;top:50%" in create_css
    assert "transform:translate(-50%,-50%)" in create_css
    assert ".trocr-product .trocr-editor .mc-trocr-canvas-bar" in frame_css
    assert ".mc-video-studio .mc-cadu-video-stage-bar" in frame_css
    assert ".studio-chat .studio-new-draft" in create_css


def test_trocr_editor_uses_the_react_workspace_assets():
    root = Path(__file__).resolve().parents[1]
    template = (root / "aicentralv2" / "templates" / "cadu_studio" / "trocr.html").read_text(encoding="utf-8")

    assert "cadu_studio/editor/react/app.css') }}?v={{ static_fingerprint('cadu_studio/editor/react/app.css')" in template
    assert "cadu_studio/editor/react/app.js') }}?v={{ static_fingerprint('cadu_studio/editor/react/app.js')" in template
    assert 'id="cadu-studio-editor-root"' in template
    assert "trocr-editor.css" not in template


def test_edit_quote_is_one_image_generation_at_the_catalog_price_for_every_quality():
    from aicentralv2.creative_format_lab.swap import quote_swap
    from aicentralv2.creative_media.studio_costs import image_credits
    base = {'instruction': 'Troque o fundo', 'aspect_ratio': '4:5', 'reference': 'studio-editor'}

    draft = quote_swap({**base, 'quality': 'draft'})['estimated_tokens']
    high = quote_swap({**base, 'quality': 'high'})['estimated_tokens']

    assert draft == high == image_credits(0), "uma edição custa o mesmo que uma criação"


def test_edit_quote_route_is_registered_for_the_editor():
    from aicentralv2.creative_media import studio
    rules = []

    class Recorder:
        def add_url_rule(self, rule, **kwargs):
            rules.append(rule)

    studio.register_studio_routes(Recorder())

    assert '/api/format-lab/studio/edit-quote' in rules


def test_static_fingerprint_changes_with_the_file_content(tmp_path):
    from aicentralv2 import static_fingerprint
    bundle = tmp_path / "app.js"
    bundle.write_text("one")
    first = static_fingerprint(str(tmp_path), "app.js")

    bundle.write_text("two!")

    assert first != static_fingerprint(str(tmp_path), "app.js")
    assert static_fingerprint(str(tmp_path), "missing.js") == "0"


def test_editor_audio_and_navbar_bundles_are_versioned_by_content():
    from pathlib import Path
    templates = Path(__file__).parents[1] / "aicentralv2" / "templates" / "cadu_studio"
    for name in ("trocr.html", "audio.html", "_context_bar.html"):
        html = (templates / name).read_text()
        assert "static_fingerprint(" in html, name
        assert "react/app.css') }}?v=1" not in html and "app.js') }}?v=1" not in html, name


def test_director_routes_start_with_haiku_on_openrouter_and_fall_back_to_openai():
    from aicentralv2.creative_media import studio_create
    routes = studio_create.director_routes()
    assert routes[0] == ("openrouter", "anthropic/claude-haiku-4.5")
    assert ("openai", "gpt-5-nano") in routes and len(routes) == len(set(routes))


def test_director_prompt_is_never_cut_mid_word():
    from aicentralv2.creative_media.studio_create import whole_words
    long = "Primeira frase completa. " * 20 + "palavracomprida final"
    cut = whole_words(long, 120)
    assert cut.endswith(".") and len(cut) <= 120
    assert whole_words("um dois três quatro", 12) == "um dois"
    assert whole_words("curto", 50) == "curto"


def test_playbook_lists_the_exact_copy_unless_the_image_is_text_free():
    from aicentralv2.creative_media import studio_playbook
    briefing = "Título: Sua conta de luz\nTexto de apoio: NO WHATSAPP · 2ª via sem sair de casa.\nBotão: Chame agora"
    copy = ["Sua conta de luz", *studio_playbook.support_copy(briefing), "Chame agora"]
    lines = studio_playbook.prompt_lines(copy, text_free=False)
    assert '"NO WHATSAPP"\n"2ª via sem sair de casa."' in lines[0] and "DO NOT ADD" in lines[-1]
    assert not any("EXACT COPY" in line for line in studio_playbook.prompt_lines(copy, text_free=True))


def test_display_unit_without_composition_gets_the_default_band_layout():
    from aicentralv2.creative_media import ad_masks, studio_create
    data = {"original_prompt": "Título: Sua conta de luz\nBotão: Chame agora",
            "brand_context": {"logo_url": "/static/uploads/logo.webp"}}
    reference = studio_create.display_mask_reference(data, [], 300, 250, "branded_creative")
    spec = ad_masks.spec_from_url(reference["url"])
    assert spec["format"] == "iab-300x250" and spec["family"] == "faixa-inferior" and spec["cta"] and spec["logo"] != "none"
    no_cta = studio_create.display_mask_reference({"original_prompt": "Título: Só título"}, [], 300, 250, "neutral_asset")
    assert ad_masks.spec_from_url(no_cta["url"])["cta"] is False
    with_support = studio_create.display_mask_reference({**data, "original_prompt": data["original_prompt"] + "\nTexto de apoio: NO WHATSAPP"},
                                                        [], 300, 250, "branded_creative")
    assert ad_masks.spec_from_url(with_support["url"])["family"] == "faixa-inferior"
    assert studio_create.display_mask_reference(data, [], 1080, 1350, "branded_creative") is None
    assert studio_create.display_mask_reference({**data, "auto_mask": False}, [], 300, 250, "branded_creative") is None
    assert studio_create.display_mask_reference({"original_prompt": "sem cópia"}, [], 300, 250, "branded_creative") is None


def test_composer_sets_support_under_the_headline_and_a_legible_cta():
    from PIL import Image
    from aicentralv2.creative_media import ad_masks, banner_compose
    spec = next(item for item in ad_masks.served_specs() if item["id"] == "iab-300x250:split:bottom-right:cta")
    busy = Image.effect_noise((300, 250), 90).convert("RGB")
    image, layers = banner_compose.render_text_layers(busy, spec, "Sua conta de luz", "Chame agora", {}, ["#0F6C58", "#041E18"],
                                                      support=["NO WHATSAPP", "2ª via sem sair de casa."])
    kinds = {layer["type"]: layer for layer in layers}
    assert set(kinds) == {"headline", "support", "cta"} and kinds["cta"]["text"] == "Chame agora"
    assert banner_compose.SUPPORT_MIN_PX <= kinds["support"]["size_px"] < kinds["headline"]["size_px"]
    # The side panel is painted in the brand's darkest color, whatever the model drew there.
    px, py, pw, ph = spec["zones"]["panel"]
    assert image.getpixel((round(px * 300) + 2, round(py * 250) + 2))[:3] == (0x04, 0x1E, 0x18)
    band = next(item for item in ad_masks.served_specs() if item["id"] == "iab-300x250:faixa-inferior:bottom-right:cta")
    _, tight = banner_compose.render_text_layers(busy, band, "Sua conta de luz", "Chame agora", {}, ["#041E18"],
                                                 support=["NO WHATSAPP", "2ª via sem sair de casa."])
    assert all(layer["size_px"] >= banner_compose.SUPPORT_MIN_PX for layer in tight if layer["type"] == "support")
    assert kinds["cta"]["box"][3] * 250 >= 250 * 0.085 - 1
    x, y, w, h = kinds["cta"]["box"]
    assert x >= 0.06 and y + h <= 0.94, "CTA dentro da margem segura"


def test_cta_never_grows_under_the_logo_and_tall_units_keep_a_modest_button():
    from PIL import Image
    from aicentralv2.creative_media import ad_masks, banner_compose
    band = next(item for item in ad_masks.served_specs() if item["id"] == "iab-300x250:faixa-inferior:bottom-right:cta")
    _, layers = banner_compose.render_text_layers(Image.new("RGB", (300, 250), "white"), band, "Título", "Peça já o seu cartão de crédito agora",
                                                  {}, ["#041E18"])
    cta = next(layer for layer in layers if layer["type"] == "cta")
    assert cta["box"][0] + cta["box"][2] <= band["zones"]["logo"][0] and cta["text"] == "Peça já o seu cartão de crédito agora"
    tall = next(item for item in ad_masks.served_specs() if item["format"] == "iab-300x600" and item["cta"])
    _, tall_layers = banner_compose.render_text_layers(Image.new("RGB", (300, 600), "white"), tall, "Título", "Saiba mais", {}, ["#041E18"])
    # The button never grows past the larger of its zone and 8.5% of the short side (300 px here, not 600).
    height_px = next(layer for layer in tall_layers if layer["type"] == "cta")["box"][3] * 600
    assert height_px <= max(tall["zones"]["cta"][3] * 600, 300 * 0.085) + 1


def test_every_ad_size_is_accepted_and_small_display_units_get_code_typesetting():
    from aicentralv2 import creative_format_registry as registry
    from aicentralv2.creative_media import studio_create
    sizes = {(item["width"], item["height"]) for item in registry.catalog_entries()}
    for size in [(320, 50), (300, 50), (468, 60), (88, 31), (300, 1050), (120, 600), (336, 280), (970, 90)]:
        assert size in sizes
        assert min(size) >= studio_create.MIN_SIDE_PX
    data = {"original_prompt": "Título: Conta no app\nBotão: Baixe já"}
    for width, height in [(320, 50), (300, 50), (468, 60), (970, 90), (336, 280), (300, 1050), (120, 600)]:
        assert studio_create.display_mask_reference(data, [], width, height, "neutral_asset"), (width, height)


def test_new_formats_do_not_steal_existing_aliases():
    from collections import Counter
    from aicentralv2 import creative_format_registry as registry
    names = Counter(name for item in registry.catalog_entries() for name in [item["format_key"], *item["aliases"]])
    assert not [name for name, count in names.items() if count > 1]
    assert registry.entry("iab-wide-skyscraper")["width"] == 160
    assert registry.entry("iab-120x600")["width"] == 120


def test_copy_budget_shrinks_with_the_piece():
    from aicentralv2.creative_media.studio_playbook import copy_budget
    assert copy_budget(88, 31)["tamanho"] == "micro" and copy_budget(88, 31)["cta_max_palavras"] == 0
    assert copy_budget(320, 50)["tamanho"] == "faixa" and copy_budget(728, 90)["apoio_max_linhas"] == 0
    assert copy_budget(300, 250)["tamanho"] == "pequeno" and copy_budget(300, 250)["apoio_max_linhas"] == 0
    assert copy_budget(300, 600)["tamanho"] == "medio" and copy_budget(300, 600)["apoio_max_linhas"] == 1
    assert copy_budget(1080, 1350)["tamanho"] == "grande" and copy_budget(0, 0)["tamanho"] == "grande"


def test_director_copy_is_kept_only_when_it_cuts_the_briefing():
    from aicentralv2.creative_media.studio_playbook import copy_budget, edited_copy
    briefing = "Título: Outlet com +20% EXTRA em toda a loja\nTexto de apoio: Use o cupom DIADOCLIENTE · Frete grátis\nBotão: Comprar agora"
    kept = edited_copy({"headline": "Outlet +20% EXTRA", "support": ["Use o cupom DIADOCLIENTE · Frete grátis"], "cta": "Comprar agora"},
                       briefing, copy_budget(300, 600))
    assert kept == {"headline": "Outlet +20% EXTRA", "support": ["Use o cupom DIADOCLIENTE"], "cta": "Comprar agora"}
    long_cta = edited_copy({"headline": "Outlet +20% EXTRA", "cta": "Comprar agora em toda a loja"}, briefing + " em toda a loja",
                           copy_budget(300, 250))
    assert long_cta["cta"] == "Comprar agora"
    invented = edited_copy({"headline": "Mega liquidação imperdível", "cta": "Aproveite"}, briefing, copy_budget(300, 250))
    assert invented is None
    no_cta = edited_copy({"headline": "Outlet +20%", "cta": "Comprar agora"}, briefing, copy_budget(88, 31))
    assert no_cta["cta"] == "" and no_cta["support"] == []


def test_director_copy_that_drops_the_offer_number_is_refused():
    from aicentralv2.creative_media.studio_playbook import copy_budget, edited_copy
    briefing = "Título: Semana do Cliente Reserva com +20% EXTRA\nBotão: Comprar agora"
    assert edited_copy({"headline": "Semana do Cliente Reserva", "cta": "Comprar agora"}, briefing, copy_budget(300, 250)) is None
    assert edited_copy({"headline": "Semana do Cliente +20% EXTRA", "cta": "Comprar agora"}, briefing,
                       copy_budget(300, 250))["headline"] == "Semana do Cliente +20% EXTRA"


def test_copy_labels_read_the_same_on_one_line_or_many():
    from aicentralv2.creative_media.banner_compose import extract_copy
    from aicentralv2.creative_media.studio_playbook import support_copy
    flat = "Anúncio. Título: Sua conta de luz no WhatsApp Texto de apoio: 2ª via · Religação Botão: Chame agora"
    assert extract_copy(flat) == ("Sua conta de luz no WhatsApp", "Chame agora")
    assert support_copy(flat) == ["2ª via", "Religação"]


def test_the_offer_line_moves_into_the_headline_when_there_is_no_room_for_support():
    from aicentralv2.creative_media.studio_playbook import copy_budget, edited_copy, with_offer
    assert with_offer("Outlet com", ["+20% EXTRA", "Use o cupom DIADOCLIENTE"], 0) == ("Outlet com +20% EXTRA", [])
    assert with_offer("Outlet com", ["+20% EXTRA", "Frete grátis"], 1) == ("Outlet com", ["+20% EXTRA"])
    briefing = "Título: Outlet com\nTexto de apoio: +20% EXTRA · Use o cupom DIADOCLIENTE\nBotão: Fale com a gente"
    copy = edited_copy({"headline": "Outlet com", "support": ["+20% EXTRA"], "cta": "Fale com a gente"}, briefing, copy_budget(300, 250))
    assert copy["headline"] == "Outlet com +20% EXTRA" and copy["cta"] == "Fale com a gente"


def test_a_long_button_is_never_cut_to_a_lone_verb():
    from aicentralv2.creative_media.studio_playbook import _trim_words
    assert _trim_words("Fale com a gente", 3) == "Fale com a gente"
    assert _trim_words("Comprar agora no site", 3) == "Comprar agora"


def test_composer_makes_the_offer_the_hero_and_keeps_copy_order():
    from PIL import Image
    from aicentralv2.creative_media import ad_masks, banner_compose
    assert banner_compose.split_offer("Outlet com +20% EXTRA") == ("Outlet com", "+20% EXTRA")
    assert banner_compose.split_offer("Semana +20% EXTRA no outlet") == ("Semana +20% EXTRA no outlet", "")
    spec = next(item for item in ad_masks.served_specs() if item["id"] == "iab-300x600:faixa-inferior:bottom-right:cta")
    _, layers = banner_compose.render_text_layers(Image.new("RGB", (300, 600), "white"), spec, "Outlet com +20% EXTRA",
                                                  "Comprar agora", {}, ["#000000", "#A56E45", "#C99A3C"])
    headline = next(layer for layer in layers if layer["type"] == "headline")
    assert headline["hero"] == "+20% EXTRA" and headline["size_px"] >= 2 * headline["kicker_size_px"]
    assert headline["text"] == "OUTLET COM +20% EXTRA"  # as drawn: the reviewer checks what is on the piece


def test_an_offer_the_director_cut_from_the_support_comes_back_as_the_hero():
    from aicentralv2.creative_media.studio_playbook import copy_budget, edited_copy
    briefing = "Título: Outlet com\nTexto de apoio: +20% EXTRA · Use o cupom DIADOCLIENTE.\nBotão: Comprar agora"
    copy = edited_copy({"headline": "Outlet com", "support": [], "cta": "Comprar agora"}, briefing, copy_budget(300, 250))
    assert copy["headline"] == "Outlet com +20% EXTRA"


def test_the_highlight_is_protected_and_does_not_count_against_the_budget():
    from aicentralv2.creative_media.studio_playbook import copy_budget, edited_copy, fits
    briefing = "Título: Sua conta de luz\nDestaque: NA PALMA DA MÃO\nBotão: Acesse agora"
    copy = edited_copy({"headline": "Sua conta de luz", "support": [], "cta": "Acesse agora"}, briefing, copy_budget(300, 250))
    assert copy["headline"] == "Sua conta de luz NA PALMA DA MÃO"
    assert fits(copy, copy_budget(300, 250), briefing) and not fits(copy, copy_budget(300, 250))


def test_an_offer_already_in_the_headline_is_not_glued_in_again():
    from aicentralv2.creative_media.studio_playbook import copy_budget, edited_copy
    briefing = "Título: Outlet com\nTexto de apoio: +20% EXTRA · Use o cupom DIADOCLIENTE.\nBotão: Comprar agora"
    copy = edited_copy({"headline": "Outlet +20% EXTRA", "support": ["+20% EXTRA Use o cupom DIADOCLIENTE."],
                        "cta": "Comprar agora"}, briefing, copy_budget(300, 250))
    assert copy["headline"] == "Outlet +20% EXTRA"


def test_a_capital_highlight_closing_the_headline_is_the_hero():
    from aicentralv2.creative_media.banner_compose import split_offer
    assert split_offer("Sua conta de luz NA PALMA DA MÃO") == ("Sua conta de luz", "NA PALMA DA MÃO")
    assert split_offer("SEMANA DO CLIENTE") == ("SEMANA DO CLIENTE", "")


def test_an_opaque_logo_loses_its_flat_background_and_keeps_the_artwork():
    from PIL import Image, ImageDraw
    from aicentralv2.creative_media.studio_create import _without_flat_background
    logo = Image.new("RGBA", (200, 100), (71, 112, 76, 255))
    ImageDraw.Draw(logo).rectangle((40, 30, 160, 70), fill=(10, 10, 10, 255))
    keyed = _without_flat_background(logo)
    assert keyed.getpixel((2, 2))[3] == 0 and keyed.getpixel((100, 50))[3] == 255
    photo = Image.effect_noise((200, 100), 80).convert("RGBA")
    assert _without_flat_background(photo) is photo


def test_a_short_acronym_at_the_end_is_not_a_hero():
    from aicentralv2.creative_media.banner_compose import split_offer
    assert split_offer("Conta digital do BDMG PJ") == ("Conta digital do BDMG PJ", "")


def test_a_capital_highlight_with_an_offer_is_the_hero_and_the_title_stays_whole():
    from aicentralv2.creative_media.banner_compose import split_offer
    assert split_offer("Leve do primeiro ao último passo 10% OFF NA 1ª COMPRA") == (
        "Leve do primeiro ao último passo", "10% OFF NA 1ª COMPRA")
    assert split_offer("Joias para o Dia das Mães ATÉ 30% OFF") == ("Joias para o Dia das Mães", "ATÉ 30% OFF")


def test_the_highlight_leaves_the_support_and_becomes_the_hero():
    from aicentralv2.creative_media.studio_playbook import copy_budget, edited_copy
    briefing = "Título: Para quem brilha em você\nDestaque: DIA DAS MÃES\nBotão: Ver coleção"
    copy = edited_copy({"headline": "Para quem brilha em você", "support": ["DIA DAS MÃES"], "cta": "Ver coleção"},
                       briefing, copy_budget(300, 600))
    assert copy["headline"] == "Para quem brilha em você DIA DAS MÃES" and copy["support"] == []


def test_a_logo_badge_in_a_brand_color_keeps_its_square():
    from PIL import Image, ImageDraw
    from aicentralv2.creative_media.studio_create import _without_flat_background
    badge = Image.new("RGBA", (200, 200), (210, 40, 40, 255))
    ImageDraw.Draw(badge).rectangle((50, 80, 150, 120), fill=(255, 255, 255, 255))
    assert _without_flat_background(badge, palette=["#D22828"]) is badge
    assert _without_flat_background(badge, palette=["#000000"]).getpixel((2, 2))[3] == 0


def test_a_support_line_that_repeats_the_headline_is_dropped():
    from aicentralv2.creative_media.studio_playbook import copy_budget, edited_copy
    briefing = "Título: Sabor que junta gente\nDestaque: 2 POR R$ 9\nBotão: Aproveite"
    copy = edited_copy({"headline": "Sabor que junta gente 2 POR R$ 9", "support": ["2 POR R$ 9"], "cta": "Aproveite"},
                       briefing, copy_budget(300, 600))
    assert copy["headline"] == "Sabor que junta gente 2 POR R$ 9" and copy["support"] == []


def test_an_svg_logo_is_rasterized_and_never_sent_to_the_model_as_a_reference():
    import base64
    import io
    import sys
    import types
    from PIL import Image
    from aicentralv2.creative_media import studio_create
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="10"><rect width="40" height="10"/></svg>'
    png = io.BytesIO()
    Image.new("RGBA", (40, 10), (0, 0, 0, 255)).save(png, "PNG")
    fake = types.SimpleNamespace(svg2png=lambda bytestring, output_width, unsafe: png.getvalue())
    with patch.dict(sys.modules, {"cairosvg": fake}):
        logo = studio_create._open_trimmed_logo("data:image/svg+xml;base64," + base64.b64encode(svg).decode())
    assert logo is not None and logo.size == (40, 10)
    assert studio_create.official_logo_reference({"logo_url": "https://studio.example/static/x/logo.svg"}) is None


def test_a_highlight_the_director_mangled_is_restored_in_place_not_repeated():
    from aicentralv2.creative_media.studio_playbook import copy_budget, edited_copy
    briefing = "Título: Sabor que junta gente\nDestaque: 2 POR R$ 9\nBotão: Aproveite"
    copy = edited_copy({"headline": "Sabor que junta gente 2 POR R 9", "support": [], "cta": "Aproveite"}, briefing,
                       copy_budget(300, 600))
    assert copy["headline"] == "Sabor que junta gente 2 POR R$ 9"
