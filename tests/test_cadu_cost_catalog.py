import unittest

from aicentralv2.cadu_cost_catalog import cost_metadata, usage_metadata


class CaduCostCatalogTest(unittest.TestCase):
    def test_audio_transcription_has_standard_metadata(self):
        item = cost_metadata("whisper", modality="audio", operation="transcription")
        self.assertEqual(item.modality, "audio")
        self.assertEqual(item.unit, "minute")

    def test_video_and_perplexity_use_different_technical_catalog_entries(self):
        perplexity = cost_metadata("perplexity/sonar-pro")
        video = cost_metadata("bytedance/seedance", modality="video")
        self.assertNotEqual(perplexity.technical_unit_cost_usd, video.technical_unit_cost_usd)

    def test_usage_metadata_has_global_contract(self):
        data = usage_metadata(model="perplexity/sonar-pro", technical_units=2,
                              technical_cost_usd="2", cadu_tokens_charged=200,
                              idempotency_key="abc")
        self.assertEqual(data["technical_units"], 2)
        self.assertEqual(data["cadu_tokens_charged"], 200)
        self.assertEqual(data["commercial_rule_version"], "cadu-commercial-v1")


if __name__ == "__main__":
    unittest.main()
