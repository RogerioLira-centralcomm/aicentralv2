from unittest import TestCase
from aicentralv2.cadu_connect.report_analysis import extraction_messages, normalize_suggestion


class ReportAnalysisTests(TestCase):
    def test_message_is_source_bound_and_uses_image_data(self):
        messages = extraction_messages({'id': 7, 'image_bytes': b'png'}, {'campaign_name': 'Aurora'})
        self.assertIn('source_id=7', messages[1]['content'][0]['text'])
        self.assertTrue(messages[1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,'))

    def test_suggestion_requires_evidence_and_matching_source(self):
        payload = {'source_id': 7, 'metrics': [dict(name='Cliques', raw='120', unit='count', definition='Cliques', scope='01–31 maio', evidence='Tabela', confidence='high')]}
        self.assertEqual(normalize_suggestion(payload, 7)['metrics'][0]['name'], 'Cliques')
        with self.assertRaises(ValueError): normalize_suggestion(dict(payload, source_id=8), 7)
