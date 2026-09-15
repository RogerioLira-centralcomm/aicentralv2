from unittest import TestCase, mock

from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_family.copy_ads import aspect_ratio, fields_for, validate_copy
from tests.test_cadu_family import FamilyTest


class FormatContractTest(TestCase):
    def test_search_fields_and_limits(self):
        fields = fields_for({'plataforma_slug': 'google_ads', 'tipo': 'search'})
        self.assertEqual([row['limit'] for row in fields], [30, 30, 30, 90, 90])

    def test_platform_branches(self):
        cases = [
            ('meta_ads', 'Stories', 'video', '1080x1920', [500, 40]),
            ('meta_ads', 'Carrossel', 'image', '1080x1080', [500, 40, 30]),
            ('linkedin', 'InMail', '', '', [60, 1500, 20]),
            ('linkedin', 'Video', 'video', '', [600, 200]),
            ('tiktok', 'Spark Ads', '', '', [150, 20]),
            ('youtube', 'Bumper', '', '', [40, 10]),
            ('youtube', 'In-feed', '', '', [100, 35, 35]),
            ('x_ads', 'Video', 'video', '', [280, 70, 20]),
            ('native', '', 'native', '', [90, 300, 25]),
        ]
        for platform, name, kind, dimensions, limits in cases:
            with self.subTest(platform=platform, name=name):
                rows = fields_for(dict(plataforma_slug=platform, nome=name, tipo=kind, dimensoes=dimensions))
                self.assertEqual([row['limit'] for row in rows], limits)

    def test_dimensions_and_custom_fields(self):
        self.assertEqual(aspect_ratio('728x90, 970x90'), 728 / 90)
        self.assertEqual(aspect_ratio('1080×1920'), 1080 / 1920)
        self.assertEqual(aspect_ratio('100x0'), 0)
        row = {'dados_extras': '{"campos_copy":[{"nome":"title","label":"Título","limite":12,"recomendado":8}]}'}
        fields = fields_for(row)
        self.assertEqual(fields[0]['limit'], 12)
        self.assertEqual(fields[0]['name'], 'title')

    def test_validation_does_not_truncate_and_counts_unicode(self):
        spec = {'fields': [{'name': 'title', 'label': 'Título', 'limit': 2, 'recommended': 1}]}
        self.assertTrue(validate_copy(spec, {'title': 'á😀'})['valid'])
        result = validate_copy(spec, {'title': 'abc'})
        self.assertFalse(result['valid'])
        self.assertEqual(result['fields'][0]['text'], 'abc')
        self.assertFalse(validate_copy(spec, {})['valid'])
        with self.assertRaises(BadRequest):
            validate_copy(spec, {'foreign_field': 'text'})


class CopyAdsRouteTest(FamilyTest):
    def test_formats_require_login(self):
        self.assertEqual(self.client.get('/familia/api/studio/copy-ads/formats').status_code, 401)

    def test_validation_uses_server_catalog_and_performs_no_writes(self):
        self.login()
        spec = {'id': 3, 'fields': [{'name': 'headline', 'label': 'Headline', 'limit': 2, 'recommended': 2}]}
        with mock.patch('aicentralv2.cadu_family.copy_ads.formats', return_value=[spec]), \
                mock.patch('aicentralv2.cadu_family.repository.get_db') as db:
            result = self.post('studio/copy-ads/validate', {'format_id': 3, 'values': {'headline': 'long'}, 'limit': 999})
            self.assertEqual(result.status_code, 200)
            self.assertFalse(result.get_json()['valid'])
            db.assert_not_called()

    def test_editor_has_no_central_agent_or_php_link(self):
        self.login()
        html = self.client.get('/familia/studio/copy-ads').get_data(as_text=True)
        self.assertIn('id="copy-editor"', html)
        self.assertNotIn('id="conversation-panel"', html)
        self.assertNotIn('Abrir ferramenta atual', html)
