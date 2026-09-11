"""Contrato dos cinco agentes: fronteiras e slugs OpenRouter."""

import unittest
from unittest.mock import Mock

from aicentralv2.creative_agents.contract import PieceContract
from aicentralv2.creative_agents.models import AGENT_MODELS, assert_openrouter_gpt
from aicentralv2.creative_agents.orchestrator import run_agent
from aicentralv2.creative_agents import dna, extractor, producer, reviewer, scriptwriter
from aicentralv2.creative_modeling_service import CreativeModelingService
from tests.test_modelagem_criativos import FakeStorage


def _llm(payload):
    def _call(*args, **kwargs):
        return {"message": {"content": payload}, "model": kwargs.get("model")}
    return _call


class CreativeAgentsContractTest(unittest.TestCase):
    def test_modelos_sao_gpt_no_openrouter(self):
        for name, slug in AGENT_MODELS.items():
            self.assertTrue(slug.startswith("openai/gpt-"), name)
            self.assertEqual(assert_openrouter_gpt(slug), slug)
        with self.assertRaises(ValueError):
            assert_openrouter_gpt("anthropic/claude-sonnet-4")

    def test_dna_nao_escreve_copy_de_campanha(self):
        result = dna.run(
            PieceContract(campaign_id="x", scenes=[]),
            brand_id="tim",
            brand_profile={"color_palette": ["#0033A0"]},
        )
        self.assertEqual(result.brand_id, "tim")
        self.assertTrue(result.tokens.get("palette"))
        self.assertEqual(result.scenes, [])
        self.assertEqual(result.instance_data, {})

    def test_extrator_recusa_copy_no_json(self):
        with self.assertRaises(ValueError):
            extractor.run(
                text_callable=_llm(
                    '{"family":"square_1x1","regions":[],"tokens":{"headline":"Oferta"}}'
                ),
                image_url="data:image/png;base64,xx",
            )

    def test_roteirista_recusa_variacao_inventada(self):
        with self.assertRaises(ValueError):
            scriptwriter.run(
                text_callable=_llm(
                    '{"template_variation":"layout-secreto","scenes":[]}'
                ),
                family="sequence_16x9",
                library=[{"id": "seed-sequence-line"}],
                brief="Black Família",
            )

    def test_roteirista_escolhe_carta_existente(self):
        result = scriptwriter.run(
            text_callable=_llm(
                '{"template_variation":"seed-sequence-line","scenes":['
                '{"role":"gancho","copy_on_frame":false},'
                '{"role":"contexto","copy_on_frame":false},'
                '{"role":"beneficio","copy_on_frame":false},'
                '{"role":"fechamento","copy_on_frame":true}]}'
            ),
            family="sequence_16x9",
            library=[{"id": "seed-sequence-line"}],
            brief="Black Família",
        )
        self.assertEqual(result.template_variation, "seed-sequence-line")
        self.assertEqual(result.status, "roteirizado")
        self.assertFalse(result.scenes[0].copy_on_frame)
        self.assertTrue(result.scenes[-1].copy_on_frame)
        self.assertFalse(result.scenes[0].headline)

    def test_produtor_nao_mexe_no_schema(self):
        start = PieceContract(
            template_id="square-feed-v1",
            template_variation="seed-square-right",
            family="square_1x1",
            params={"photo_side": "right", "headline_font_size": 26, "cta_gap": 12},
        )
        result = producer.run(start, headline="Oferta", cta="Assine")
        self.assertEqual(result.instance_data["headline"], "Oferta")
        self.assertEqual(result.params["photo_side"], "right")
        self.assertEqual(result.family, "square_1x1")
        self.assertEqual(result.status, "produzido")

    def test_revisor_nao_reescreve_peca(self):
        start = PieceContract(
            family="sequence_16x9",
            instance_data={"headline": "Oferta"},
            params={"scenography": "line"},
            scenes=[{"role": "fechamento", "copy_on_frame": True}],
        )
        result = reviewer.run(start, expected_headline="Oferta")
        self.assertEqual(result.instance_data["headline"], "Oferta")
        self.assertEqual(result.params, start.params)
        self.assertEqual(result.status, "aguardando_aprovacao")
        self.assertTrue(result.qa.passed)

    def test_orquestrador_encadeia_o_mesmo_contrato(self):
        drafted = run_agent(
            "scriptwriter",
            {
                "family": "square_1x1",
                "library": [{"id": "seed-square-right"}],
                "brief": "TIM",
            },
            text_callable=_llm(
                '{"template_variation":"seed-square-right","scenes":[{"role":"unico","copy_on_frame":true}]}'
            ),
        )
        filled = run_agent(
            "producer",
            {"headline": "Plano", "cta": "Ver"},
            contract=drafted,
        )
        self.assertEqual(filled.template_variation, "seed-square-right")
        self.assertEqual(filled.instance_data["headline"], "Plano")

    def test_servico_expoe_o_agente(self):
        service = CreativeModelingService(
            repository=Mock(),
            generator=Mock(),
            storage=FakeStorage(),
        )
        result = service.run_creative_agent("dna", {
            "brand_id": "tim",
            "brand_profile": {"color_palette": ["#0033A0"]},
        })
        self.assertEqual(result["brand_id"], "tim")

    def test_extrator_grava_rascunho_na_biblioteca(self):
        repo = Mock()
        repo.list_compose_templates.return_value = [
            {"id": 9, "slug": "square-feed-v1"},
        ]
        repo.create_compose_variation.return_value = {
            "id": 77,
            "template_id": 9,
            "name": "Rascunho extraído",
            "params": {},
            "status": "experimental",
        }
        service = CreativeModelingService(
            repository=repo,
            generator=Mock(),
            storage=FakeStorage(),
        )
        result = service.run_creative_agent("extractor", {
            "image_url": "data:image/png;base64,xx",
            "family": "square_1x1",
            "text_callable": _llm(
                '{"family":"square_1x1","regions":'
                '[{"tipo":"logo","x":4,"y":6,"w":12,"h":10}],'
                '"tokens":{},"params":{}}'
            ),
        })
        self.assertEqual(result["saved_variation"]["id"], 77)
        self.assertEqual(result["family"], "square_1x1")
        self.assertEqual(result["saved_variation"]["template_id"], 9)
        self.assertEqual(result["saved_variation"]["template_slug"], "square-feed-v1")
        repo.create_compose_variation.assert_called_once()

    def test_desdobrar_nao_e_agente(self):
        with self.assertRaises(ValueError):
            run_agent("unfold", {})

    def test_copywriter_na_bancada_respeita_limite_do_dna(self):
        result = producer.run(
            PieceContract(
                brand_dna={"fonts": {"primary": "Manrope", "fallback": "Manrope"}, "text_limits": {"headline_max_chars": 12, "subhead_max_chars": 8}},
                regions=[{"tipo": "texto", "x": 8, "y": 6, "w": 70, "h": 16}],
            ),
            headline="Headline longo demais para o slot",
            cta="Comprar agora já",
        )
        self.assertLessEqual(len(result.instance_data["headline"]), 12)
        self.assertLessEqual(len(result.instance_data["cta"]), 8)
        self.assertEqual(result.brand_dna["fonts"]["primary"], "Manrope")

    def test_brand_checker_bloqueia_fonte_errada(self):
        result = reviewer.run(
            PieceContract(
                brand_dna={"fonts": {"primary": "Manrope", "fallback": "Manrope"}},
                regions=[{
                    "tipo": "texto",
                    "x": 8, "y": 6, "w": 70, "h": 16,
                    "content": {"text": "Pai", "font": "Impact"},
                }],
            ),
        )
        self.assertFalse(result.qa.passed)
        self.assertEqual(result.status, "reprovado")
        self.assertTrue(any("fonte" in note for note in result.qa.notes))


if __name__ == "__main__":
    unittest.main()
