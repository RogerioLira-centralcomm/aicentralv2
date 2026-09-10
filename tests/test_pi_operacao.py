"""Testes sem PostgreSQL da API e das regras da Operação do PI."""

import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from flask import Flask

from aicentralv2.pi_operacao_routes import bp
from aicentralv2.pi_operacao_repository import (
    PiOperacaoRepository,
    PropriedadeInvalidaError,
)
from aicentralv2.pi_operacao_service import PiOperacaoService


class FakeRepository:
    def __init__(self, substatus=2):
        self.pi = {
            "id_pi": 10,
            "id_cliente": 20,
            "id_agencia": None,
            "id_parceiro": 21,
            "parceiro_nome": "Parceiro Regional Teste",
            "id_resp_comercial": 99,
            "id_pi_tipo": 1,
            "vr_bruto_pi": "R$ 1.000,00",
            "id_sub_status_pi": substatus,
            "periodo_inicio": date.today() - timedelta(days=5),
            "periodo_fim": date.today() + timedelta(days=5),
            "sub_status_descricao": "Em configuração",
        }
        self.campanhas = [
            {
                "id_campanha": 30,
                "id_pi": 10,
                "nome_campanha": "Display",
                "id_plataforma": 1,
                "id_objetivos_campanha": 1,
                "id_responsavel_operacao": 99,
                "periodo_inicio": date.today() - timedelta(days=5),
                "periodo_fim": date.today() + timedelta(days=5),
                "obj_contratados": "1000",
                "totalizador_atingido": "600",
                "totalizador_gasto": "R$ 100,00",
                "status_descricao": "Ativa",
            }
        ]
        self.checklist = []
        self.destinatarios = [
            {
                "id_contato_cliente": 40,
                "nome_completo": "Cliente Teste",
                "email": "cliente@example.com",
                "papel": "cliente_final",
                "padrao": True,
            }
        ]
        self.emails = []
        self.etapas = {}
        self.interacoes = []
        self.sync_calls = []
        self.logs = []

    def obter_pi(self, id_pi):
        return dict(self.pi)

    def listar_campanhas(self, id_pi):
        return [dict(item) for item in self.campanhas]

    def obter_campanha(self, id_campanha):
        for item in self.campanhas:
            if int(item["id_campanha"]) == int(id_campanha):
                return dict(item)
        raise LookupError("Campanha não encontrada.")

    def listar_checklist(self, id_pi):
        return [dict(item) for item in self.checklist]

    def validar_campanhas(self, id_pi, ids_campanha):
        existentes = {item["id_campanha"] for item in self.campanhas}
        ids = sorted({int(item) for item in ids_campanha})
        if not set(ids).issubset(existentes):
            raise PropriedadeInvalidaError("Campanha não pertence ao PI.")
        return ids

    def gerar_checklist(self, id_pi, itens, autor_id):
        existentes = {
            (item.get("id_campanha"), item.get("codigo"))
            for item in self.checklist
        }
        for item in itens:
            chave = (item.get("id_campanha"), item.get("codigo"))
            if chave in existentes:
                continue
            self.checklist.append(
                {
                    **item,
                    "id": len(self.checklist) + 1,
                    "concluido": False,
                    "evidencia": None,
                    "obrigatorio": True,
                }
            )
            existentes.add(chave)
        return self.listar_checklist(id_pi)

    def concluir_itens_automaticos(self, id_pi, conclusoes):
        por_chave = {
            (item["codigo"], item.get("id_campanha")): item
            for item in conclusoes
        }
        for item in self.checklist:
            evidencia = por_chave.get(
                (item.get("codigo"), item.get("id_campanha"))
            )
            if evidencia and item.get("modo_conclusao") == "automatico":
                item["concluido"] = True
                item["evidencia"] = evidencia["evidencia"]
        return self.listar_checklist(id_pi)

    def atualizar_item_checklist(self, id_pi, item_id, concluido, autor_id):
        for item in self.checklist:
            if item["id"] != item_id:
                continue
            if item.get("modo_conclusao") != "manual":
                raise PropriedadeInvalidaError("Somente itens manuais.")
            item["concluido"] = concluido
            return dict(item)
        raise LookupError("Item não encontrado.")

    def listar_destinatarios(self, id_pi):
        return [dict(item) for item in self.destinatarios]

    def listar_destinatarios_sugeridos(self, id_pi):
        return []

    def listar_contatos_disponiveis(self, id_pi):
        return []

    def listar_emails(self, id_pi, limite=50):
        return [dict(item) for item in self.emails]

    def listar_etapas(self, id_pi):
        return dict(self.etapas)

    def listar_interacoes(self, id_pi):
        return list(self.interacoes)

    def obter_ultima_atualizacao(self, id_pi):
        return None

    def sincronizar_etapas(self, id_pi, etapas, autor_id):
        self.sync_calls.append((id_pi, tuple(etapas), autor_id))
        return {}

    def criar_interacao(self, id_pi, tipo, descricao, autor_id):
        item = {"id": 1, "tipo": tipo, "descricao": descricao, "autor_id": autor_id}
        self.interacoes.append(item)
        return item

    def criar_email_log(self, id_pi, tipo, assunto, destinatario, html, autor_id):
        self.logs.append(
            {
                "tipo": tipo,
                "assunto": assunto,
                "destinatario": destinatario["email"],
                "html": html,
            }
        )
        return len(self.logs)

    def concluir_email_log(self, log_id, resultado):
        self.logs[log_id - 1]["resultado"] = resultado


class FakeBrevo:
    def __init__(self):
        self.envios = []

    def enviar_email(self, **kwargs):
        self.envios.append(kwargs)
        return {"success": True, "messageId": "brevo-123"}


class PiOperacaoRepositoryTest(unittest.TestCase):
    def test_obter_pi_usa_coluna_legada_do_parceiro(self):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchone.return_value = {"id_pi": 175, "id_parceiro": 21}
        connection = MagicMock()
        connection.cursor.return_value = cursor

        result = PiOperacaoRepository(connection=connection).obter_pi(175)

        query = cursor.execute.call_args.args[0]
        self.assertIn('p."Id_parc_reg" AS id_parceiro', query)
        self.assertIn('parc.id_cliente = p."Id_parc_reg"', query)
        self.assertNotIn("p.id_parceiro", query)
        self.assertEqual(result["id_parceiro"], 21)


class PiOperacaoServiceTest(unittest.TestCase):
    def test_estado_expoe_parceiro_para_contexto_da_sidebar(self):
        estado = PiOperacaoService(repository=FakeRepository()).estado_completo(10)

        self.assertEqual(estado["pi"]["id_parceiro"], 21)
        self.assertEqual(estado["pi"]["parceiro_nome"], "Parceiro Regional Teste")

    def test_catalogo_respeita_estagio(self):
        service = PiOperacaoService(repository=FakeRepository(substatus=2))
        tipos = {item["tipo"] for item in service.catalogo(10)["tipos"]}
        self.assertEqual(
            tipos,
            {
                "solicitar_materiais",
                "confirmar_recebimento_pi",
                "pendencias_dados",
                "atualizacao_manual",
            },
        )

    def test_get_estado_nao_sincroniza_nem_escreve(self):
        repo = FakeRepository()
        service = PiOperacaoService(repository=repo)
        repo.gerar_checklist(
            10, service._itens_canonicos(10, repo.campanhas), autor_id=99
        )
        estado = service.estado_completo(10)
        self.assertEqual(repo.sync_calls, [])
        timeline = {item["etapa"]: item for item in estado["timeline"]}
        self.assertFalse(timeline["dados_validados"]["concluida"])
        self.assertFalse(timeline["campanhas_configuradas"]["concluida"])
        self.assertTrue(timeline["campanha_iniciada"]["concluida"])

    def test_checklist_separa_pi_e_campanhas_sem_duplicar(self):
        repo = FakeRepository()
        repo.campanhas.append(
            {
                **repo.campanhas[0],
                "id_campanha": 31,
                "nome_campanha": "Vídeo",
                "plataforma_nome": "YouTube",
            }
        )
        service = PiOperacaoService(repository=repo)
        service.gerar_checklist(10, {}, autor_id=99)
        service.gerar_checklist(10, {}, autor_id=99)
        estado = service.estado_completo(10)["checklist_operacional"]
        self.assertEqual(len(estado["itens_pi"]), 13)
        self.assertEqual(len(estado["campanhas"]), 2)
        self.assertTrue(all(len(item["itens"]) == 5 for item in estado["campanhas"]))
        self.assertEqual(len(repo.checklist), 23)

    def test_checklist_escala_para_vinte_campanhas(self):
        repo = FakeRepository()
        base = repo.campanhas[0]
        repo.campanhas = [
            {
                **base,
                "id_campanha": 30 + indice,
                "nome_campanha": f"Campanha {indice:02d}",
                "plataforma_nome": "DV360" if indice % 2 else "Meta Ads",
            }
            for indice in range(1, 21)
        ]
        service = PiOperacaoService(repository=repo)
        service.gerar_checklist(10, {}, autor_id=99)
        estrutura = service.estado_completo(10)["checklist_operacional"]
        self.assertEqual(estrutura["progresso"]["total"], 113)
        self.assertEqual(len(estrutura["campanhas"]), 20)
        self.assertTrue(
            all(len(campanha["itens"]) == 5 for campanha in estrutura["campanhas"])
        )

    def test_estado_campanha_isola_checklist_e_progresso(self):
        repo = FakeRepository()
        repo.campanhas.append(
            {
                **repo.campanhas[0],
                "id_campanha": 31,
                "nome_campanha": "Vídeo",
                "plataforma_nome": "YouTube",
            }
        )
        service = PiOperacaoService(repository=repo)
        service.gerar_checklist(10, {}, autor_id=99)
        manual = next(
            item
            for item in repo.checklist
            if item.get("id_campanha") == 30
            and item["codigo"] == "verificar_criativos"
        )
        service.atualizar_item(10, manual["id"], True, autor_id=99)

        estado = service.estado_campanha(10, 30)

        self.assertEqual([item["id_campanha"] for item in estado["campanhas"]], [30])
        self.assertTrue(
            all(item.get("id_campanha") == 30 for item in estado["checklist"])
        )
        self.assertEqual(estado["checklist_operacional"]["progresso"]["total"], 5)
        self.assertEqual(len(estado["checklist_operacional"]["campanhas"]), 1)
        self.assertEqual(estado["checklist_operacional"]["itens_pi"], [])
        self.assertEqual(
            [item["id_campanha"] for item in estado["campanhas_relacionadas"]],
            [30, 31],
        )
        self.assertTrue(estado["campanhas_relacionadas"][0]["atual"])
        self.assertFalse(estado["campanhas_relacionadas"][1]["atual"])

    def test_estado_campanha_rejeita_pi_incorreto(self):
        service = PiOperacaoService(repository=FakeRepository())
        with self.assertRaisesRegex(PropriedadeInvalidaError, "não pertence"):
            service.estado_campanha(999, 30)

    def test_falha_em_destinatarios_nao_interrompe_estado_operacional(self):
        class RecipientFailureRepository(FakeRepository):
            def __init__(self):
                super().__init__()
                self.rollback_calls = 0

            def listar_destinatarios(self, id_pi):
                raise RuntimeError("tabela indisponível")

            def listar_contatos_disponiveis(self, id_pi):
                return [
                    {
                        "id_contato_cliente": 40,
                        "pk_id_tbl_cliente": 20,
                        "nome_completo": "Cliente Teste",
                        "email": "cliente@example.com",
                    }
                ]

            def rollback(self):
                self.rollback_calls += 1

        repo = RecipientFailureRepository()
        estado = PiOperacaoService(repository=repo).estado_completo(10)

        self.assertEqual(repo.rollback_calls, 1)
        self.assertEqual(estado["destinatarios"], [])
        self.assertEqual(len(estado["contatos_disponiveis"]), 1)
        self.assertIn("Não foi possível carregar", estado["recipient_error"])
        self.assertIn("checklist_operacional", estado)

    def test_destinatario_sugerido_precisa_ser_salvo_antes_do_email(self):
        class SuggestedRecipientRepository(FakeRepository):
            def __init__(self):
                super().__init__(substatus=3)
                self.destinatarios = []

            def listar_destinatarios_sugeridos(self, id_pi):
                return [{
                    "id_contato_cliente": 40,
                    "nome_completo": "Cliente Teste",
                    "email": "cliente@example.com",
                    "papel": "cliente_final",
                    "padrao": True,
                }]

        repo = SuggestedRecipientRepository()
        service = PiOperacaoService(
            repository=repo,
            renderer=lambda *args, **kwargs: "<p>ok</p>",
        )
        estado = service.estado_completo(10)

        self.assertFalse(estado["destinatarios_confirmados"])
        self.assertEqual(len(estado["destinatarios"]), 1)
        with self.assertRaisesRegex(ValueError, "Nenhum destinatário operacional"):
            service.preview_email(10, {"tipo": "campanha_iniciada"})

    def test_marcos_de_objetivo_sao_automaticos_por_campanha(self):
        repo = FakeRepository(substatus=3)
        service = PiOperacaoService(repository=repo)
        service.gerar_checklist(10, {}, autor_id=99)
        itens = {
            (item["codigo"], item.get("id_campanha")): item
            for item in service.estado_completo(10)["checklist"]
        }
        self.assertTrue(itens[("objetivo_50", 30)]["concluido"])
        self.assertFalse(itens[("objetivo_90", 30)]["concluido"])
        self.assertIn("60.0%", itens[("objetivo_50", 30)]["evidencia"])

    def test_cotacao_enviada_exibe_evidencia_sem_confirmar_item(self):
        repo = FakeRepository()
        repo.pi["cotacao_id"] = 88
        repo.pi["proposta_enviada_em"] = date(2026, 9, 1)
        service = PiOperacaoService(repository=repo)
        service.gerar_checklist(10, {}, autor_id=99)
        item = next(
            item for item in service.estado_completo(10)["checklist"]
            if item["codigo"] == "verificar_cotacao_enviada"
        )
        self.assertFalse(item["concluido"])
        self.assertEqual(item["evidencia"], "Cotação enviada em 01/09/2026")

    def test_item_automatico_nao_pode_ser_marcado_manualmente(self):
        repo = FakeRepository()
        service = PiOperacaoService(repository=repo)
        service.gerar_checklist(10, {}, autor_id=99)
        automatico = next(
            item for item in repo.checklist
            if item["codigo"] == "campanha_iniciada"
        )
        with self.assertRaises(PropriedadeInvalidaError):
            service.atualizar_item(10, automatico["id"], True, autor_id=99)

    def test_envio_financeiro_conclui_item_do_pi(self):
        repo = FakeRepository(substatus=4)
        service = PiOperacaoService(repository=repo)
        service.gerar_checklist(10, {}, autor_id=99)
        estado = service.estado_completo(10)["checklist_operacional"]
        item = next(
            item for item in estado["itens_pi"]
            if item["codigo"] == "enviar_financeiro"
        )
        self.assertTrue(item["concluido"])

    def test_preview_consolida_todas_as_campanhas(self):
        repo = FakeRepository(substatus=3)
        repo.campanhas[0]["plataforma_nome"] = "DV360"
        repo.campanhas.append(
            {
                **repo.campanhas[0],
                "id_campanha": 31,
                "nome_campanha": "Social",
                "plataforma_nome": "Meta Ads",
            }
        )
        contexto = {}

        def renderer(template, **kwargs):
            contexto.update(kwargs)
            return "<p>ok</p>"

        service = PiOperacaoService(repository=repo, renderer=renderer)
        service.preview_email(
            10, {"tipo": "campanha_iniciada", "id_campanha": 30}
        )
        self.assertEqual(len(contexto["campanhas"]), 2)
        self.assertEqual(
            {item["plataforma"] for item in contexto["campanhas"]},
            {"DV360", "Meta Ads"},
        )
        self.assertEqual(
            sum(bool(item["destaque"]) for item in contexto["campanhas"]), 1
        )
        self.assertEqual(
            contexto["logo_centralcomm_url"],
            "https://ai.centralcomm.media/static/images/cc_logo.png",
        )

    def test_saude_sem_metricas_retorna_sem_dados(self):
        repo = FakeRepository(substatus=3)
        repo.campanhas[0]["obj_contratados"] = None
        estado = PiOperacaoService(repository=repo).estado_completo(10)
        self.assertEqual(estado["saude"]["status"], "sem_dados")

    def test_tipo_de_email_invalido_para_estagio(self):
        repo = FakeRepository(substatus=1)
        service = PiOperacaoService(
            repository=repo, renderer=lambda *args, **kwargs: "<p>ok</p>"
        )
        with self.assertRaisesRegex(ValueError, "não permitido"):
            service.preview_email(10, {"tipo": "campanha_iniciada"})

    def test_envio_real_passa_pelo_brevo_e_grava_log(self):
        repo = FakeRepository(substatus=3)
        brevo = FakeBrevo()
        service = PiOperacaoService(
            repository=repo,
            brevo_service=brevo,
            renderer=lambda template, **ctx: "<p>Campanha iniciada</p>",
        )
        resultado = service.enviar_email(
            10, {"tipo": "campanha_iniciada"}, autor_id=99
        )
        self.assertTrue(resultado["success"])
        self.assertEqual(brevo.envios[0]["to_email"], "cliente@example.com")
        self.assertEqual(repo.logs[0]["resultado"]["messageId"], "brevo-123")
        self.assertEqual(len(repo.sync_calls), 1)


class PiOperacaoRoutesTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY="test")
        self.app.register_blueprint(bp)
        self.client = self.app.test_client()

    def test_api_exige_login_json(self):
        response = self.client.get("/api/cadu_pi/10/operacao")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.get_json()["success"])

    def test_api_campanha_exige_login_json(self):
        response = self.client.get("/api/cadu_pi/10/operacao/campanhas/30")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.get_json()["success"])

    def test_api_bloqueia_usuario_externo(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 99
            sess["is_centralcomm"] = False
        response = self.client.get("/api/cadu_pi/10/operacao")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.get_json()["success"])

    def test_payload_invalido_obedece_contrato(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 99
            sess["is_centralcomm"] = True
        response = self.client.put(
            "/api/cadu_pi/10/operacao/destinatarios", json={"destinatarios": {}}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.get_json()), {"success", "error"})

    def test_edicao_de_campanha_e_catalogo_compartilham_operacao_corrigida(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 99
            sess["is_centralcomm"] = True
        service = MagicMock()
        service.estado_campanha.return_value = {
            "campanha": {"id_campanha": 345, "id_pi": 175}
        }
        service.catalogo.return_value = {"substatus": 2, "tipos": []}

        with patch(
            "aicentralv2.pi_operacao_routes._service",
            return_value=service,
        ):
            campanha = self.client.get(
                "/api/cadu_pi/175/operacao/campanhas/345"
            )
            catalogo = self.client.get(
                "/api/cadu_pi/175/operacao/comunicacoes/catalogo"
            )

        self.assertEqual(campanha.status_code, 200)
        self.assertEqual(catalogo.status_code, 200)
        service.estado_campanha.assert_called_once_with(175, 345)
        service.catalogo.assert_called_once_with(175)


if __name__ == "__main__":
    unittest.main()
