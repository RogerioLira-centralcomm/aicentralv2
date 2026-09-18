import unittest

from pathlib import Path

from aicentralv2.smart_planner.helpers import campaign_from_campos
from aicentralv2.smart_planner.service import wizard_context
from aicentralv2.smart_planner.mix import (
    METHODS,
    allocate,
    normalize_mix,
    normalize_pcts,
    recommend_methods,
    shares_to_money,
    spec_for_js,
)


class MixEngineTest(unittest.TestCase):
    def test_six_methods_and_two_recommendations(self):
        self.assertEqual(len(METHODS), 6)
        self.assertEqual(recommend_methods("reconhecimento"), ["funil", "presenca"])
        self.assertEqual(recommend_methods("vendas"), ["funil", "eficiencia"])
        self.assertEqual(recommend_methods("consideracao"), ["alcance", "funil"])
        self.assertEqual(recommend_methods(""), ["funil", "alcance"])

    def test_allocate_sums_100_and_follows_objective(self):
        canais = ["google_ads", "meta_ads", "netflix", "g1", "ooh"]
        brand = allocate(canais, "reconhecimento", "funil")
        sales = allocate(canais, "vendas", "funil")
        self.assertEqual(sum(item["pct"] for item in brand), 100)
        self.assertEqual(sum(item["pct"] for item in sales), 100)
        google_brand = next(item["pct"] for item in brand if item["id"] == "google_ads")
        google_sales = next(item["pct"] for item in sales if item["id"] == "google_ads")
        netflix_brand = next(item["pct"] for item in brand if item["id"] == "netflix")
        netflix_sales = next(item["pct"] for item in sales if item["id"] == "netflix")
        self.assertGreater(google_sales, google_brand)
        self.assertGreater(netflix_brand, netflix_sales)

    def test_alcance_spreads_across_groups(self):
        weights = allocate(["google_ads", "meta_ads", "netflix", "g1"], "vendas", "alcance")
        by_id = {item["id"]: item["pct"] for item in weights}
        self.assertEqual(by_id["google_ads"], by_id["meta_ads"])
        self.assertEqual(by_id["netflix"], by_id["g1"])
        self.assertEqual(by_id["google_ads"], by_id["netflix"])
        self.assertEqual(sum(by_id.values()), 100)

    def test_frequencia_concentrates_on_two_groups(self):
        weights = allocate(
            ["google_ads", "meta_ads", "netflix", "g1", "ooh", "spotify"],
            "vendas",
            "frequencia",
        )
        by_group = {}
        for item in weights:
            by_group[item["group"]] = by_group.get(item["group"], 0) + item["pct"]
        top = sorted(by_group.values(), reverse=True)
        self.assertGreaterEqual(top[0] + top[1], 70)
        self.assertEqual(sum(item["pct"] for item in weights), 100)

    def test_manual_keeps_relative_weights(self):
        weights = allocate(
            ["google_ads", "meta_ads"],
            "vendas",
            "manual",
            [{"id": "google_ads", "pct": 80}, {"id": "meta_ads", "pct": 20}],
        )
        self.assertEqual(weights[0]["pct"], 80)
        self.assertEqual(weights[1]["pct"], 20)

    def test_normalize_mix_and_money_close_the_budget(self):
        mix = normalize_mix({"method": "funil"}, ["google_ads", "meta_ads", "netflix"], "leads")
        self.assertEqual(mix["method"], "funil")
        money = shares_to_money(mix["weights"], 1000)
        self.assertEqual(sum(money.values()), 1000)
        self.assertEqual(set(money), {item["id"] for item in mix["weights"]})

    def test_normalize_pcts_largest_remainder(self):
        self.assertEqual(sum(normalize_pcts([("a", 1), ("b", 1), ("c", 1)]).values()), 100)

    def test_campaign_from_campos_keeps_mix(self):
        out = campaign_from_campos({
            "canais": ["g1"],
            "mix": {"method": "presenca", "weights": [{"id": "g1", "pct": 100}]},
        })
        self.assertEqual(out["mix"]["method"], "presenca")

    def test_spec_for_js_has_tables_and_media(self):
        spec = spec_for_js()
        self.assertIn("funil", spec["tables"])
        self.assertIn("google_ads", spec["media"])
        self.assertEqual(len(spec["methods"]), 6)

    def test_wizard_context_exposes_mix_desk(self):
        ctx = wizard_context({
            "nome_campanha": "Lançamento",
            "cliente": "Cliente",
            "objetivo": "vendas",
            "budget": "R$ 80 mil",
            "prazo": "90 dias",
            "quality_score": 72,
            "session_token": "tok-mix",
            "dados_detectados": {
                "campanha": {
                    "canais": ["google_ads", "meta_ads", "netflix"],
                    "objetivo": "vendas",
                    "praca": "nacional",
                },
                "publico": "Adultos urbanos",
                "kpis": ["CPL", "Vendas"],
            },
            "briefing_melhorado": "Campanha de vendas.",
            "plan_content": {},
        }, "revisao")
        self.assertEqual(ctx["mix_desk"]["recommended"], ["funil", "eficiencia"])
        self.assertTrue(ctx["mix_desk"]["weights"])
        self.assertIn("calendar", ctx["mix_desk"])
        self.assertIn("progress", ctx["mix_desk"])
        self.assertEqual(sum(item["pct"] for item in ctx["mix_desk"]["weights"]), 100)
        self.assertEqual(ctx["campos"]["verba"], "R$ 80 mil")
        self.assertIn("one_page", ctx["cost_options"])
        self.assertIn("completo", ctx["cost_options"])
        self.assertGreater(ctx["cost_options"]["completo"]["usd"], ctx["cost_options"]["one_page"]["usd"])
        self.assertEqual(ctx["briefing_original"], "")
        self.assertTrue(ctx["wait_steps"]["one_page"])
        self.assertGreater(len(ctx["wait_steps"]["completo"]), len(ctx["wait_steps"]["one_page"]))

    def test_review_template_has_three_columns(self):
        html = (Path(__file__).resolve().parents[1] / "aicentralv2" / "templates" / "smart_planner" / "wizard.html").read_text()
        self.assertIn('class="sp-hi-plan"', html)
        self.assertIn('class="sp-hi-budget"', html)
        self.assertIn('class="sp-hi-mix"', html)
        self.assertNotIn("sp-crumb", html)
        self.assertNotIn("sp-stepper", html)
        self.assertIn("Salvar rascunho", html)
        self.assertIn("Planejamentos", html)
        self.assertIn("_product_bar.html", html)
        self.assertIn("sp-places-desk", html)
        self.assertIn("Interativos", html)
        self.assertIn("Balanceamento de mídia", html)
        self.assertIn("Gestão de mídia", html)
        self.assertIn("Gestão de canais", html)
        self.assertIn('id="sp-media"', html)
        self.assertIn("Calendário de balanceamento", html)
        self.assertIn("Mídia progressiva", html)
        self.assertIn("Distribuir automaticamente", html)
        self.assertIn('aria-modal="true"', html)
        self.assertIn('name="objetivo_texto"', html)
        self.assertIn('<textarea id="sp-field-objetivo-texto"', html)
        self.assertIn('data-acc="essentials"', html)
        review_acc = html.split('id="sp-revisao-form"', 1)[1].split("</form>", 1)[0]
        self.assertRegex(review_acc, r'data-acc="essentials"[^>]*\sopen')
        self.assertRegex(review_acc, r'data-acc="audience"[^>]*\sopen')
        self.assertRegex(review_acc, r'data-acc="context"[^>]*\sopen')
        self.assertIn("cx-checkbox-sm", review_acc)
        self.assertIn("sp-bf is-pair", review_acc)
        self.assertIn("data-acc-meta", html)
        self.assertIn("sp-complete-checks", html)
        self.assertIn("4 campos", html)
        self.assertNotIn("Dados da campanha", html)
        review = html.split('id="sp-revisao-form"', 1)[1].split("</form>", 1)[0]
        self.assertNotIn('name="verba"', review)
        self.assertNotIn('name="praca"', review)
        self.assertIn('name="objetivo"', review)
        budget = html.split("sp-hi-budget", 1)[1].split("sp-hi-mix", 1)[0]
        self.assertIn('name="verba"', budget)
        self.assertIn('name="praca"', budget)
        self.assertIn('name="kpis"', budget)
        self.assertIn('id="sp-gen"', html)
        self.assertIn('id="sp-original"', html)
        self.assertIn("Gerar documentos", html)
        self.assertIn("<span>Anunciante</span>", html)
        self.assertIn("Nome confidencial nos documentos", html)
        self.assertIn("Narrativa corrida", html)
        self.assertIn('class="sp-wait"', html)
        self.assertIn('id="sp-wait-gen-steps"', html)
        self.assertIn("Analisando o briefing", html)
        self.assertIn("sp-wait-folio", html)
        self.assertIn("sp-wait-dismiss", html)
        css = (Path(__file__).resolve().parents[1] / "aicentralv2" / "static" / "css" / "smart_planner.css").read_text()
        self.assertIn("--wait-paper: #eef4f5", css)
        self.assertIn(".sp-wait:not([hidden])", css)
        self.assertNotIn("color-mix(in srgb, var(--wait-ink) 54%", css)
        overlay = html.split('id="sp-compile-overlay"', 1)[1].split('id="sp-wait-dismiss"', 1)[0]
        self.assertNotIn("<i>", overlay)
        self.assertNotIn("<span>Cliente</span>", html)
        self.assertIn("Refazer briefing", html)
        self.assertIn('data-gen-mode="{{ plan_mode or \'one_page\' }}"', html)
        self.assertIn("Confirmar geração", html)
        self.assertIn("_product_bar.html", html)
        guide = (Path(__file__).resolve().parents[1] / "aicentralv2" / "templates" / "smart_planner" / "_guide.html").read_text()
        self.assertIn("Como funciona", guide)
        self.assertIn("Na prática", guide)
        self.assertIn("GPT-5", guide)
        self.assertIn("Página única", guide)
        self.assertIn("Página única", guide)

    def test_persist_review_keeps_flight_and_progress(self):
        from unittest.mock import patch

        from aicentralv2.smart_planner import service

        saved = {}

        def _save(_token, campos, briefing=None):
            saved.update(campos)
            saved["briefing"] = briefing
            return {"ok": True}

        with patch.object(service, "save_campos", side_effect=_save):
            service.persist_review("tok", {
                "briefing": "Narrativa",
                "canais": ["google_ads", "netflix"],
                "mix": {
                    "method": "funil",
                    "progress": True,
                    "weights": [{"id": "google_ads", "pct": 40}, {"id": "netflix", "pct": 60}],
                },
                "verba_alocacao": {"2026-09": 20000, "2026-10": 30000},
                "campos": {
                    "objetivo": "vendas",
                    "verba": "R$ 50.000",
                    "verba_valor": 50000,
                    "verba_base": "total",
                    "periodo": "set a out 2026",
                },
            })

        self.assertTrue(saved["mix"]["progress"])
        self.assertEqual(sum(item["pct"] for item in saved["mix"]["weights"]), 100)
        self.assertEqual(saved["verba_alocacao"]["2026-09"], 20000)
        self.assertEqual(saved["verba_alocacao"]["2026-10"], 30000)

    def test_persist_review_keeps_places_off_when_channel_unchecked(self):
        from unittest.mock import patch

        from aicentralv2.smart_planner import service

        saved = {}

        def _save(_token, campos, briefing=None):
            saved.update(campos)
            return {"ok": True}

        with patch.object(service, "save_campos", side_effect=_save):
            service.persist_review("tok", {
                "canais": ["google_ads"],
                "places": [],
                "mix": {"method": "funil", "weights": [{"id": "google_ads", "pct": 100}]},
                "campos": {"objetivo": "vendas", "verba": "R$ 10.000", "periodo": "30 dias"},
            })

        self.assertNotIn("places", saved.get("canais") or [])
        self.assertEqual(saved.get("places") or [], [])

    def test_media_modal_js_reverts_and_holds_autosave(self):
        js = (
            Path(__file__).resolve().parents[1]
            / "aicentralv2"
            / "static"
            / "js"
            / "smart_planner"
            / "wizard.js"
        ).read_text()
        self.assertIn("restoreMediaSnapshot", js)
        self.assertIn("sp-media-will-open", js)
        self.assertIn("if (!manual && mediaOpen()) return;", js)
        self.assertIn('if (channel && !channel.checked) return [];', js)
        self.assertIn("/canais|canal/", js)

    def test_normalize_mix_closes_dirty_percentages(self):
        mix = normalize_mix(
            {"method": "manual", "locked": True, "weights": [
                {"id": "google_ads", "pct": 10},
                {"id": "netflix", "pct": 10},
            ]},
            ["google_ads", "netflix"],
            "vendas",
        )
        self.assertEqual(sum(item["pct"] for item in mix["weights"]), 100)

    def test_rewrite_from_plan_keeps_original(self):
        from contextlib import nullcontext
        from unittest.mock import patch

        from aicentralv2.smart_planner import processor

        stored = {
            "input_text_original": "Texto original longo o suficiente para reescrever o briefing do cliente com contexto.",
            "briefing_compilado": "antigo",
            "briefing_melhorado": "antigo",
            "dados_detectados": {"campanha": {"objetivo": "vendas", "canais": ["g1"]}},
        }

        def _update(_token, payload):
            stored.update(payload)
            return stored

        with patch.object(processor, "get_by_token", return_value=stored), patch.object(
            processor, "compose_narrative", return_value="Narrativa nova"
        ), patch.object(processor, "update_session", side_effect=_update), patch.object(
            processor, "bound_session", return_value=nullcontext()
        ):
            result = processor.rewrite_from_plan("tok")

        self.assertEqual(result["briefing"], "Narrativa nova")
        self.assertIn("Texto original", stored["input_text_original"])
        self.assertEqual(stored["briefing_melhorado"], "Narrativa nova")


if __name__ == "__main__":
    unittest.main()
