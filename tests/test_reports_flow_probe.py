import unittest

from aicentralv2.cadu_connect import reports_flow_probe as probe
from aicentralv2.cadu_connect.reports_flow import _normalize_flow_config

LEAD = '''<html><head><title>Oferta</title><script>gtag('event','page_view')</script></head><body><h1>Fale agora</h1>
<form action="/enviar" method="post"><label for="n">Nome</label><input id="n" name="nome" required>
<input name="email" type="email" required><input name="fone" type="tel"><textarea name="msg"></textarea>
<input type="checkbox" name="lgpd" required><button type="submit">Quero uma proposta</button></form>
<a href="https://wa.me/5511900000000">Whats</a></body></html>'''


class ProbeTests(unittest.TestCase):
    def test_parse_and_classify_lead_form(self):
        summary = probe.parse_page(LEAD, 'https://x.com/lp-oferta')
        form = summary['forms'][0]
        self.assertEqual(probe.classify_form(form), 'lead')
        self.assertEqual(form['submit_label'], 'Quero uma proposta')
        self.assertEqual(form['fields'][0]['label'], 'Nome')
        self.assertTrue(summary['whatsapp'])
        self.assertTrue(probe.submit_safety(form)[0])

    def test_unsafe_forms_are_blocked(self):
        for html, word in [('<form><input name="email" type="email"><div class="g-recaptcha" data-sitekey="k"></div></form>', 'anti-robô'),
                           ('<form><input name="u"><input type="password" name="p"></form>', 'acesso'),
                           ('<form><input name="q" type="search"></form>', 'Busca'),
                           ('<form><input name="numero_cartao"><input name="nome"></form>', 'pagamento')]:
            form = probe.parse_page(html)['forms'][0]
            allowed, reason = probe.submit_safety(form)
            self.assertFalse(allowed)
            self.assertIn(word, reason)

    def test_fake_values_are_marked_and_never_invent_documents(self):
        form = probe.parse_page(LEAD)['forms'][0]
        values = probe.fake_values(form, 'abc')['values']
        self.assertTrue(values['email'].endswith('@example.invalid'))
        self.assertTrue(values['lgpd'])
        doc = probe.parse_page('<form><input name="cpf" required><input name="email" type="email"></form>')['forms'][0]
        self.assertEqual(probe.fake_values(doc)['unfilled'], ['cpf'])

    def test_outcomes(self):
        self.assertEqual(probe.classify_outcome('https://x.com/a', 'https://x.com/obrigado')['type'], 'redirect_confirmation')
        self.assertEqual(probe.classify_outcome('https://x.com/a', 'https://x.com/a', 'Mensagem enviada!')['type'], 'in_page_message')
        self.assertEqual(probe.classify_outcome('https://x.com/a', 'https://x.com/a', '')['type'], 'no_confirmation_signal')

    def test_landing_proposal_is_valid_flow_config(self):
        result = probe.analyze_html(LEAD, 'https://x.com/lp-oferta', '/lp-oferta')
        self.assertEqual(result['site_kind']['kind'], 'landing')
        proposal = result['proposal']
        self.assertTrue(any('confirmação' in warning or 'pixel' in warning for warning in proposal['warnings']))
        types = [node['type'] for node in proposal['nodes']]
        self.assertEqual(types[0], 'source')
        self.assertIn('page', types)
        self.assertIn('event', types)
        self.assertEqual(types[-1], 'conversion')
        self.assertTrue(all(node['x'] >= 80 for node in proposal['nodes']))
        self.assertTrue(any(edge.get('variant') == 'planned' for edge in proposal['edges']))
        config, _ = _normalize_flow_config({'nodes': proposal['nodes'], 'edges': proposal['edges']}, 'x.com')
        self.assertEqual(len(config['nodes']), len(proposal['nodes']))

    def test_multipage_defers_to_catalog(self):
        links = ''.join(f'<a href="/p{i}">p</a>' for i in range(30))
        result = probe.analyze_html(f'<html><body>{links}</body></html>', 'https://x.com/', '/')
        self.assertEqual(result['site_kind']['kind'], 'multipagina')
        self.assertTrue(result['proposal']['use_catalog'])

    def test_cooldown(self):
        self.assertTrue(probe.cooldown_ok('f-test', 10, now=100.0)[0])
        self.assertFalse(probe.cooldown_ok('f-test', 10, now=105.0)[0])
        self.assertTrue(probe.cooldown_ok('f-test', 10, now=111.0)[0])


if __name__ == '__main__':
    unittest.main()


class LandingMeasurementTests(unittest.TestCase):
    def test_landing_steps_are_ones_the_tag_measures(self):
        result = probe.analyze_html(LEAD, 'https://x.com/lp-oferta', '/lp-oferta')
        nodes = result['proposal']['nodes']
        self.assertIn('scroll_depth', [node.get('event_name') for node in nodes])
        self.assertIn('whatsapp', [node['type'] for node in nodes])
        self.assertNotIn('cta_click', [node.get('event_name') for node in nodes])

    def test_scroll_step_matches_mirrored_event(self):
        from aicentralv2.cadu_connect.reports_flow_matching import match_flow_node
        node = {'id': 'e', 'type': 'event', 'path': '/lp', 'event_name': 'scroll_depth'}
        self.assertEqual(match_flow_node([node], '/lp', 'x.com', 'custom_event', 'scroll_depth'), node)
        self.assertIsNone(match_flow_node([node], '/lp', 'x.com', 'custom_event', 'outro'))
