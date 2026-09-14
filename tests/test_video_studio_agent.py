import unittest

from aicentralv2.creative_media.studio_agent import plan_request, suggest_narration
from aicentralv2.creative_skills import load_video_skill


class StudioAgentPlanTest(unittest.TestCase):
    def test_seedance_skill_is_installed_in_runtime_catalog(self):
        skill = load_video_skill("seedance-2-5-image-to-video")
        self.assertIn("Uma imagem por geração", skill)
        self.assertIn("Saída 720p", skill)

    def test_single_image_plan_enforces_skill_contract(self):
        plan = plan_request(
            "Anime esta imagem por 8 segundos com câmera suave, som ambiente, formato 9:16 e seed 42",
            {"selected_scene": {"id": "scene-1", "aspect_ratio": "1:1"}},
        )
        self.assertEqual(plan["skill"], "seedance-2-5-image-to-video")
        self.assertEqual(plan["patch"]["generation_mode"], "single_image")
        self.assertEqual(plan["patch"]["duration"], 8)
        self.assertEqual(plan["patch"]["quality"], "production")
        self.assertIsNone(plan["patch"]["seed"])
        self.assertEqual(plan["patch"]["aspect_ratio"], "9:16")
        self.assertTrue(plan["patch"]["audio"]["enabled"])
        self.assertTrue(plan["patch"]["audio"]["ambience"])
        self.assertTrue(any("seed não é suportada" in item for item in plan["warnings"]))

    def test_agent_rejects_untrusted_fields_from_model(self):
        def model(*_args, **_kwargs):
            return {"message": {"content": {
                "summary": "Plano",
                "steps": ["Gerar agora"],
                "patch": {
                    "generation_mode": "single_image",
                    "duration": 12,
                    "delete_all": True,
                    "edit": {"sound_volume": 50, "command": "rm"},
                },
            }}}
        plan = plan_request("Anime esta imagem", {"selected_scene": {"id": "scene-1"}}, text_callable=model)
        self.assertNotIn("delete_all", plan["patch"])
        self.assertNotIn("duration", plan["patch"])
        self.assertEqual(plan["patch"]["edit"], {"sound_volume": 1})
        self.assertEqual(plan["provider"], "ai")

    def test_missing_image_is_explained_before_apply(self):
        plan = plan_request("Anime esta imagem por 5 segundos", {})
        self.assertTrue(any("Selecione uma imagem" in item for item in plan["warnings"]))

    def test_empty_request_is_rejected(self):
        with self.assertRaises(ValueError):
            plan_request("  ")

    def test_agent_combines_narration_music_and_ambience(self):
        plan = plan_request("Com narração, música de fundo e efeitos de ambiente")
        self.assertEqual(plan["patch"]["audio"]["narration_mode"], "guided")
        self.assertTrue(plan["patch"]["audio"]["music_enabled"])
        self.assertTrue(plan["patch"]["audio"]["ambience"])

    def test_narration_fallback_uses_only_creative_copy_and_duration(self):
        result = suggest_narration({"scenes": [{
            "headline": "Internet de 500 Mega",
            "support": "Por R$ 89,99 por mês",
            "cta": "Confira os planos",
        }]}, duration=5)
        self.assertIn("500 Mega", result["script"])
        self.assertLessEqual(len(result["script"].split()), 11)
        self.assertEqual(result["provider"], "rules")

    def test_narration_drops_model_copy_with_an_unknown_number(self):
        def model(*_args, **_kwargs):
            return {"message": {"content": {
                "script": "Ganhe 900 Mega agora.",
                "prompt": "Voz animada",
            }}}
        result = suggest_narration(
            {"scenes": [{"headline": "Internet de 500 Mega", "cta": "Confira"}]},
            duration=8,
            text_callable=model,
        )
        self.assertIn("500 Mega", result["script"])
        self.assertNotIn("900", result["script"])

    def test_agent_edits_the_open_clip_without_triggering_generation(self):
        plan = plan_request(
            "Corte para começar em 2s, terminar em 8s e deixe em 0,5x com volume em 35%",
            {"has_clip": True, "clip": {"id": "clip-1", "duration": 10, "has_audio": True}},
        )
        self.assertEqual(plan["patch"]["edit"]["start"], 2)
        self.assertEqual(plan["patch"]["edit"]["end"], 8)
        self.assertEqual(plan["patch"]["edit"]["speed"], .5)
        self.assertEqual(plan["patch"]["edit"]["original_volume"], .35)
        self.assertFalse(plan["requires_generation"])

    def test_agent_explains_that_an_edit_needs_an_open_clip(self):
        plan = plan_request("Deixe em câmera lenta")
        self.assertTrue(any("Abra um clipe" in item for item in plan["warnings"]))


if __name__ == "__main__":
    unittest.main()
