import pytest
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_workspace import brand_site_inspector as inspector


class Response:
    def __init__(self, status=200, content_type="text/html", body=b"", location="", peer="93.184.216.34"):
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        if location:
            self.headers["Location"] = location
        self._body = body
        sock = type("Sock", (), {"getpeername": lambda self: (peer, 443)})()
        self.raw = type("Raw", (), {"_connection": type("Connection", (), {"sock": sock})()})()

    def iter_content(self, _size):
        yield self._body

    def close(self):
        pass


class Session:
    def __init__(self, responses):
        self.responses = list(responses)

    def get(self, *_args, **_kwargs):
        return self.responses.pop(0)


def public_dns(monkeypatch):
    monkeypatch.setattr(inspector.socket, "getaddrinfo", lambda *_args, **_kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))])


def test_private_brand_site_is_blocked(monkeypatch):
    monkeypatch.setattr(inspector.socket, "getaddrinfo", lambda *_args, **_kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(BadRequest, match="precisa ser público"):
        inspector.inspect_brand_site("http://localhost")


def test_site_inspection_discovers_and_validates_logo(monkeypatch):
    public_dns(monkeypatch)
    html = b'<html><head><title> Acme Brasil </title></head><body><img class="brand-logo" src="/logo.svg"></body></html>'
    result = inspector.inspect_brand_site("acme.example", session=Session([
        Response(body=html), Response(content_type="image/svg+xml", body=b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'),
    ]))
    assert result["ready_for_analysis"] is True
    assert result["title"] == "Acme Brasil"
    assert result["suggested_logo_url"] == "https://acme.example/logo.svg"
    assert result["logo_candidates"][0]["same_domain"] is True


def test_explicit_logo_must_return_image(monkeypatch):
    public_dns(monkeypatch)
    result = inspector.inspect_brand_site("https://acme.example", logo_url="https://acme.example/logo",
                                          session=Session([Response(body=b"<html></html>"), Response(content_type="text/plain")]))
    assert result["explicit_logo"]["valid_image"] is False
    assert "não retornou uma imagem válida" in result["warnings"][0]


def test_connected_private_ip_is_rejected_after_public_dns(monkeypatch):
    public_dns(monkeypatch)
    with pytest.raises(BadRequest, match="não corresponde"):
        inspector.inspect_brand_site("https://acme.example", session=Session([Response(peer="127.0.0.1")]))


def test_invalid_port_is_a_domain_error(monkeypatch):
    public_dns(monkeypatch)
    with pytest.raises(BadRequest):
        inspector.inspect_brand_site("https://acme.example:not-a-port")


def test_html_without_content_type_can_be_analyzed(monkeypatch):
    public_dns(monkeypatch)
    result = inspector.inspect_brand_site("https://acme.example", session=Session([
        Response(content_type="", body=b"<html><title>Acme</title></html>"),
    ]))
    assert result["ready_for_analysis"] is True
