from io import BytesIO
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_workspace import media_creation_service as service


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    with app.app_context():
        yield app


def _context(client_id=7, user_id=3):
    return SimpleNamespace(client_id=client_id, user_id=user_id)


def _png():
    return FileStorage(stream=BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64), filename="edit.png", content_type="image/png")


def test_prepared_upload_is_bound_to_the_requesting_account(app):
    prepared = service.prepare_edit_source_upload(_context())
    assert prepared["field"] == "file" and prepared["upload_token"]
    with pytest.raises(BadRequest):
        service.save_edit_source_upload(_context(client_id=8), prepared["upload_token"], _png())
    with pytest.raises(BadRequest):
        service.save_edit_source_upload(_context(), "token-invalido", _png())


def test_upload_returns_a_studio_source_url_accepted_by_edit_image(app, tmp_path, monkeypatch):
    from aicentralv2 import creative_modeling_storage as storage

    monkeypatch.setattr(storage, "_root", lambda name: tmp_path)
    app.config["STUDIO_BASE_URL"] = ""
    prepared = service.prepare_edit_source_upload(_context())
    saved = service.save_edit_source_upload(_context(), prepared["upload_token"], _png())
    assert saved["status"] == "uploaded"
    assert saved["source_url"].startswith("/static/uploads/creative_")
    assert list(tmp_path.iterdir())
