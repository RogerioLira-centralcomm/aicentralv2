from pathlib import Path

from flask import Flask, render_template


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
    assert "Gerar 5 direções" in html
    assert 'id="studioBoardWorld"' in html
    assert '>Aprovadas<' in html
    assert '>Retiradas<' in html
    assert 'id="studioBindings"' in html
    assert 'id="studioMaskTools"' in html
    assert 'id="studioChatToggle"' in html
    assert 'id="studioChatClose"' in html
    assert "Referência de composição" not in html  # Roles are rendered from JS.
    assert "Editor avançado" in html
    assert "Rascunho pessoal" in html
