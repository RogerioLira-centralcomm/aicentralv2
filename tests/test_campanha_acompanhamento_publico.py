"""Testes do payload da página pública de acompanhamento da campanha."""

import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from aicentralv2.campanha_acompanhamento_publico import (
    contexto_pagina,
    montar_payload_acompanhamento_campanha,
    montar_payload_acompanhamento_pi,
    normalizar_url_embed_looker_studio,
    anexar_series_entrega,
    grafico_ritmo,
    normalizar_url_visualizacao_looker_studio,
    resolver_dashboard_publico,
    token_amigavel,
)


class FakeOperacaoService:
    def estado_campanha(self, id_pi, id_campanha):
        hoje = date.today()
        return {
            "pi": {
                "id_pi": id_pi,
                "codigo_pi_cc": "PI036826",
                "cliente_nome": "Cliente Teste",
                "id_resp_comercial": 99,
                "responsavel_comercial_nome": "Ana Comercial",
                "periodo_inicio": hoje - timedelta(days=5),
                "periodo_fim": hoje + timedelta(days=10),
                "googled_pi_princ": "https://drive.example/pi",
                "cotacao_id": None,
            },
            "campanha": {
                "id_campanha": id_campanha,
                "nome_campanha": "Display Principal",
                "link_dash": "https://lookerstudio.google.com/reporting/x/page/y",
                "periodo_inicio": hoje - timedelta(days=5),
                "periodo_fim": hoje + timedelta(days=10),
                "objetivo_nome": "Alcance",
                "obj_contratados": "1000000",
                "plataforma_nome": "Google Ads",
                "updated_at": hoje,
            },
            "campanhas_relacionadas": [
                {
                    "id_campanha": id_campanha,
                    "nome": "Display Principal",
                    "plataforma": "Google Ads",
                    "atual": True,
                }
            ],
            "destinatarios": [
                {
                    "nome_completo": "Contato Cliente",
                    "email": "cliente@example.com",
                    "papel": "cliente_final",
                }
            ],
            "timeline": [
                {"etapa": "dados_validados", "concluida": True, "concluida_em": hoje - timedelta(days=4)},
                {"etapa": "campanha_iniciada", "concluida": True, "concluida_em": hoje - timedelta(days=1)},
            ],
            "resumo": {"ultima_atualizacao": hoje},
        }


CAMPANHAS_PI = [
    {
        "id_campanha": 30,
        "nome_campanha": "Display Principal",
        "plataforma_nome": "Google Ads",
        "objetivo_nome": "Alcance",
        "status_nome": "Em andamento",
        "obj_contratados": "1.000.000",
        "totalizador_atingido": "250.000",
        "totalizador_gasto": "98.765,43",
        "valor_plataforma": "77.711,00",
        "custo_midia_orcado": "66.622,00",
        "periodo_inicio": date.today() - timedelta(days=5),
        "periodo_fim": date.today() + timedelta(days=10),
        "link_dash": "https://datastudio.google.com/u/0/reporting/abc/page/VgD",
        "link_dash_incorporar": True,
    },
    {
        "id_campanha": 31,
        "nome_campanha": "Vídeo",
        "plataforma_nome": "YouTube",
        "obj_contratados": "",
        "totalizador_atingido": None,
        "link_dash": "",
    },
]


class CampanhaAcompanhamentoPublicoTest(unittest.TestCase):
    def test_normalizar_url_looker_com_conta_google(self):
        url = "https://datastudio.google.com/u/0/reporting/c5a3/page/VgD"
        self.assertEqual(
            normalizar_url_embed_looker_studio(url),
            "https://datastudio.google.com/embed/reporting/c5a3/page/VgD",
        )
        self.assertEqual(
            normalizar_url_visualizacao_looker_studio(url),
            "https://datastudio.google.com/reporting/c5a3/page/VgD",
        )
        self.assertEqual(
            normalizar_url_embed_looker_studio("https://lookerstudio.google.com/u/2/embed/reporting/x/page/y"),
            "https://lookerstudio.google.com/embed/reporting/x/page/y",
        )

    def test_token_amigavel(self):
        token = token_amigavel("Animale", "Black Friday · Fim de Ano")
        self.assertRegex(token, r"^animale-black-friday-fim-de-ano-[a-z2-9]{6}$")
        self.assertLessEqual(len(token), 64)
        self.assertRegex(token_amigavel("", ""), r"^campanha-[a-z2-9]{6}$")


    def test_normalizar_url_looker_view_para_embed(self):
        view = (
            "https://lookerstudio.google.com/reporting/abc123/page/def456"
        )
        self.assertEqual(
            normalizar_url_embed_looker_studio(view),
            "https://lookerstudio.google.com/embed/reporting/abc123/page/def456",
        )

    def test_normalizar_url_looker_ja_embed(self):
        embed = "https://lookerstudio.google.com/embed/reporting/x/page/y"
        self.assertEqual(normalizar_url_embed_looker_studio(embed), embed)

    def test_resolver_dashboard_pi_e_override(self):
        pi_url = "https://lookerstudio.google.com/reporting/pi/page/1"
        camp_url = "https://lookerstudio.google.com/reporting/camp/page/2"
        pi = {"link_dash": pi_url, "link_dash_incorporar": True, "titulo_pi": "Projeto A"}
        d = resolver_dashboard_publico(pi, None)
        self.assertEqual(d["escopo"], "pi")
        self.assertIn("/embed/reporting/pi/", d["dash_embed"])

        sel_mesmo = {
            "nome": "Display",
            "dash_abrir": normalizar_url_visualizacao_looker_studio(pi_url),
            "dash_embed": d["dash_embed"],
        }
        self.assertEqual(resolver_dashboard_publico(pi, sel_mesmo)["escopo"], "pi")

        sel_outro = {
            "nome": "Vídeo",
            "dash_abrir": normalizar_url_visualizacao_looker_studio(camp_url),
            "dash_embed": normalizar_url_embed_looker_studio(camp_url),
        }
        over = resolver_dashboard_publico(pi, sel_outro)
        self.assertEqual(over["escopo"], "campanha")
        self.assertEqual(over["nome"], "Vídeo")

    @patch("aicentralv2.db.obter_cadu_pi_por_id")
    @patch("aicentralv2.db.obter_campanha_pi_por_id")
    @patch("aicentralv2.db.obter_contato_por_id")
    def test_montar_payload_estrutura_template(self, contato_mock, campanha_mock, pi_db_mock):
        pi_db_mock.return_value = {}
        campanha_mock.return_value = {
            "id_campanha": 30,
            "id_pi": 10,
            "nome_campanha": "Display Principal",
        }
        contato_mock.return_value = {
            "nome_completo": "Ana Comercial",
            "email": "ana@centralcomm.media",
            "telefone": "(11) 98888-7777",
        }

        payload = montar_payload_acompanhamento_campanha(
            30,
            service=FakeOperacaoService(),
            linhas_campanhas=CAMPANHAS_PI,
        )

        self.assertFalse(payload["demo"])
        self.assertEqual(payload["campanha"], "Display Principal")
        self.assertEqual(payload["pi"], "PI036826")
        self.assertIn("marcos", payload)
        self.assertEqual(len(payload["marcos"]), 8)
        self.assertIn("modulos", payload)
        self.assertEqual(
            payload["modulos"]["dashboard"]["url_embed"],
            "https://lookerstudio.google.com/embed/reporting/x/page/y",
        )
        pi_marco = next(m for m in payload["marcos"] if m["id"] == "pi")
        self.assertTrue(pi_marco["realizado"])
        self.assertEqual(payload["modulos"]["contatos"]["cliente"][0]["email"], "cliente@example.com")

        # Resultados: meta, atingido e %, sem nenhum valor de custo.
        res = payload["resultados"]
        self.assertEqual([r["id"] for r in res], [30, 31])
        principal = res[0]
        self.assertTrue(principal["atual"])
        self.assertEqual(principal["meta_label"], "1.000.000")
        self.assertEqual(principal["pct"], 25)
        self.assertEqual(
            principal["dash_embed"],
            "https://datastudio.google.com/embed/reporting/abc/page/VgD",
        )
        self.assertIsNone(res[1]["pct"])
        texto = repr(res)
        for proibido in ("98.765", "77.711", "66.622", "gasto", "custo", "valor"):
            self.assertNotIn(proibido, texto)

        # Executivo interno com WhatsApp a partir do telefone do contato.
        self.assertEqual(payload["executivo"]["nome"], "Ana Comercial")
        self.assertEqual(payload["executivo"]["whatsapp"], "https://wa.me/5511988887777")

        ctx = contexto_pagina(payload)
        self.assertEqual([p["id"] for p in ctx["paginas"]], ["geral", "relatorios", "documentos"])
        self.assertTrue(all(p["ok"] for p in ctx["paginas"]))
        self.assertEqual(ctx["atual"]["id"], "materiais")
        self.assertEqual(ctx["atual"]["curto"], "Materiais")
        # Sem ?c= num PI de 2 campanhas: escopo "todas", média só das que têm meta.
        self.assertIsNone(ctx["sel"])
        self.assertEqual(ctx["metricas"]["pct"], 25)
        self.assertEqual(ctx["metricas"]["n_com_meta"], 1)
        # Com ?c=30: métricas da campanha e gráfico de ritmo.
        ctx30 = contexto_pagina(payload, campanha_id=30)
        self.assertEqual(ctx30["sel"]["id"], 30)
        self.assertEqual(ctx30["metricas"]["desvio"], 25 - ctx30["metricas"]["tempo_pct"])
        self.assertIsNotNone(ctx30["grafico"])

    def test_grafico_ritmo_e_series(self):
        r = {
            "id": 30,
            "periodo": {"inicio": "2026-11-01", "fim": "2026-11-30"},
            "meta": 1000.0,
            "atingido": 400.0,
        }
        payload = {"resultados": [r]}
        anexar_series_entrega(payload, [
            {"id_campanha": 30, "data_evento": date(2026, 11, 10), "atingido": "200"},
            {"id_campanha": 99, "data_evento": date(2026, 11, 10), "atingido": "5"},
        ])
        self.assertEqual(r["serie"], [("2026-11-10", 200.0)])
        g = grafico_ritmo(r, hoje=date(2026, 11, 16))
        # 3 pontos: início (0), diário de 10/11 e o total de hoje.
        self.assertEqual(g["real"].count("L"), 2)
        self.assertEqual(g["esperado"]["valor"], "517")  # 1000 * 15/29 dias
        self.assertEqual([t["rotulo"] for t in g["eixo_x"]], ["01/11", "15/11", "30/11"])
        self.assertIsNone(grafico_ritmo(dict(r, meta=None)))
        antes = grafico_ritmo(r, hoje=date(2026, 10, 1))
        self.assertEqual(antes["esperado"]["valor"], "0")

    @patch("aicentralv2.db.obter_cadu_pi_por_id")
    @patch("aicentralv2.db.obter_campanha_pi_por_id")
    @patch("aicentralv2.db.obter_contato_por_id")
    def test_payload_pi_dashboard_no_modulo(self, contato_mock, campanha_mock, pi_db_mock):
        pi_url = "https://lookerstudio.google.com/reporting/pi-agg/page/z"
        pi_db_mock.return_value = {
            "link_dash": pi_url,
            "link_dash_incorporar": True,
            "titulo_pi": "Black Friday",
            "codigo_pi_cc": "PI036826",
        }
        campanha_mock.return_value = {"id_campanha": 30, "id_pi": 10, "nome_campanha": "Display Principal"}
        contato_mock.return_value = {}
        payload = montar_payload_acompanhamento_pi(
            10, service=FakeOperacaoService(), linhas_campanhas=CAMPANHAS_PI, diarios=[]
        )
        embed = payload["modulos"]["dashboard"]["url_embed"]
        self.assertIn("/embed/reporting/pi-agg/", embed)
        ctx = contexto_pagina(payload)
        self.assertEqual(ctx["dash"]["escopo"], "pi")

    @patch("aicentralv2.db.obter_cadu_pi_por_id")
    @patch("aicentralv2.db.obter_campanha_pi_por_id")
    @patch("aicentralv2.db.obter_contato_por_id")
    def test_payload_do_pi_agrupa_campanhas(self, contato_mock, campanha_mock, pi_db_mock):
        pi_db_mock.return_value = {}
        campanha_mock.side_effect = lambda i: {"id_campanha": i, "id_pi": 10, "nome_campanha": "X"}
        contato_mock.return_value = {}
        linhas = [dict(CAMPANHAS_PI[1], periodo_inicio=date(2026, 12, 1), periodo_fim=date(2027, 1, 20)),
                  dict(CAMPANHAS_PI[0], periodo_inicio=date(2026, 11, 1), periodo_fim=date(2026, 12, 31))]
        payload = montar_payload_acompanhamento_pi(
            10, service=FakeOperacaoService(), linhas_campanhas=linhas, diarios=[]
        )
        self.assertTrue(payload["grupo"])
        self.assertEqual(payload["id_pi"], 10)
        # Título e período passam a ser do grupo (PI), não da 1ª campanha.
        self.assertEqual(payload["campanha"], "PI036826")
        self.assertEqual(payload["periodo"], {"inicio": "2026-11-01", "fim": "2027-01-20"})
        self.assertEqual([r["id"] for r in payload["resultados"]], [30, 31])
        self.assertFalse(any(r["atual"] for r in payload["resultados"]))
        dash = next(m for m in payload["marcos"] if m["id"] == "dashboard")
        self.assertTrue(dash["realizado"])

    @patch("aicentralv2.db.obter_cadu_pi_por_id")
    @patch("aicentralv2.db.obter_campanha_pi_por_id")
    @patch("aicentralv2.db.obter_contato_por_id")
    def test_payload_do_pi_com_uma_campanha_mantem_nome(self, contato_mock, campanha_mock, pi_db_mock):
        pi_db_mock.return_value = {}
        campanha_mock.return_value = {"id_campanha": 30, "id_pi": 10, "nome_campanha": "Display Principal"}
        contato_mock.return_value = {}
        payload = montar_payload_acompanhamento_pi(
            10, service=FakeOperacaoService(), linhas_campanhas=[CAMPANHAS_PI[0]], diarios=[]
        )
        self.assertFalse(payload["grupo"])
        self.assertEqual(payload["campanha"], "Display Principal")
        self.assertTrue(payload["resultados"][0]["atual"])

    def test_payload_do_pi_sem_campanhas(self):
        with self.assertRaises(LookupError):
            montar_payload_acompanhamento_pi(10, linhas_campanhas=[])


if __name__ == "__main__":
    unittest.main()
