"""Canonical product URLs and host-aware entry routing for the Cadu family."""

from __future__ import annotations

from urllib.parse import unquote, urlparse

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import current_app, make_response, redirect, render_template, request, send_file, url_for


PRODUCT_CONFIG_KEYS = {
    "cadu": "CADU_URL",
    "centralx": "CENTRALX_URL",
    "studio": "STUDIO_URL",
    "skills": "SKILLS_URL",
    "planner": "PLANNER_URL",
    "connect": "CONNECT_URL",
    "workspace": "WORKSPACE_URL",
    "auth": "AUTH_URL",
}


def product_url(product: str, path: str = "/") -> str:
    """Build a URL without allowing callers to replace the configured host."""
    key = PRODUCT_CONFIG_KEYS.get(str(product).strip().lower())
    if not key:
        raise KeyError(f"Produto desconhecido: {product}")
    base = str(current_app.config.get(key) or "").rstrip("/")
    clean_path = "/" + str(path or "/").lstrip("/")
    return f"{base}{clean_path}" if base else clean_path


def _configured_host(config_key: str) -> str:
    return (urlparse(str(current_app.config.get(config_key) or "")).hostname or "").lower()


def safe_product_target(value: str | None, fallback: str = "/") -> str:
    """Accept relative URLs or HTTPS URLs on a configured product host only."""
    raw = str(value or "").strip()
    # Browsers normalize backslashes and controls differently from urlparse.
    decoded = unquote(raw)
    if any(ord(char) < 32 or ord(char) == 127 for char in decoded) or '\\' in decoded:
        return fallback
    if raw.startswith("/") and not decoded.startswith("//"):
        return raw
    try:
        parsed = urlparse(raw)
        hostname = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        return fallback
    allowed = {_configured_host(key) for key in PRODUCT_CONFIG_KEYS.values()}
    if (parsed.scheme in {"http", "https"} and hostname and hostname in allowed
            and not parsed.username and not parsed.password and port in (None, 443)):
        # Production products are HTTPS. Normalizing also handles an internal
        # reverse proxy that forwarded the original request as HTTP.
        return parsed._replace(scheme="https").geturl()
    return fallback


def register_product_host_routing(app) -> None:
    """Give each product domain a useful root while legacy paths remain valid."""

    @app.get("/cadu-assets/<family>/icon-<int:size>.png")
    def cadu_maintenance_product_icon(family: str, size: int):
        """Approved Cadu 3.0 symbols, exposed only for the public pause page."""
        if family not in {"workspace", "studio", "connect", "skills", "planner"} or size not in {16, 20, 24, 32, 40, 48, 64, 96, 128, 192, 512, 1024}:
            return "", 404
        asset = Path(app.root_path).parent / "output" / "mockups" / "brand-assets" / "icons-2d" / family / f"icon-{size}.png"
        return send_file(asset, mimetype="image/png", max_age=86400)

    endpoints = {
        "AUTH_URL": "cadu_identity.index",
        "CONNECT_URL": "cadu_connect.index",
        "STUDIO_URL": "parametros.modelagem_criativos",
        "SKILLS_URL": "cadu_skills.marketplace",
        "PLANNER_URL": "smart_planner.index",
        "WORKSPACE_URL": "cadu_workspace.index",
    }

    @app.before_request
    def route_product_root():
        host = (request.host.split(":", 1)[0] or "").lower()
        cadu_host = _configured_host("CADU_URL") or "cadu.centralcomm.media"

        # O domínio do Cadu passa à experiência 3.0: links antigos são contidos
        # aqui, sem envolver CentralX nem o aplicativo PHP desativado.
        release_at = datetime(2026, 10, 14, tzinfo=ZoneInfo("America/Sao_Paulo"))
        if (
            request.method in {"GET", "HEAD"}
            and request.endpoint not in {"static", "cadu_maintenance_product_icon"}
            and host == cadu_host
            and datetime.now(ZoneInfo("America/Sao_Paulo")) < release_at
        ):
            response = make_response(render_template("cadu_maintenance.html", release_at=release_at))
            response.headers["Cache-Control"] = "no-store, max-age=0"
            return response

        # Login é atendido no host do produto. Isso mantém cookies e estado
        # isolados entre CentralX e a família Cadu, inclusive quando há uma
        # sessão antiga de outro produto no mesmo navegador.
        if request.path != "/":
            return None
        for config_key, endpoint in endpoints.items():
            if host and host == _configured_host(config_key):
                return redirect(url_for(endpoint), code=302)
        return None
