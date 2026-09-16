from unittest import TestCase
from aicentralv2.cadu_connect.import_recognition import recognize_platform


class ImportRecognitionTests(TestCase):
    def test_recognizes_known_platforms_without_guessing(self):
        self.assertEqual(recognize_platform('Meta Ads', 'maio.png')['platform'], 'Meta Ads')
        self.assertEqual(recognize_platform('', 'relatorio_googleads_maio.xlsx')['platform'], 'Google Ads')
        self.assertEqual(recognize_platform('', 'resultado-final.pdf')['platform'], 'Não identificado')
