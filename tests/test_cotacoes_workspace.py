"""Testes do workspace comercial e de suas pendências derivadas."""

import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from aicentralv2 import cotacoes_routes


def cotacao_completa(status="Rascunho"):
    return {
        "id": 191,
        "client_id": 10,
        "responsavel_comercial": 20,
        "nome_campanha": "Campanha de teste",
        "objetivo_campanha": "Conversão",
        "periodo_inicio": "2026-09-01",
        "periodo_fim": "2026-09-30",
        "budget_estimado": 42000,
        "status": status,
        "link_publico_token": "token",
        "link_publico_ativo": True,
        "proposta_enviada_em": (
            "2026-09-08 10:00:00" if status != "Rascunho" else None
        ),
    }


def linha_completa():
    return {
        "id": 1,
        "plataforma": "Programática",
        "segmentacao": "Público de interesse",
        "objetivo_kpi": "CPM",
        "data_inicio": "2026-09-01",
        "data_fim": "2026-09-30",
        "investimento_bruto": 42000,
        "investimento_liquido": 33600,
    }


def anexo_pdf():
    return {
        "id": 1,
        "descricao": cotacoes_routes.DESCRICAO_ANEXO_PROPOSTA_PDF,
    }


class EstadoComercialCotacaoTest(unittest.TestCase):
    def test_estado_completo_nao_exige_audiencia_opcional(self):
        estado = cotacoes_routes.montar_estado_comercial_cotacao(
            cotacao_completa(status="Aprovada"),
            linhas=[linha_completa()],
            audiencias=[],
            anexos=[anexo_pdf()],
        )

        audiencia = next(item for item in estado["checklist"] if item["codigo"] == "audiencias")
        self.assertTrue(audiencia["opcional"])
        self.assertEqual(estado["progresso"]["concluidos"], estado["progresso"]["total"])
        self.assertIsNone(estado["proxima_pendencia"])

    def test_primeira_pendencia_aponta_para_dados(self):
        cotacao = cotacao_completa()
        cotacao["responsavel_comercial"] = None
        estado = cotacoes_routes.montar_estado_comercial_cotacao(cotacao)

        self.assertEqual(estado["proxima_pendencia"]["codigo"], "dados")
        self.assertIn("executivo responsável", estado["proxima_pendencia"]["evidencia"])
        self.assertLess(estado["progresso"]["percentual"], 100)

    def test_cotacao_enviada_recomenda_registrar_decisao(self):
        estado = cotacoes_routes.montar_estado_comercial_cotacao(
            cotacao_completa(status="Enviada"),
            linhas=[linha_completa()],
            anexos=[anexo_pdf()],
        )

        self.assertEqual(estado["proxima_pendencia"]["codigo"], "decisao")
        self.assertIn("aprovação ou rejeição", estado["proxima_pendencia"]["evidencia"])

    def test_cotacao_aprovada_nao_recomenda_nova_pendencia(self):
        cotacao = cotacao_completa(status="Aprovada")
        cotacao["link_publico_ativo"] = False
        estado = cotacoes_routes.montar_estado_comercial_cotacao(cotacao)

        self.assertIsNone(estado["proxima_pendencia"])
        self.assertIn("aprovada", estado["recomendacao"].lower())


class WorkspaceComercialRouteTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY="test")
        self.app.register_blueprint(cotacoes_routes.bp)
        self.client = self.app.test_client()

    @patch.object(cotacoes_routes, "_serializar", side_effect=lambda value: value)
    @patch.object(cotacoes_routes.db, "obter_anexos_cotacao", return_value=[anexo_pdf()])
    @patch.object(cotacoes_routes.db, "obter_audiencias_cotacao", return_value=[])
    @patch.object(cotacoes_routes.db, "obter_linhas_cotacao", return_value=[linha_completa()])
    @patch.object(cotacoes_routes.db, "obter_cotacao_por_id", return_value=cotacao_completa())
    def test_endpoint_retorna_contrato_da_sidebar(self, *_mocks):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 99

        response = self.client.get("/api/cotacoes/191/workspace-comercial")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(
            set(payload["data"]),
            {"status", "recomendacao", "proxima_pendencia", "checklist", "progresso"},
        )

    def test_template_preserva_secoes_e_adota_shell_erp(self):
        template = (
            Path(__file__).parents[1]
            / "aicentralv2"
            / "templates"
            / "cadu_cotacoes_detalhes.html"
        ).read_text()

        self.assertIn("{% extends 'base_erp.html' %}", template)
        self.assertIn("cotacoes/_sidebar_comercial.html", template)
        self.assertIn('data-section="itens"', template)
        self.assertIn('data-section="audiencias"', template)
        self.assertIn('data-section="historico"', template)
        self.assertIn('data-section="anexos"', template)
        self.assertIn("cot-op-table-wrap", template)

    def test_resumo_prioriza_itens_antes_de_conteudo_secundario(self):
        template = (
            Path(__file__).parents[1]
            / "aicentralv2"
            / "templates"
            / "cadu_cotacoes_detalhes.html"
        ).read_text()

        self.assertIn("cot-op-primary-section", template)
        self.assertIn("A proposta ainda não tem itens", template)
        self.assertIn("Adicionar primeiro item", template)
        self.assertIn("rf_total_itens_liquido", template)
        css = (
            Path(__file__).parents[1]
            / "aicentralv2"
            / "static"
            / "css"
            / "cotacao_detalhes.css"
        ).read_text()
        self.assertLess(
            css.index('[data-section="itens"] { order: 1; }'),
            css.index('[data-section="parametros_proposta"] { order: 4; }'),
        )

    def test_informacoes_secundarias_usam_disclosure_semantico(self):
        template = (
            Path(__file__).parents[1]
            / "aicentralv2"
            / "templates"
            / "cadu_cotacoes_detalhes.html"
        ).read_text()

        self.assertIn(
            '<details data-section="resumo_comercial" class="cot-op-disclosure">',
            template,
        )
        self.assertIn(
            '<details data-section="parametros_proposta"',
            template,
        )
        self.assertIn("Premissas, observações e conteúdo do PDF", template)

    def test_abas_sao_controladas_pelo_javascript_vanilla(self):
        root = Path(__file__).parents[1] / "aicentralv2"
        template = (root / "templates" / "cadu_cotacoes_detalhes.html").read_text()
        javascript = (root / "static" / "js" / "cotacao_detalhes.js").read_text()

        self.assertNotIn("var mapa = {", template)
        self.assertIn("var tabSections =", javascript)
        self.assertIn("window.mostrarTabCotacao = showQuoteTab", javascript)
        self.assertIn("section.hidden =", javascript)
        self.assertNotIn("sessionStorage", javascript)
        self.assertIn('role="tablist"', template)
        self.assertIn("ArrowRight", javascript)
        self.assertIn("button.tabIndex = active ? 0 : -1", javascript)

    def test_header_e_resumo_usam_shell_operacional_vanilla(self):
        root = Path(__file__).parents[1] / "aicentralv2"
        template = (root / "templates" / "cadu_cotacoes_detalhes.html").read_text()
        css = (root / "static" / "css" / "cotacao_detalhes.css").read_text()

        self.assertIn('class="cot-op-header"', template)
        self.assertIn('class="cot-op-summary-rail"', template)
        metric_count = template.count('<div class="cot-op-metric">')
        metric_count += template.count('<div class="cot-op-metric cot-op-metric--money">')
        self.assertEqual(metric_count, 6)
        self.assertIn('data-cot-header-action="pdf"', template)
        self.assertIn('class="cot-op-actions-menu"', template)
        header = template[template.index('<header class="cot-op-header">'):template.index("</header>")]
        self.assertNotIn("onclick=", header)
        self.assertNotIn("onchange=", header)
        self.assertIn(".cot-op-summary-rail", css)
        self.assertIn("grid-template-columns: 0.8fr 1.2fr", css)

    def test_secoes_secundarias_removem_handlers_inline_ativos(self):
        root = Path(__file__).parents[1] / "aicentralv2"
        template = (root / "templates" / "cadu_cotacoes_detalhes.html").read_text()
        javascript = (root / "static" / "js" / "cotacao_detalhes.js").read_text()

        self.assertIn("data-open-audience", template)
        self.assertIn("data-open-attachment", template)
        self.assertIn("data-attachment-dropzone", template)
        self.assertNotIn("toggleAudienciasCollapse", template)
        self.assertNotIn("trocarAbaCotacao", template)
        self.assertNotIn("handleDragOver", template)
        self.assertIn("function initSupplementalInteractions()", javascript)

    def test_sidebar_evitaria_cartoes_aninhados(self):
        root = Path(__file__).parents[1] / "aicentralv2"
        sidebar = (root / "templates" / "cotacoes" / "_sidebar_comercial.html").read_text()
        css = (root / "static" / "css" / "cotacao_detalhes.css").read_text()

        self.assertIn("Revise o que falta sem sair da montagem.", sidebar)
        self.assertIn(".cot-op-panel,\n.cot-op-next", css)
        self.assertIn("border: 0;", css)

    def test_tabela_de_midia_prioriza_compra_e_valores(self):
        root = Path(__file__).parents[1] / "aicentralv2"
        template = (root / "templates" / "cadu_cotacoes_detalhes.html").read_text()

        self.assertIn('class="cot-media-table"', template)
        self.assertIn("Mídia e segmentação", template)
        self.assertIn("KPI e período", template)
        self.assertIn("data-open-media-item", template)
        self.assertIn("data-line-id=", template)
        css = (root / "static" / "css" / "cotacao_detalhes.css").read_text()
        self.assertIn("cotacao_detalhes.css') }}?v=6", template)
        self.assertIn("@media (max-width: 900px)", css)
        self.assertIn("tr[data-media-row]", css)
        self.assertIn('content: "Praça"', css)
        self.assertIn('[data-cot-header-action="pdf"]', css)
        self.assertNotIn(
            'data-investimento-liquido="{{ linha.investimento_liquido or 0 }}" onclick="visualizarOuEditarLinha',
            template,
        )

    def test_modais_de_item_compartilham_sistema_semantico(self):
        root = Path(__file__).parents[1] / "aicentralv2"
        template = (root / "templates" / "cadu_cotacoes_detalhes.html").read_text()

        self.assertIn('data-media-item-dialog="create"', template)
        self.assertIn('data-media-item-dialog="edit"', template)
        self.assertEqual(template.count("cot-media-dialog__header"), 2)
        self.assertEqual(template.count("cot-media-dialog__footer"), 3)
        self.assertIn('id="form_nova_linha"', template)
        self.assertIn('id="form_editar_linha"', template)
        self.assertIn('id="btn_salvar_linha"', template)
        self.assertIn('id="edit_btn_salvar_linha"', template)
        self.assertIn('id="modal_confirmar_exclusao_linha"', template)

    def test_controlador_vanilla_assume_acoes_principais_dos_itens(self):
        root = Path(__file__).parents[1] / "aicentralv2"
        template = (root / "templates" / "cadu_cotacoes_detalhes.html").read_text()
        javascript = (root / "static" / "js" / "cotacao_detalhes.js").read_text()

        self.assertIn("function initMediaItems()", javascript)
        self.assertIn("window.CotacaoMediaUI", javascript)
        self.assertIn("confirmDeleteMediaItem", javascript)
        self.assertIn("[data-save-media-item]", javascript)
        self.assertNotIn('onclick="salvarNovaLinha()"', template)
        self.assertNotIn('onclick="salvarEdicaoLinha()"', template)
        delete_start = template.index("function excluirLinhaDoModal()")
        delete_end = template.index("async function confirmarRemoverLinha", delete_start)
        self.assertNotIn("confirm(", template[delete_start:delete_end])


if __name__ == "__main__":
    unittest.main()
