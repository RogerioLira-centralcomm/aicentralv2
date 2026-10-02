"""O Editor (React) só chama rotas do Studio: token do Studio no cabeçalho X-Trocr-CSRF-Token."""
from pathlib import Path

from flask import Flask

from aicentralv2.creative_media.studio_csrf import HEADER, SESSION_KEY, studio_csrf_required

ROOT = Path(__file__).resolve().parents[1]


def test_editor_requests_use_the_header_the_studio_validates():
    api = (ROOT / "frontend/cadu-studio-editor/api.js").read_text(encoding="utf-8")
    assert "'X-CSRF-Token'" not in api
    assert api.count(f"'{HEADER}': csrf") == 3


def test_editor_page_receives_the_studio_token():
    routes = (ROOT / "aicentralv2/creative_modeling_routes.py").read_text(encoding="utf-8")
    assert 'mc_trocr_csrf=studio_csrf_token() if page in {"criar", "video", "trocar"} else ""' in routes
    assert "trocr_csrf_token" not in routes


def test_studio_guard_accepts_the_editor_request_shape():
    app = Flask(__name__)
    app.secret_key = "test"

    @app.post("/guarded")
    @studio_csrf_required
    def guarded():
        return "ok"

    client = app.test_client()
    with client.session_transaction() as sess:
        sess[SESSION_KEY] = "studio-token"
        sess["trocr_csrf_token"] = "trocr-token"
    assert client.post("/guarded", headers={HEADER: "studio-token"}).status_code == 200
    assert client.post("/guarded", headers={"X-CSRF-Token": "trocr-token"}).status_code == 403


def test_quote_is_available_to_studio_accounts_not_only_staff():
    routes = (ROOT / "aicentralv2/creative_modeling_routes.py").read_text(encoding="utf-8")
    assert "@studio_or_admin_required_api\ndef api_format_lab_quote():" in routes
