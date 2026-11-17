"""Acesso ao banco das tabelas ``pi_entrada*`` (novas, só desta tela). Nada aqui toca ``cadu_pi``."""

from __future__ import annotations

import json
import uuid

STATUS = ("recebido", "lendo", "lido", "aprovado", "rascunho", "erro")


def _db():
    from .. import db
    return db


def _json(valor):
    return json.dumps(valor, ensure_ascii=False, default=str) if valor is not None else None


def _executar(sql, params=(), *, uma=False, nenhuma=False, commit=False):
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            resultado = None
            if not nenhuma:
                resultado = cursor.fetchone() if uma else cursor.fetchall()
        if commit:
            conn.commit()
        return resultado
    except Exception:
        conn.rollback()
        raise


def _linha(row):
    return dict(row) if row else None


def criar_entrada(origem="centralx", *, id_usuario=None, id_cliente_envio=None, id_contato_envio=None, id_executivo=None) -> int:
    row = _executar(
        """INSERT INTO pi_entrada (uuid, origem, status, id_usuario_criou, id_cliente_envio, id_contato_envio, id_executivo)
           VALUES (%s, %s, 'recebido', %s, %s, %s, %s) RETURNING id""",
        (str(uuid.uuid4()), origem, id_usuario, id_cliente_envio, id_contato_envio, id_executivo), uma=True, commit=True)
    return int(row["id"])


def registrar_arquivo(id_entrada, nome_original, sha256, tamanho, caminho, paginas=None) -> None:
    _executar("""INSERT INTO pi_entrada_arquivo (id_entrada, nome_original, sha256, tamanho_bytes, caminho, paginas)
                 VALUES (%s, %s, %s, %s, %s, %s)""",
              (id_entrada, nome_original[:255], sha256, tamanho, caminho, paginas), nenhuma=True, commit=True)


def entrada_por_sha(sha256):
    """Entrada anterior com o mesmo arquivo (que não terminou em erro): evita ler e cobrar duas vezes o mesmo PDF."""
    return _linha(_executar(
        """SELECT e.id, e.status, e.numero_pi FROM pi_entrada e JOIN pi_entrada_arquivo a ON a.id_entrada = e.id
            WHERE a.sha256 = %s AND e.status <> 'erro' ORDER BY e.id DESC LIMIT 1""", (sha256,), uma=True))


def obter(id_entrada):
    return _linha(_executar("SELECT * FROM pi_entrada WHERE id = %s", (id_entrada,), uma=True))


def arquivo_da_entrada(id_entrada):
    return _linha(_executar("SELECT * FROM pi_entrada_arquivo WHERE id_entrada = %s ORDER BY id LIMIT 1", (id_entrada,), uma=True))


def listar(limite=100, *, status=None, id_executivo=None):
    condicoes, params = ["NOT (e.origem = 'hub' AND e.enviado_em IS NULL)"], []     # rascunho do cliente não entra na fila da equipe
    if status:
        condicoes.append("e.status = %s")
        params.append(status)
    if id_executivo:
        condicoes.append("(e.id_executivo = %s OR e.id_usuario_criou = %s)")
        params += [id_executivo, id_executivo]
    where = ("WHERE " + " AND ".join(condicoes)) if condicoes else ""
    rows = _executar(
        f"""SELECT e.id, e.origem, e.status, e.numero_pi, e.titulo, e.confianca, e.erro, e.criado_em, e.id_executivo,
                   e.id_cliente_detectado, e.cotacao_id, e.conferencias, e.enviado_em,
                   a.nome_original, cli.nome_fantasia AS cliente_nome, ex.nome_completo AS executivo_nome
              FROM pi_entrada e
              LEFT JOIN LATERAL (SELECT nome_original FROM pi_entrada_arquivo WHERE id_entrada = e.id ORDER BY id LIMIT 1) a ON TRUE
              LEFT JOIN tbl_cliente cli ON cli.id_cliente = e.id_cliente_detectado
              LEFT JOIN tbl_contato_cliente ex ON ex.id_contato_cliente = e.id_executivo
              {where} ORDER BY e.id DESC LIMIT %s""", (*params, int(limite)))
    return [dict(r) for r in rows]


def mudar_status(id_entrada, status, erro=None) -> None:
    if status not in STATUS:
        raise ValueError(f"Status inválido: {status}")
    _executar("UPDATE pi_entrada SET status = %s, erro = %s, atualizado_em = NOW() WHERE id = %s",
              (status, erro, id_entrada), nenhuma=True, commit=True)


def salvar_leitura(id_entrada, *, pi, bruto, metodo, modelo, prompt_versao, tokens_entrada, tokens_saida, resumo, ids) -> None:
    _executar(
        """UPDATE pi_entrada SET status = 'lido', erro = NULL, lido_em = NOW(), atualizado_em = NOW(),
                  numero_pi = %s, titulo = %s, modelo = %s, prompt_versao = %s, metodo_leitura = %s,
                  tokens_entrada = %s, tokens_saida = %s, confianca = %s,
                  json_extraido = %s::jsonb, json_revisado = %s::jsonb, conferencias = %s::jsonb,
                  id_cliente_detectado = %s, id_agencia_detectada = %s,
                  id_executivo = CASE WHEN origem = 'hub' THEN COALESCE(id_executivo, %s) ELSE COALESCE(%s, id_executivo) END
            WHERE id = %s""",
        (pi.get("numero_pi") or None, (pi.get("campanha") or (pi.get("cliente") or {}).get("nome") or "")[:200] or None,
         modelo, prompt_versao, metodo, tokens_entrada, tokens_saida, pi.get("confianca_geral"),
         _json({"pi": pi, "bruto": bruto}), _json(pi), _json(resumo),
         ids.get("cliente_id"), ids.get("agencia_id"), ids.get("executivo_id"), ids.get("executivo_id"), id_entrada), nenhuma=True, commit=True)


def salvar_revisado(id_entrada, pi_revisado) -> None:
    _executar("UPDATE pi_entrada SET json_revisado = %s::jsonb, atualizado_em = NOW() WHERE id = %s",
              (_json(pi_revisado), id_entrada), nenhuma=True, commit=True)


def definir_cotacao(id_entrada, cotacao_id) -> None:
    _executar("UPDATE pi_entrada SET cotacao_id = %s, atualizado_em = NOW() WHERE id = %s",
              (cotacao_id, id_entrada), nenhuma=True, commit=True)


def registrar_ajuste(id_entrada, *, campo, tipo, valor_lido, valor_final, motivo, justificativa, id_usuario) -> None:
    _executar(
        """INSERT INTO pi_entrada_ajuste (id_entrada, campo, tipo, valor_lido, valor_final, motivo, justificativa, id_usuario)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (id_entrada, campo[:80], tipo, valor_lido, valor_final, motivo[:40], justificativa, id_usuario), nenhuma=True, commit=True)


def ajustes(id_entrada):
    """Último registro de cada campo (o executivo pode ter ajustado o mesmo campo mais de uma vez)."""
    rows = _executar(
        """SELECT DISTINCT ON (campo) campo, tipo, valor_lido, valor_final, motivo, justificativa, id_usuario, criado_em
             FROM pi_entrada_ajuste WHERE id_entrada = %s ORDER BY campo, id DESC""", (id_entrada,))
    return [dict(r) for r in rows]


def aprovar(id_entrada, id_usuario, rascunho) -> None:
    _executar(
        """UPDATE pi_entrada SET status = 'rascunho', rascunho = %s::jsonb, aprovado_em = NOW(), id_usuario_aprovou = %s,
                  atualizado_em = NOW() WHERE id = %s""", (_json(rascunho), id_usuario, id_entrada), nenhuma=True, commit=True)


def registrar_log(id_entrada, etapa, duracao_ms=None, detalhe=None) -> None:
    try:
        _executar("INSERT INTO pi_entrada_log (id_entrada, etapa, duracao_ms, detalhe) VALUES (%s, %s, %s, %s)",
                  (id_entrada, etapa[:40], duracao_ms, (detalhe or "")[:2000]), nenhuma=True, commit=True)
    except Exception:                                                       # log nunca derruba a leitura
        pass


# ---------- hub do cliente ----------

def obter_por_uuid(uuid_entrada):
    return _linha(_executar("SELECT * FROM pi_entrada WHERE uuid = %s", (str(uuid_entrada),), uma=True))


def enviadas_pelo_cliente(id_cliente, limite=10):
    rows = _executar(
        """SELECT e.uuid, e.status, e.numero_pi, e.titulo, e.criado_em, e.enviado_em, e.erro,
                  (SELECT nome_original FROM pi_entrada_arquivo WHERE id_entrada = e.id ORDER BY id LIMIT 1) AS nome_original
             FROM pi_entrada e WHERE e.origem = 'hub' AND e.id_cliente_envio = %s ORDER BY e.id DESC LIMIT %s""", (id_cliente, int(limite)))
    return [dict(r) for r in rows]


def pre_pis_do_cliente(id_cliente, limite=30):
    """Pré-PIs (Entrada de PI) que o cliente ou a agência pode ver no hub: os que a própria conta enviou e os que a equipe
    cadastrou no CentralX e atribuiu a ela (cliente ou agência detectados no PDF). Os da equipe só aparecem depois da leitura."""
    rows = _executar(
        """SELECT e.uuid, e.origem, e.status, e.numero_pi, e.titulo, e.criado_em, e.enviado_em, e.json_revisado
             FROM pi_entrada e
            WHERE e.status <> 'erro'
              AND ((e.origem = 'hub' AND e.id_cliente_envio = %s)
                   OR (e.origem <> 'hub' AND e.status IN ('lido', 'aprovado', 'rascunho')
                       AND (e.id_cliente_detectado = %s OR e.id_agencia_detectada = %s)))
            ORDER BY e.id DESC LIMIT %s""", (id_cliente, id_cliente, id_cliente, int(limite)))
    return [dict(r) for r in rows]


def contar_envios_recentes(id_cliente, minutos=60) -> int:
    row = _executar("""SELECT COUNT(*) AS n FROM pi_entrada WHERE origem = 'hub' AND id_cliente_envio = %s
                          AND criado_em > NOW() - (%s || ' minutes')::interval""", (id_cliente, str(int(minutos))), uma=True)
    return int(row["n"])


def marcar_enviado(id_entrada, mensagem=None) -> bool:
    """Cliente confirmou o envio ao executivo. Só vale uma vez e só para entrada já lida."""
    row = _executar(
        """UPDATE pi_entrada SET enviado_em = NOW(), mensagem_cliente = %s, atualizado_em = NOW()
            WHERE id = %s AND origem = 'hub' AND status = 'lido' AND enviado_em IS NULL RETURNING id""",
        ((mensagem or "").strip()[:1000] or None, id_entrada), uma=True, commit=True)
    return bool(row)
