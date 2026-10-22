from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock, patch

from aicentralv2 import leads_v3_email as em
from aicentralv2.leads_v3_prospeccao import ProspeccaoError

AGORA = datetime(2026, 10, 22, 15, 30)
USUARIO = {"id": 7, "nome": "Apolo Lira", "email": "apolo@centralcomm.media"}
PREFS = {"modelo_assinatura": "simples", "cargo": "Diretor", "telefone": "(11) 99999-0000",
         "linkedin_url": "https://www.linkedin.com/in/apolo"}


class Cursor:
    """Responde cada fetchone na ordem dada e guarda os SQLs executados."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.sqls = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.sqls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.respostas.pop(0) if self.respostas else None

    def executou(self, trecho):
        return [p for s, p in self.sqls if trecho in s]


class MontagemTest(TestCase):
    def test_assinatura_simples_texto_e_html(self):
        texto, html = em.assinatura(PREFS, nome_usuario="Apolo Lira")
        self.assertEqual(texto, "Apolo Lira\nDiretor · CentralComm\n(11) 99999-0000 · https://www.linkedin.com/in/apolo · centralcomm.media")
        self.assertIn("<strong", html)
        self.assertIn('href="tel:+5511999990000"', html)
        self.assertIn('href="https://www.linkedin.com/in/apolo"', html)
        self.assertNotIn("<img", html)

    def test_email_poe_assinatura_antes_do_rodape_do_celular_e_linka_urls(self):
        html, texto = em.montar_email("Ana, veja https://kantar.com/x.\n\nFaz sentido?\n\nAbs,\nApolo\n\nEnviado do meu iPhone",
                                      PREFS, nome_usuario="Apolo Lira")
        self.assertTrue(texto.startswith("Ana, veja https://kantar.com/x.\n\nFaz sentido?\n\nAbs,\nApolo\n\nApolo Lira\nDiretor"))
        self.assertTrue(texto.endswith("\n\nEnviado do meu iPhone"))
        self.assertIn('<a href="https://kantar.com/x" style="color:#1a56db">https://kantar.com/x</a>.', html)
        self.assertLess(html.index("Diretor"), html.index("Enviado do meu iPhone"))

    def test_link_com_texto_vira_ancora_e_texto_com_url(self):
        html, texto = em.montar_email("Veja [o estudo da Kantar](https://kantar.com/ctv).", {}, nome_usuario="Apolo")
        self.assertIn('<a href="https://kantar.com/ctv" style="color:#1a56db">o estudo da Kantar</a>', html)
        self.assertTrue(texto.startswith("Veja o estudo da Kantar (https://kantar.com/ctv)."))

    def test_assunto_de_resposta_nao_empilha_re(self):
        self.assertEqual(em.assunto_resposta("RE: Re: dado de ctv"), "Re: dado de ctv")
        self.assertEqual(em.assunto_resposta("Fwd: dado"), "Re: dado")

    def test_html_escapa_o_texto(self):
        html, _ = em.montar_email("<script>x</script>", {}, nome_usuario="Apolo")
        self.assertNotIn("<script>", html)

    def test_preferencias_validam_linkedin_e_modelo(self):
        self.assertEqual(em.normalizar_preferencias({"linkedin_url": "linkedin.com/in/a"})["linkedin_url"], "https://linkedin.com/in/a")
        self.assertEqual(em.normalizar_preferencias({"linkedin_url": "http://www.linkedin.com/in/a"})["linkedin_url"],
                         "https://www.linkedin.com/in/a")
        with self.assertRaises(ProspeccaoError):
            em.normalizar_preferencias({"linkedin_url": "https://evil.com/in/a"})
        with self.assertRaises(ProspeccaoError):
            em.normalizar_preferencias({"modelo_assinatura": "neon"})

    def test_remetente_so_do_dominio_autenticado(self):
        self.assertEqual(em.validar_remetente("Apolo@CentralComm.media"), "apolo@centralcomm.media")
        with self.assertRaises(ProspeccaoError):
            em.validar_remetente("apolo@gmail.com")


def _inscricao(**extra):
    return {"id": 3, "id_lead": 10, "id_contato": 20, "status": "ativa", "passo_atual": 1, "passo": {"canal": "email"},
            "contato_nome": "Ana Lima", "email": "ana@marca.com", "email_status": "valido", **extra}


class EnvioTest(TestCase):
    def test_na_mesma_conversa_responde_com_re_e_cabecalhos(self):
        anterior = {"provedor_message_id": "<m2@brevo>", "ocorreu_em": AGORA,
                    "payload": {"assunto": "Re: dado de ctv", "assunto_conversa": "dado de ctv", "referencias": ["<m1@brevo>"]}}
        cursor = Cursor([_inscricao(), None, {"n": 0}, anterior])
        enviar = MagicMock(return_value={"success": True, "messageId": "<m3@brevo>"})
        with patch.object(em.cadencias, "avancar", return_value={"status": "ativa", "passo_atual": 2, "proxima_em": None}):
            r = self._enviar(cursor, enviar, assunto="", na_conversa=True)
        kw = enviar.call_args.kwargs
        self.assertEqual(kw["subject"], "Re: dado de ctv")
        self.assertEqual(kw["headers"], {"In-Reply-To": "<m2@brevo>", "References": "<m1@brevo> <m2@brevo>"})
        gravado = cursor.executou("'enviado', 'brevo'")[0][4].obj
        self.assertEqual((gravado["assunto_conversa"], gravado["referencias"]), ("dado de ctv", ["<m1@brevo>", "<m2@brevo>"]))
        self.assertEqual(r["assunto"], "Re: dado de ctv")

    def test_conversa_sem_email_anterior_vira_conversa_nova(self):
        cursor = Cursor([_inscricao(), None, {"n": 0}, None])
        enviar = MagicMock(return_value={"success": True, "messageId": "<m1@brevo>"})
        with patch.object(em.cadencias, "avancar", return_value={"status": "ativa", "passo_atual": 2, "proxima_em": None}):
            self._enviar(cursor, enviar, na_conversa=True)
        self.assertEqual(enviar.call_args.kwargs["subject"], "dado de ctv")
        self.assertIsNone(enviar.call_args.kwargs["headers"])

    def test_previa_mostra_envelope_e_bloqueio(self):
        cursor = Cursor([_inscricao(), None, {"n": 0}, None])
        p = em.previa(cursor, 3, assunto="dado de ctv", texto="Ana, oi.", prefs=PREFS, usuario=USUARIO, na_conversa=False)
        self.assertEqual(p["de"], {"name": "Apolo Lira", "email": "apolo@centralcomm.media"})
        self.assertEqual(p["reply_to"], p["de"])
        self.assertEqual(p["para"]["email"], "ana@marca.com")
        self.assertIn("Diretor · CentralComm", p["html"])
        self.assertIsNone(p["bloqueio"])
        self.assertFalse(p["tem_conversa"])
        fora = em.previa(Cursor([_inscricao()]), 3, assunto="x", texto="y", prefs={}, usuario={**USUARIO, "email": "a@gmail.com"},
                         na_conversa=False)
        self.assertIn("@centralcomm.media", fora["bloqueio"])

    def _enviar(self, cursor, enviar_fn, **extra):
        kwargs = dict(assunto="dado de ctv", texto="Ana, oi.\n\nAbs,\nApolo", passo=1, usuario=USUARIO, prefs=PREFS,
                      enviar_fn=enviar_fn, agora=AGORA)
        kwargs.update(extra)
        return em.enviar_passo(cursor, 3, **kwargs)

    def test_envia_como_executivo_e_marca_o_passo(self):
        cursor = Cursor([_inscricao(), None, {"n": 0}])
        enviar = MagicMock(return_value={"success": True, "messageId": "<abc@brevo>"})
        with patch.object(em.cadencias, "avancar", return_value={"status": "ativa", "passo_atual": 2, "proxima_em": None}) as avancar:
            r = self._enviar(cursor, enviar, id_gancho=5)
        kw = enviar.call_args.kwargs
        self.assertEqual(kw["sender"], {"name": "Apolo Lira", "email": "apolo@centralcomm.media"})
        self.assertEqual(kw["reply_to"], kw["sender"])
        self.assertEqual(kw["to_email"], "ana@marca.com")
        self.assertEqual(kw["tags"], ["leads-v3"])
        self.assertIn("Diretor · CentralComm", kw["text_content"])
        insert = cursor.executou("'enviado', 'brevo'")[0]
        self.assertEqual(insert[3], "<abc@brevo>")
        self.assertEqual(insert[4].obj["id_usuario"], "7")
        self.assertEqual(insert[4].obj["id_gancho"], 5)
        self.assertEqual(avancar.call_args.args[2], "feito")
        self.assertEqual(r["message_id"], "<abc@brevo>")

    def test_nao_envia_quando_o_passo_ja_andou(self):
        enviar = MagicMock()
        with self.assertRaises(ProspeccaoError):
            self._enviar(Cursor([_inscricao(passo_atual=2)]), enviar)
        enviar.assert_not_called()

    def test_bloqueios_antes_de_enviar(self):
        casos = [
            [_inscricao(passo={"canal": "whatsapp"})],
            [_inscricao(email="")],
            [_inscricao(email_status="invalido")],
            [_inscricao(), {"?column?": 1}],             # opt-out
            [_inscricao(), None, {"n": em.LIMITE_DIARIO}],  # limite diário
        ]
        for respostas in casos:
            enviar = MagicMock()
            with self.subTest(respostas=respostas), self.assertRaises(ProspeccaoError):
                self._enviar(Cursor(respostas), enviar)
            enviar.assert_not_called()

    def test_sem_assunto_ou_login_de_fora_nem_consulta(self):
        with self.assertRaises(ProspeccaoError):
            self._enviar(Cursor([]), MagicMock(), assunto=" ")
        with self.assertRaises(ProspeccaoError):
            self._enviar(Cursor([]), MagicMock(), usuario={**USUARIO, "email": "apolo@gmail.com"})

    def test_falha_da_brevo_vira_mensagem_e_nada_e_gravado(self):
        cursor = Cursor([_inscricao(), None, {"n": 0}])
        enviar = MagicMock(return_value={"success": False, "user_message": "Remetente não verificado."})
        with self.assertRaisesRegex(ProspeccaoError, "Remetente não verificado"):
            self._enviar(cursor, enviar)
        self.assertEqual(cursor.executou("'enviado', 'brevo'"), [])


ENVIO = {"id_lead": 10, "id_contato": 20, "id_inscricao": 3}


class EventosTest(TestCase):
    def test_nome_do_evento(self):
        self.assertEqual(em.nome_evento("uniqueOpened"), "unique_opened")
        self.assertEqual(em.nome_evento("hard_bounce"), "hard_bounce")
        self.assertEqual(em.nome_evento("Opened"), "opened")

    def test_abertura_real_e_proxy_contam_separado(self):
        p = em.somar_evento("aberto", {}, nome="proxy_open", quando="2026-10-22T10:00")
        p = em.somar_evento("aberto", p, nome="opened", quando="2026-10-22T10:05")
        p = em.somar_evento("aberto", p, nome="opened", quando="2026-10-22T11:00")
        self.assertEqual(p, {"proxy": 1, "reais": 2, "primeira_real": "2026-10-22T10:05", "ultima_real": "2026-10-22T11:00"})

    def test_unique_e_opened_juntos_nao_contam_em_dobro(self):
        def contar(nomes):
            p = {}
            for n in nomes:
                p = em.somar_evento("aberto", p, nome=n, quando="t")
            return p.get("reais"), p.get("proxy")
        self.assertEqual(contar(["unique_opened"]), (1, None))  # configuração atual da conta
        self.assertEqual(contar(["unique_opened", "opened", "opened"]), (2, None))
        self.assertEqual(contar(["opened", "unique_opened", "opened"]), (2, None))
        self.assertEqual(contar(["unique_proxy_open", "unique_opened"]), (1, 1))

    def test_cliques_guardam_os_links(self):
        p = em.somar_evento("clicado", {}, nome="click", quando="t1", url="https://a")
        p = em.somar_evento("clicado", p, nome="click", quando="t2", url="https://a")
        self.assertEqual((p["vezes"], p["urls"], p["ultimo_em"]), (2, ["https://a"], "t2"))

    def test_evento_de_email_de_fora_do_leads_e_ignorado(self):
        cursor = Cursor([None])
        self.assertFalse(em.aplicar_evento_brevo(cursor, {"event": "opened", "message-id": "<x>"}))
        self.assertEqual(len(cursor.sqls), 1)
        self.assertFalse(em.aplicar_evento_brevo(Cursor([]), {"event": "deferred", "message-id": "<x>"}))

    def test_abertura_grava_no_lead(self):
        cursor = Cursor([ENVIO, {"id": 99, "payload": {"reais": 1}}])
        self.assertTrue(em.aplicar_evento_brevo(cursor, {"event": "opened", "message-id": "<abc>"}, agora=AGORA))
        update = cursor.executou("UPDATE cadu_lead_mensagem_eventos SET payload")[0]
        self.assertEqual(update[0].obj["reais"], 2)
        self.assertEqual(update[0].obj["ultima_real"], "2026-10-22T15:30")
        self.assertEqual(cursor.executou("INSERT INTO cadu_lead_mensagem_eventos")[0][3], "aberto")

    def test_aviso_de_leitura_so_na_primeira_abertura_real_e_clique_novo(self):
        self.assertEqual(em.aviso_de_leitura("aberto", {}, {"reais": 1}, assunto="dado"), "Abriu o e-mail «dado».")
        self.assertIsNone(em.aviso_de_leitura("aberto", {"reais": 1}, {"reais": 2}))
        self.assertIsNone(em.aviso_de_leitura("aberto", {}, {"proxy": 1}))
        self.assertIn("https://a", em.aviso_de_leitura("clicado", {}, {"urls": ["https://a"]}, url="https://a"))
        self.assertIsNone(em.aviso_de_leitura("clicado", {"urls": ["https://a"]}, {"urls": ["https://a"]}, url="https://a"))

    def test_primeira_abertura_vira_atividade_da_pessoa(self):
        cursor = Cursor([{**ENVIO, "assunto": "dado de ctv"}, {"id": 99, "payload": {}}])
        em.aplicar_evento_brevo(cursor, {"event": "unique_opened", "message-id": "<abc>"}, agora=AGORA)
        atividade = cursor.executou("INSERT INTO cadu_lead_atividades")[0]
        self.assertEqual(atividade[:4], [10, "nota", "Abriu o e-mail «dado de ctv».", 20])
        self.assertEqual(atividade[5], "Brevo")

    def test_descadastro_registra_optout_e_encerra_cadencias(self):
        cursor = Cursor([ENVIO, {"id": 99, "payload": {}}, {"nome": "Ana", "email": "Ana@Marca.com"}])
        self.assertTrue(em.aplicar_evento_brevo(cursor, {"event": "unsubscribed", "message-id": "<abc>"}, agora=AGORA))
        self.assertEqual(cursor.executou("INSERT INTO cadu_lead_optout")[0][0], "ana@marca.com")
        self.assertEqual(cursor.executou("UPDATE cadu_lead_cadencia_inscricoes")[0][0], "cancelada")

    def test_bounce_definitivo_invalida_o_email_e_pausa(self):
        cursor = Cursor([ENVIO, {"id": 99, "payload": {}}])
        self.assertTrue(em.aplicar_evento_brevo(cursor, {"event": "hard_bounce", "message-id": "<abc>", "reason": "no mailbox"}, agora=AGORA))
        self.assertTrue(cursor.executou("SET email_status = 'invalido'"))
        self.assertEqual(cursor.executou("UPDATE cadu_lead_cadencia_inscricoes")[0][0], "pausada")

    def test_soft_bounce_so_registra(self):
        cursor = Cursor([ENVIO, {"id": 99, "payload": {}}])
        em.aplicar_evento_brevo(cursor, {"event": "soft_bounce", "message-id": "<abc>"}, agora=AGORA)
        self.assertFalse(cursor.executou("UPDATE cadu_lead_cadencia_inscricoes"))


class RotasTest(TestCase):
    def _client(self, email="apolo@centralcomm.media"):
        from tests.test_leads_v3_routes import _client
        client = _client()
        with client.session_transaction() as s:
            s["user_email"] = email
        return client

    def test_salvar_preferencias_grava_campos_e_devolve_a_assinatura(self):
        from aicentralv2 import leads_v3_routes as routes
        from tests.test_leads_v3_routes import FakeConn
        conn = FakeConn([])
        cursor = Cursor([{"dispositivo": "iphone", "assinatura": "Abs,", "cargo": "Diretor",
                          "linkedin_url": "https://linkedin.com/in/apolo", "modelo_assinatura": "simples"}])
        conn.cursor = lambda: cursor
        with patch.object(routes.db, "get_db", return_value=conn):
            resp = self._client().put("/leads-v3/api/preferencias", json={
                "dispositivo": "iphone", "assinatura": "Abs,", "cargo": "Diretor", "linkedin_url": "linkedin.com/in/apolo"})
        data = resp.get_json()["data"]
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(conn.committed)
        self.assertIn("cargo = EXCLUDED.cargo", cursor.sqls[0][0])
        self.assertEqual(cursor.sqls[0][1][-1], "https://linkedin.com/in/apolo")
        self.assertEqual(data["linkedin_url"], "https://linkedin.com/in/apolo")
        self.assertTrue(data["remetente"]["pode_enviar"])
        self.assertIn("Diretor · CentralComm", data["assinatura_texto"])

    def test_trocar_so_o_rodape_nao_apaga_a_assinatura(self):
        from aicentralv2 import leads_v3_routes as routes
        from tests.test_leads_v3_routes import FakeConn
        conn = FakeConn([])
        cursor = Cursor([{"dispositivo": "iphone", "cargo": "Diretor", "modelo_assinatura": "simples"}])
        conn.cursor = lambda: cursor
        with patch.object(routes.db, "get_db", return_value=conn):
            resp = self._client().put("/leads-v3/api/preferencias", json={"dispositivo": "iphone"})
        upsert = cursor.sqls[0][0]
        self.assertIn("(id_usuario, dispositivo)", upsert)
        self.assertNotIn("cargo", upsert)
        self.assertEqual(resp.get_json()["data"]["cargo"], "Diretor")

    def test_login_de_fora_do_dominio_nao_pode_enviar(self):
        from aicentralv2 import leads_v3_routes as routes
        from tests.test_leads_v3_routes import FakeConn
        conn = FakeConn([])
        conn.cursor = lambda: Cursor([None])
        with patch.object(routes.db, "get_db", return_value=conn):
            resp = self._client("exec@gmail.com").put("/leads-v3/api/preferencias", json={"dispositivo": "nenhum"})
        self.assertFalse(resp.get_json()["data"]["remetente"]["pode_enviar"])

    def test_enviar_exige_o_passo_e_traduz_o_bloqueio(self):
        from aicentralv2 import leads_v3_routes as routes
        from tests.test_leads_v3_routes import FakeConn
        self.assertEqual(self._client().post("/leads-v3/api/inscricoes/3/enviar-email", json={"assunto": "a"}).status_code, 400)
        conn = FakeConn([])
        conn.cursor = lambda: Cursor([None])  # preferências ainda não salvas
        with patch.object(routes.db, "get_db", return_value=conn), \
             patch.object(routes.email_mail, "enviar_passo", side_effect=ProspeccaoError("Esta pessoa pediu para não receber e-mails.")):
            resp = self._client().post("/leads-v3/api/inscricoes/3/enviar-email", json={"passo": 1, "assunto": "a", "texto": "b"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("não receber", resp.get_json()["error"])
        self.assertTrue(conn.rolled_back)
