from pathlib import Path

from flask import Flask, render_template


def test_create_screen_keeps_project_as_the_only_visible_context_selector():
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
    assert 'mc-cadu-brand--internal' in html
    assert ">Criar<" in html
    assert ">Editar<" in html
    assert ">Vídeos<" in html
    assert ">Biblioteca<" in html
    assert "Gerar 5 direções" in html
    assert "0 de 2" in html
    assert "Formatos IAB" in html
    assert "Abrir no editor completo" in html
    assert "Histórico do projeto" in html
