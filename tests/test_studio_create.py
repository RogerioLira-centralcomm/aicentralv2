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
    assert 'href="/static/css/cadu-studio-create-v2.css?v=39"' in html
    assert 'src="/static/js/cadu-studio-create-v2.js?v=37"' in html
    assert 'data-group="variations"><button class="is-selected" type="button">1</button><button type="button">2</button><button type="button">4</button>' in html
    assert "Inclui direção criativa e revisão final do prompt" in html
    assert "A peça gerada terá uma estrutura similar" in html
    assert "Formatos para Social" in html
    assert 'src="/static/js/cadu-studio-create-v2.js?v=37"' in html
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
    assert 'referenceCount * 220' in source
    assert '.reference-card .reference-check i' in styles
    assert 'height:100dvh' in styles
    assert '.reference-preview-frame{min-height:0;margin:0;padding:0;border:0' in styles
    assert "normalizePromptHex" in source
    assert "rgbToHex" in source
    assert "project_id: state.projectId, colors: paletteChoice" in source
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

    assert "cadu_studio/editor/react/app.css') }}?v=1" in template
    assert "cadu_studio/editor/react/app.js') }}?v=1" in template
    assert 'id="cadu-studio-editor-root"' in template
    assert "trocr-editor.css" not in template
