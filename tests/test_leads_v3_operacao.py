from unittest import TestCase
from unittest.mock import MagicMock, patch

from aicentralv2 import leads_v3_mensagens as m
from aicentralv2 import leads_v3_routes as routes
from aicentralv2.leads_v3_prospeccao import ProspeccaoError
from tests.test_leads_v3_routes import FakeConn, _client


def _chat(texto, fontes=()):
    return MagicMock(return_value=(texto, list(fontes)))


class MensagemTest(TestCase):
    base = dict(objetivo="abrir conversa", pessoa={"nome": "Ana Lima", "cargo": "Gerente de Mídia", "papel": "midia"},
                empresa={"nome": "Vale", "segmento": "Mineração"})

    def test_prompt_leva_etapa_canal_gancho_foco_e_historico(self):
        gancho = {"fato": "Varejo cresceu 12% em CTV", "numero": "12%", "fonte_nome": "Kantar", "data_fato": "2026-08",
                  "angulo": "Onde a marca aparece na TV conectada?"}
        system, user = m.montar_prompt_mensagem(canal="linkedin_conexao", etapa="topo", foco="Conteúdos de topo: estudo ESG",
                                                contexto="Vale lançou campanha X", historico=["E-mail enviado"], remetente="Apolo",
                                                gancho=gancho, ja_usados=["Fato antigo"], **self.base)
        self.assertIn("TOPO de funil", system)
        self.assertIn("280 caracteres", system)
        self.assertIn("Nunca invente", system)
        self.assertIn("Você escreve como Apolo", system)
        for trecho in ("Ana Lima", "Gerente de Mídia", "estudo ESG", "Varejo cresceu 12% em CTV", "Kantar (2026-08)",
                       "Fato antigo", "E-mail enviado"):
            self.assertIn(trecho, user)
        self.assertNotIn("campanha X", user)  # com gancho, o contexto solto não entra

    def test_sem_gancho_usa_contexto(self):
        _, user = m.montar_prompt_mensagem(canal="email", etapa="topo", contexto="Vale lançou campanha X", **self.base)
        self.assertIn("campanha X", user)

    def test_canal_ou_etapa_invalidos(self):
        with self.assertRaises(ProspeccaoError):
            m.montar_prompt_mensagem(canal="fax", etapa="topo", **self.base)
        with self.assertRaises(ProspeccaoError):
            m.montar_prompt_mensagem(canal="email", etapa="lateral", **self.base)

    def test_email_separa_assunto_e_assina_como_executivo(self):
        r = m.gerar_mensagem("k", chat_fn=_chat("Assunto: dado de ctv no varejo\n\nAna, o Kantar mostrou X.\n\nFaz sentido?\n\nUm abraço,\nApolo Lira"),
                             canal="email", etapa="meio", remetente="Apolo Lira", dispositivo="iphone", **self.base)
        self.assertEqual(r["assunto"], "dado de ctv no varejo")
        self.assertEqual(r["texto"], "Ana, o Kantar mostrou X.\n\nFaz sentido?\n\nAbs,\nApolo\n\nEnviado do meu iPhone")
        self.assertEqual(r["alertas"], [])

    def test_assinatura_propria_e_whatsapp_sem_assinatura(self):
        self.assertEqual(m.assinar("Oi", "email", assinatura="Abraço\nApolo · CentralComm", dispositivo="galaxy"),
                         "Oi\n\nAbraço\nApolo · CentralComm\n\nEnviado do meu Galaxy")
        self.assertEqual(m.assinar("Oi, Ana\n\nAbs", "whatsapp", remetente="Apolo"), "Oi, Ana")

    def test_frase_de_ia_forca_uma_reescrita(self):
        chat = MagicMock(side_effect=[("Ana, espero que esteja bem. Vi campanhas incríveis.", []),
                                      ("Ana, vi que o varejo cresceu 12% em CTV. Faz sentido aí?", [])])
        r = m.gerar_mensagem("k", chat_fn=chat, canal="whatsapp", etapa="topo", **self.base)
        self.assertEqual(chat.call_count, 2)
        self.assertIn("espero que esteja bem", chat.call_args_list[1].args[3])
        self.assertEqual(r["alertas"], [])
        self.assertEqual(m.frases_proibidas("Tudo bem? Soluções que vão alavancar"), ["tudo bem?", "soluções", "alavancar"])

    def test_reescrita_sem_assunto_mantem_o_primeiro(self):
        chat = MagicMock(side_effect=[("Assunto: dado de ctv\n\nAna, espero que esteja bem.", []), ("Ana, o varejo cresceu 12%.", [])])
        r = m.gerar_mensagem("k", chat_fn=chat, canal="email", etapa="topo", **self.base)
        self.assertEqual(r["assunto"], "dado de ctv")

    def test_convite_linkedin_respeita_300_caracteres(self):
        r = m.gerar_mensagem("k", chat_fn=_chat("palavra " * 80), canal="linkedin_conexao", etapa="topo", **self.base)
        self.assertLessEqual(len(r["texto"]), 300)

    def test_dossie_valida_ganchos_e_resolve_fonte_por_indice(self):
        resposta = """```json
        {"resumo": "Vale investe em marca.", "ganchos": [
          {"tipo": "setor", "etapa": "topo", "fato": "Mineração dobrou investimento em mídia", "numero": "2x",
           "fonte_nome": "Cenp", "fonte_url": "[2]", "data": "2026-07", "angulo": "E a Vale?"},
          {"tipo": "xpto", "etapa": "fundo", "fato": "Sem fonte", "fonte_url": ""},
          {"tipo": "campanha", "etapa": "meio", "fato": "Vale lançou campanha ESG", "fonte_url": "https://mm.com.br/a"},
          {"tipo": "campanha", "etapa": "meio", "fato": "Vale lançou campanha ESG", "fonte_url": "https://mm.com.br/b"}]}
        ```"""
        d = m.gerar_dossie("k", empresa="Vale", chat_fn=_chat(resposta, ["https://a.com", "https://cenp.com.br/x"]))
        self.assertEqual(d["contexto"]["texto"], "Vale investe em marca.")
        self.assertEqual([g["fato"] for g in d["ganchos"]], ["Mineração dobrou investimento em mídia", "Vale lançou campanha ESG"])
        self.assertEqual(d["ganchos"][0]["fonte_url"], "https://cenp.com.br/x")
        self.assertEqual((d["ganchos"][0]["data_fato"], d["ganchos"][1]["etapa"]), ("2026-07", "meio"))

    def test_dossie_sem_json_guarda_texto(self):
        d = m.gerar_dossie("k", empresa="Vale", chat_fn=_chat("Não achei nada.", []))
        self.assertEqual((d["contexto"]["texto"], d["ganchos"]), ("Não achei nada.", []))

    def test_sugerir_foco(self):
        foco = m.sugerir_foco("k", empresa="Vale", ganchos=[{"etapa": "topo", "tipo": "setor", "fato": "F"}],
                              chat_fn=_chat('{"topo": "CTV", "meio": "case", "tom": "direto", "evitar": "preço"}'))
        self.assertEqual(foco, {"topo": "CTV", "meio": "case", "tom": "direto", "evitar": "preço"})
        with self.assertRaises(ProspeccaoError):
            m.sugerir_foco("k", empresa="Vale", chat_fn=_chat("sem json"))

    def test_chat_le_fontes_das_anotacoes(self):
        resp = MagicMock()
        resp.json.return_value = {"choices": [{"message": {"content": "ok", "annotations": [
            {"type": "url_citation", "url_citation": {"url": "https://valor.globo.com/a"}}]}}]}
        texto, fontes = m.chat("k", "perplexity/sonar", "s", "u", post=MagicMock(return_value=resp))
        self.assertEqual((texto, fontes), ("ok", ["https://valor.globo.com/a"]))

    def test_chat_sem_chave(self):
        with self.assertRaises(ProspeccaoError):
            m.chat("", "x", "s", "u")


class AlvoTest(TestCase):
    def test_valor_alvo_aceita_numero_e_formato_brasileiro(self):
        self.assertEqual(routes._campos_alvo({"valor_alvo": "120000.5"})[1], [120000.5])
        self.assertEqual(routes._campos_alvo({"valor_alvo": "R$ 1.234.567,89"})[1], [1234567.89])
        self.assertEqual(routes._campos_alvo({"valor_alvo": ""})[1], [None])
        with self.assertRaises(ProspeccaoError):
            routes._campos_alvo({"valor_alvo": "abc"})

    def test_marco_prazo_e_papeis_validados(self):
        with self.assertRaises(ProspeccaoError):
            routes._campos_alvo({"proximo_marco": "festa"})
        with self.assertRaises(ProspeccaoError):
            routes._campos_alvo({"prazo": "31/12/2026"})
        with self.assertRaises(ProspeccaoError):
            routes._campos_alvo({"papeis_alvo": ["rh"]})
        sets, params = routes._campos_alvo({"proximo_marco": "reuniao", "papeis_alvo": ["midia"]})
        self.assertEqual(params, ["reuniao", ["midia"]])


class OperacaoRoutesTest(TestCase):
    def test_acao_de_passo_invalida(self):
        self.assertEqual(_client().post("/leads-v3/api/inscricoes/1/apagar", json={}).status_code, 404)

    def test_passo_feito_chama_a_cadencia(self):
        with patch.object(routes.db, "get_db", return_value=FakeConn([])), \
                patch.object(routes.cadencias, "avancar", return_value={"status": "ativa", "passo_atual": 2, "proxima_em": None}) as avancar:
            resp = _client().post("/leads-v3/api/inscricoes/5/feito", json={"nota": "x" * 500})
        self.assertEqual(resp.status_code, 200)
        args, kwargs = avancar.call_args
        self.assertEqual(args[1:], (5, "feito"))
        self.assertEqual(len(kwargs["nota"]), 300)

    def test_inscrever_repetido_responde_409(self):
        with patch.object(routes.db, "get_db", return_value=FakeConn([])), \
                patch.object(routes.cadencias, "inscrever", return_value=None):
            resp = _client().post("/leads-v3/api/contatos/1/cadencia", json={})
        self.assertEqual(resp.status_code, 409)

    def test_foco_valida_canais_e_limpa_textos(self):
        self.assertEqual(_client().patch("/leads-v3/api/leads/1/empresa", json={"canais_foco": ["fax"]}).status_code, 400)
        conn = FakeConn([])
        with patch.object(routes.db, "get_db", return_value=conn):
            _client().patch("/leads-v3/api/leads/1/empresa", json={"canais_foco": ["email"], "foco_conteudo": {"topo": " estudo ", "meio": "", "x": "y"}})
        sql, params = conn.calls[0]
        self.assertIn("canais_foco = %s, foco_conteudo = %s", sql)
        self.assertEqual(params[0], ["email"])
        self.assertEqual(params[1].obj, {"topo": "estudo"})

    def test_mensagem_exige_pessoa(self):
        self.assertEqual(_client().post("/leads-v3/api/mensagens/gerar", json={}).status_code, 400)

    def test_gancho_valida_campos(self):
        with patch.object(routes.db, "get_db", return_value=FakeConn([])):
            self.assertEqual(_client().post("/leads-v3/api/leads/1/ganchos", json={"fato": " "}).status_code, 400)
            self.assertEqual(_client().post("/leads-v3/api/leads/1/ganchos", json={"fato": "F", "fonte_url": "mm.com"}).status_code, 400)
            self.assertEqual(_client().patch("/leads-v3/api/ganchos/1", json={"status": "x"}).status_code, 400)
            self.assertEqual(_client().patch("/leads-v3/api/ganchos/1", json={}).status_code, 400)

    def test_preferencias_validam_dispositivo(self):
        self.assertEqual(_client().put("/leads-v3/api/preferencias", json={"dispositivo": "nokia"}).status_code, 400)


class MigracaoLegadoTest(TestCase):
    def test_mesclar_exige_outro_lead(self):
        self.assertEqual(_client().post("/leads-v3/api/leads/5/mesclar", json={}).status_code, 400)
        self.assertEqual(_client().post("/leads-v3/api/leads/5/mesclar", json={"id_duplicado": 5}).status_code, 400)

    def test_analise_recusa_data_invalida(self):
        self.assertEqual(_client().get("/leads-v3/api/analise?data_inicio=01/01/2026").status_code, 400)

    def test_paginas_antigas_foram_removidas_e_redirecionam(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        for arquivo in ("templates/cadu_leads.html", "templates/leads_analise.html", "static/js/leads.js", "static/css/leads.css"):
            self.assertFalse((root / "aicentralv2" / arquivo).exists(), arquivo)
        rotas = (root / "aicentralv2/routes.py").read_text()
        self.assertIn("return redirect(url_for('leads_v3.pagina'))", rotas)
        self.assertIn("return redirect(url_for('leads_v3.pagina', vista='analise'))", rotas)


class VisaoGeralOperacaoTest(TestCase):
    def test_operacao_traz_hoje_proximos_e_feitos(self):
        with patch.object(routes.db, "get_db", return_value=FakeConn([])), \
                patch.object(routes.cadencias, "fila_do_dia", return_value=[{"id": 1}]), \
                patch.object(routes.cadencias, "proximos_passos", return_value=[{"id": 2}]) as prox, \
                patch.object(routes.cadencias, "feitos_hoje", return_value=[{"id": 3}]), \
                patch.object(routes, "tarefas_pendentes", return_value=[]):
            resp = _client().get("/leads-v3/api/operacao?executivo=9")
        data = resp.get_json()["data"]
        self.assertEqual([data[k][0]["id"] for k in ("passos", "proximos", "feitos")], [1, 2, 3])
        self.assertEqual(prox.call_args.kwargs["executivo"], 9)


class AnaliseSemanalTest(TestCase):
    def test_periodo_invalido(self):
        self.assertEqual(_client().get("/leads-v3/api/analise/semanal?data_inicio=2026-10-21&data_fim=2026-10-01").status_code, 400)
        self.assertEqual(_client().get("/leads-v3/api/analise/semanal?data_inicio=2024-01-01&data_fim=2026-10-01").status_code, 400)
        self.assertEqual(_client().get("/leads-v3/api/analise/semanal?data_inicio=xx").status_code, 400)

    def test_semanas_comecam_na_segunda(self):
        from datetime import date
        self.assertEqual(routes._semanas(date(2026, 10, 8), date(2026, 10, 20)), ["2026-10-05", "2026-10-12", "2026-10-19"])


class FluxosTest(TestCase):
    passo = {"dia": 0, "canal": "email", "etapa": "meio", "titulo": "Retomar", "objetivo": "x"}

    def test_normaliza_fluxo_e_recusa_o_que_nao_cabe(self):
        from aicentralv2 import leads_v3_cadencias as cad

        f = cad.normalizar_fluxo({"nome": "  Já   conversou ", "estagio": "em_conversa", "papeis": ["midia", "rh", "midia"],
                                  "passos": [self.passo, {**self.passo, "dia": 3, "canal": "linkedin", "acao": "conectar", "etapa": "fundo"}]})
        self.assertEqual(f["nome"], "Já conversou")
        self.assertEqual(f["papeis"], ["midia"])
        self.assertEqual([(p["acao"], p["etapa"]) for p in f["passos"]], [("enviar", "meio"), ("conectar", "fundo")])
        for ruim in ({"nome": ""}, {"nome": "x", "estagio": "quente", "passos": [self.passo]}, {"nome": "x", "passos": []},
                     {"nome": "x", "passos": [{**self.passo, "etapa": "lateral"}]},
                     {"nome": "x", "passos": [{**self.passo, "dia": 5}, {**self.passo, "dia": 2}]},
                     {"nome": "x", "passos": [self.passo] * 13}):
            with self.assertRaises(ProspeccaoError):
                cad.normalizar_fluxo(ruim)

    def test_etapa_do_passo_antigo_segue_a_regra_de_antes(self):
        from aicentralv2.leads_v3_cadencias import etapa_do_passo

        self.assertEqual([etapa_do_passo({}, i, 5) for i in range(5)], ["topo", "topo", "topo", "meio", "meio"])
        self.assertEqual(etapa_do_passo({"etapa": "fundo"}, 0, 5), "fundo")

    def test_prompt_leva_o_ponto_do_fluxo_e_a_etapa_de_fundo(self):
        fluxo = {"fluxo": "Já conversou", "estagio": "Já conversou com a gente", "posicao": "passo 3 de 4",
                 "anteriores": ["Retomar a conversa", "Material sob medida"], "seguintes": ["Próximo passo"]}
        system, user = m.montar_prompt_mensagem(canal="email", etapa="fundo", fluxo=fluxo, **MensagemTest.base)
        self.assertIn("FUNDO de funil", system)
        for trecho in ("Fluxo: Já conversou", "passo 3 de 4", "Material sob medida", "não antecipe"):
            self.assertIn(trecho, user)

    def test_editar_fluxo_em_uso_cria_versao_nova(self):
        from aicentralv2 import leads_v3_cadencias as cad

        cursor = MagicMock()
        cursor.fetchone.side_effect = [{"id": 4, "chave": "inbound", "passos": [], "em_uso": True}, {"id": 9}]
        r = cad.atualizar_fluxo(cursor, 4, {"nome": "Veio do site", "estagio": "inbound", "passos": [self.passo]}, usuario_id=1)
        self.assertEqual(r, {"id": 9, "nova_versao": True})
        sqls = [c.args[0] for c in cursor.execute.call_args_list]
        self.assertIn("SET ativo = FALSE, chave = NULL", sqls[1])
        self.assertEqual(cursor.execute.call_args_list[2].args[1][0], "inbound")  # chave vai para a versão nova

    def test_rotas_de_fluxo_validam_antes_do_banco(self):
        self.assertEqual(_client().post("/leads-v3/api/cadencias", json={"nome": ""}).status_code, 400)

    def test_renomear_fluxo_em_uso_com_passos_antigos_nao_cria_versao(self):
        from aicentralv2 import leads_v3_cadencias as cad

        antigo = {"dia": 0, "canal": "email", "acao": "enviar", "titulo": "Retomar"}  # sem etapa nem objetivo
        cursor = MagicMock()
        cursor.fetchone.side_effect = [{"id": 4, "chave": None, "passos": [antigo], "em_uso": True}]
        r = cad.atualizar_fluxo(cursor, 4, {"nome": "Outro nome", "estagio": "novo",
                                            "passos": [{**antigo, "etapa": "topo", "objetivo": ""}]}, usuario_id=1)
        self.assertEqual(r, {"id": 4, "nova_versao": False})


class ControleCadenciaTest(TestCase):
    def test_rotas_pedem_fluxo_e_passo(self):
        c = _client()
        self.assertEqual(c.post("/leads-v3/api/inscricoes/3/trocar", json={}).status_code, 400)
        self.assertEqual(c.post("/leads-v3/api/inscricoes/3/passo", json={}).status_code, 400)
        self.assertEqual(c.post("/leads-v3/api/leads/3/trocar-fluxo", json={}).status_code, 400)

    def test_adiar_valida_a_data_antes_do_banco(self):
        from datetime import date
        from aicentralv2 import leads_v3_cadencias as cad

        cursor = MagicMock()
        for ruim in ("21/10/2026", "2026-10-19", "2027-06-01"):
            with self.assertRaises(ProspeccaoError):
                cad.adiar(cursor, 1, ruim, usuario_id=1, hoje=date(2026, 10, 21))
        cursor.execute.assert_not_called()

    def test_trocar_para_o_mesmo_fluxo_ou_passo_inexistente(self):
        from aicentralv2 import leads_v3_cadencias as cad

        aberta = {"id": 1, "id_lead": 2, "id_contato": 3, "id_executivo": 4, "id_cadencia": 7, "status": "ativa",
                  "passo_atual": 0, "cadencia": "A", "passos": [{}], "contato_nome": "Ana"}
        for destino, passo, msg in (({"id": 7, "nome": "A", "passos": [{}]}, 0, "já está neste fluxo"),
                                    ({"id": 8, "nome": "B", "passos": [{}]}, 3, "não tem esse passo")):
            cursor = MagicMock()
            cursor.fetchone.side_effect = [dict(aberta), destino]
            with self.assertRaises(ProspeccaoError) as ctx:
                cad.trocar_fluxo(cursor, 1, destino["id"], passo=passo, usuario_id=1)
            self.assertIn(msg, str(ctx.exception))
