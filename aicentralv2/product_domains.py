"""Canonical product URLs and host-aware entry routing for the Cadu family."""

from __future__ import annotations

from urllib.parse import unquote, urlparse

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import abort, current_app, make_response, redirect, render_template, request, send_file, url_for
from flask.sessions import SecureCookieSessionInterface
from werkzeug.routing import BuildError


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


_WORKSPACE_LEGACY_SECTIONS = {
    "": "/workspace/app",
    "inicio": "/workspace/app",
    "clientes": "/workspace/app",
    "conversas": "/workspace/app/conversas",
    "workflows": "/workspace/app/conversas",
    "projetos": "/workspace/app/projetos",
    "marcas": "/workspace/app/marcas",
    "equipe": "/workspace/app/equipe",
    "usuarios": "/workspace/app/equipe",
    "integracoes": "/workspace/app/integracoes",
    "planos": "/workspace/app/planos",
    "consumo": "/workspace/app/creditos",
    "creditos": "/workspace/app/creditos",
    "faturamento": "/workspace/app/faturamento",
    "financeiro": "/workspace/app/faturamento",
    "perfil": "/workspace/app/perfil",
    "conta": "/workspace/app/perfil",
    "organizacao": "/workspace/app/organizacao",
}


def canonical_workspace_legacy_path(path: str, brand_id: str | int | None = None) -> str:
    """Translate the retired Family Workspace surface to its native app.

    Old links remain valid, but no longer render a second Workspace shell.
    ``brand_id`` lets the former generic brand-system entry land on the
    corresponding native brand record instead of losing the selected brand.
    """
    clean = str(path or "").split("?", 1)[0].strip("/")
    prefix = "familia/workspace"
    if clean == prefix:
        clean = ""
    elif clean.startswith(f"{prefix}/"):
        clean = clean[len(prefix) + 1:]
    if clean == "marcas/sistema":
        value = str(brand_id or "").strip()
        return f"/workspace/app/marcas/{value}" if value.isdigit() and int(value) > 0 else "/workspace/app/marcas"
    return _WORKSPACE_LEGACY_SECTIONS.get(clean, "/workspace/app")


def _configured_host(config_key: str) -> str:
    return (urlparse(str(current_app.config.get(config_key) or "")).hostname or "").lower()


def is_centralx_request() -> bool:
    """Whether the current request belongs to CentralX, never the Cadu hub."""
    return (request.host.split(":", 1)[0] or "").lower() == _configured_host("CENTRALX_URL")


class ProductSessionInterface(SecureCookieSessionInterface):
    """Share one Cadu session across product subdomains, isolating CentralX."""

    def get_cookie_name(self, app):
        if is_centralx_request():
            return app.config["CENTRALX_SESSION_COOKIE_NAME"]
        return app.config["CADU_SESSION_COOKIE_NAME"]

    def get_cookie_domain(self, app):
        """Use the parent domain only for Cadu product hosts.

        CentralX retains its host-only cookie. This prevents an internal
        CentralX identity from leaking into the customer-facing Cadu family,
        while Workspace and Connect receive the exact same signed session.
        """
        if is_centralx_request():
            return None
        return app.config.get("CADU_SESSION_COOKIE_DOMAIN")


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

    # Planner owns its subdomain, so its public navigation must not expose the
    # internal Family mount point.  The Family blueprint remains the single
    # implementation; these product-host aliases are deliberately thin.
    def planner_host_only():
        if (request.host.split(':', 1)[0] or '').lower() != _configured_host('PLANNER_URL'):
            abort(404)

    def planner_page(module=None):
        planner_host_only()
        return app.view_functions['cadu_family.page']('planner', module)

    for planner_module in ('planos', 'audiencias', 'canais', 'formatos', 'interativos', 'places', 'docs', 'links'):
        app.add_url_rule(f'/{planner_module}', endpoint=f'planner_host_{planner_module}',
                         view_func=lambda module=planner_module: planner_page(module), methods=['GET'])

    @app.get('/planos/<plan_id>')
    def planner_host_plan_detail(plan_id):
        planner_host_only()
        return app.view_functions['cadu_family.planner_plan_media_desk'](plan_id)

    @app.get('/audiencias/<int:audience_id>')
    def planner_host_audience_detail(audience_id):
        planner_host_only()
        return app.view_functions['cadu_family.planner_audience_detail'](audience_id)

    @app.get('/<kind>/<int:item_id>')
    def planner_host_catalog_detail(kind, item_id):
        planner_host_only()
        return app.view_functions['cadu_family.planner_catalog_detail_page'](kind, item_id)

    @app.get('/docs/public/<token>')
    def planner_host_public_doc(token):
        planner_host_only()
        return app.view_functions['cadu_family.planner_doc_public'](token)

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
        "STUDIO_URL": "studio_product.studio_home",
        "SKILLS_URL": "cadu_skills.marketplace",
        # The planner product is customer-facing.  The legacy Smart Planner
        # remains an internal CentralX tool reached from the CentralX menu.
        "PLANNER_URL": "/familia/planner/",
        "WORKSPACE_URL": "cadu_workspace.index",
    }

    @app.before_request
    def route_product_root():
        host = (request.host.split(":", 1)[0] or "").lower()
        cadu_host = _configured_host("CADU_URL") or "cadu.centralcomm.media"

        if request.method in {'GET', 'HEAD'} and host == _configured_host('PLANNER_URL'):
            if request.path in {'/familia/planner', '/familia/planner/'}:
                return redirect(product_url('planner', '/'), code=302)
            if request.path.startswith('/familia/planner/'):
                suffix = request.path.removeprefix('/familia/planner/')
                target = product_url('planner', f'/{suffix}')
                if request.query_string:
                    target = f"{target}?{request.query_string.decode('utf-8')}"
                return redirect(target, code=302)
            if request.path == '/' and 'cadu_family.page' in app.view_functions:
                return planner_page()

        # Product subdomains own their shells. Navigation published during the
        # Family pilot can still target /familia/<product>/ and sub-pages;
        # resolve every such legacy entry before the gated blueprint can 404.
        legacy_product_entries = {
            "CONNECT_URL": ("/familia/connect", "connect", "/"),
            "STUDIO_URL": ("/familia/studio", "studio", "/studio/modelagem-criativos"),
            "SKILLS_URL": ("/familia/skills", "skills", "/skills/"),
            "WORKSPACE_URL": ("/familia/workspace", "workspace", "/workspace/app"),
        }
        legacy_entry = legacy_product_entries.get(next(
            (key for key in legacy_product_entries if host == _configured_host(key)),
            None,
        ))
        if (
            request.method in {"GET", "HEAD"}
            and legacy_entry
            and (
                request.path.rstrip("/") == legacy_entry[0]
                or request.path.startswith(f"{legacy_entry[0]}/")
            )
        ):
            legacy_path = legacy_entry[2]
            if legacy_entry[1] == "workspace":
                legacy_path = canonical_workspace_legacy_path(
                    request.path,
                    request.args.get("creative_client_id")
                    or request.args.get("brand_id")
                    or request.args.get("crm_client_id")
                    or request.args.get("client_id"),
                )
            target = product_url(legacy_entry[1], legacy_path)
            if request.query_string:
                target = f"{target}?{request.query_string.decode('utf-8')}"
            return redirect(target, code=302)

        # Connect is useful directly at its product domain.  Keep /connect as
        # a compatibility alias, but do not leave it in a customer URL.
        if request.method in {"GET", "HEAD"} and host == _configured_host("CONNECT_URL"):
            if request.path.rstrip("/") == "/connect":
                target = product_url("connect", "/")
                if request.query_string:
                    target = f"{target}?{request.query_string.decode('utf-8')}"
                return redirect(target, code=302)
            if request.path == "/":
                return app.view_functions["cadu_connect.index"]()

        # Parametros was the first host for Creative Modeling.  On the Studio
        # domain it is now a compatibility entry only: keep shared links alive
        # while making the address and browser history product-owned.
        if (
            request.method in {"GET", "HEAD"}
            and host == _configured_host("STUDIO_URL")
            and request.path.startswith("/parametros/modelagem-criativos")
        ):
            suffix = request.path.removeprefix("/parametros/modelagem-criativos")
            target = product_url("studio", f"/studio/modelagem-criativos{suffix}")
            if request.query_string:
                target = f"{target}?{request.query_string.decode('utf-8')}"
            return redirect(target, code=302)

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

        # Login é atendido no host do produto. A família Cadu compartilha a
        # sessão SSO entre seus subdomínios; CentralX mantém identidade própria.
        if request.path != "/":
            return None
        for config_key, endpoint in endpoints.items():
            if host and host == _configured_host(config_key):
                if str(endpoint).startswith("/"):
                    target = endpoint
                else:
                    # A diagnostics/minimal app can omit a product blueprint.
                    # The product host root must still redirect safely, not 500.
                    try:
                        target = url_for(endpoint)
                    except BuildError:
                        target = "/"
                # Studio's canonical entry is itself ``/``. Redirecting the
                # product root to that URL creates an infinite 302 loop, so
                # dispatch its registered view directly instead.  The
                # fallback remains a redirect for reduced diagnostic apps
                # that do not mount the Studio blueprint.
                if target == "/" and endpoint == "studio_product.studio_home":
                    view = app.view_functions.get(endpoint)
                    if view is not None:
                        return view()
                return redirect(target, code=302)
        return None
