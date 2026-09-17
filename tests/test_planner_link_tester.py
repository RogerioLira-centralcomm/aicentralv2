from unittest import TestCase, mock
from urllib.parse import urlparse

from aicentralv2.cadu_planner import link_tester


HTML = '''<html><head><title>Landing</title><meta name="description" content="Teste"></head><body>
<script src="https://www.googletagmanager.com/gtm.js?id=GTM-ABC"></script>
<script>gtag('event', 'whatsapp_click');fbq('init','123')</script>
<a href="https://wa.me/5511999999999">WhatsApp</a><form></form>cookie política de privacidade
<script type="application/ld+json">{"@type":"Organization"}</script></body></html>'''


class PlannerLinkTesterTest(TestCase):
    def setUp(self):
        self.common = {'original_url': 'https://example.com/?utm_source=test', 'final_url': 'https://example.com/',
                       'final_parsed': urlparse('https://example.com/'), 'status': 200, 'reachable': True,
                       'elapsed_ms': 80, 'redirects': [{'url': 'https://example.com/', 'status': 200}],
                       'html': HTML, 'headers': {}}

    def test_each_report_has_an_independent_contract(self):
        with mock.patch.object(link_tester, '_common', return_value=self.common), \
             mock.patch.object(link_tester, '_certificate', return_value={'valid': True}), \
             mock.patch.object(link_tester, '_fetch', return_value=(200, {}, '# Example\n\n> Summary\n\n- [Home](https://example.com)')):
            for mode in ('destination', 'media', 'agentic'):
                result = link_tester.test({'url': 'https://example.com/?utm_source=test', 'mode': mode})
                self.assertEqual(mode, result['kind'])
                self.assertGreaterEqual(result['score'], 0)
                self.assertLessEqual(result['score'], 100)
                self.assertIn('evidence', result)

    def test_media_flags_unmeasured_form(self):
        result = link_tester._media({**self.common, 'html': '<form></form>'})
        self.assertIn('Formulário detectado sem evento de conversão.', result['alerts'])
