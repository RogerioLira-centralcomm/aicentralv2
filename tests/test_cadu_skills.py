from pathlib import Path
from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_skills.catalog import (
    CADU_MEDIA_PLANNING, CADU_OFFICIAL_SKILLS, DEFERRED_SKILLS, DIRECTORY_SKILLS, TOP_SKILLS, get_public_skill,
)
from aicentralv2.cadu_skills.consultations import consultation_state
from aicentralv2.cadu_skills.credits import balance_from_ledger
from aicentralv2.cadu_skills.repository import customization_as_skill, customization_markdown
from aicentralv2.cadu_skills.routes import bp


ROOT = Path(__file__).resolve().parents[1]


def _app():
    app = Flask(__name__, template_folder=str(ROOT / "aicentralv2" / "templates"), static_folder=str(ROOT / "aicentralv2" / "static"))
    app.secret_key = "test"
    app.add_url_rule("/login", endpoint="login", view_func=lambda: "login")
    app.register_blueprint(bp)
    app.context_processor(lambda: {"product_url": lambda product, path="": f"/{product}{path}"})
    return app


class CaduSkillsTest(TestCase):
    def test_catalog_promotes_ten_and_defers_ninety(self):
        self.assertEqual(len(TOP_SKILLS), 10)
        self.assertEqual(len(DEFERRED_SKILLS), 90)
        self.assertEqual(len(DIRECTORY_SKILLS), 100)
        script = next(item for item in TOP_SKILLS if item["slug"] == "script-writing")
        self.assertIn("Nunca prometa gerar", script["instructions"])

    def test_official_family_is_installable_and_has_catalogs(self):
        self.assertEqual(len(CADU_OFFICIAL_SKILLS), 4)
        for skill in CADU_OFFICIAL_SKILLS:
            self.assertTrue(skill["installable"])
            self.assertTrue(Path(skill["path"]).is_file())
        planning_refs = Path(CADU_MEDIA_PLANNING["path"]).parent / "references"
        for name in ("channels.csv", "audiences.csv", "formats.csv"):
            self.assertTrue((planning_refs / name).is_file())
        import csv
        with (planning_refs / "audiences.csv").open(encoding="utf-8", newline="") as handle:
            header = next(csv.reader(handle))
        self.assertNotIn("cpm_custo", header)
        self.assertNotIn("cpm_venda", header)
        self.assertIn("verification_gaps", header)

    @mock.patch("aicentralv2.cadu_skills.routes.managed_skills", side_effect=lambda rows: [dict(item, views=0, copies=0, installs=0, runs=0, engagements=0, display_rank=item["rank"]) for item in rows])
    @mock.patch("aicentralv2.cadu_skills.routes.record_event", return_value=True)
    def test_public_marketplace_and_detail_do_not_require_login(self, _event, _managed):
        client = _app().test_client()
        response = client.get("/skills/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Top 10 para experimentar", html)
        self.assertIn("Família oficial Cadu", html)
        self.assertIn("Mais 90 referências", html)
        self.assertIn("Produção de vídeos curtos", html)
        detail = client.get("/skills/cadu-media-planning")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("agente de teste", detail.get_data(as_text=True).lower())
        self.assertEqual(client.get("/skills/assets/skills-icon-64.png").status_code, 200)

    @mock.patch("aicentralv2.cadu_skills.routes.record_event", return_value=True)
    def test_official_skill_download_is_a_complete_zip(self, _event):
        client = _app().test_client()
        response = client.get("/skills/cadu-audience-intelligence/download")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            names = set(archive.namelist())
        self.assertIn("cadu-audience-intelligence/SKILL.md", names)
        self.assertIn("cadu-audience-intelligence/references/audiences.csv", names)

    @mock.patch("aicentralv2.cadu_skills.routes.record_event", return_value=True)
    def test_official_detail_exposes_public_agent_install_address(self, _event):
        client = _app().test_client()
        detail = client.get("/skills/cadu-media-planning")
        self.assertEqual(detail.status_code, 200)
        html = detail.get_data(as_text=True)
        self.assertIn("Endereço de instalação", html)
        self.assertIn("/skills/install/cadu-media-planning", html)
        self.assertIn("Copiar instrução para GPT", html)
        self.assertIn("Copiar instrução para Claude", html)
        self.assertIn("O que vem no pacote", html)
        self.assertIn('class="sk-page-index"', html)
        self.assertIn('data-page-position>01 / 06', html)
        self.assertIn('href="#experimentar" data-page-link', html)

        install = client.get("/skills/install/cadu-media-planning")
        self.assertEqual(install.status_code, 200)
        self.assertIn("text/markdown", install.content_type)
        self.assertIn("inline", install.headers["Content-Disposition"])
        self.assertIn("application/zip", install.headers["Link"])
        body = install.get_data(as_text=True)
        self.assertIn("# Instalar Planejamento de mídia Cadu", body)
        self.assertIn("/skills/cadu-media-planning/download", body)
        self.assertIn("## GPT e Codex", body)
        self.assertIn("## Claude", body)
        self.assertNotIn("cpm_custo", body)

    @mock.patch("aicentralv2.cadu_skills.routes._shared_record", return_value=None)
    def test_premium_share_urls_are_not_enumerable(self, _shared):
        client = _app().test_client()
        self.assertEqual(client.get("/skills/s/curto").status_code, 404)
        self.assertEqual(client.get("/skills/s/" + "x" * 40).status_code, 404)

    @mock.patch("aicentralv2.cadu_skills.routes.managed_skills", side_effect=lambda rows: [dict(item, views=0, copies=0, installs=0, runs=0, engagements=0, display_rank=item["rank"]) for item in rows])
    @mock.patch("aicentralv2.cadu_skills.routes.reserve_run", side_effect=ValueError("Nenhum plano Cadu ativo foi encontrado."))
    def test_studio_requires_login_and_api_checks_ledger(self, _reserve, _managed):
        client = _app().test_client()
        self.assertEqual(client.get("/skills/studio").status_code, 302)
        with client.session_transaction() as sess:
            sess["user_id"] = 7
            sess["cliente_id"] = 12
        response = client.post("/skills/api/cadu-media-planning/runs", json={"prompt": "Planeje uma campanha regional"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "CREDITS_UNAVAILABLE")

    def test_credit_balance_respects_reservations_and_releases(self):
        balance = balance_from_ledger([
            {"kind": "monthly_grant", "amount": 20}, {"kind": "reserve", "amount": -5},
            {"kind": "release", "amount": 2}, {"kind": "capture", "amount": -3},
        ])
        self.assertEqual(balance.available, 14)
        self.assertTrue(balance.can_reserve(CADU_MEDIA_PLANNING["credit_cost"]))
        self.assertIs(get_public_skill("cadu-media-planning"), CADU_MEDIA_PLANNING)

    @mock.patch("aicentralv2.cadu_skills.routes.managed_skills", side_effect=lambda rows: [dict(item, views=0, copies=0, installs=0, runs=0, engagements=0, display_rank=item["rank"]) for item in rows])
    @mock.patch("aicentralv2.cadu_skills.routes.record_event", return_value=True)
    @mock.patch("aicentralv2.cadu_skills.routes.run_test_skill", return_value={"answer": "Plano de teste", "model": "test"})
    def test_public_preview_runs_agent_and_stops_at_three(self, _run, _event, _managed):
        client = _app().test_client()
        for expected in (1, 2, 3):
            response = client.post("/skills/api/public/cadu-media-planning/preview", json={"prompt": "Planeje uma campanha regional de varejo"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["state"]["count"], expected)
            self.assertEqual(response.get_json()["answer"], "Plano de teste")
            expected_stage = "discover" if expected == 2 else "family" if expected == 3 else ""
            self.assertEqual(response.get_json()["state"]["ecosystem_stage"], expected_stage)
        self.assertEqual(client.post("/skills/api/public/cadu-media-planning/preview", json={"prompt": "Planeje uma campanha regional de varejo"}).status_code, 429)
        self.assertFalse(consultation_state(3, is_client=True)["show_ecosystem_invite"])

    @mock.patch("aicentralv2.cadu_skills.routes.record_event", return_value=True)
    def test_public_skill_presents_cadu_family_after_second_preview(self, _event):
        client = _app().test_client()
        with client.session_transaction() as sess:
            sess["skill_preview_cadu-media-planning"] = 2
        response = client.get("/skills/cadu-media-planning")
        html = response.get_data(as_text=True)
        self.assertIn('data-stage="discover"', html)
        self.assertIn("Para agências", html)
        self.assertIn("Para produtores de conteúdo", html)
        self.assertIn("Para clientes finais", html)
        self.assertIn("Cadu Places", html)
        self.assertEqual(html.count("-2d.svg"), 9)

    def test_personalized_download_contains_client_project_and_context(self):
        row = {
            "id": 9, "name": "Skill da campanha", "summary": "Versão para varejo", "client_id": 12,
            "client_name": "Cliente teste", "project_id": 3, "project_name": "Natal", "context_json": {"tom": "direto"},
            "instructions": "Use o contexto aprovado.", "model": "openai/gpt-4o-mini", "credit_cost": 2,
        }
        skill = customization_as_skill(row, CADU_MEDIA_PLANNING)
        content = customization_markdown(row, skill)
        self.assertIn("Cliente teste", content)
        self.assertIn("Natal", content)
        self.assertIn('"tom": "direto"', content)

    @mock.patch("aicentralv2.cadu_skills.routes.get_customization", return_value={"id": 9, "status": "published"})
    @mock.patch("aicentralv2.cadu_skills.routes.create_share", return_value="secret_token")
    def test_admin_can_create_unlisted_hashed_share_link(self, create, _get):
        client = _app().test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 7
            sess["user_type"] = "admin"
        response = client.post("/skills/api/gestao/personalizadas/9/link", json={"permission": "run"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("/skills/s/secret_token", response.get_json()["url"])
        create.assert_called_once_with(9, user_id=7, permission="run")

    def test_management_requires_admin(self):
        client = _app().test_client()
        self.assertEqual(client.get("/skills/gestao").status_code, 302)

    @mock.patch("aicentralv2.cadu_skills.routes.all_cadu_skills", return_value=[CADU_MEDIA_PLANNING])
    def test_agent_desk_lives_inside_cadu_skills(self, _skills):
        response = _app().test_client().get("/skills/agentes")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Agentes e capacidades", html)
        self.assertIn("Agente de Skills", html)
        self.assertIn("Contas, MCPs, relatórios e campanhas", html)

    def test_deploy_runs_both_skills_migrations(self):
        deploy = (ROOT / "deploy.sh").read_text()
        self.assertIn("run_add_cadu_skills_marketplace.py", deploy)
        self.assertIn("run_add_cadu_skills_management.py", deploy)
        migration = (ROOT / "migrations" / "add_cadu_skills_management.sql").read_text()
        self.assertIn("d.owner_type = 'centralx'", migration)
        self.assertIn("SET is_testable = TRUE", migration)
