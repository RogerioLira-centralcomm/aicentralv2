import unittest
from unittest.mock import Mock, patch

from flask import Flask, session

from aicentralv2.creative_media.studio_agent import plan_request, suggest_narration
from aicentralv2.creative_skills import load_video_skill
from aicentralv2.services.openrouter_service import OpenRouterError


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

    def test_financial_error_is_not_hidden_by_local_fallback(self):
        def insufficient(*_args, **_kwargs):
            raise ValueError("Saldo insuficiente.")

        with self.assertRaisesRegex(ValueError, "Saldo insuficiente"):
            plan_request("Anime esta imagem", text_callable=insufficient)

    def test_provider_unavailability_still_uses_safe_local_fallback(self):
        def offline(*_args, **_kwargs):
            raise OpenRouterError("Provedores indisponíveis.")

        result = plan_request("Anime esta imagem por 5 segundos", text_callable=offline)
        self.assertEqual(result["provider"], "rules")

    def test_studio_endpoint_binds_billing_actor_and_propagates_credit_error(self):
        from aicentralv2.creative_media import studio

        app = Flask(__name__)
        app.secret_key = "test"
        modeling = Mock()
        modeling._credits_crm_id.return_value = 174
        payload = {"client_id": 31, "request_id": "request-1", "message": "Anime esta imagem"}
        http = (lambda fn: fn(), lambda: payload, lambda data: data, lambda: modeling)
        view = studio.studio_agent_plan.__wrapped__.__wrapped__

        with app.test_request_context("/studio/agent/plan", method="POST"):
            session["user_id"] = 32
            with patch.object(studio, "_http", return_value=http), \
                 patch.object(studio, "_scope"), \
                 patch("aicentralv2.services.cadu_ai_connector.CaduAIConnector.complete",
                       side_effect=ValueError("Saldo insuficiente.")) as complete:
                with self.assertRaisesRegex(ValueError, "Saldo insuficiente"):
                    view()

        call = complete.call_args.kwargs
        self.assertEqual((call["client_id"], call["user_id"]), (174, 32))
        self.assertEqual(call["estimated_tokens"], 2400)
        self.assertEqual(call["idempotency_key"], "studio:agent-plan:request-1")

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


def test_voice_prompt_keeps_narrator_direction_when_the_script_is_long():
    from aicentralv2.creative_media.studio_agent import _voice_prompt, VOICE_PROMPT_LIMIT
    direction = "Narrador brasileiro, voz grave e calorosa, ritmo pausado, sorriso na voz."
    script = "Oferta " * 150
    prompt = _voice_prompt(direction, script.strip())
    assert prompt.startswith(direction)
    assert "Conteúdo factual da peça: Oferta" in prompt
    assert len(prompt) <= VOICE_PROMPT_LIMIT


def test_voice_prompt_does_not_repeat_a_script_already_in_the_direction():
    from aicentralv2.creative_media.studio_agent import _voice_prompt
    assert _voice_prompt("Narre: Chegou o Cadu.", "Chegou o Cadu.") == "Narre: Chegou o Cadu."


class StudioStoryboardEndpointTest(unittest.TestCase):
    def _call(self, payload, complete):
        from aicentralv2.creative_media import studio

        app = Flask(__name__)
        app.secret_key = "test"
        modeling = Mock()
        modeling._credits_crm_id.return_value = 174
        modeling.get_client.return_value = {"name": "Cemig"}
        http = (lambda fn: fn(), lambda: payload, lambda data: data, lambda: modeling)
        view = studio.studio_agent_storyboard.__wrapped__.__wrapped__
        with app.test_request_context("/studio/agent/storyboard", method="POST"):
            session["user_id"] = 32
            with patch.object(studio, "_http", return_value=http), patch.object(studio, "_scope"), \
                 patch("aicentralv2.services.cadu_ai_connector.CaduAIConnector.complete", side_effect=complete) as mocked:
                try:
                    return view(), mocked
                except ValueError as error:
                    return error, mocked

    def test_monta_beats_e_cobra_o_pagador_com_chave_idempotente(self):
        beats = [{"purpose": p, "visual": "Família na sala", "motion": "push-in", "hold": "logo",
                  "transition": "cut", "spoken": ""} for p in ("hook", "offer", "end")]
        result, mocked = self._call(
            {"client_id": 31, "request_id": "r1", "briefing": "Internet fibra para famílias, 500 mega.", "duration": 15},
            lambda *a, **k: {"message": {"content": {"beats": beats}}})
        self.assertEqual(len(result["beats"]), 3)
        call = mocked.call_args.kwargs
        self.assertEqual((call["client_id"], call["user_id"]), (174, 32))
        self.assertEqual(call["idempotency_key"], "studio:storyboard:r1")
        self.assertEqual(call["stage"], "video_storyboard")

    def test_saldo_insuficiente_chega_ao_usuario(self):
        def broke(*a, **k):
            raise ValueError("Saldo insuficiente.")
        result, _ = self._call({"client_id": 31, "request_id": "r2", "briefing": "Internet fibra para famílias."}, broke)
        self.assertIsInstance(result, ValueError)
        self.assertIn("Saldo insuficiente", str(result))


class StudioStoryboardBeatEndpointTest(unittest.TestCase):
    def _call(self, payload, complete):
        from aicentralv2.creative_media import studio

        app = Flask(__name__)
        app.secret_key = "test"
        modeling = Mock()
        modeling._credits_crm_id.return_value = 174
        modeling.get_client.return_value = {"name": "Cemig"}
        http = (lambda fn: fn(), lambda: payload, lambda data: data, lambda: modeling)
        view = studio.studio_agent_storyboard_beat.__wrapped__.__wrapped__
        with app.test_request_context("/studio/agent/storyboard/beat", method="POST"):
            session["user_id"] = 32
            with patch.object(studio, "_http", return_value=http), patch.object(studio, "_scope"), \
                 patch("aicentralv2.services.cadu_ai_connector.CaduAIConnector.complete", side_effect=complete) as mocked:
                try:
                    return view(), mocked
                except ValueError as error:
                    return error, mocked

    SCENES = [{"id": "a", "purpose": "hook", "visual": "Família na sala"}, {"id": "b", "purpose": "end", "visual": "Logo final"}]

    def test_reescreve_uma_cena_e_cobra_so_texto_com_chave_propria(self):
        result, mocked = self._call(
            {"client_id": 31, "request_id": "b1", "briefing": "Internet fibra para famílias.", "beats": self.SCENES, "index": 1, "instruction": "mais direto"},
            lambda *a, **k: {"message": {"content": {"beat": {"visual": "Logo da marca sobre fundo azul", "spoken": "Fale com a gente"}}}})
        self.assertEqual(result["beat"]["id"], "b")
        call = mocked.call_args.kwargs
        self.assertEqual((call["client_id"], call["user_id"]), (174, 32))
        self.assertEqual(call["idempotency_key"], "studio:storyboard-beat:b1")
        self.assertEqual(call["stage"], "video_storyboard_beat")

    def test_indice_invalido_nao_chama_o_modelo(self):
        result, mocked = self._call(
            {"client_id": 31, "briefing": "Internet fibra para famílias.", "beats": self.SCENES, "index": "1"},
            lambda *a, **k: {"message": {"content": {"beat": {"visual": "x"}}}})
        self.assertIsInstance(result, ValueError)
        mocked.assert_not_called()


class StudioStoryboardImagePriceTest(unittest.TestCase):
    def test_preco_previo_segue_o_formato_e_a_referencia_de_estilo(self):
        from aicentralv2.creative_media.studio import _storyboard_image_prices
        wide = _storyboard_image_prices("16:9", 9999)
        square = _storyboard_image_prices("1:1", 9999)
        self.assertGreater(wide["credits_with_reference"], wide["credits_per_image"])
        self.assertLess(square["credits_per_image"], wide["credits_per_image"])
        self.assertNotEqual(wide["credits_per_image"], 9999)

    def test_falha_na_estimativa_cai_para_o_valor_padrao(self):
        from aicentralv2.creative_media.studio import _storyboard_image_prices
        with patch("aicentralv2.creative_media.studio_create.provider_canvas", side_effect=RuntimeError("x")):
            self.assertEqual(_storyboard_image_prices("16:9", 4977), {"credits_per_image": 4977, "credits_with_reference": 4977})


class StudioStoryboardImageEndpointTest(unittest.TestCase):
    def _call(self, payload, *, claim=None, owned=("/static/a.png",), create=None, library=None):
        from aicentralv2.creative_media import studio, studio_create

        app = Flask(__name__)
        app.secret_key = "test"
        modeling = Mock()
        modeling.add_format_lab_swap_library_still.side_effect = library or (lambda *a, **k: {"id": "lib-1", "run_id": "run-1"})
        history = Mock()
        history.claim_image.return_value = claim or {"state": "claimed"}
        history.owned_image_urls.return_value = set(owned)
        create = create or Mock(return_value={"image_url": "/static/new.png", "charged_credits": 120})
        http = (lambda fn: fn(), lambda: payload, lambda data: data, lambda: modeling)
        view = studio.studio_storyboard_image.__wrapped__.__wrapped__
        with app.test_request_context("/studio/agent/storyboard/image", method="POST"):
            session["user_id"] = 32
            with patch.object(studio, "_http", return_value=http), patch.object(studio, "_scope"), \
                 patch.object(studio, "_creation_history", return_value=history), \
                 patch.object(studio_create, "create_image", create):
                try:
                    return view(), create, history, modeling
                except (ValueError, RuntimeError) as error:
                    return error, create, history, modeling

    BEAT = {"visual": "Família na sala com o roteador", "hold": "logo da marca"}

    def test_gera_a_imagem_limpa_e_entrega_a_cena_da_biblioteca(self):
        out, create, history, modeling = self._call(
            {"client_id": 31, "request_id": "req-12345678", "beat": self.BEAT, "index": 1, "total": 3, "aspect_ratio": "9:16"})
        self.assertEqual((out["scene_id"], out["run_id"], out["charged_credits"]), ("lib-1", "run-1", 120))
        request = create.call_args.args[0]
        self.assertEqual(request["creation_intent"], "neutral_asset")
        self.assertEqual(request["references"], [])
        self.assertIn("Família na sala", request["prompt"])
        self.assertIn("Sem texto", request["prompt"])
        self.assertEqual(create.call_args.args[2:], (31, 32))

    def test_primeira_imagem_aprovada_vira_referencia_de_estilo(self):
        _, create, _, _ = self._call(
            {"client_id": 31, "request_id": "req-12345678", "beat": self.BEAT, "index": 1, "total": 3, "anchor_url": "/static/a.png"})
        reference = create.call_args.args[0]["references"][0]
        self.assertEqual((reference["url"], reference["role"]), ("/static/a.png", "style"))

    def test_referencia_de_outra_marca_e_recusada_antes_de_cobrar(self):
        out, create, _, _ = self._call(
            {"client_id": 31, "request_id": "req-12345678", "beat": self.BEAT, "anchor_url": "/static/outra.png"})
        self.assertIsInstance(out, ValueError)
        create.assert_not_called()

    def test_dry_run_so_informa_o_custo(self):
        out, create, _, _ = self._call({"client_id": 31, "dry_run": True})
        self.assertIn("credits_per_image", out)
        create.assert_not_called()

    def test_clique_repetido_nao_gera_nem_cobra_de_novo(self):
        out, create, _, _ = self._call(
            {"client_id": 31, "request_id": "req-12345678", "beat": self.BEAT}, claim={"state": "pending"})
        self.assertIsInstance(out, ValueError)
        create.assert_not_called()
        out, create, _, _ = self._call(
            {"client_id": 31, "request_id": "req-12345678", "beat": self.BEAT},
            claim={"state": "completed", "result": {"image_url": "/static/new.png", "scene_id": "lib-9", "run_id": "r"}})
        self.assertEqual((out["scene_id"], out["replayed"]), ("lib-9", True))
        create.assert_not_called()

    def test_falha_na_biblioteca_depois_de_pago_fecha_a_geracao(self):
        def broken(*a, **k):
            raise RuntimeError("biblioteca fora do ar")
        out, _, history, _ = self._call(
            {"client_id": 31, "request_id": "req-12345678", "beat": self.BEAT}, library=broken)
        self.assertIsInstance(out, RuntimeError)
        # concluída antes da falha: o retry reencontra a imagem paga em vez de ficar preso em "pendente"
        history.complete_image.assert_called_once()
        history.fail_image.assert_not_called()
