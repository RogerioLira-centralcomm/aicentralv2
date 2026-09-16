"""Preview local da mesa Camadas V2, sem o ERP completo."""

from __future__ import annotations

import io
import sys
from pathlib import Path

from flask import Blueprint, Flask, render_template_string, session
from PIL import Image
from werkzeug.datastructures import FileStorage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aicentralv2.camadas.routes import register_camadas_routes
from aicentralv2.camadas.service import CamadasService
from aicentralv2.camadas.storage import CamadasStorage
from tests.test_camadas_v2 import FakeRepository, _lifestyle

PAGE = """
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Preview Camadas V2</title>
  <link rel="stylesheet" href="/static/css/tailwind/output.css">
  <link rel="stylesheet" href="/static/css/tailwind/enterprise-system.css">
  <link rel="stylesheet" href="/static/css/camadas-v2.css?v=5">
  <style>
    body { margin: 0; background: #141816; }
  </style>
</head>
<body>
  {% include "parametros/_mc_camadas_v2.html" %}
  <script type="module" src="/static/js/camadas/index.js?v=9"></script>
  <script>
    const brand = document.getElementById("mcCv2Brand");
    if (brand && !brand.value) brand.value = "10";
  </script>
</body>
</html>
"""


def _still():
    canvas, _predict = _lifestyle()
    return canvas


def _predictor(image):
    _canvas, predict = _lifestyle()
    return predict(image)


def _image_callable(prompt, **_kwargs):
    well = Image.new("RGB", (240, 120), (18, 92, 48))
    return well


def _text_callable(messages, **_kwargs):
    return {
        "content": {
            "headline": "Grito da peça",
            "support": "É de graça!",
            "cta": "Entrar",
            "dates": "24 julho",
            "venue": "Mineirinho",
        }
    }


def build_app():
    app = Flask(
        __name__,
        template_folder=str(ROOT / "aicentralv2" / "templates"),
        static_folder=str(ROOT / "aicentralv2" / "static"),
    )
    app.config.update(SECRET_KEY="camadas-v2-preview", CAMADAS_V2_ENABLED=True)
    upload_root = ROOT / "aicentralv2" / "static" / "uploads" / "camadas"
    upload_root.mkdir(parents=True, exist_ok=True)
    storage = CamadasStorage(root=upload_root)
    service = CamadasService(
        repository=FakeRepository(),
        storage=storage,
        text_callable=_text_callable,
        predictor=_predictor,
        image_callable=_image_callable,
        spawn_job=lambda fn, job_id, creative_id: fn(job_id, creative_id),
    )
    blueprint = Blueprint("parametros", __name__, url_prefix="/parametros")
    register_camadas_routes(blueprint)
    app.register_blueprint(blueprint)

    @app.before_request
    def _login():
        session["user_id"] = 1
        session["user_type"] = "admin"
        session["user_name"] = "Preview"

    @app.route("/preview-camadas-v2")
    def preview():
        return render_template_string(PAGE)

    @app.route("/preview-camadas-v2/demo.png")
    def demo_png():
        buffer = io.BytesIO()
        _still().save(buffer, format="PNG")
        buffer.seek(0)
        return app.response_class(buffer.getvalue(), mimetype="image/png")

    app.config["CAMADAS_V2_SERVICE"] = service
    return app, service


def seed(service):
    buffer = io.BytesIO()
    _still().save(buffer, format="PNG")
    buffer.seek(0)
    service.create_creative(
        FileStorage(stream=buffer, filename="still.png", content_type="image/png"),
        {"name": "Demo", "brand_id": 10},
    )


if __name__ == "__main__":
    application, service = build_app()
    from aicentralv2.camadas import routes as camadas_routes

    camadas_routes._service = lambda: service
    print("http://127.0.0.1:55141/preview-camadas-v2")
    application.run(host="127.0.0.1", port=55141, debug=False, use_reloader=False)
