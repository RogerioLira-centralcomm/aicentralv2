from unittest import TestCase
from scripts.inventory_cadu_conversations import inspect_source, markdown


class InventoryTest(TestCase):
    def test_only_names_and_locations_are_extracted(self):
        source = """const password = 'DO_NOT_EXPORT';
  async sendMessage(query) {
    fetch('/api/chat/tools.php');
  }
function load(array $params): array {
 $prompt = $params['prompt'];
 SELECT * FROM cadu_conversations;
}
"""
        result = inspect_source(source)
        self.assertNotIn('DO_NOT_EXPORT', str(result))
        self.assertEqual(result['symbols'][0], {'name': 'sendMessage', 'line': 2})
        self.assertEqual(result['php_fields'], [{'name': 'prompt', 'line': 6}])
        self.assertEqual(result['tables'][0]['name'], 'cadu_conversations')

    def test_control_flow_is_not_counted_as_function(self):
        self.assertEqual(inspect_source('if (ready) {\nwhile (true) {')['symbols'], [])

    def test_report_warns_about_lexical_inventory(self):
        output = markdown({'summary': {'files': 0}, 'tools': [], 'files': [], 'limitations': 'Not feature parity'})
        self.assertIn('Not feature parity', output)

    def test_scope_separates_docs_and_excluded_tools(self):
        tools = [{'alias': name, 'file': file, 'class': 'Tool', 'line': 1}
                 for name, file in [('doc', 'DocSaver.php'), ('cotacao', 'CotacaoCreator.php'),
                                    ('analytics_data', 'AnalyticsData.php'), ('channel_search', 'ChannelSearch.php')]]
        output = markdown({'summary': {}, 'tools': tools, 'files': [], 'limitations': ''})
        self.assertIn('DocSaver.php | Conexão com Docs do Media/SmartPlanner', output)
        self.assertIn('CotacaoCreator.php | Fora desta migração', output)
        self.assertIn('AnalyticsData.php | Fora desta migração', output)
        self.assertIn('ChannelSearch.php | Referência para reconstrução', output)
