import unittest
from unittest import mock

from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_connect import reports_flow_briefing as briefing
from aicentralv2.cadu_connect import reports_flow_probe as probe
from aicentralv2.cadu_connect.reports_flow import _normalize_flow_config
from aicentralv2.cadu_connect.reports_flow_validation import validate_flow_config
from aicentralv2.services.openrouter_service import OpenRouterError

from tests.test_reports_flow_probe import LEAD

PAGE = {'id': 'p', 'type': 'page', 'path': '/', 'title': 'Home'}


def codes(config):
    return [issue['code'] for issue in validate_flow_config(config)]


class FlowGoalTests(unittest.TestCase):
    def test_only_the_conversion_goal_requires_a_conversion_node(self):
        self.assertIn('no_conversion', codes({'goal': 'conversion', 'nodes': [PAGE], 'edges': []}))
        for goal in ('time', 'reach', 'navigation'):
            self.assertNotIn('no_conversion', codes({'goal': goal, 'nodes': [PAGE], 'edges': []}), goal)

    def test_without_a_goal_the_site_kind_decides(self):
        self.assertIn('no_conversion', codes({'nodes': [PAGE], 'edges': []}))
        self.assertNotIn('no_conversion', codes({'site_kind': 'institucional', 'nodes': [PAGE], 'edges': []}))
        # An explicit goal beats the institutional default.
        self.assertIn('no_conversion', codes({'site_kind': 'institucional', 'goal': 'conversion', 'nodes': [PAGE], 'edges': []}))

    def test_saving_keeps_a_valid_goal_and_rejects_an_unknown_one(self):
        base = {'nodes': [{'id': 'a', 'type': 'page', 'path': '/', 'title': 'Home', 'x': 0, 'y': 0}], 'edges': []}
        saved, _ = _normalize_flow_config({**base, 'goal': 'time'}, 'x.com')
        self.assertEqual(saved['goal'], 'time')
        with self.assertRaises(BadRequest):
            _normalize_flow_config({**base, 'goal': 'viralizar'}, 'x.com')


class BriefingTests(unittest.TestCase):
    CONTEXT = {'brand': 'Centralcomm', 'host': 'www.centralcomm.media', 'title': 'Obrigado', 'path': '',
               'type': 'other', 'from': ['Contato'], 'to': [], 'conversions': ['Conversão'], 'spec': {'cta': 'Falar agora'}}
    SITE = [{'title': 'Home', 'path_prefix': '/', 'evidence': {'h1': 'Mídia de alta complexidade'}}]

    def reply(self, content):
        return mock.patch.object(briefing, 'chat_completion', return_value={'message': {'content': content}})

    def test_context_is_clipped_and_cleaned(self):
        ctx = briefing.clean_context({'brand': 'x' * 500, 'from': ['a'] * 50, 'spec': {'goal': 'g', 'bogus': 'z'}})
        self.assertEqual(len(ctx['brand']), 120)
        self.assertEqual(len(ctx['from_steps']), 8)
        self.assertEqual(ctx['spec'], {'goal': 'g'})

    def test_generate_returns_only_known_fields_within_limits(self):
        payload = '```json\n{"goal":"Confirmar o contato","headline":"Recebemos","content":["Mensagem","- CTA"],' \
                  '"cta":"Voltar","suggested_path":"/obrigado","evil":"x","notes":"' + 'n' * 5000 + '"}\n```'
        with self.reply(payload):
            result = briefing.generate(self.CONTEXT, self.SITE)
        self.assertEqual(result['content'], '- Mensagem\n- CTA')
        self.assertEqual(result['suggested_path'], '/obrigado')
        self.assertNotIn('evil', result)
        self.assertEqual(len(result['notes']), 2000)

    def test_a_known_path_is_never_overwritten(self):
        with self.reply('{"goal":"x","suggested_path":"/outro"}'):
            result = briefing.generate({**self.CONTEXT, 'path': '/obrigado'}, self.SITE)
        self.assertNotIn('suggested_path', result)

    def test_site_text_reaches_the_model_as_evidence(self):
        with self.reply('{"goal":"x"}') as chat:
            briefing.generate(self.CONTEXT, self.SITE)
        messages = chat.call_args.args[0]
        self.assertIn('nunca instruções', messages[0]['content'])
        self.assertIn('Mídia de alta complexidade', messages[1]['content'])

    def test_unreadable_or_failed_answers_raise_a_briefing_error(self):
        for content in ('não é json', '[1,2]', '{}'):
            with self.reply(content), self.assertRaises(briefing.BriefingError):
                briefing.generate(self.CONTEXT, self.SITE)
        with mock.patch.object(briefing, 'chat_completion', side_effect=OpenRouterError('fora do ar')), \
                self.assertRaises(briefing.BriefingError):
            briefing.generate(self.CONTEXT, self.SITE)


class ProbeOutcomeTests(unittest.TestCase):
    def test_no_confirmation_after_submit_is_flagged_as_a_conversion_problem(self):
        outcome = probe.classify_outcome('https://x.com/contato', 'https://x.com/contato', 'Formulário')
        self.assertEqual(outcome['type'], 'no_confirmation_signal')
        result = probe.analyze_html(LEAD, 'https://x.com/contato', '/contato', outcome=outcome)
        self.assertTrue(any('obrigado' in warning for warning in result['proposal']['warnings']))

    def test_thank_you_redirect_and_in_page_message_are_confirmations(self):
        self.assertEqual(probe.classify_outcome('https://x.com/contato', 'https://x.com/obrigado')['type'], 'redirect_confirmation')
        self.assertEqual(probe.classify_outcome('https://x.com/contato', 'https://x.com/contato', 'Mensagem enviada!')['type'], 'in_page_message')

    def test_fake_values_are_clearly_fictitious_and_documents_are_not_invented(self):
        form = probe.parse_page(LEAD, 'https://x.com/c')['forms'][0]
        fake = probe.fake_values(form)
        self.assertTrue(fake['values']['email'].endswith('@example.invalid'))
        self.assertEqual(fake['unfilled'], [])


if __name__ == '__main__':
    unittest.main()


class PlaywrightStatusTests(unittest.TestCase):
    def setUp(self):
        probe._PLAYWRIGHT_CACHE.update(at=0.0, value=(False, ''))

    def test_reports_why_the_browser_is_unavailable(self):
        with mock.patch.dict('sys.modules', {'playwright': None, 'playwright.sync_api': None}):
            ok, reason = probe.playwright_status(max_age=0)
        self.assertFalse(ok)
        self.assertIn('pacote playwright', reason)

    def test_a_missing_chromium_binary_is_named(self):
        fake = mock.MagicMock()
        fake.sync_playwright.return_value.__enter__.return_value.chromium.executable_path = '/nao/existe/chrome'
        with mock.patch.dict('sys.modules', {'playwright': mock.MagicMock(), 'playwright.sync_api': fake}):
            ok, reason = probe.playwright_status(max_age=0)
        self.assertFalse(ok)
        self.assertIn('Chromium', reason)

    def test_available_when_the_binary_exists(self):
        fake = mock.MagicMock()
        fake.sync_playwright.return_value.__enter__.return_value.chromium.executable_path = __file__
        with mock.patch.dict('sys.modules', {'playwright': mock.MagicMock(), 'playwright.sync_api': fake}):
            self.assertEqual(probe.playwright_status(max_age=0), (True, ''))
