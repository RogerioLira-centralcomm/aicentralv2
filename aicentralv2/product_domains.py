"""Canonical product URLs and host-aware entry routing for the Cadu family."""

from __future__ import annotations

from urllib.parse import urlparse

from flask import current_app, redirect, request, url_for


PRODUCT_CONFIG_KEYS = {
    "cadu": "CADU_URL",
    "centralx": "CENTRALX_URL",
    "studio": "STUDIO_URL",
    "skills": "SKILLS_URL",
    "planner": "PLANNER_URL",
    "connect": "CONNECT_URL",
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
    if raw.startswith("/") and not raw.startswith("//"):
        return raw
    parsed = urlparse(raw)
    hostname = (parsed.hostname or "").lower()
    allowed = {_configured_host(key) for key in PRODUCT_CONFIG_KEYS.values()}
    if parsed.scheme in {"http", "https"} and hostname and hostname in allowed:
        # Production products are HTTPS. Normalizing also handles an internal
        # reverse proxy that forwarded the original request as HTTP.
        return parsed._replace(scheme="https").geturl()
    return fallback


def register_product_host_routing(app) -> None:
    """Give each product domain a useful root while legacy paths remain valid."""

    endpoints = {
        "AUTH_URL": "cadu_identity.index",
        "CONNECT_URL": "cadu_connect.index",
        "STUDIO_URL": "parametros.modelagem_criativos",
        "SKILLS_URL": "cadu_skills.marketplace",
        "PLANNER_URL": "smart_planner.index",
    }

    @app.before_request
    def route_product_root():
        host = (request.host.split(":", 1)[0] or "").lower()
        auth_host = _configured_host("AUTH_URL")
        known_hosts = {_configured_host(key) for key in PRODUCT_CONFIG_KEYS.values()}
        identity_endpoints = {"login", "forgot_password", "reset_password"}
        if (
            request.method == "GET"
            and request.endpoint in identity_endpoints
            and host in known_hosts
            and host != auth_host
        ):
            query = f"?{request.query_string.decode('utf-8')}" if request.query_string else ""
            return redirect(product_url("auth", request.path) + query, code=302)
        if request.path != "/":
            return None
        for config_key, endpoint in endpoints.items():
            if host and host == _configured_host(config_key):
                return redirect(url_for(endpoint), code=302)
        return None
