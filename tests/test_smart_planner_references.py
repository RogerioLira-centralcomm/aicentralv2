import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from aicentralv2.smart_planner import planner, processor
from aicentralv2.smart_planner.helpers import looks_like_reference_dump, strip_markdown
from aicentralv2.smart_planner.materials import (
    apoio_block,
    compose_material,
    normalize_reference,
    scrape_url,
)
from aicentralv2.smart_planner.references import capture_file, capture_search, capture_url, review_reference
from aicentralv2.smart_planner.service import wizard_context


class SmartPlannerReferencesTest(unittest.TestCase):
    def test_strip_markdown_removes_headings_and_fences(self):
        cleaned = strip_markdown("```md\n## Menu\n- Home\n**Oferta** relâmpago\n```")
        self.assertNotIn("##", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertIn("Oferta relâmpago", cleaned)

    def test_looks_like_reference_dump(self):
        self.assertTrue(looks_like_reference_dump("## Referência — página: marca.com\nHome Contato"))
        self.assertTrue(looks_like_reference_dump("## Notas de apoio (url: marca.com)\nProduto"))
        self.assertFalse(looks_like_reference_dump("Cliente quer lançar a linha premium em outubro."))

    def test_scrape_url_prefers_firecrawl_main_content(self):
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "fc-test"}, clear=False), patch(
            "aicentralv2.crm_v3_web_scout._firecrawl_scrape",
            return_value={"markdown": "Produto premium da marca, sem menu de cookie." * 3},
        ) as scrape:
            raw = scrape_url("https://marca.com/campanha")
        self.assertIn("Produto premium", raw)
        scrape.assert_called_once()
        self.assertTrue(scrape.call_args.kwargs["only_main_content"])
        self.assertEqual(scrape.call_args.kwargs["formats"], ["markdown"])

    def test_scrape_url_falls_back_to_html_parser(self):
        html = "<html><body><nav>Menu</nav><p>" + ("Conteúdo principal da campanha. " * 8) + "</p></body></html>"
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": ""}, clear=False), patch(
            "aicentralv2.services.integration_credentials.resolve_firecrawl_api_key",
            return_value="",
        ), patch(
            "aicentralv2.smart_planner.materials.requests.get"
        ) as get:
            get.return_value.text = html
            get.return_value.raise_for_status = lambda: None
            raw = scrape_url("https://marca.com/campanha")
        self.assertIn("Conteúdo principal da campanha", raw)

    def test_review_reference_strips_markdown_and_keeps_facts(self):
        with patch("aicentralv2.smart_planner.references.chat_json", return_value={
            "notas": "## Marca\n**Churrascaria** com delivery em BH.",
            "fatos": {"cliente": "Montana Grill", "praca_detalhe": "Belo Horizonte"},
            "papel": "marca",
        }):
            reviewed = review_reference("x" * 120, kind="url", label="montana.com")
        self.assertNotIn("##", reviewed["notas"])
        self.assertNotIn("**", reviewed["notas"])
        self.assertIn("Churrascaria", reviewed["notas"])
        self.assertEqual(reviewed["fatos"]["cliente"], "Montana Grill")
        self.assertEqual(reviewed["papel"], "marca")

    def test_review_search_forces_mercado_papel(self):
        with patch("aicentralv2.smart_planner.references.chat_json", return_value={
            "notas": "Categoria cresce no interior.",
            "fatos": {"verba": "R$ 80 mil"},
            "papel": "campanha",
        }):
            reviewed = review_reference("x" * 120, kind="search", label="churrasco BH")
        self.assertEqual(reviewed["papel"], "mercado")

    def test_review_search_uses_selected_scope(self):
        with patch("aicentralv2.smart_planner.references.chat_json", return_value={
            "notas": "A marca lançou uma nova campanha.",
            "fatos": {},
            "papel": "mercado",
        }):
            reviewed = review_reference("x" * 120, kind="search", label="lançamentos", scope="campanhas")
        self.assertEqual(reviewed["papel"], "campanha")

    def test_capture_url_returns_reviewed_notes_not_heading_block(self):
        with patch("aicentralv2.smart_planner.references.scrape_url", return_value="x" * 200), patch(
            "aicentralv2.smart_planner.references.review_reference",
            return_value={"notas": "A marca vende cortes premium.", "fatos": {}, "papel": "marca"},
        ):
            captured = capture_url("https://marca.com")
        self.assertEqual(captured["notas"], "A marca vende cortes premium.")
        self.assertNotIn("## Referência", captured["bloco"])
        self.assertEqual(captured["kind"], "url")

    def test_search_scrapes_top_pages_not_only_snippets(self):
        hits = [
            {"title": "Portal", "snippet": "trecho curto", "url": "https://portal.com/materia"},
            {"title": "Outro", "snippet": "outro", "url": "https://outro.com"},
        ]
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "fc-test"}, clear=False), patch(
            "aicentralv2.smart_planner.references._firecrawl_search",
            return_value=hits,
        ), patch(
            "aicentralv2.smart_planner.references.scrape_url",
            return_value="Matéria longa sobre o mercado de churrasco em Minas.",
        ), patch(
            "aicentralv2.smart_planner.references.review_reference",
            return_value={"notas": "Mercado mineiro de churrasco segue aquecido.", "fatos": {}, "papel": "mercado"},
        ):
            captured = capture_search("churrasco minas")
        self.assertEqual(captured["papel"], "mercado")
        self.assertIn("aquecido", captured["notas"])

    def test_search_scope_guides_query_and_reference_role(self):
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "fc-test"}, clear=False), patch(
            "aicentralv2.smart_planner.references._firecrawl_search",
            return_value=[{"title": "Case", "snippet": "Campanha recente", "url": ""}],
        ) as search, patch(
            "aicentralv2.smart_planner.references.review_reference",
            return_value={"notas": "Campanha recente da marca.", "fatos": {}, "papel": "campanha"},
        ):
            captured = capture_search("ações recentes", "Marca XPTO", "campanhas")
        self.assertEqual(captured["scope"], "campanhas")
        self.assertEqual(captured["source_mode"], "web")
        self.assertEqual(captured["papel"], "campanha")
        self.assertIn("campanhas recentes", search.call_args.args[0])
        self.assertIn("Marca XPTO", search.call_args.args[0])

    def test_search_scope_falls_back_without_breaking_old_clients(self):
        with patch(
            "aicentralv2.smart_planner.references.search_web",
            return_value="Conteúdo público suficiente sobre a categoria e seu comportamento.",
        ), patch(
            "aicentralv2.smart_planner.references.review_reference",
            return_value={"notas": "Resumo público.", "fatos": {}, "papel": "mercado"},
        ):
            captured = capture_search("categoria regional", scope="desconhecido")
        self.assertEqual(captured["scope"], "briefing")
        self.assertEqual(captured["source_mode"], "web")

    def test_search_origin_survives_reference_normalization(self):
        normalized = normalize_reference({
            "kind": "search",
            "label": "mercado regional",
            "notas": "Mercado em expansão.",
            "scope": "mercado",
            "source_mode": "web",
        })
        self.assertEqual(normalized["scope"], "mercado")
        self.assertEqual(normalized["source_mode"], "web")

    def test_capture_file_and_image_go_through_review(self):
        with patch(
            "aicentralv2.smart_planner.references.extract_pdf",
            return_value="Documento com verba de 40 mil no trimestre e restrição de marca.",
        ), patch(
            "aicentralv2.smart_planner.references.review_reference",
            return_value={"notas": "Verba de 40 mil no trimestre.", "fatos": {"verba": "R$ 40 mil"}, "papel": "campanha"},
        ):
            pdf = capture_file("/tmp/brief.pdf", "brief.pdf")
        self.assertEqual(pdf["kind"], "file")
        self.assertEqual(pdf["papel"], "campanha")
        self.assertIn("40 mil", pdf["notas"])

        with patch(
            "aicentralv2.smart_planner.references._read_image",
            return_value="Cartaz com a frase Aproveite o combo da casa.",
        ), patch(
            "aicentralv2.smart_planner.references.review_reference",
            return_value={"notas": "Cartaz promove o combo da casa.", "fatos": {}, "papel": "visual"},
        ):
            image = capture_file("/tmp/cartaz.png", "cartaz.png")
        self.assertEqual(image["kind"], "image")
        self.assertEqual(image["papel"], "visual")
        self.assertIn("combo da casa", image["notas"])

    def test_compose_material_keeps_user_briefing_first(self):
        material = compose_material(
            "Cliente quer vender no interior.",
            [{"kind": "url", "label": "marca.com", "notas": "Cortes premium e delivery.", "papel": "marca"}],
        )
        self.assertTrue(material.startswith("Briefing do usuário"))
        self.assertIn("Cliente quer vender", material)
        self.assertIn("Notas de apoio", material)
        self.assertNotIn("## Referência", material)

    def test_normalize_reference_uses_text_as_notas_fallback(self):
        item = normalize_reference({"kind": "file", "name": "brief.pdf", "text": "Verba de 50 mil no trimestre."})
        self.assertEqual(item["kind"], "file")
        self.assertIn("50 mil", item["notas"])
        self.assertEqual(item["papel"], "campanha")

    def test_apply_support_facts_fills_empty_and_search_skips_budget(self):
        campos = {"cliente": "", "verba": "", "publico": ""}
        filled = processor.apply_support_facts(campos, [
            {"kind": "url", "papel": "marca", "fatos": {"cliente": "Montana Grill", "publico": "quem janta fora"}},
            {"kind": "search", "papel": "mercado", "fatos": {"verba": "R$ 80 mil", "contexto": "Categoria em alta"}},
        ])
        self.assertEqual(filled["cliente"], "Montana Grill")
        self.assertEqual(filled["publico"], "quem janta fora")
        self.assertEqual(filled["verba"], "")
        self.assertEqual(filled["contexto"], "Categoria em alta")

    def test_apply_support_facts_does_not_override_user_fields(self):
        campos = {"cliente": "Do usuário", "publico": "Famílias"}
        filled = processor.apply_support_facts(campos, [
            {"kind": "url", "fatos": {"cliente": "Da URL", "publico": "Outro"}},
        ])
        self.assertEqual(filled["cliente"], "Do usuário")
        self.assertEqual(filled["publico"], "Famílias")

    def test_process_briefing_stores_user_text_and_fonte(self):
        stored = {"dados_detectados": {"cliente": "Seed", "agencia": "Agência"}}

        def _update(_token, payload):
            stored.update(payload)
            return stored

        def _merge(_token, payload):
            dados = stored.get("dados_detectados") or {}
            dados.update(payload)
            stored["dados_detectados"] = dados
            return stored

        with patch.object(processor, "get_by_token", return_value=stored), patch.object(
            processor, "extract_fields",
            return_value={"campos": {"cliente": "", "objetivo": "vendas"}, "analysis": {}, "score": 40},
        ), patch.object(processor, "compose_narrative", return_value="Narrativa limpa"), patch.object(
            processor, "update_session", side_effect=_update
        ), patch.object(processor, "merge_dados", side_effect=_merge), patch.object(
            processor, "bound_session", return_value=nullcontext()
        ):
            result = processor.process_briefing(
                "tok",
                "Briefing escrito pelo executivo com contexto suficiente.",
                [{
                    "kind": "url",
                    "label": "marca.com",
                    "url": "https://marca.com",
                    "notas": "Cortes premium.",
                    "fatos": {"publico": "BH"},
                    "papel": "marca",
                }],
            )

        self.assertEqual(stored["input_text_original"], "Briefing escrito pelo executivo com contexto suficiente.")
        self.assertNotIn("Home", stored["input_text_original"])
        fonte = stored["dados_detectados"]["fonte"]
        self.assertTrue(fonte["briefing"].startswith("Briefing escrito"))
        self.assertEqual(fonte["referencias"][0]["notas"], "Cortes premium.")
        self.assertIn("Cortes premium.", stored["dados_detectados"]["conteudo_capturado"])
        self.assertEqual(result["campos"]["publico"], "BH")
        self.assertTrue(result["campos"]["campanha"].startswith("Seed ·"))

    def test_source_material_prefers_fonte_over_url_dump(self):
        material = processor.source_material({
            "input_text_original": "## Referência — página: marca.com\nHome Contato Cookie",
            "briefing_compilado": "antigo",
            "dados_detectados": {
                "fonte": {
                    "briefing": "Texto do usuário com contexto suficiente para o plano.",
                    "referencias": [{"kind": "url", "label": "marca.com", "notas": "Produto premium, sem menu."}],
                }
            },
        })
        self.assertIn("Texto do usuário", material)
        self.assertNotIn("Home Contato Cookie", material)
        self.assertIn("Produto premium", material)

    def test_rewrite_from_plan_uses_fonte_not_dump(self):
        stored = {
            "input_text_original": "## Referência — página: marca.com\nHome Menu Cookie Política",
            "briefing_compilado": "antigo",
            "briefing_melhorado": "antigo",
            "dados_detectados": {
                "fonte": {
                    "briefing": "Cliente quer vender no interior com apoio da marca.",
                    "referencias": [{"kind": "url", "label": "marca.com", "notas": "Cortes premium em BH."}],
                },
                "campanha": {"objetivo": "vendas", "canais": ["g1"]},
            },
        }
        seen = {}

        def _narrative(material, campos, origem=""):
            seen["material"] = material
            return "Narrativa nova"

        with patch.object(processor, "get_by_token", return_value=stored), patch.object(
            processor, "compose_narrative", side_effect=_narrative
        ), patch.object(
            processor, "update_session", side_effect=lambda _t, payload: stored.update(payload) or stored
        ), patch.object(processor, "bound_session", return_value=nullcontext()):
            result = processor.rewrite_from_plan("tok")

        self.assertEqual(result["briefing"], "Narrativa nova")
        self.assertNotIn("Home Menu Cookie", seen["material"])
        self.assertIn("Cliente quer vender", seen["material"])

    def test_apoio_block_and_pack_include_reviewed_notes(self):
        dados = {
            "fonte": {
                "referencias": [
                    {"kind": "url", "label": "marca.com", "notas": "Cortes premium e delivery.", "papel": "marca"},
                    {"kind": "search", "label": "mercado", "notas": "Categoria cresce no interior.", "papel": "mercado"},
                ]
            }
        }
        block = apoio_block(dados)
        packed = planner._pack("Briefing compilado", {"objetivo": "vendas"}, apoio=block)
        self.assertIn("Apoio revisado", packed)
        self.assertIn("Cortes premium", packed)
        self.assertNotIn("<nav>", packed)

    def test_wizard_context_splits_original_and_support(self):
        ctx = wizard_context({
            "session_token": "tok",
            "input_text_original": "## Referência — página: marca.com\nHome",
            "briefing_melhorado": "Narrativa",
            "quality_score": 50,
            "dados_detectados": {
                "fonte": {
                    "briefing": "Texto do usuário na mesa.",
                    "referencias": [{"kind": "url", "label": "marca.com", "notas": "Produto premium."}],
                },
                "campanha": {},
            },
            "plan_content": {},
        }, "revisao")
        self.assertEqual(ctx["briefing_original"], "Texto do usuário na mesa.")
        self.assertEqual(ctx["fonte_referencias"][0]["notas"], "Produto premium.")

    def test_wizard_copy_keeps_central_briefing(self):
        html = (Path(__file__).resolve().parents[1] / "aicentralv2" / "templates" / "smart_planner" / "wizard.html").read_text()
        js = (Path(__file__).resolve().parents[1] / "aicentralv2" / "static" / "js" / "smart_planner" / "wizard.js").read_text()
        insert = js.split('sp-ref-insert")', 1)[1]
        self.assertIn("Usar como apoio", html)
        self.assertNotIn("Inserir no briefing", html)
        self.assertIn("sp-sources-open", html)
        self.assertIn('data-source-mode="url"', html)
        self.assertIn('data-source-mode="file"', html)
        self.assertIn('data-source-mode="image"', html)
        self.assertIn('data-source-mode="campaign"', html)
        self.assertIn('accept=".pdf"', html)
        self.assertNotIn('accept=".pdf,.doc', html)
        self.assertIn("Pesquisar campanhas", html)
        self.assertIn("sp-campaign-research-open", html)
        self.assertIn("sp-campaign-modal", html)
        self.assertIn("references: refs.map", js)
        self.assertIn("scope: item.scope", js)
        self.assertIn("source_mode: item.source_mode", js)
        self.assertNotIn("textarea.value", insert.split("if (cards)", 1)[0])

    def test_narrative_prompt_is_prose_and_strips_markdown(self):
        self.assertNotIn("Use títulos ##", processor.NARRATIVE_PROMPT)
        self.assertIn("não use markdown", processor.NARRATIVE_PROMPT.lower())
        self.assertIn("anunciante", processor.NARRATIVE_PROMPT.lower())
        with patch.object(processor, "chat_text", return_value="## Anunciante\n**COPASA** leva o app."):
            out = processor.compose_narrative("x" * 80, {"cliente": "COPASA"})
        self.assertNotIn("##", out)
        self.assertNotIn("**", out)
        self.assertIn("COPASA", out)

    def test_narrative_redacts_confidential_name(self):
        with patch.object(processor, "chat_text", return_value="A COPASA leva o app oficial."):
            out = processor.compose_narrative(
                "A COPASA precisa divulgar o app.",
                {"cliente": "COPASA", "anunciante_confidencial": True},
            )
        self.assertNotIn("COPASA", out)
        self.assertIn("o anunciante", out.lower())

    def test_extract_drops_advertiser_gap_when_seeded(self):
        gaps = processor._drop_advertiser_gaps(
            ["nome do anunciante", "verba", "clientes da Copasa no público"],
            {"cliente": "COPASA"},
        )
        self.assertNotIn("nome do anunciante", gaps)
        self.assertIn("verba", gaps)

    def test_start_page_asks_advertiser_and_confidential(self):
        html = (Path(__file__).resolve().parents[1] / "aicentralv2" / "templates" / "smart_planner" / "start.html").read_text()
        self.assertIn("Anunciante", html)
        self.assertIn("Nome confidencial nos documentos", html)
        self.assertNotIn("Cliente final", html)


if __name__ == "__main__":
    unittest.main()
