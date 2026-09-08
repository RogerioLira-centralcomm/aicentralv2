import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CrmV3FeedbackContractTest(unittest.TestCase):
    def test_crm_nao_usa_confirmacoes_ou_alertas_bloqueantes(self):
        scripts = "\n".join(
            (
                (ROOT / "aicentralv2/static/js/crm_v3.js").read_text(),
                (ROOT / "aicentralv2/static/js/crm_v3_drawers.js").read_text(),
            )
        )
        templates = "\n".join(
            (
                (ROOT / "aicentralv2/templates/crm_v3.html").read_text(),
                (ROOT / "aicentralv2/templates/crm_v3/_modals.html").read_text(),
                (
                    ROOT
                    / "aicentralv2/templates/crm_v3/_drawer_cotacao.html"
                ).read_text(),
            )
        )

        self.assertIsNone(re.search(r"\b(?:window\.)?confirm\s*\(", scripts))
        self.assertIsNone(re.search(r"\b(?:window\.)?alert\s*\(", scripts))
        self.assertNotIn('role="alert"', templates)
        self.assertNotIn('id="crm-v3-modal-confirm-obj"', templates)
        self.assertNotIn('id="cx-cot-unlink-dialog"', templates)


if __name__ == "__main__":
    unittest.main()
