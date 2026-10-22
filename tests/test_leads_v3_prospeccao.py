import re
from datetime import date
from unittest import TestCase
from unittest.mock import MagicMock, patch

from aicentralv2 import leads_v3_prospeccao as p
from aicentralv2 import leads_v3_routes as routes
from tests.test_leads_v3_routes import FakeConn, _client


class ClassificacaoTest(TestCase):
    def test_papeis_de_foco(self):
        self.assertEqual(p.classificar_cargo("Gerente de Mídia"), ("midia", "gerente"))
        self.assertEqual(p.classificar_cargo("Head of Media"), ("midia", "diretor"))
        self.assertEqual(p.classificar_cargo("Diretora de Marketing"), ("marketing", "diretor"))
        self.assertEqual(p.classificar_cargo("CMO"), ("marketing", "c_level"))
        self.assertEqual(p.classificar_cargo("Diretor de Criação"), ("criacao", "diretor"))
        self.assertEqual(p.classificar_cargo("CEO"), ("diretoria", "c_level"))
        self.assertEqual(p.classificar_cargo("Analista de Compras"), ("compras", "analista"))
        self.assertEqual(p.classificar_cargo("Engenheiro de Processos"), ("outro", "outro"))

    def test_termo_curto_nao_casa_no_meio_da_palavra(self):
        # "vp" e "coo" não podem casar dentro de outras palavras.
        self.assertEqual(p.classificar_cargo("Coordenador de Marketing")[1], "coordenador")

    def test_titulo_do_linkedin(self):
        self.assertEqual(p._parse_titulo_linkedin("Ana Lima - Gerente de Mídia - Gerdau | LinkedIn"), ("Ana Lima", "Gerente de Mídia"))
        self.assertEqual(p._parse_titulo_linkedin("Bruno Reis – Gerdau | LinkedIn"), ("Bruno Reis", "Gerdau"))
        self.assertEqual(p._parse_titulo_linkedin(""), ("", ""))

    def test_dominio_e_trimestre(self):
        self.assertEqual(p.normalizar_dominio("https://www.Gerdau.com.br/pt/sobre"), "gerdau.com.br")
        self.assertEqual(p.normalizar_dominio("contato@vale.com"), "vale.com")
        self.assertEqual(p.normalizar_dominio(""), "")
        self.assertEqual(p.trimestre_atual(date(2026, 10, 19)), "2026-Q4")
        self.assertEqual(p.trimestre_atual(date(2027, 1, 2)), "2027-Q1")


def _resp(status=200, body=None, text=""):
    r = MagicMock(status_code=status, ok=200 <= status < 300, text=text)
    r.json.return_value = body or {}
    return r


class ProvedoresTest(TestCase):
    def test_apollo_busca_usa_dominio_e_classifica(self):
        body = {"total_entries": 2, "people": [
            {"id": "a1", "first_name": "Ana", "last_name_obfuscated": "Li***a", "title": "Gerente de Mídia", "has_email": True},
            {"id": "a2", "first_name": "Rui", "last_name_obfuscated": "S***", "title": "Marketing Director", "has_email": False},
        ]}
        with patch.object(p.requests, "post", return_value=_resp(body=body)) as post:
            candidatos, total = p.apollo_buscar_pessoas("k", "gerdau.com.br")
        sent = post.call_args.kwargs
        self.assertEqual(sent["headers"]["X-Api-Key"], "k")
        self.assertEqual(sent["json"]["q_organization_domains_list"], ["gerdau.com.br"])
        self.assertTrue(post.call_args.args[0].endswith("/mixed_people/api_search"))
        self.assertEqual(total, 2)
        self.assertEqual(candidatos[0]["nome"], "Ana Li***a")
        self.assertEqual((candidatos[0]["papel_sugerido"], candidatos[1]["papel_sugerido"]), ("midia", "marketing"))

    def test_apollo_sem_chave_ou_sem_credito_vira_mensagem(self):
        with self.assertRaises(p.ProspeccaoError):
            p.apollo_buscar_pessoas("", "x.com")
        with patch.object(p.requests, "post", return_value=_resp(422, text="insufficient credits")):
            with self.assertRaisesRegex(p.ProspeccaoError, "créditos"):
                p.apollo_revelar("k", apollo_id="a1")

    def test_apollo_revelar_ignora_email_bloqueado(self):
        body = {"person": {"id": "a1", "name": "Ana Lima", "email": "email_not_unlocked@domain.com", "email_status": "verified"}}
        with patch.object(p.requests, "post", return_value=_resp(body=body)):
            self.assertIsNone(p.apollo_revelar("k", apollo_id="a1")["email"])

    def test_busca_web_filtra_homonimos_e_cargos_fora_do_foco(self):
        body = {"data": {"web": [
            {"url": "https://br.linkedin.com/in/ana-lima", "title": "Ana Lima - Gerente de Mídia - Gerdau | LinkedIn", "description": ""},
            {"url": "https://br.linkedin.com/in/ana-lima", "title": "Ana Lima - Gerente de Mídia - Gerdau | LinkedIn", "description": ""},
            {"url": "https://br.linkedin.com/in/joao", "title": "João - Engenheiro - Gerdau | LinkedIn", "description": ""},
            {"url": "https://br.linkedin.com/in/maria", "title": "Maria - Diretora de Marketing - Vale | LinkedIn", "description": ""},
            {"url": "https://gerdau.com/blog", "title": "Gerdau marketing", "description": ""},
        ]}}
        with patch.object(p.requests, "post", return_value=_resp(body=body)), \
                patch.object(p, "_firecrawl_search_endpoint", return_value="https://fc/v2/search"):
            candidatos = p.web_buscar_pessoas("fc", "Gerdau")
        self.assertEqual([c["provedor_ref"] for c in candidatos], ["ana-lima"])
        self.assertEqual(candidatos[0]["linkedin_url"], "https://www.linkedin.com/in/ana-lima")


class GoldenRoutesTest(TestCase):
    def test_criar_grava_so_as_validas(self):
        conn = FakeConn([])
        validas = {"ok": True, "bloqueios": [], "avisos": [], "dados": {"nome": "Vale"}}
        bloqueada = {"ok": False, "bloqueios": ["Esta empresa já está no Golden Circle deste executivo no trimestre."], "avisos": [], "dados": {}}
        with patch.object(routes.db, "get_db", return_value=conn), \
                patch.object(routes.prospeccao, "validar_conta", side_effect=[validas, bloqueada]) as validar, \
                patch.object(routes.prospeccao, "criar_conta", return_value={"id": 3, "id_lead": 9}) as criar:
            resp = _client().post("/leads-v3/api/golden", json={
                "id_executivo": 9, "trimestre": "2026-Q4", "contas": [{"nome": "Vale"}, {"nome": "Gerdau"}]})
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()["data"]
        self.assertEqual([c["nome"] for c in data["criadas"]], ["Vale"])
        self.assertEqual(data["recusadas"][0]["nome"], "Gerdau")
        self.assertEqual(validar.call_args_list[0].kwargs["id_executivo"], 9)
        criar.assert_called_once()
        self.assertTrue(conn.committed)

    def test_lote_vazio_e_recusado(self):
        with patch.object(routes.db, "get_db", return_value=FakeConn([])):
            resp = _client().post("/leads-v3/api/golden/validar", json={"contas": []})
        self.assertEqual(resp.status_code, 400)

    def test_migracao_pendente_responde_503(self):
        erro = Exception("relation does not exist")
        erro.sqlstate = "42P01"
        conn = FakeConn([])
        conn.cursor = MagicMock(side_effect=erro)
        with patch.object(routes.db, "get_db", return_value=conn):
            resp = _client().get("/leads-v3/api/golden")
        self.assertEqual(resp.status_code, 503)
        self.assertIn("migração", resp.get_json()["error"])


class ContatoRoutesTest(TestCase):
    def test_perfil_valida_valores(self):
        self.assertEqual(_client().patch("/leads-v3/api/contatos/1/perfil", json={"papel": "rh"}).status_code, 400)
        self.assertEqual(_client().patch("/leads-v3/api/contatos/1/perfil", json={"linkedin_url": "https://x.com/a"}).status_code, 400)
        self.assertEqual(_client().patch("/leads-v3/api/contatos/1/perfil", json={}).status_code, 400)

    def test_perfil_atualiza_so_campos_enviados(self):
        conn = FakeConn([1])
        conn.cursor().fetchone = None
        with patch.object(routes.db, "get_db", return_value=conn):
            resp = _client().patch("/leads-v3/api/contatos/1/perfil", json={"papel": "midia", "influencia": "decisor"})
        # FakeConn devolve fetchall, não fetchone: aqui só conferimos o SQL montado.
        sql, params = conn.calls[0]
        self.assertIn("papel = %s, influencia = %s", sql)
        self.assertEqual(params, ["midia", "decisor", 1])
        self.assertIn(resp.status_code, (200, 500))

    def test_descobrir_exige_fonte_valida(self):
        self.assertEqual(_client().post("/leads-v3/api/leads/1/descobrir", json={"fonte": "x"}).status_code, 400)

    def test_apollo_sem_dominio_explica_o_que_falta(self):
        with patch.object(routes, "_lead_para_busca", return_value=({"empresa": "Onfly", "nome": "x"}, "")), \
                patch.object(routes.db, "get_db", return_value=FakeConn([])):
            resp = _client().post("/leads-v3/api/leads/1/descobrir", json={"fonte": "apollo"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("domínio", resp.get_json()["error"])

    def test_empresa_rejeita_cnpj_curto_e_normaliza_dominio(self):
        self.assertEqual(_client().patch("/leads-v3/api/leads/1/empresa", json={"cnpj": "123"}).status_code, 400)
        conn = FakeConn([])
        with patch.object(routes.db, "get_db", return_value=conn):
            _client().patch("/leads-v3/api/leads/1/empresa", json={"dominio": "https://www.vale.com/br"})
        self.assertEqual(conn.calls[0][1][0], "vale.com")


class AcharEmailTest(TestCase):
    def test_monta_local_pelo_padrao(self):
        self.assertEqual(p.gerar_local("Carlos André Eyer", "nome.sobrenome"), "carlos.eyer")
        self.assertEqual(p.gerar_local("Ana Maria da Silva", "nsobrenome"), "asilva")
        self.assertEqual(p.gerar_local("GABRIELA MARTINS", "nome"), "gabriela")
        self.assertIsNone(p.gerar_local("Madonna", "nome.sobrenome"))
        self.assertEqual(p.gerar_local("Ana", "nome"), "ana")

    def test_inferir_pelos_contatos_conhecidos(self):
        exemplos = [("GABRIELA MARTINS", "gabriela.martins@zerezes.com.br"), ("Rui Lopes", "rui.lopes@zerezes.com.br"),
                    ("Ana Lima", "alima@zerezes.com.br")]
        self.assertEqual(p.inferir_padrao_por_exemplos(exemplos), ("nome.sobrenome", 2))
        self.assertEqual(p.inferir_padrao_por_exemplos([("Ana", "contato@x.com")]), (None, 0))

    def test_inferir_pela_estrutura_ignora_genericos(self):
        self.assertEqual(p.inferir_padrao_por_estrutura(["contato@x.com", "imprensa@x.com"]), (None, 0))
        self.assertEqual(p.inferir_padrao_por_estrutura(["maria.souza@x.com", "j.lima@x.com", "pedro.reis@x.com"]),
                         ("nome.sobrenome", 2))

    def test_cascata_usa_contatos_antes_do_firecrawl(self):
        coletar = MagicMock()
        r = p.achar_email("Carlos Eyer", "zerezes.com.br", [("Gabriela Martins", "gabriela.martins@zerezes.com.br")],
                          firecrawl_key="fc", coletar=coletar, mx=lambda d: True)
        self.assertEqual((r["email"], r["metodo"]), ("carlos.eyer@zerezes.com.br", "padrao_contatos"))
        coletar.assert_not_called()

    def test_cascata_cai_no_site_e_respeita_mx(self):
        coletar = MagicMock(return_value=(["ana.lima@vale.com", "contato@vale.com"], ["(31) 3333-4444"]))
        r = p.achar_email("Bruno Reis", "vale.com", [], firecrawl_key="fc", coletar=coletar, mx=lambda d: True)
        self.assertEqual((r["email"], r["metodo"]), ("bruno.reis@vale.com", "padrao_site"))
        self.assertEqual(r["telefones_empresa"], ["(31) 3333-4444"])
        sem_mx = p.achar_email("Bruno Reis", "vale.com", [], firecrawl_key="fc", coletar=coletar, mx=lambda d: False)
        self.assertIsNone(sem_mx["email"])
        self.assertIn("não recebe e-mail", sem_mx["motivo"])

    def test_sem_padrao_sugere_apollo(self):
        r = p.achar_email("Bruno Reis", "vale.com", [], firecrawl_key="fc", coletar=lambda k, d: ([], []), mx=lambda d: True)
        self.assertIsNone(r["email"])
        self.assertIn("Apollo", r["motivo"])

    def test_coleta_so_emails_do_dominio(self):
        emails, tels = p._coletar_contatos("Fale: ana.lima@vale.com, x@gmail.com, ri@br.vale.com. Tel (31) 99999-8888", "vale.com")
        self.assertEqual(emails, ["ana.lima@vale.com", "ri@br.vale.com"])
        self.assertEqual(tels, ["(31) 99999-8888"])

    def test_cargo_manda_mais_que_o_resumo(self):
        body = {"data": {"web": [{"url": "https://br.linkedin.com/in/carlos", "title": "Carlos Eyer - Chief Marketing Officer - Zerezes | LinkedIn",
                                  "description": "Design e criação de marcas na Zerezes"}]}}
        with patch.object(p.requests, "post", return_value=_resp(body=body)), \
                patch.object(p, "_firecrawl_search_endpoint", return_value="https://fc/v2/search"):
            candidato = p.web_buscar_pessoas("fc", "Zerezes")[0]
        self.assertEqual((candidato["papel_sugerido"], candidato["senioridade_sugerida"]), ("marketing", "c_level"))


class AcharEmailNivelTest(TestCase):
    def test_nome_oculto_do_apollo_nao_vira_palpite(self):
        r = p.achar_email("Joao Pe***a", "zerezes.com.br", [("Gabriela Martins", "gabriela.martins@zerezes.com.br")], mx=lambda d: True)
        self.assertIsNone(r["email"])
        self.assertEqual(r["nivel"], "pessoa")

    def test_falta_de_padrao_e_da_empresa(self):
        r = p.achar_email("Bruno Reis", "vale.com", [], firecrawl_key="fc", coletar=lambda k, d: ([], []), mx=lambda d: True)
        self.assertEqual(r["nivel"], "empresa")
        sem_sobrenome = p.achar_email("Madonna", "vale.com", [("Ana Lima", "ana.lima@vale.com")], mx=lambda d: True)
        self.assertEqual(sem_sobrenome["nivel"], "pessoa")


class CelularApolloTest(TestCase):
    def test_pedido_manda_webhook_e_reveal_phone(self):
        with patch.object(p.requests, "post", return_value=_resp(body={"person": {"id": "ap1"}})) as post:
            self.assertEqual(p.apollo_pedir_celular("k", "https://x/webhook", linkedin_url="https://linkedin.com/in/a")["apollo_id"], "ap1")
        body = post.call_args.kwargs["json"]
        self.assertTrue(body["reveal_phone_number"])
        self.assertEqual(body["webhook_url"], "https://x/webhook")
        self.assertEqual(body["linkedin_url"], "https://linkedin.com/in/a")

    def test_pedido_aproveita_o_email_que_ja_foi_cobrado(self):
        body = {"person": {"id": "ap1", "name": "Ana Lima", "email": "ana@vale.com", "email_status": "verified"}}
        with patch.object(p.requests, "post", return_value=_resp(body=body)):
            r = p.apollo_pedir_celular("k", "https://x/webhook", apollo_id="ap1")
        self.assertEqual((r["email"], r["email_status"]), ("ana@vale.com", "valido"))

    def test_so_celular_entra_e_fixo_fica_fora(self):
        payload = {"people": [{"id": "ap1", "phone_numbers": [
            {"sanitized_number": "+553133330000", "type_cd": "work_hq", "status_cd": "valid_number"},
            {"sanitized_number": "+5531999990000", "type_cd": "mobile", "status_cd": "invalid_number"},
            {"sanitized_number": "+5531988880000", "type_cd": "mobile", "status_cd": "valid_number"},
            {"sanitized_number": "+553132221111", "type_cd": "mobile", "status_cd": "valid_number"},  # fixo marcado como mobile
            {"sanitized_number": "+5531977770000", "type_cd": "work_direct", "status_cd": "no_status"},
            {"sanitized_number": "+5531966660000", "type_cd": "work_hq", "status_cd": "valid_number"},  # linha da empresa
        ]}]}
        self.assertEqual(p.celulares_do_webhook(payload, "ap1"), [
            {"numero": "+5531988880000", "status": "valido"},
            {"numero": "+5531977770000", "status": "nao_verificado"},
        ])
        self.assertEqual(p.celulares_do_webhook({"people": [{"id": "ap1", "phone_numbers": []}]}, "ap1"), [])

    def test_celular_brasileiro_e_estrangeiro(self):
        self.assertEqual(p.celular_br("(31) 98888-0000"), "+5531988880000")
        self.assertEqual(p.celular_br("+55 31 98888-0000"), "+5531988880000")
        self.assertIsNone(p.celular_br("(31) 3333-0000"))
        self.assertIsNone(p.celular_br("+55 31 3333-0000"))
        self.assertEqual(p.celular_br("+1 415 555 0100"), "+14155550100")
        self.assertIsNone(p.celular_br(""))

    def test_estrangeiro_so_entra_se_o_apollo_disser_mobile(self):
        payload = {"people": [{"id": "ap1", "phone_numbers": [
            {"sanitized_number": "+14155550100", "type_cd": "work_direct"},
            {"sanitized_number": "+14155550199", "type_cd": "mobile"}]}]}
        self.assertEqual([c["numero"] for c in p.celulares_do_webhook(payload)], ["+14155550199"])

    def test_juntar_celulares_sem_repetir(self):
        atuais = [{"numero": "+5531988880000", "status": "valido"}]
        novos = [{"numero": "+5531988880000", "status": "nao_verificado"}, {"numero": "+5531977770000", "status": "valido"}]
        self.assertEqual([c["numero"] for c in p.juntar_celulares(atuais, novos)], ["+5531988880000", "+5531977770000"])
        self.assertEqual(p.juntar_celulares(atuais, novos)[0]["status"], "valido")
        subiu = p.juntar_celulares([{"numero": "+5531988880000", "status": "nao_verificado"}], [{"numero": "+5531988880000", "status": "valido"}])
        self.assertEqual(subiu, [{"numero": "+5531988880000", "status": "valido"}])

    def test_celular_extra_errado_sai_e_o_do_whatsapp_fica(self):
        conn = _Roteiro({"id": 5, "id_lead": 1, "nome": "Ana", "email": None, "telefone": "+5531988880000",
                         "celulares": [{"numero": "+5531988880000"}, {"numero": "+5531977770000"}]})
        with patch.object(routes.db, "get_db", return_value=conn):
            resp = _client().post("/leads-v3/api/contatos/5/dado-errado", json={"campo": "telefone", "valor": "+5531977770000"})
        self.assertEqual(resp.status_code, 200)
        _, params = next(c for c in conn.calls if "celulares = %s" in c[0])
        self.assertEqual(params[0], "+5531988880000")
        self.assertEqual(params[2].obj, [{"numero": "+5531988880000"}])

    def test_celular_do_whatsapp_errado_passa_para_o_proximo(self):
        conn = _Roteiro({"id": 5, "id_lead": 1, "nome": "Ana", "email": None, "telefone": "+5531988880000",
                         "celulares": [{"numero": "+5531988880000"}, {"numero": "+5531977770000"}]})
        with patch.object(routes.db, "get_db", return_value=conn):
            _client().post("/leads-v3/api/contatos/5/dado-errado", json={"campo": "telefone"})
        _, params = next(c for c in conn.calls if "celulares = %s" in c[0])
        self.assertEqual(params[0], "+5531977770000")

    def test_flags_da_busca_gratis(self):
        self.assertEqual(p.flags_apollo({"has_email": False, "has_direct_phone": "Yes"}), (False, True))
        self.assertEqual(p.flags_apollo({"has_email": True, "has_direct_phone": "Maybe: please request direct dial via people/bulk_match"}), (True, None))
        self.assertEqual(p.flags_apollo({}), (None, None))

    def test_sem_email_avisa_do_credito_do_perfil(self):
        with patch.object(p.requests, "post", return_value=_resp(body={"person": {"id": "a1", "name": "Ana Lima"}})):
            r = p.apollo_revelar("k", apollo_id="a1")
        self.assertIsNone(r["email"])
        self.assertIn("1 crédito", r["motivo"])

    def test_email_bloqueado_explica_o_motivo(self):
        body = {"person": {"id": "a1", "name": "Ana", "email": "email_not_unlocked@domain.com"}}
        with patch.object(p.requests, "post", return_value=_resp(body=body)):
            r = p.apollo_revelar("k", apollo_id="a1")
        self.assertIsNone(r["email"])
        self.assertIn("créditos", r["motivo"])


class WebhookCelularTest(TestCase):
    def test_assinatura_invalida_e_recusada(self):
        resp = _client().post("/leads-v3/webhooks/apollo/celular/7?token=errado", json={"people": []})
        self.assertEqual(resp.status_code, 403)

    def test_webhook_nao_exige_login(self):
        from tests.test_leads_v3_routes import _app
        app = _app()
        with app.test_request_context():
            token = routes._assinatura_contato(7)
        conn = FakeConn([])
        conn.cursor().fetchone = lambda: None
        with patch.object(routes.db, "get_db", return_value=conn):
            resp = app.test_client().post(f"/leads-v3/webhooks/apollo/celular/7?token={token}", json={"people": []})
        self.assertNotEqual(resp.status_code, 302)


class CelularSemVerificacaoTest(TestCase):
    def test_numero_sem_verificacao_ainda_serve(self):
        payload = {"people": [{"id": "ap1", "phone_numbers": [
            {"sanitized_number": "+5531977770000", "type_cd": "mobile", "status_cd": "no_status"}]}]}
        self.assertEqual(p.celulares_do_webhook(payload, "ap1")[0]["numero"], "+5531977770000")

    def test_verificado_vence_sem_verificacao_do_mesmo_tipo(self):
        payload = {"people": [{"id": "ap1", "phone_numbers": [
            {"sanitized_number": "+5531991110000", "type_cd": "mobile", "status_cd": "no_status"},
            {"sanitized_number": "+5531992220000", "type_cd": "mobile", "status_cd": "valid_number"}]}]}
        self.assertEqual(p.celulares_do_webhook(payload, "ap1")[0]["numero"], "+5531992220000")


class _Roteiro:
    """Conexão falsa que devolve, em ordem, as linhas de cada fetchone e guarda o SQL executado."""
    def __init__(self, *linhas):
        self.linhas, self.calls = list(linhas), []

    def cursor(self):
        conn = self

        class C:
            def __enter__(self): return self
            def __exit__(self, *e): return False
            def execute(self, sql, params=None): conn.calls.append((" ".join(sql.split()), params))
            def fetchone(self): return conn.linhas.pop(0) if conn.linhas else None
        return C()

    def commit(self): pass
    def rollback(self): pass


class CreditoApolloRotasTest(TestCase):
    def _contato(self, **extra):
        return {"id": 5, "id_lead": 1, "nome": "Ana Lima", "email": None, "email_status": None, "linkedin_url": None,
                "origem_dado": "apollo", "origem_ref": "ap1", "apollo_person_id": "ap1", "telefone": None,
                "telefone_status": None, "apollo_tem_email": None, "apollo_tem_celular": None, "apollo_revelado_em": None,
                "cargo": None, "dominio": "vale.com", "url_site": None, **extra}

    def test_revelar_nao_cobra_quem_a_busca_disse_que_nao_tem_email(self):
        conn = _Roteiro(self._contato(apollo_tem_email=False))
        with patch.object(routes.db, "get_db", return_value=conn), patch.object(p.requests, "post") as post:
            r = _client().post("/leads-v3/api/contatos/5/revelar", json={}).get_json()["data"]
        post.assert_not_called()
        self.assertTrue(r["bloqueado"])

    def test_revelar_de_novo_quem_ja_voltou_sem_email_pede_confirmacao(self):
        conn = _Roteiro(self._contato(apollo_revelado_em="2026-10-01"))
        with patch.object(routes.db, "get_db", return_value=conn), patch.object(p.requests, "post") as post:
            r = _client().post("/leads-v3/api/contatos/5/revelar", json={}).get_json()["data"]
        post.assert_not_called()
        self.assertIn("outro crédito", r["motivo"])

    def test_revelar_com_forcar_consulta(self):
        conn = _Roteiro(self._contato(apollo_tem_email=False))
        body = {"person": {"id": "ap1", "name": "Ana Lima", "email": "ana@vale.com", "email_status": "verified"}}
        with patch.object(routes.db, "get_db", return_value=conn), \
                patch.object(routes, "resolve_apollo_api_key", return_value="k"), \
                patch.object(p.requests, "post", return_value=_resp(body=body)):
            r = _client().post("/leads-v3/api/contatos/5/revelar", json={"forcar": True}).get_json()["data"]
        self.assertEqual(r["email"], "ana@vale.com")
        self.assertTrue(any("apollo_revelado_em = CURRENT_TIMESTAMP" in sql for sql, _ in conn.calls))

    def test_celular_nao_e_pedido_quando_o_apollo_ja_disse_que_nao_tem(self):
        conn = _Roteiro(self._contato(telefone_status="sem_numero"))
        with patch.object(routes.db, "get_db", return_value=conn), patch.object(p.requests, "post") as post:
            r = _client().post("/leads-v3/api/contatos/5/celular", json={}).get_json()["data"]
        post.assert_not_called()
        self.assertTrue(r["bloqueado"])

    def _webhook(self, conn, payload):
        from tests.test_leads_v3_routes import _app
        app = _app()
        with app.test_request_context():
            token = routes._assinatura_contato(5)
        with patch.object(routes.db, "get_db", return_value=conn):
            return app.test_client().post(f"/leads-v3/webhooks/apollo/celular/5?token={token}", json=payload)

    def test_webhook_guarda_varios_celulares_e_troca_fixo_pelo_celular(self):
        conn = _Roteiro({"id": 5, "id_lead": 1, "nome": "Ana", "apollo_person_id": "ap1", "telefone": "(31) 3333-0000",
                         "celulares": [{"numero": "+5531988880000", "status": "valido"}]})
        resp = self._webhook(conn, {"people": [{"id": "ap1", "phone_numbers": [
            {"sanitized_number": "+5531988880000", "type_cd": "mobile", "status_cd": "valid_number"},
            {"sanitized_number": "+5531977770000", "type_cd": "mobile", "status_cd": "no_status"},
            {"sanitized_number": "+553133330000", "type_cd": "work_hq"}]}]})
        self.assertEqual(resp.status_code, 200)
        sql, params = next(c for c in conn.calls if "SET telefone = %s, celulares" in c[0])
        self.assertEqual(params[0], "+5531988880000")
        self.assertEqual([c["numero"] for c in params[1].obj], ["+5531988880000", "+5531977770000"])
        self.assertTrue(any("Celular de Ana encontrado" in str(prm) for _, prm in conn.calls))  # só o novo conta

    def test_webhook_so_com_fixo_marca_sem_numero(self):
        conn = _Roteiro({"id": 5, "id_lead": 1, "nome": "Ana", "apollo_person_id": "ap1", "telefone": None, "celulares": None})
        self._webhook(conn, {"people": [{"id": "ap1", "phone_numbers": [{"sanitized_number": "+553133330000", "type_cd": "work_hq"}]}]})
        self.assertTrue(any("telefone_status = 'sem_numero'" in sql for sql, _ in conn.calls))

    def test_escolher_celular_do_whatsapp(self):
        conn = _Roteiro({"id": 5, "id_lead": 1, "nome": "Ana", "celulares": [{"numero": "+5531977770000"}]})
        with patch.object(routes.db, "get_db", return_value=conn):
            resp = _client().patch("/leads-v3/api/contatos/5/celular-principal", json={"numero": "(31) 97777-0000"})
        self.assertEqual(resp.get_json()["data"]["telefone"], "+5531977770000")
        conn = _Roteiro({"id": 5, "id_lead": 1, "nome": "Ana", "celulares": []})
        with patch.object(routes.db, "get_db", return_value=conn):
            self.assertEqual(_client().patch("/leads-v3/api/contatos/5/celular-principal", json={"numero": "31977770000"}).status_code, 409)


class UrlWebhookTest(TestCase):
    def test_usa_o_dominio_publico_configurado(self):
        from tests.test_leads_v3_routes import _app
        app = _app()
        app.config["LEADS_V3_WEBHOOK_BASE_URL"] = "https://ai.centralcomm.media/"
        with app.test_request_context("/", base_url="http://127.0.0.1:8001"):
            url = routes._url_webhook_celular(7)
        self.assertTrue(url.startswith("https://ai.centralcomm.media/leads-v3/webhooks/apollo/celular/7?token="), url)


class MesmaPessoaTest(TestCase):
    def test_sobrenome_mascarado_do_apollo(self):
        self.assertTrue(p.nomes_batem("Ana Ma***s", "Ana Flávia Martins"))
        self.assertTrue(p.nomes_batem("Giovane Lu***a", "Giovane Lucena"))
        self.assertFalse(p.nomes_batem("Giovane Lu***a", "Giovane Luz"))
        self.assertFalse(p.nomes_batem("Juliana Ol***a", "Juliana Romano"))

    def test_nome_completo(self):
        self.assertTrue(p.nomes_batem("JULIANA ROMANO", "Juliana Romano"))
        self.assertTrue(p.nomes_batem("Ana Martins", "Ana Flávia Martins"))
        self.assertFalse(p.nomes_batem("Ana Paula Barros", "Ana Paula Sanchez"))
        self.assertFalse(p.nomes_batem("Ana Paula Martins", "Ana Clara Martins"))
        self.assertFalse(p.nomes_batem("Paula", "Paula Nunes"))  # só o primeiro nome é pouco para juntar

    def test_achar_existente_por_ids_antes_do_nome(self):
        contatos = [{"id": 1, "nome": "Ana Souza", "email": "ana@x.com"},
                    {"id": 2, "nome": "Bia Lima", "linkedin_url": "https://www.linkedin.com/in/bia-lima/"},
                    {"id": 3, "nome": "Caio Reis", "origem_dado": "apollo", "origem_ref": "ap1"}]
        self.assertEqual(p.achar_existente({"nome": "Outra", "email": "ANA@x.com"}, contatos)["id"], 1)
        self.assertEqual(p.achar_existente({"nome": "B L", "linkedin_url": "http://linkedin.com/in/Bia-Lima?x=1"}, contatos)["id"], 2)
        self.assertEqual(p.achar_existente({"nome": "?", "apollo_id": "ap1"}, contatos)["id"], 3)
        self.assertEqual(p.achar_existente({"nome": "Caio Re***s"}, contatos)["id"], 3)
        self.assertIsNone(p.achar_existente({"nome": "Davi Melo"}, contatos))

    def test_pares_duplicados_nao_repete_contato(self):
        contatos = [{"id": 1, "nome": "JULIANA ROMANO", "email": "j@q.com"}, {"id": 2, "nome": "Juliana Romano", "email": "j@q.com"},
                    {"id": 3, "nome": "Juliana Romano"}, {"id": 4, "nome": "Felipe Anjos"}]
        self.assertEqual([(a["id"], b["id"]) for a, b in p.pares_duplicados(contatos)], [(1, 2)])


class MesclarRoutesTest(TestCase):
    def test_mesclar_exige_outro_contato(self):
        self.assertEqual(_client().post("/leads-v3/api/contatos/5/mesclar", json={}).status_code, 400)
        self.assertEqual(_client().post("/leads-v3/api/contatos/5/mesclar", json={"id_duplicado": 5}).status_code, 400)

    def test_dado_errado_valida_campo(self):
        self.assertEqual(_client().post("/leads-v3/api/contatos/5/dado-errado", json={"campo": "nome"}).status_code, 400)

    def test_acao_de_candidato_invalida(self):
        self.assertEqual(_client().post("/leads-v3/api/candidatos/1/xpto", json={}).status_code, 404)


class LeadDoFormularioTest(TestCase):
    def test_empresa_do_dominio(self):
        self.assertEqual(p.empresa_do_dominio("nitrolab.com.br"), "Nitrolab")
        self.assertEqual(p.empresa_do_dominio("secom.mt.gov.br"), "Secom")
        self.assertEqual(p.empresa_do_dominio("asia-tcomm.tv.br"), "Asia Tcomm")
        self.assertEqual(p.empresa_do_dominio("x.ai"), "X")

    def test_sugestoes_com_email_corporativo(self):
        lead = {"nome": "Adriene Mendes", "empresa": "", "email": "adriene@nitrolab.com.br", "cargo": "Midia OFF"}
        s = p.sugestoes_do_lead(lead, [])
        self.assertEqual((s["dominio"], s["empresa"]), ("nitrolab.com.br", "Nitrolab"))
        self.assertEqual(s["contato"], {"nome": "Adriene Mendes", "email": "adriene@nitrolab.com.br", "telefone": None, "cargo": "Midia OFF"})

    def test_sugestoes_com_email_pessoal_e_contato_ja_existente(self):
        lead = {"nome": "Aline Benatti", "empresa": "Aline Benatti", "email": "aline@gmail.com"}
        self.assertEqual(p.sugestoes_do_lead(lead, []), {"dominio": None, "empresa": None, "contato": None})
        lead = {"nome": "Ana Lima", "empresa": "X", "email": "ana@x.com.br", "dominio": "x.com.br"}
        self.assertIsNone(p.sugestoes_do_lead(lead, [{"id": 1, "nome": "ANA LIMA", "email": None}])["contato"])

    def test_gatilho_usa_a_mesma_lista_de_emails_pessoais(self):
        from pathlib import Path
        sql = (Path(__file__).resolve().parents[1] / "migrations/add_cadu_leads_v3_site_contato.sql").read_text()
        lista = set(re.findall(r"'([a-z.]+\.[a-z]+)'", sql.split("NOT IN (", 1)[1].split(")", 1)[0]))
        self.assertEqual(lista, p.FREE_EMAIL_DOMAINS)

