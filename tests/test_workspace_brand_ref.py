import pytest
from flask import Flask, url_for

from aicentralv2.cadu_workspace.brand_ref import BrandRefConverter, decode_brand_ref, encode_brand_id


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret"
    app.url_map.converters["brand"] = BrandRefConverter

    @app.get("/marcas/<brand:brand_id>")
    def detail(brand_id):
        return {"id": brand_id}

    return app


def test_reference_round_trips_and_hides_the_database_id(app):
    with app.app_context():
        for brand_id in (1, 50, 51, 123456, (1 << 40) - 1):
            token = encode_brand_id(brand_id)
            assert token.startswith("b") and not token.isdigit()
            assert str(brand_id) not in token or brand_id < 10
            assert decode_brand_ref(token) == brand_id
        assert encode_brand_id(50) != encode_brand_id(51)


def test_reference_depends_on_the_secret_key(app):
    with app.app_context():
        token = encode_brand_id(50)
    app.config["SECRET_KEY"] = "other-secret"
    with app.app_context():
        assert decode_brand_ref(token) != 50


def test_routes_emit_tokens_and_accept_tokens_and_legacy_numbers(app):
    client = app.test_client()
    with app.test_request_context():
        url = url_for("detail", brand_id=50)
    assert url != "/marcas/50" and url.startswith("/marcas/b")
    assert client.get(url).get_json() == {"id": 50}
    assert client.get("/marcas/50").get_json() == {"id": 50}
    assert client.get("/marcas/0").status_code == 404
    assert client.get("/marcas/bzzzzzzzzzzzz").status_code == 404
    assert client.get("/marcas/not-a-token").status_code == 404
