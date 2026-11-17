"""Entrada de PI contra um Postgres de verdade (descartável). Pulado sem ``PI_ENTRADA_TEST_DSN``.

Uso: PI_ENTRADA_TEST_DSN="host=127.0.0.1 port=55432 user=postgres dbname=postgres" pytest tests/test_pi_entrada_banco.py
Cria tabelas mínimas no lugar das antigas (``tbl_cliente``, ``cadu_pi``...) e aplica ``create_pi_entrada.sql``.
Nunca aponte para o banco de produção: o teste escreve.
"""

import os
from pathlib import Path

import pytest

DSN = os.getenv("PI_ENTRADA_TEST_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="defina PI_ENTRADA_TEST_DSN para rodar contra um Postgres descartável")

psycopg = pytest.importorskip("psycopg")
from psycopg import connect as conectar_de_verdade                                    # noqa: E402  (o conftest troca psycopg.connect por uma recusa em cada teste)
from psycopg.rows import dict_row                                                   # noqa: E402

from aicentralv2.pi_entrada import cadastro, esquema, repositorio                   # noqa: E402
from tests.test_pi_entrada_leitura import resposta_modelo                           # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
TABELAS_ANTIGAS = """
DROP TABLE IF EXISTS cadu_cotacao_linhas, cadu_cotacoes, cadu_pi, tbl_contato_cliente, tbl_cliente CASCADE;
CREATE TABLE tbl_cliente (id_cliente SERIAL PRIMARY KEY, cnpj TEXT, razao_social TEXT, nome_fantasia TEXT, inscricao_estadual TEXT,
  inscricao_municipal TEXT, endereco TEXT, logradouro TEXT, numero TEXT, complemento TEXT, bairro TEXT, cep TEXT, cidade TEXT,
  estado TEXT, email TEXT, telefone TEXT, vendas_central_comm INTEGER, observacoes_comerciais_adicionais TEXT, status BOOLEAN DEFAULT TRUE);
CREATE TABLE tbl_contato_cliente (id_contato_cliente SERIAL PRIMARY KEY, pk_id_tbl_cliente INTEGER, nome_completo TEXT, email TEXT);
CREATE TABLE cadu_pi (id_pi SERIAL PRIMARY KEY, codigo_pi_cc VARCHAR(40), codigo_pi_ag VARCHAR(40), titulo_pi VARCHAR(200));
CREATE TABLE cadu_cotacoes (id SERIAL PRIMARY KEY, numero_cotacao TEXT, nome_campanha TEXT, periodo_inicio DATE, periodo_fim DATE,
  status TEXT, valor_total_proposta NUMERIC, budget_estimado NUMERIC, plataforma_campanha TEXT, tipo_de_contrato TEXT,
  client_id INTEGER, agencia_id INTEGER, deleted_at TIMESTAMP, created_at TIMESTAMP DEFAULT NOW());
CREATE TABLE cadu_cotacao_linhas (id SERIAL PRIMARY KEY, cotacao_id INTEGER, plataforma TEXT, formatos TEXT, formato TEXT, objetivo_kpi TEXT,
  formato_compra TEXT, praca TEXT, segmentacao TEXT, volume_contratado BIGINT, valor_unitario NUMERIC, valor_unitario_negociado NUMERIC,
  investimento_bruto NUMERIC, investimento_liquido NUMERIC, valor_total NUMERIC, data_inicio DATE, data_fim DATE, ordem INTEGER,
  is_subtotal BOOLEAN DEFAULT FALSE, is_header BOOLEAN DEFAULT FALSE, is_deleted BOOLEAN DEFAULT FALSE);
"""


@pytest.fixture()
def banco(monkeypatch):
    conn = conectar_de_verdade(DSN, row_factory=dict_row, autocommit=False)
    with conn.cursor() as c:
        c.execute("DROP TABLE IF EXISTS pi_entrada_log, pi_entrada_ajuste, pi_entrada_arquivo, pi_entrada CASCADE")
        c.execute(TABELAS_ANTIGAS)
        c.execute((RAIZ / "migrations" / "create_pi_entrada.sql").read_text(encoding="utf-8"))
    conn.commit()

    class FalsoDb:
        @staticmethod
        def get_db():
            return conn

    monkeypatch.setattr(repositorio, "_db", lambda: FalsoDb)
    monkeypatch.setattr(cadastro, "_db", lambda: FalsoDb)
    yield conn
    conn.close()


def test_fluxo_da_entrada_no_banco(banco):
    with banco.cursor() as c:
        c.execute("INSERT INTO tbl_contato_cliente (nome_completo, email) VALUES ('Executivo Teste', 'exec@x.exemplo') RETURNING id_contato_cliente")
        exec_id = c.fetchone()["id_contato_cliente"]
        c.execute("INSERT INTO tbl_cliente (cnpj, razao_social, nome_fantasia, vendas_central_comm) VALUES ('11.222.333/0001-81', 'CLIENTE EXEMPLO S.A.', 'CLIENTE EXEMPLO', %s) RETURNING id_cliente", (exec_id,))
        cliente_id = c.fetchone()["id_cliente"]
        c.execute("INSERT INTO cadu_pi (codigo_pi_cc, titulo_pi) VALUES ('086761', 'PI antigo')")
    banco.commit()

    entrada = repositorio.criar_entrada("centralx", id_usuario=exec_id)
    repositorio.registrar_arquivo(entrada, "pi.pdf", "a" * 64, 1234, "/tmp/x.pdf", 2)
    assert repositorio.entrada_por_sha("a" * 64)["id"] == entrada
    assert repositorio.obter(entrada)["status"] == "recebido"

    pi = esquema.normalizar_extracao(resposta_modelo())
    ctx = cadastro.contexto(pi)
    assert ctx["cliente_id"] == cliente_id and ctx["executivo_id"] == exec_id
    assert ctx["pi_existente"]["id_pi"] and ctx["pi_existente"]["codigo"] == "086761"        # 86761 acha 086761 (zeros à esquerda)
    repositorio.salvar_leitura(entrada, pi=pi, bruto={"x": 1}, metodo="texto", modelo="m", prompt_versao="v", tokens_entrada=10,
                               tokens_saida=5, resumo={"erro": 0, "oportunidades": 2}, ids=ctx)
    linha = repositorio.obter(entrada)
    assert linha["status"] == "lido" and linha["numero_pi"] == "86761" and linha["id_cliente_detectado"] == cliente_id
    assert linha["json_revisado"]["totais"]["bruto"] == "10000.00" and linha["conferencias"]["oportunidades"] == 2
    assert repositorio.entrada_por_sha("a" * 64)["id"] == entrada
    fila = repositorio.listar(id_executivo=exec_id)
    assert fila[0]["cliente_nome"] == "CLIENTE EXEMPLO" and fila[0]["nome_original"] == "pi.pdf"

    repositorio.registrar_ajuste(entrada, campo="totais.bruto", tipo="ajuste", valor_lido="10000.00", valor_final="9000.00",
                                 motivo="erro_do_pi", justificativa="primeira", id_usuario=exec_id)
    repositorio.registrar_ajuste(entrada, campo="totais.bruto", tipo="ajuste", valor_lido="10000.00", valor_final="9500.00",
                                 motivo="combinado_com_cliente", justificativa="segunda", id_usuario=exec_id)
    ajuste = repositorio.ajustes(entrada)
    assert len(ajuste) == 1 and ajuste[0]["justificativa"] == "segunda"                          # só o último de cada campo

    repositorio.aprovar(entrada, exec_id, {"campos": {"titulo_pi": "X"}})
    final = repositorio.obter(entrada)
    assert final["status"] == "rascunho" and final["rascunho"]["campos"]["titulo_pi"] == "X" and final["aprovado_em"]
    repositorio.mudar_status(entrada, "erro", "falhou")
    assert repositorio.entrada_por_sha("a" * 64) is None                                         # erro libera reenvio do mesmo arquivo
    with pytest.raises(ValueError):
        repositorio.mudar_status(entrada, "inventado")


def test_cotacoes_do_cliente_e_linhas(banco):
    with banco.cursor() as c:
        c.execute("INSERT INTO tbl_cliente (cnpj, razao_social) VALUES ('11.222.333/0001-81', 'C') RETURNING id_cliente")
        cid = c.fetchone()["id_cliente"]
        c.execute("""INSERT INTO cadu_cotacoes (numero_cotacao, nome_campanha, periodo_inicio, periodo_fim, status, valor_total_proposta, client_id)
                     VALUES ('COT-1', 'Campanha A', '2026-11-01', '2026-11-30', 'Aprovada', 10000, %s) RETURNING id""", (cid,))
        cot = c.fetchone()["id"]
        c.execute("INSERT INTO cadu_cotacoes (nome_campanha, client_id, deleted_at) VALUES ('Apagada', %s, NOW())", (cid,))
        c.execute("""INSERT INTO cadu_cotacao_linhas (cotacao_id, plataforma, objetivo_kpi, volume_contratado, valor_unitario_negociado, investimento_bruto, ordem)
                     VALUES (%s, 'Amazon DSP', 'CPM', 163425, 61.1875, 10000, 1), (%s, 'x', 'CPM', 1, 1, 1, 2)""", (cot, cot))
        c.execute("UPDATE cadu_cotacao_linhas SET is_deleted = TRUE WHERE plataforma = 'x'")
    banco.commit()
    lista = cadastro.cotacoes_do_cliente(cid)
    assert [x["nome_campanha"] for x in lista] == ["Campanha A"]                                 # a apagada não aparece
    completa = cadastro.cotacao_completa(cot)
    assert completa["numero_cotacao"] == "COT-1" and len(completa["linhas"]) == 1 and completa["linhas"][0]["plataforma"] == "Amazon DSP"
    assert cadastro.cotacao_completa(99999) is None


def test_entrada_do_hub_so_chega_a_fila_da_equipe_depois_de_enviada(banco):
    with banco.cursor() as c:
        c.execute("INSERT INTO tbl_contato_cliente (nome_completo, email) VALUES ('Executivo da conta', 'e@x.exemplo') RETURNING id_contato_cliente")
        dono = c.fetchone()["id_contato_cliente"]
        c.execute("INSERT INTO tbl_contato_cliente (nome_completo, email) VALUES ('Outro executivo', 'o@x.exemplo') RETURNING id_contato_cliente")
        outro = c.fetchone()["id_contato_cliente"]
        c.execute("INSERT INTO tbl_cliente (cnpj, razao_social, nome_fantasia, vendas_central_comm) VALUES ('11.222.333/0001-81', 'CLIENTE EXEMPLO S.A.', 'CLIENTE EXEMPLO', %s) RETURNING id_cliente", (outro,))
        cliente_pi = c.fetchone()["id_cliente"]
    banco.commit()
    entrada = repositorio.criar_entrada("hub", id_cliente_envio=500, id_contato_envio=9, id_executivo=dono)
    repositorio.registrar_arquivo(entrada, "pi.pdf", "d" * 64, 10, "/tmp/z.pdf")
    assert repositorio.listar() == []                                                        # rascunho do cliente não aparece para a equipe
    assert repositorio.marcar_enviado(entrada, "oi") is False                                # ainda não foi lido
    pi = esquema.normalizar_extracao(resposta_modelo())
    ctx = {"cliente_id": cliente_pi, "agencia_id": None, "executivo_id": outro}              # o PI é de um cliente com OUTRO executivo
    repositorio.salvar_leitura(entrada, pi=pi, bruto={}, metodo="texto", modelo="m", prompt_versao="v", tokens_entrada=1, tokens_saida=1, resumo={}, ids=ctx)
    assert repositorio.obter(entrada)["id_executivo"] == dono                                # no hub vale o executivo de quem enviou
    assert repositorio.listar() == []
    assert repositorio.marcar_enviado(entrada, "  Recado  ") is True and repositorio.marcar_enviado(entrada, "de novo") is False
    visto = repositorio.obter(entrada)
    assert visto["mensagem_cliente"] == "Recado" and visto["enviado_em"] is not None
    fila = repositorio.listar()
    assert [f["id"] for f in fila] == [entrada] and fila[0]["origem"] == "hub"
    assert repositorio.contar_envios_recentes(500, 60) == 1 and repositorio.contar_envios_recentes(501, 60) == 0
    assert [e["status"] for e in repositorio.enviadas_pelo_cliente(500)] == ["lido"]
    assert repositorio.obter_por_uuid(visto["uuid"])["id"] == entrada and repositorio.obter_por_uuid("00000000-0000-0000-0000-000000000000") is None
    # pelo CentralX o executivo continua sendo o do cliente do PI
    interna = repositorio.criar_entrada("centralx", id_usuario=dono, id_executivo=dono)
    repositorio.salvar_leitura(interna, pi=pi, bruto={}, metodo="texto", modelo="m", prompt_versao="v", tokens_entrada=1, tokens_saida=1, resumo={}, ids=ctx)
    assert repositorio.obter(interna)["id_executivo"] == outro
    assert cadastro.executivo_da_conta(cliente_pi) == outro and cadastro.contato_por_id(dono)["nome_completo"] == "Executivo da conta"


def test_pre_pis_visiveis_ao_cliente_e_a_agencia(banco):
    """Pré-PI no hub: os que a conta enviou e os do CentralX atribuídos a ela (cliente ou agência), sem os que deram erro."""
    pi = esquema.normalizar_extracao(resposta_modelo())

    def lido(origem, **kw):
        i = repositorio.criar_entrada(origem, **kw)
        repositorio.salvar_leitura(i, pi=pi, bruto={}, metodo="texto", modelo="m", prompt_versao="v", tokens_entrada=1, tokens_saida=1, resumo={},
                                   ids={"cliente_id": kw.pop("detectado", None), "agencia_id": None, "executivo_id": None})
        return i

    def atribuir(i, cliente=None, agencia=None):
        with banco.cursor() as c:
            c.execute("UPDATE pi_entrada SET id_cliente_detectado = %s, id_agencia_detectada = %s WHERE id = %s", (cliente, agencia, i))
        banco.commit()
    meu = lido("hub", id_cliente_envio=500)                                   # enviado por esta conta (ainda sem enviar ao executivo)
    de_outro = lido("hub", id_cliente_envio=501)
    da_equipe_cliente = lido("centralx"); atribuir(da_equipe_cliente, cliente=500)
    da_equipe_agencia = lido("centralx"); atribuir(da_equipe_agencia, cliente=77, agencia=500)
    da_equipe_outro = lido("centralx"); atribuir(da_equipe_outro, cliente=77, agencia=78)
    lendo = repositorio.criar_entrada("centralx"); atribuir(lendo, cliente=500)               # equipe ainda lendo: não aparece
    com_erro = lido("hub", id_cliente_envio=500)
    repositorio.mudar_status(com_erro, "erro", "falhou")
    ids = lambda r: sorted(repositorio.obter_por_uuid(x["uuid"])["id"] for x in r)                  # noqa: E731
    assert ids(repositorio.pre_pis_do_cliente(500)) == sorted([meu, da_equipe_cliente, da_equipe_agencia])
    assert ids(repositorio.pre_pis_do_cliente(501)) == [de_outro]
    assert ids(repositorio.pre_pis_do_cliente(999)) == []
