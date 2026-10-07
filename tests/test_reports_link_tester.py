from unittest import TestCase, mock
from urllib.parse import urlparse

from aicentralv2.cadu_connect import reports_link_agentic as agentic
from aicentralv2.cadu_connect import reports_link_tester as link_tester


HTML = '''<html><head><title>Landing</title><meta name="description" content="Teste"></head><body>
<script src="https://www.googletagmanager.com/gtm.js?id=GTM-ABC"></script>
<script>gtag('event', 'whatsapp_click');fbq('init','123')</script>
<a href="https://wa.me/5511999999999">WhatsApp</a><form></form>cookie política de privacidade
<script type="application/ld+json">{"@type":"Organization"}</script></body></html>'''


class ReportsLinkTesterTest(TestCase):
    def setUp(self):
        self.common = {'original_url': 'https://example.com/?utm_source=test', 'final_url': 'https://example.com/',
                       'final_parsed': urlparse('https://example.com/'), 'status': 200, 'reachable': True,
                       'elapsed_ms': 80, 'redirects': [{'url': 'https://example.com/', 'status': 200}],
                       'html': HTML, 'headers': {}}

    def test_each_report_has_an_independent_contract(self):
        with mock.patch.object(link_tester, '_common', return_value=self.common), \
             mock.patch.object(link_tester, '_certificate', return_value={'valid': True}), \
             mock.patch.object(link_tester, '_fetch', return_value=(200, {}, '# Example\n\n> Summary\n\n- [Home](https://example.com)')), \
             mock.patch.object(agentic, '_get', side_effect=lambda url, **kw: fake_site({})(url, **kw)):
            for mode in ('destination', 'media', 'agentic'):
                result = link_tester.test({'url': 'https://example.com/?utm_source=test', 'mode': mode})
                self.assertEqual(mode, result['kind'])
                self.assertGreaterEqual(result['score'], 0)
                self.assertLessEqual(result['score'], 100)
                self.assertIn('evidence', result)

    def test_media_flags_unmeasured_form(self):
        result = link_tester._media({**self.common, 'html': '<form></form>'})
        self.assertIn('Formulário detectado sem evento de conversão.', result['alerts'])


def reply(body='', status=200, content_type='text/plain'):
    return {'status': status, 'headers': {}, 'body': body, 'content_type': content_type, 'error': None, 'final_url': 'https://example.com/', 'ms': 5}


def fake_site(files):
    """_get double: unknown paths 404, like a server that really lacks the file."""
    def get(url, **kwargs):
        path = url.split('example.com', 1)[-1] or '/'
        agent = kwargs.get('agent') or ''
        if agent and 'blocked-agent' in files and any(token in agent for token in files['blocked-agent']):
            return reply('Forbidden', 403, 'text/html')
        return files.get(path) or reply('', 404, 'text/html')
    return get


PAGE = '<html lang="pt-BR"><head><title>Loja Exemplo - sapatos</title></head><body><main><h1>Sapatos</h1><h2>Nossa linha</h2>' + 'palavra ' * 400 + '</main></body></html>'


class AgenticAuditTest(TestCase):
    def audit(self, files, html=PAGE, rendered='', status=200):
        common = {'original_url': 'https://example.com/', 'final_url': 'https://example.com/', 'final_parsed': urlparse('https://example.com/'),
                  'status': status, 'reachable': status < 400, 'elapsed_ms': 80, 'redirects': [], 'html': html, 'raw_html': html,
                  'rendered_html': rendered, 'headers': {}, 'capture': {}}
        with mock.patch.object(agentic, '_get', side_effect=fake_site(files)):
            return agentic.analyze(common)

    def titles(self, result):
        return {item['title'] for item in result['evidence']['findings']}

    def test_catch_all_html_does_not_count_as_llms_or_robots(self):
        spa = reply('<!doctype html><html></html>', 200, 'text/html')
        result = self.audit({'/robots.txt': spa, '/llms.txt': spa, '/sitemap.xml': spa})
        titles = self.titles(result)
        self.assertIn('llms.txt devolve HTML', titles)
        self.assertIn('robots.txt devolve HTML, não regras', titles)
        self.assertFalse(result['evidence']['resources']['llms.txt']['available'])

    def test_wildcard_disallow_blocks_search_bots_and_caps_the_score(self):
        robots = reply('User-agent: *\nDisallow: /\n')
        result = self.audit({'/robots.txt': robots})
        self.assertIn('Robôs de busca de IA bloqueados no robots.txt', self.titles(result))
        self.assertLessEqual(result['score'], 55)

    def test_waf_blocking_ai_user_agents_is_critical_even_with_open_robots(self):
        files = {'/robots.txt': reply('User-agent: *\nAllow: /\n'), 'blocked-agent': ('GPTBot', 'ClaudeBot')}
        result = self.audit(files)
        self.assertIn('CDN/WAF barra robôs de IA', self.titles(result))
        self.assertLessEqual(result['score'], 40)

    def test_javascript_only_content_is_flagged_and_capped(self):
        shell = '<html lang="pt"><head><title>App de vendas online</title></head><body><div id="root"></div></body></html>'
        result = self.audit({}, html=shell, rendered=PAGE)
        self.assertTrue(result['evidence']['content']['js_dependent'])
        self.assertLessEqual(result['score'], 55)

    def test_well_prepared_site_scores_high(self):
        ld = '<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Organization","name":"X"},{"@type":"Product","name":"Y"}]}</script>'
        html = PAGE.replace('</head>', '<meta name="description" content="' + 'Loja de sapatos com entrega para todo o Brasil e troca grátis em trinta dias.' + '">' + ld + '</head>')
        files = {'/robots.txt': reply('User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n'),
                 '/llms.txt': reply('# Loja\n> Sapatos online.\n\n## Páginas\n- [A](https://example.com/a): a\n- [B](https://example.com/b): b\n- [C](https://example.com/c): c\n'),
                 '/a': reply('ok'), '/b': reply('ok'), '/c': reply('ok'),
                 '/sitemap.xml': reply('<urlset><url><loc>https://example.com/</loc><lastmod>2026-09-01</lastmod></url></urlset>', 200, 'application/xml')}
        result = self.audit(files, html=html)
        self.assertGreaterEqual(result['score'], 85)
        self.assertEqual('Pronto para agentes', result['status_label'])

    def test_every_run_gets_highlights_for_the_email(self):
        result = self.audit({})
        result['highlights'] = link_tester._highlights(result)
        self.assertTrue(result['highlights'])
        self.assertTrue(all(item['tone'] in {'ok', 'warn', 'bad'} for item in result['highlights']))


class LinkTestEmailTest(TestCase):
    def render(self, mode, screenshot):
        import datetime
        from flask import Flask
        from aicentralv2.cadu_connect import reports_link_test_email as email
        app = Flask('t', template_folder=str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'aicentralv2' / 'templates'))
        result = {'status_label': 'Atenção', 'summary': 'Resumo.', 'highlights': [{'tone': 'warn', 'text': 'Sem UTM.'}], 'evidence': {'screenshot': screenshot}}
        run = {'mode': mode, 'score': 70, 'final_url': 'https://example.com/', 'result': result, 'public_token': 'tok', 'created_at': datetime.datetime(2026, 10, 7, 12, 0)}
        with app.app_context():
            return email.render(run, 'https://reports.example/')

    def test_each_kind_has_its_own_template_with_report_link_and_screenshot(self):
        for mode in ('destination', 'media', 'agentic'):
            subject, html = self.render(mode, '/connect/public/link-tests/tok/screenshot')
            self.assertIn('70/100', subject)
            self.assertIn(f'hero-{mode}.jpg', html)
            self.assertIn('https://reports.example/connect/public/link-tests/tok', html)
            self.assertIn('https://reports.example/connect/public/link-tests/tok/screenshot', html)
            self.assertIn('Sem UTM.', html)

    def test_missing_screenshot_shows_a_placeholder_not_a_broken_image(self):
        _, html = self.render('media', None)
        self.assertIn('ainda não está disponível', html)


class MediaFormCountTest(TestCase):
    def test_a_form_present_in_raw_and_rendered_html_counts_once(self):
        page = '<html><body><form><input type="email"></form></body></html>'
        result = link_tester._media({'html': page, 'raw_html': page.replace('<body>', '<body><p>raw</p>'), 'capture': {}})
        self.assertEqual(1, result['evidence']['conversion']['forms'])


class ScreenshotOneSigningTest(TestCase):
    def test_every_capture_url_is_signed_with_the_secret(self):
        import hashlib, hmac
        from urllib.parse import urlsplit
        from aicentralv2.cadu_connect import reports_link_screenshots as shots
        for device in ('desktop', 'mobile'):
            url = shots.signed_url('https://example.com/?a=1', device, ('ACCESS', 'SECRET'))
            query, signature = urlsplit(url).query.rsplit('&signature=', 1)
            self.assertEqual(hmac.new(b'SECRET', query.encode(), hashlib.sha256).hexdigest(), signature)
            self.assertIn('access_key=ACCESS', query)
            self.assertNotIn('SECRET', url)

    def test_without_keys_no_capture_starts(self):
        from aicentralv2.cadu_connect import reports_link_screenshots as shots
        self.assertEqual({}, shots.start('https://example.com/', None))
