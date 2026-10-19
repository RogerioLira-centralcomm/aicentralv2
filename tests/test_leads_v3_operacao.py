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

    def test_prompt_leva_etapa_canal_foco_contexto_e_historico(self):
        system, user = m.montar_prompt_mensagem(canal="linkedin_conexao", etapa="topo", foco="Conteúdos de topo: estudo ESG",
                                                contexto="Vale lançou campanha X", historico=["E-mail enviado"], remetente="Apolo", **self.base)
        self.assertIn("TOPO de funil", system)
        self.assertIn("280 caracteres", system)
        self.assertIn("nunca invente", system)
        for trecho in ("Ana Lima", "Gerente de Mídia", "estudo ESG", "campanha X", "E-mail enviado", "Assine como Apolo"):
            self.assertIn(trecho, user)

    def test_canal_ou_etapa_invalidos(self):
        with self.assertRaises(ProspeccaoError):
            m.montar_prompt_mensagem(canal="fax", etapa="topo", **self.base)
        with self.assertRaises(ProspeccaoError):
            m.montar_prompt_mensagem(canal="email", etapa="fundo", **self.base)

    def test_email_separa_assunto(self):
        r = m.gerar_mensagem("k", chat_fn=_chat("Assunto: Ideia de mídia para a Vale\n\nOlá Ana,\nTudo bem?"), canal="email", etapa="meio", **self.base)
        self.assertEqual(r["assunto"], "Ideia de mídia para a Vale")
        self.assertTrue(r["texto"].startswith("Olá Ana"))

    def test_convite_linkedin_respeita_300_caracteres(self):
        r = m.gerar_mensagem("k", chat_fn=_chat("palavra " * 80), canal="linkedin_conexao", etapa="topo", **self.base)
        self.assertLessEqual(len(r["texto"]), 300)

    def test_contexto_guarda_fontes(self):
        ctx = m.gerar_contexto_mercado("k", empresa="Vale", chat_fn=_chat("1. Fato", ["https://g1.globo.com/x"]))
        self.assertEqual(ctx["fontes"], ["https://g1.globo.com/x"])
        self.assertEqual(ctx["texto"], "1. Fato")

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
