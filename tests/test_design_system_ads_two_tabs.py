"""Duas abas da mesa: 409 e recarga. Distinto do render do incremento 4."""

from pathlib import Path
import threading
import unittest

from flask import Flask, jsonify, request

from aicentralv2.creative_modeling_repository import CreativeConflictError
from aicentralv2.creative_modeling_service import CreativeModelingService
from aicentralv2.design_system_ads.commands import parse_adapt, parse_approve_brand, parse_patch_brand
from aicentralv2.design_system_ads.materialize import ensure_brand_design_system
from aicentralv2.design_system_ads.revision import BRAND_CONFLICT, read_revision

ROOT = Path(__file__).resolve().parents[1]


class FakeBrandRepo:
    def __init__(self):
        self.clients = {
            9: {
                "id": 9,
                "name": "Clara",
                "primary_color": "#082C9C",
                "brand_profile": {},
            }
        }

    def list_clients(self):
        return [{"id": item["id"], "name": item["name"]} for item in self.clients.values()]

    def get_client(self, client_id):
        row = self.clients[int(client_id)]
        return {
            **row,
            "brand_profile": dict(row.get("brand_profile") or {}),
        }

    def update_client_brand_profile_cas(self, client_id, profile, expected):
        row = self.clients[int(client_id)]
        stored = read_revision((row.get("brand_profile") or {}).get("design_system_ads") or {})
        if stored != expected:
            raise CreativeConflictError(BRAND_CONFLICT)
        row["brand_profile"] = dict(profile)


def _ok(data):
    return jsonify({"success": True, "data": data})


def _error(exc, status):
    return jsonify({"success": False, "error": str(exc)}), status


def make_mesa_app():
    repo = FakeBrandRepo()
    service = CreativeModelingService.__new__(CreativeModelingService)
    service.repository = repo
    service.get_client = repo.get_client
    service.list_clients = repo.list_clients
    client = repo.get_client(9)
    service._persist_brand_design_system(
        client, ensure_brand_design_system(client), expected_revision=0
    )

    app = Flask(
        __name__,
        static_folder=str(ROOT / "aicentralv2" / "static"),
        static_url_path="/static",
    )
    templates = ROOT / "aicentralv2" / "templates" / "parametros"

    def wrap(callback):
        try:
            return _ok(callback())
        except CreativeConflictError as exc:
            return _error(exc, 409)
        except (ValueError, KeyError) as exc:
            return _error(exc, 400)

    @app.get("/parametros/modelagem-criativos/design-system")
    def page():
        body = (templates / "_mc_design_system.html").read_text(encoding="utf-8")
        return (
            '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            "<title>Design System Ads</title>"
            '<link rel="stylesheet" href="/static/css/modelagem_criativos.css?v=103">'
            "</head><body>"
            f"{body}"
            '<script src="/static/js/mc-dsa-write-queue.js?v=63"></script>'
            '<script src="/static/js/mc-design-system.js?v=63" defer></script>'
            "</body></html>"
        )

    @app.get("/parametros/api/clients")
    def clients():
        return _ok(service.list_clients())

    @app.get("/parametros/api/campaigns")
    def campaigns():
        return _ok([])

    @app.get("/parametros/api/design-system/brand/<client_id>")
    def get_brand(client_id):
        return wrap(lambda: service.get_brand_design_system(client_id))

    @app.post("/parametros/api/design-system/brand/<client_id>/approve")
    def approve(client_id):
        command = parse_approve_brand(request.get_json(silent=True) or {})
        return wrap(
            lambda: service.approve_brand_design_system(
                client_id, expected_revision=command.expected_revision
            )
        )

    @app.post("/parametros/api/design-system/brand/<client_id>/tokens")
    def tokens(client_id):
        command = parse_patch_brand(request.get_json(silent=True) or {})
        return wrap(
            lambda: service.patch_brand_design_system(
                client_id,
                tokens=command.tokens,
                ad_copy=command.ad_copy,
                dna=command.dna,
                archetype=command.archetype,
                expected_revision=command.expected_revision,
            )
        )

    @app.post("/parametros/api/design-system/brand/<client_id>/adapt")
    def adapt(client_id):
        command = parse_adapt(request.get_json(silent=True) or {})
        return wrap(
            lambda: service.adapt_brand_design_system(
                client_id,
                format_key=command.format,
                layer_count=command.layers,
                swaps=command.swaps,
                archetype=command.archetype,
                expected_revision=command.expected_revision,
            )
        )

    @app.get("/lab/design-system/marca/<client_id>")
    def specimen(client_id):
        return "<html><body></body></html>"

    return app


def _start(app):
    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


class DesignSystemAdsTwoTabsTest(unittest.TestCase):
    def test_approve_depois_patch_antigo_devolve_409(self):
        app = make_mesa_app()
        client = app.test_client()
        first = client.get("/parametros/api/design-system/brand/9").get_json()["data"]
        revision = first["revision"]
        approved = client.post(
            "/parametros/api/design-system/brand/9/approve",
            json={"expected_revision": revision},
        )
        self.assertEqual(approved.status_code, 200)
        stale = client.post(
            "/parametros/api/design-system/brand/9/tokens",
            json={
                "expected_revision": revision,
                "ad_copy": {"headline": "Clara mudou"},
            },
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.get_json()["error"], BRAND_CONFLICT)
        fresh = client.get("/parametros/api/design-system/brand/9").get_json()["data"]
        self.assertEqual(fresh["status"], "approved")
        self.assertEqual(fresh["ad_copy"]["headline"], first["ad_copy"]["headline"])

    def test_mesa_cita_o_409_e_recarrega_sem_adaptar(self):
        js = (ROOT / "aicentralv2" / "static" / "js" / "mc-design-system.js").read_text(
            encoding="utf-8"
        )
        queue = (
            ROOT / "aicentralv2" / "static" / "js" / "mc-dsa-write-queue.js"
        ).read_text(encoding="utf-8")
        self.assertIn(BRAND_CONFLICT, js)
        self.assertIn("error.message || BRAND_CONFLICT", js)
        self.assertIn("skipAdapt: true", js)
        self.assertIn("BRAND_CONFLICT", queue)
        self.assertNotIn("dump de hash", js)

    def test_aprovar_numa_aba_e_patch_na_outra_recarrega(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            self.skipTest("Playwright ausente")

        server, origin = _start(make_mesa_app())
        url = f"{origin}/parametros/modelagem-criativos/design-system"
        playwright = None
        browser = None
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=True)
        except Exception:
            server.shutdown()
            if playwright:
                playwright.stop()
            self.skipTest("Chromium ausente")

        try:
            context = browser.new_context()
            first = context.new_page()
            second = context.new_page()
            first.goto(url, wait_until="domcontentloaded")
            second.goto(url, wait_until="domcontentloaded")
            for page in (first, second):
                page.select_option("#mcDsaClient", "9")
                page.wait_for_selector("#mcDsaApprove:not([disabled])")
            first.click("#mcDsaApprove")
            first.wait_for_function(
                "document.getElementById('mcDsaOffer')?.textContent.includes('Aprovado')"
            )
            second.fill("#mcDsaCopy [name=headline]", "Clara mudou")
            second.wait_for_function(
                "document.getElementById('mcDsaStatus')?.textContent.includes('A marca mudou. Recarregue.')",
                timeout=8000,
            )
            second.wait_for_function(
                "document.getElementById('mcDsaOffer')?.textContent.includes('Aprovado')",
                timeout=8000,
            )
            self.assertTrue(second.locator("#mcDsaApprove").is_disabled())
        finally:
            if browser:
                browser.close()
            if playwright:
                playwright.stop()
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
