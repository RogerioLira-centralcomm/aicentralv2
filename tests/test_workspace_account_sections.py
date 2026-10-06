from unittest import TestCase, mock

from aicentralv2.cadu_workspace import routes as workspace_routes
from tests.test_product_portals import _app

R = "aicentralv2.cadu_workspace.routes."
DB = "aicentralv2.db."


class AccountSectionLoadingTest(TestCase):
    def test_every_section_has_a_declared_set_of_reads(self):
        self.assertEqual(set(workspace_routes._ACCOUNT_SECTION_NEEDS),
                         {'perfil', 'agencia', 'equipe', 'planos', 'uso', 'creditos', 'faturamento'})

    @mock.patch(R + "credit_position", return_value={"configured": False, "available": 0, "monthly": 0})
    @mock.patch(R + "get_db")
    @mock.patch(DB + "obter_invites_cliente", return_value=[])
    @mock.patch(DB + "obter_planos_clientes", return_value=[])
    @mock.patch(DB + "obter_contatos_por_cliente", return_value=[])
    def test_profile_reads_no_people_plans_invites_or_ledgers(self, people, plans, invites, get_db, credit):
        data = workspace_routes._php_account_data(12, workspace_routes._ACCOUNT_SECTION_NEEDS['perfil'])
        people.assert_not_called()
        plans.assert_not_called()
        invites.assert_not_called()
        get_db.assert_not_called()
        credit.assert_called_once_with(12)
        self.assertEqual(data["people"], [])
        self.assertEqual(data["movements"], [])
        self.assertEqual(data["space"]["files"], 0)

    @mock.patch(R + "credit_position", return_value={"configured": False, "available": 0, "monthly": 0})
    @mock.patch(R + "get_db")
    @mock.patch(DB + "obter_invites_cliente", return_value=[{"id": 1}])
    @mock.patch(DB + "obter_planos_clientes", return_value=[])
    @mock.patch(DB + "obter_contatos_por_cliente", return_value=[{"nome_completo": "A"}])
    def test_team_reads_people_and_invites_only(self, people, plans, invites, get_db, _credit):
        data = workspace_routes._php_account_data(12, workspace_routes._ACCOUNT_SECTION_NEEDS['equipe'])
        people.assert_called_once()
        invites.assert_called_once()
        plans.assert_not_called()
        get_db.assert_not_called()
        self.assertEqual(data["invites"], [{"id": 1}])

    @mock.patch(R + "credit_position", return_value={"configured": False, "available": 0, "monthly": 0})
    @mock.patch(DB + "obter_invites_cliente", return_value=[{"id": 1}])
    @mock.patch(DB + "obter_planos_clientes", return_value=[])
    @mock.patch(DB + "obter_contatos_por_cliente", return_value=[])
    def test_without_sections_everything_is_still_loaded(self, people, plans, invites, _credit):
        with mock.patch(R + "get_db") as get_db:
            get_db.return_value.cursor.return_value.__enter__.return_value.fetchall.return_value = []
            workspace_routes._php_account_data(12)
        people.assert_called_once()
        plans.assert_called_once()
        invites.assert_called_once()

    def _page(self, path):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, user_name="Apolo", user_type="admin")
        with mock.patch(R + "_php_account_data", return_value={"people": [], "invites": [], "plan": {}, "position": None}) as account, \
                mock.patch(R + "_workspace_settings_data", return_value={"organization": {}, "current_user": {}, "states": []}) as settings, \
                mock.patch(R + "_workspace_projects", return_value=[]) as projects, \
                mock.patch(R + "_workspace_brands", return_value=[]) as brands, \
                mock.patch(R + "_workspace_common_dock_items", return_value=[]), \
                mock.patch(R + "_workspace_sidebar_payload", return_value={}), \
                mock.patch(R + "get_db", side_effect=AssertionError("o teste não pode abrir conexão com o banco")), \
                mock.patch.object(workspace_routes.family_repository, "project_brand_links", side_effect=AssertionError("sem banco")):
            response = client.get(path, headers={"Host": "workspace.centralcomm.media"})
        return response, account, settings, projects, brands

    def test_profile_page_skips_the_project_and_brand_tree_and_states(self):
        response, account, settings, projects, brands = self._page("/perfil")
        self.assertEqual(response.status_code, 200)
        projects.assert_not_called()
        brands.assert_not_called()
        self.assertIs(settings.call_args.kwargs["include_states"], False)
        self.assertEqual(account.call_args.args[1], frozenset())

    def test_agency_page_loads_the_tree_and_states(self):
        response, account, settings, projects, brands = self._page("/agencia")
        self.assertEqual(response.status_code, 200)
        projects.assert_called_once()
        brands.assert_called_once()
        self.assertIs(settings.call_args.kwargs["include_states"], True)
        self.assertEqual(account.call_args.args[1], frozenset({'people'}))
