from datetime import date, datetime
from unittest import TestCase, mock

from aicentralv2.cadu_workspace.routes import (
    _workspace_billing_data,
    _workspace_integration_data,
)
from tests.test_product_portals import _app
from tests.test_workspace_account_usage import _account_fixture


class WorkspaceBillingAndIntegrationsTest(TestCase):
    @mock.patch('aicentralv2.db.obter_invoices', return_value=[
        {
            'id_invoice': 4, 'invoice_number': 'INV-004', 'invoice_status': 'overdue',
            'reference_month': date(2026, 8, 1), 'due_date': date(2026, 9, 10),
            'total': 1299.9, 'pdf_url': 'https://files.example/invoice-4.pdf',
        },
        {
            'id_invoice': 3, 'invoice_number': 'INV-003', 'status': 'paid',
            'billing_month': date(2026, 7, 1), 'due_date': date(2026, 8, 10),
            'total': 999.0, 'paid_at': datetime(2026, 8, 8, 9, 0),
            'pdf_url': 'javascript:alert(1)',
        },
    ])
    def test_billing_normalizes_legacy_schemas_and_rejects_unsafe_pdf(self, invoices):
        data = _workspace_billing_data(12)

        invoices.assert_called_once_with({'cliente_id': 12})
        self.assertEqual(data['summary'], {
            'open_total': 1299.9, 'open_count': 1, 'overdue_count': 1, 'paid_count': 1,
        })
        self.assertEqual(data['invoices'][0]['status_normalized'], 'overdue')
        self.assertEqual(data['invoices'][0]['pdf_safe_url'], 'https://files.example/invoice-4.pdf')
        self.assertIsNone(data['invoices'][1]['pdf_safe_url'])

    @mock.patch('aicentralv2.cadu_workspace.routes.accounts_for_workspace_context', return_value=[
        {'provider': 'google_ads', 'status': 'active', 'name': 'Conta mídia'},
        {'provider': 'meta_ads', 'status': 'error', 'name': 'Conta social'},
    ])
    def test_integration_summary_uses_organization_and_workspace_client_scope(self, accounts):
        app = _app()
        with app.test_request_context('/integracoes', headers={'Host': 'workspace.centralcomm.media'}):
            data = _workspace_integration_data(12, 44)

        accounts.assert_called_once_with(44, workspace_client_id=12)
        self.assertEqual(data['connected_count'], 1)
        self.assertEqual(data['accounts'][0]['provider_label'], 'Google Ads')
        self.assertEqual([item['name'] for item in data['priority_connectors']], [
            'Canva', 'Google Drive', 'ERP da agência',
        ])
        self.assertEqual([item['name'] for item in data['coming_soon_connectors']], [
            'ClickUp', 'Trello', 'Slack',
        ])

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_billing_data', return_value={
        'summary': {'open_total': 1299.9, 'open_count': 1, 'overdue_count': 1, 'paid_count': 2},
        'invoices': [{
            'number': 'INV-004', 'status_normalized': 'overdue',
            'reference': date(2026, 8, 1), 'due_date': date(2026, 9, 10),
            'type_normalized': 'subscription', 'total': 1299.9,
            'paid_on': None, 'pdf_safe_url': 'https://files.example/invoice-4.pdf',
        }],
    })
    @mock.patch('aicentralv2.cadu_workspace.routes._php_account_data', side_effect=lambda _client: _account_fixture())
    def test_billing_page_is_native_to_workspace(self, _account, _billing):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, user_name='Apolo')

        response = client.get('/faturas', headers={'Host': 'workspace.centralcomm.media'})
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('cv-account-root', html)
        self.assertIn('"section": "faturamento"', html)
        self.assertIn('INV-004', html)
        self.assertIn('1299.9', html)
        self.assertIn('overdue', html)
        self.assertNotIn('centralx', response.request.path.lower())

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_integration_data', return_value={
        'connected_count': 1,
        'priority_connectors': [{
            'name': 'Canva', 'icon': 'fa-solid fa-wand-magic-sparkles',
            'summary': 'Criativos e aprovações.', 'scope': 'Criação e identidade',
        }],
        'coming_soon_connectors': [{'name': 'Slack', 'icon': 'fa-brands fa-slack'}],
        'accounts': [{
            'provider': 'google_ads', 'provider_label': 'Google Ads',
            'name': 'Conta mídia', 'external_account_id': '123-456',
            'last_synced_at': datetime(2026, 9, 16, 8, 0), 'status': 'active',
        }],
    })
    def test_workspace_integrations_never_render_credentials(self, _data):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, organization_id=44, user_name='Apolo')

        response = client.get('/integracoes', headers={'Host': 'workspace.centralcomm.media'})
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('cv-account-root', html)
        self.assertIn('"section": "integracoes"', html)
        self.assertIn('Canva', html)
        self.assertIn('Slack', html)
        self.assertIn('Conta m\\u00eddia', html)
        self.assertNotIn('client_secret', html)
        self.assertNotIn('api_key', html)
