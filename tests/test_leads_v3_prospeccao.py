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
