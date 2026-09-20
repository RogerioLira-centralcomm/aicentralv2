from datetime import date, timedelta
import json
from unittest import TestCase, mock

from aicentralv2.cadu_workspace.routes import _workspace_account_insights
from tests.test_product_portals import _app


def _account_fixture():
    plan = {
        "plan_definition_name": "Equipe",
        "plan_status": "active",
        "pd_tokens_monthly_limit": 1000,
        "tokens_used_current_month": 250,
        "pd_max_users": 5,
        "pd_limit_image_generation": 100,
        "plan_start_date": "2026-09-01",
        "plan_end_date": "2026-12-31",
        "features": '{"brand_management": true, "studio": true, "ignored": false}',
    }
    people = [{"status": True}, {"status": True}, {"status": False}]
    position = {
        "allowance": 100,
        "adjustments": 10,
        "used": 35,
        "available": 75,
        "effective_limit": 110,
        "usage_percentage": 31.8,
    }
    return {
        "people": people,
        "invites": [],
        "plan": plan,
        "credit": {},
        "position": position,
        "movements": [{
            "movement_type": "usage",
            "amount": 7,
            "reason": "Geração da campanha Primavera",
            "reference": "studio-44",
            "created_by_name": "Ana",
            "created_at": "2026-09-16 09:30",
        }],
        "purchases": [{
            "package_name": "Pacote 25",
            "credits": 25,
            "amount_paid": 250,
            "payment_status": "paid",
            "reference": "pedido-9",
            "purchased_at": "2026-09-12 10:00",
        }],
        "insights": _workspace_account_insights(plan, position, people),
    }


def _account_bootstrap(html):
    marker = '<script id="cadu-conversations-v2-bootstrap" type="application/json">'
    payload = html.split(marker, 1)[1].split('</script>', 1)[0]
    return json.loads(payload)


class WorkspaceAccountUsageTest(TestCase):
    def test_insights_normalize_features_limits_and_validity(self):
        future = date.today() + timedelta(days=12)
        insights = _workspace_account_insights({
            "tokens_monthly_limit": "1000",
            "tokens_used_current_month": "250",
            "max_users": "4",
            "plan_end_date": future.isoformat(),
            "features": '{"brand_management": true, "project_knowledge": true, "studio": false}',
        }, {"used": 20, "effective_limit": 100}, [
            {"status": True}, {"status": False}, {"status": True},
        ])

        self.assertEqual(insights["tokens"], {
            "used": 250, "limit": 1000, "available": 750, "percentage": 25.0,
        })
        self.assertEqual(insights["users"]["used"], 2)
        self.assertEqual(insights["users"]["available"], 2)
        self.assertEqual(insights["days_remaining"], 12)
        self.assertEqual(insights["validity"]["end"], future.strftime("%d/%m/%Y"))
        self.assertEqual(insights["features"], [
            "Gestão de marcas", "Base de conhecimento dos projetos",
        ])

    @mock.patch("aicentralv2.cadu_workspace.routes._php_account_data", side_effect=lambda _client: _account_fixture())
    def test_plan_view_explains_usage_and_included_resources(self, _account):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, user_name="Apolo")

        response = client.get("/plano", headers={"Host": "workspace.centralcomm.media"})
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        bootstrap = _account_bootstrap(html)
        self.assertEqual(bootstrap["section"], "planos")
        self.assertEqual(bootstrap["account"]["plan"]["plan_definition_name"], "Equipe")
        self.assertEqual(bootstrap["account"]["insights"]["tokens"]["used"], 250)

    @mock.patch("aicentralv2.cadu_workspace.routes._php_account_data", side_effect=lambda _client: _account_fixture())
    def test_usage_view_preserves_auditable_context(self, _account):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, user_name="Apolo")

        response = client.get("/uso", headers={"Host": "workspace.centralcomm.media"})
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        bootstrap = _account_bootstrap(html)
        self.assertEqual(bootstrap["section"], "uso")
        self.assertEqual(bootstrap["account"]["movements"][0]["reason"], "Geração da campanha Primavera")
        self.assertEqual(bootstrap["account"]["movements"][0]["amount"], 7)

    @mock.patch("aicentralv2.cadu_workspace.routes._php_account_data", side_effect=lambda _client: _account_fixture())
    def test_credits_view_exposes_balance_lots_without_becoming_usage(self, _account):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, user_name="Apolo")

        response = client.get("/creditos", headers={"Host": "workspace.centralcomm.media"})
        bootstrap = _account_bootstrap(response.get_data(as_text=True))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(bootstrap["section"], "creditos")
        self.assertEqual(bootstrap["account"]["purchases"][0]["package_name"], "Pacote 25")

    @mock.patch("aicentralv2.cadu_workspace.routes._workspace_settings_data", return_value={
        "organization": {}, "states": [],
        "current_user": {
            "nome_completo": "Apolo Lira", "email": "apolo@centralcomm.media",
            "telefone": "(11) 99999-9999", "cargo_descricao": "Direção",
            "user_type": "admin",
        },
    })
    @mock.patch("aicentralv2.cadu_workspace.routes._php_account_data", side_effect=lambda _client: _account_fixture())
    def test_profile_view_replaces_legacy_settings_page(self, _account, _settings):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, user_name="Apolo", user_type="admin")

        response = client.get("/perfil", headers={"Host": "workspace.centralcomm.media"})
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Perfil de Apolo Lira", html)
        self.assertIn("apolo@centralcomm.media", html)
        self.assertIn("Salvar perfil", html)
        self.assertNotIn("Excluir Conta", html)

    @mock.patch("aicentralv2.cadu_workspace.routes._workspace_settings_data", return_value={
        "current_user": {},
        "organization": {
            "id_cliente": 12, "nome_fantasia": "CentralComm",
            "razao_social": "Central Comunicação Ltda", "cnpj": "12345678000190",
            "estado_sigla": "SP",
        },
        "states": [{"id_estado": 25, "sigla": "SP", "descricao": "São Paulo"}],
    })
    @mock.patch("aicentralv2.cadu_workspace.routes._php_account_data", side_effect=lambda _client: _account_fixture())
    def test_organization_view_explains_canonical_record(self, _account, _settings):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, user_name="Apolo", user_type="client")

        response = client.get("/equipe", headers={"Host": "workspace.centralcomm.media"})
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Núcleo da agência", html)
        self.assertIn("Projetos, marcas, plano e créditos são compartilhados", html)
        self.assertNotIn("Dados da equipe", html)
