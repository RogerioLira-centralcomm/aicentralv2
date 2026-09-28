import unittest
from unittest.mock import MagicMock, patch

from aicentralv2.services.spedy_service import (
    SpedyService,
    _normalize_customer_phones,
    build_spedy_customer_from_pi,
    build_spedy_transaction_id,
    detect_spedy_environment,
    spedy_aplica_status_negocio,
    spedy_environment_label,
)


class SpedyServiceHelpersTest(unittest.TestCase):
    def test_detect_spedy_environment_sandbox(self):
        self.assertEqual(
            detect_spedy_environment('https://sandbox-api.spedy.com.br/v1'),
            'sandbox',
        )

    def test_detect_spedy_environment_production(self):
        self.assertEqual(
            detect_spedy_environment('https://api.spedy.com.br/v1'),
            'production',
        )

    def test_spedy_environment_label(self):
        self.assertEqual(spedy_environment_label('sandbox'), 'Teste (Sandbox)')
        self.assertEqual(spedy_environment_label('production'), 'Produção')

    def test_spedy_aplica_status_negocio(self):
        self.assertFalse(spedy_aplica_status_negocio('sandbox'))
        self.assertTrue(spedy_aplica_status_negocio('production'))

    def test_build_spedy_transaction_id_preview_suffix(self):
        tx = build_spedy_transaction_id(42, 'PI-ABC', preview=True)
        self.assertTrue(tx.endswith('-preview'))
        self.assertIn('PI-42-PI-ABC', tx)

    def test_normalize_customer_phones_splits_landline_and_mobile(self):
        phones = _normalize_customer_phones('(11) 3333-4444', '(31) 99876-5432')
        self.assertEqual(phones.get('phone'), '1133334444')
        self.assertEqual(phones.get('mobilePhone'), '31998765432')

    def test_normalize_customer_phones_does_not_duplicate_mobile(self):
        phones = _normalize_customer_phones('+55 11 98765-4321')
        self.assertEqual(phones, {'mobilePhone': '11987654321'})
        self.assertNotIn('phone', phones)

    def test_build_spedy_customer_omits_invalid_fallback_phone(self):
        customer = build_spedy_customer_from_pi(
            {'id_pi': 1},
            {
                'cnpj': '12345678000199',
                'razao_social': 'Cliente Teste',
                'nome_fantasia': 'Cliente Teste',
            },
            None,
        )
        self.assertNotIn('phone', customer)
        self.assertNotIn('mobilePhone', customer)


class SpedyServiceProductTest(unittest.TestCase):
    @patch('aicentralv2.services.spedy_service.requests.request')
    def test_update_product_sends_service_invoice_settings(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"success": true}'
        mock_response.json.return_value = {'success': True}
        mock_request.return_value = mock_response

        svc = SpedyService(api_key='test-key', base_url='https://sandbox-api.spedy.com.br/v1')
        body = {
            'name': 'MIDIA',
            'invoiceModel': 'serviceInvoice',
            'serviceInvoiceSettings': {
                'fiscalDescription': 'Inserção de textos',
                'cityServiceCode': '17.25.01',
                'federalServiceCode': '17.25',
            },
        }
        svc.update_product(body, product_id='1dcacc78-34d8-43f9-806f-a2500b483275')

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], 'PUT')
        self.assertIn('/products/1dcacc78-34d8-43f9-806f-a2500b483275', call_args[0][1])
        payload = call_args.kwargs['json']
        self.assertEqual(payload['serviceInvoiceSettings']['cityServiceCode'], '17.25.01')
        self.assertEqual(payload['serviceInvoiceSettings']['fiscalDescription'], 'Inserção de textos')


if __name__ == '__main__':
    unittest.main()
