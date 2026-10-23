"""Leads v3: mesa de operações de prospecção (React) em ``/leads-v3``.

A tela reaproveita as rotas ``/api/leads/*`` do Leads v2 para detalhe, contatos,
atividades e comunicações. Aqui ficam só a página, a lista da fila e as ações em massa.
Plano em docs/leads-v3-plano.md.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, current_app, jsonify, render_template, request, session, url_for

from . import db
from . import leads_v3_cadencias as cadencias
from . import leads_v3_clientes as clientes
from . import leads_v3_email as email_mail
from . import leads_v3_mensagens as mensagens
from . import leads_v3_prospeccao as prospeccao
from .auth import centralcomm_required, centralcomm_required_api
from .services.integration_credentials import resolve_apollo_api_key, resolve_firecrawl_api_key

bp = Blueprint("leads_v3", __name__, url_prefix="/leads-v3")

# Etapas ativas do funil, na ordem da tela (as mesmas do kanban do Leads v2).
STATUS_ATIVOS = (
    ("inbox", "Inbox"),
    ("tentativa_contato", "Tentativa de contato"),
    ("reuniao_agendada", "Reunião agendada"),
    ("nutricao", "Nutrição"),
)
POTENCIAIS = (("alto", "Alto"), ("medio", "Médio"), ("baixo", "Baixo"))
MOTIVOS_DESQUALIFICACAO = (
    ("contato_errado", "Contato errado"),
    ("fora_perfil", "Fora do perfil"),
    ("sem_orcamento", "Sem orçamento"),
    ("duplicado", "Duplicado"),
    ("spam", "Spam / teste"),
    ("outro", "Outro"),
)
MAX_LOTE = 500
# Mesmos valores dos CHECKs da migração add_cadu_leads_v3_prospeccao.sql.
PAPEIS = (("marketing", "Marketing"), ("midia", "Mídia"), ("criacao", "Criação"), ("diretoria", "Diretoria"),
          ("compras", "Compras"), ("comercial", "Comercial"), ("outro", "Outro"))
SENIORIDADES = (("c_level", "C-level / VP"), ("diretor", "Diretor(a) / Head"), ("gerente", "Gerente"),
                ("coordenador", "Coordenador(a)"), ("analista", "Analista"), ("outro", "Outro"))
INFLUENCIAS = (("decisor", "Decisor"), ("influenciador", "Influenciador"), ("usuario", "Usuário"),
               ("bloqueador", "Bloqueador"))
CANAIS_FOCO = ("email", "whatsapp", "linkedin", "telefone", "evento")
STATUS_GOLDEN = ("planejada", "em_contato", "reuniao", "proposta", "ganha", "pausada", "perdida")
# SQLSTATE de tabela/coluna inexistente: a migração do Leads v3 ainda não rodou neste banco.
_SQLSTATE_SEM_ESQUEMA = {"42P01", "42703"}


def _ok(data, status=200):
    return jsonify({"success": True, "data": data}), status


def _erro(mensagem, status=400):
    return jsonify({"success": False, "error": mensagem}), status


def _json_safe(valor):
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%dT%H:%M")
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def _executivos():
    try:
        rows = db.obter_vendedores_centralcomm(incluir_usuario_comercial=True) or []
    except Exception as exc:  # a tela abre mesmo sem a lista de executivos
        current_app.logger.warning("leads-v3: executivos indisponíveis: %s", exc)
        return []
    return [{"id": r["id_contato_cliente"], "nome": r["nome_completo"]} for r in rows]


@bp.route("")
@bp.route("/")
@centralcomm_required
def pagina():
    executivos = _executivos()
    user_id = session.get("user_id")
    eh_executivo = any(e["id"] == user_id for e in executivos)
    boot = {
        "apiRoot": "/leads-v3/api",
        "legacyApiRoot": "/api/leads",
        "user": {"id": user_id, "nome": session.get("user_name") or ""},
        "executivos": executivos,
        "filtroExecutivoInicial": str(user_id) if eh_executivo else "sem",
        "status": [{"value": v, "label": l} for v, l in STATUS_ATIVOS],
        "potenciais": [{"value": v, "label": l} for v, l in POTENCIAIS],
        "motivos": [{"value": v, "label": l} for v, l in MOTIVOS_DESQUALIFICACAO],
        "papeis": [{"value": v, "label": l} for v, l in PAPEIS],
        "senioridades": [{"value": v, "label": l} for v, l in SENIORIDADES],
        "influencias": [{"value": v, "label": l} for v, l in INFLUENCIAS],
        "trimestre": prospeccao.trimestre_atual(),
        "fontes": {"apollo": bool(resolve_apollo_api_key()), "web": bool(resolve_firecrawl_api_key())},
        "conversao": _listas_conversao(),
    }
    return render_template("leads_v3.html", boot=boot)


def _listas_conversao():
    """Listas do formulário de conversão em cliente (mesmas do Leads v2)."""
    def seguro(fn):
        try:
            return fn() or []
        except Exception as exc:
            current_app.logger.warning("leads-v3: lista de conversão indisponível: %s", exc)
            return []
    return {
        "tipos": [{"id": t["id_tipo_cliente"], "nome": t.get("display")} for t in seguro(db.obter_tipos_cliente)],
        "agencias": [{"id": a["id_agencia"], "nome": a.get("display")} for a in seguro(db.obter_aux_agencia)],
        "estados": [{"id": e["id_estado"], "sigla": e.get("sigla")} for e in seguro(db.obter_estados)],
    }


@bp.route("/api/leads")
@centralcomm_required_api
def api_listar():
    """Fila: leads ativos. ``executivo`` = id, ``sem`` (sem responsável) ou vazio (todos)."""
    executivo = (request.args.get("executivo") or "").strip()
    filtros = {
        "potencial": request.args.get("potencial") or None,
        "status": request.args.get("status") or None,
        "search": (request.args.get("q") or "").strip() or None,
        "fonte": request.args.get("fonte") or None,
    }
    if executivo == "sem":
        filtros["sem_responsavel"] = True
    elif executivo.isdigit():
        filtros["id_executivo"] = int(executivo)
    try:
        rows = db.obter_leads_dashboard(**filtros)
    except Exception as exc:
        current_app.logger.error("leads-v3 listar: %s", exc)
        return _erro("Não foi possível carregar os leads.", 500)
    leads = [{k: _json_safe(v) for k, v in dict(r).items()} for r in rows]
    golden = _golden_por_lead([l["id"] for l in leads])
    for lead in leads:
        lead["golden"] = golden.get(lead["id"])
    origem = request.args.get("origem")
    if origem == "site":
        leads = [l for l in leads if l.get("fonte") == "site"]
    elif origem == "adicionados":
        leads = [l for l in leads if l.get("fonte") != "site"]
    # Golden Circle tem aba própria: a Fila mostra só os demais e informa quantos ficaram de fora.
    golden_separados = sum(1 for l in leads if l["golden"])
    if request.args.get("golden") != "incluir":
        leads = [l for l in leads if not l["golden"]]
    return _ok({"leads": leads, "total": len(leads), "golden_separados": golden_separados})


def _golden_por_lead(ids):
    """{id_lead: {id, status, proximo_marco}} das contas do trimestre; vazio se a migração não rodou."""
    if not ids:
        return {}
    conn = None
    try:  # o selo é extra: qualquer falha aqui não pode derrubar a fila
        conn = db.get_db()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT DISTINCT ON (id_lead) id_lead, id, status FROM cadu_golden_circle WHERE id_lead = ANY(%s) AND trimestre = %s ORDER BY id_lead, id",
                [ids, prospeccao.trimestre_atual()],
            )
            rows = cursor.fetchall()
        conn.rollback()
    except Exception:
        if conn is not None:
            conn.rollback()
        return {}
    return {r["id_lead"]: {"id": r["id"], "status": r["status"]} for r in rows}


def _ids_do_lote(payload):
    bruto = payload.get("ids")
    if not isinstance(bruto, list) or not bruto:
        raise ValueError("Selecione ao menos um lead.")
    ids = sorted({int(i) for i in bruto if str(i).isdigit()})
    if not ids:
        raise ValueError("Selecione ao menos um lead.")
    if len(ids) > MAX_LOTE:
        raise ValueError(f"No máximo {MAX_LOTE} leads por vez.")
    return ids


def _sql_do_lote(acao, payload):
    """Devolve (SET, parâmetros, condição de mudança, descrição da atividade ou None)."""
    if acao == "status":
        valor = payload.get("valor")
        if valor not in dict(STATUS_ATIVOS):
            raise ValueError("Etapa inválida.")
        label = dict(STATUS_ATIVOS)[valor]
        return "status = %s", [valor], ("l.status IS DISTINCT FROM %s", [valor]), f"Status alterado para {label} (em massa)"
    if acao == "desqualificar":
        motivo = (payload.get("motivo") or "").strip()
        if not motivo:
            raise ValueError("Informe o motivo da desqualificação.")
        motivo = motivo[:100]
        return (
            "status = 'nao_qualificado', motivo_desqualificacao = %s",
            [motivo],
            ("l.status IS DISTINCT FROM 'nao_qualificado'", []),
            f"Lead desqualificado: {motivo} (em massa)",
        )
    if acao == "potencial":
        valor = payload.get("valor")
        if valor not in dict(POTENCIAIS):
            raise ValueError("Potencial inválido.")
        return "potencial = %s", [valor], ("l.potencial IS DISTINCT FROM %s", [valor]), None
    if acao == "responsavel":
        valor = payload.get("valor")
        if valor in (None, "", 0, "0", "sem"):
            return "id_executivo = NULL", [], ("l.id_executivo IS NOT NULL", []), None
        if not str(valor).isdigit():
            raise ValueError("Responsável inválido.")
        exec_id = int(valor)
        return "id_executivo = %s", [exec_id], ("l.id_executivo IS DISTINCT FROM %s", [exec_id]), None
    raise ValueError("Ação desconhecida.")


@bp.route("/api/leads/lote", methods=["POST"])
@centralcomm_required_api
def api_lote():
    """Ação em massa numa única transação: status, desqualificar, potencial ou responsável."""
    payload = request.get_json(silent=True) or {}
    try:
        ids = _ids_do_lote(payload)
        set_sql, set_params, (cond_sql, cond_params), descricao = _sql_do_lote(payload.get("acao"), payload)
    except ValueError as exc:
        return _erro(str(exc))

    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE cadu_leads l
                   SET {set_sql}, updated_at = CURRENT_TIMESTAMP
                 WHERE l.id = ANY(%s) AND {cond_sql}
             RETURNING l.id
                """,
                [*set_params, ids, *cond_params],
            )
            alterados = [row["id"] for row in cursor.fetchall()]
            if descricao and alterados:
                cursor.execute(
                    """
                    INSERT INTO cadu_lead_atividades (id_lead, tipo, descricao, id_usuario, usuario_nome)
                    SELECT unnest(%s::int[]), 'status_change', %s, %s, %s
                    """,
                    [alterados, descricao, session.get("user_id"), session.get("user_name")],
                )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        current_app.logger.error("leads-v3 lote %s: %s", payload.get("acao"), exc)
        return _erro("Não foi possível aplicar a ação aos leads selecionados.", 500)
    return _ok({"alterados": alterados, "ignorados": len(ids) - len(alterados)})


# ─────────────────────────────────────────────────────
# Golden Circle, descoberta de pessoas e perfil do contato
# ─────────────────────────────────────────────────────
def _sqlstate(exc):
    return getattr(exc, "sqlstate", None) or getattr(getattr(exc, "diag", None), "sqlstate", None)


def _transacao(fn, contexto):
    """Roda fn(cursor) numa transação e traduz os erros para respostas JSON."""
    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            resultado = fn(cursor)
        conn.commit()
        return resultado
    except prospeccao.ProspeccaoError as exc:
        conn.rollback()
        return _erro(str(exc), 400)
    except Exception as exc:
        conn.rollback()
        if _sqlstate(exc) in _SQLSTATE_SEM_ESQUEMA:
            return _erro("A migração do Leads v3 ainda não foi aplicada neste banco.", 503)
        current_app.logger.error("leads-v3 %s: %s", contexto, exc)
        return _erro("Não foi possível concluir a operação.", 500)


def _int(valor):
    return int(valor) if str(valor or "").strip().isdigit() else None


@bp.route("/api/golden")
@centralcomm_required_api
def api_golden_listar():
    trimestre = request.args.get("trimestre") or prospeccao.trimestre_atual()
    executivo = _int(request.args.get("executivo"))

    def run(cursor):
        cursor.execute(
            f"""
            SELECT gc.id, gc.id_executivo, gc.trimestre, gc.nome_conta, gc.id_lead, gc.id_cliente, gc.objetivo,
                   gc.status, gc.meta, gc.created_at, gc.proximo_marco, gc.valor_alvo, l.status AS lead_status, l.dominio, l.cnpj,
                   (SELECT COUNT(*) FROM cadu_lead_cadencia_inscricoes i
                     WHERE i.id_lead = gc.id_lead AND i.status = 'ativa') AS cadencias_ativas,
                   COUNT(c.id) AS pessoas,
                   COUNT(c.id) FILTER (WHERE c.papel = 'marketing') AS marketing,
                   COUNT(c.id) FILTER (WHERE c.papel = 'midia') AS midia,
                   COUNT(c.id) FILTER (WHERE c.papel = 'criacao') AS criacao,
                   COUNT(c.id) FILTER (WHERE c.papel = 'diretoria') AS diretoria,
                   COUNT(c.id) FILTER (WHERE COALESCE(c.email, '') <> '') AS com_email,
                   (SELECT COUNT(*) FROM cadu_lead_contato_candidatos k
                     WHERE k.id_lead = gc.id_lead AND k.status = 'pendente') AS candidatos,
                   (SELECT MAX(a.created_at) FROM cadu_lead_atividades a WHERE a.id_lead = gc.id_lead) AS ultima_atividade
              FROM cadu_golden_circle gc
              LEFT JOIN cadu_leads l ON l.id = gc.id_lead
              LEFT JOIN cadu_lead_contatos c ON c.id_lead = gc.id_lead
             WHERE gc.trimestre = %s {"AND gc.id_executivo = %s" if executivo else ""}
             GROUP BY gc.id, l.id
             ORDER BY gc.ordem, lower(gc.nome_conta)
            """,
            [trimestre, executivo] if executivo else [trimestre],
        )
        contas = [{k: _json_safe(v) for k, v in dict(r).items()} for r in cursor.fetchall()]
        return _ok({"trimestre": trimestre, "contas": contas})

    return _transacao(run, "golden listar")


def _contas_do_payload(payload):
    contas = payload.get("contas")
    if not isinstance(contas, list) or not contas:
        raise prospeccao.ProspeccaoError("Informe ao menos uma empresa.")
    if len(contas) > 40:
        raise prospeccao.ProspeccaoError("No máximo 40 empresas por vez.")
    return [{"nome": str(c.get("nome") or "").strip()[:255], "dominio": c.get("dominio"), "cnpj": c.get("cnpj")}
            for c in contas if isinstance(c, dict)]


@bp.route("/api/golden/validar", methods=["POST"])
@centralcomm_required_api
def api_golden_validar():
    """Só confere (não grava): CNPJ ativo, duplicidade, se já é lead ou cliente."""
    payload = request.get_json(silent=True) or {}
    trimestre = payload.get("trimestre") or prospeccao.trimestre_atual()
    executivo = _int(payload.get("id_executivo"))

    def run(cursor):
        contas = _contas_do_payload(payload)
        return _ok({"resultados": [
            prospeccao.validar_conta(cursor, id_executivo=executivo, trimestre=trimestre, **conta) for conta in contas
        ]})

    return _transacao(run, "golden validar")


@bp.route("/api/golden", methods=["POST"])
@centralcomm_required_api
def api_golden_criar():
    """Valida de novo no servidor e grava só as empresas sem bloqueio."""
    payload = request.get_json(silent=True) or {}
    trimestre = payload.get("trimestre") or prospeccao.trimestre_atual()
    executivo = _int(payload.get("id_executivo"))

    def run(cursor):
        criadas, recusadas = [], []
        for conta in _contas_do_payload(payload):
            validacao = prospeccao.validar_conta(cursor, id_executivo=executivo, trimestre=trimestre, **conta)
            if not validacao["ok"]:
                recusadas.append({"nome": conta["nome"], "bloqueios": validacao["bloqueios"]})
                continue
            gravada = prospeccao.criar_conta(cursor, validacao, id_executivo=executivo, trimestre=trimestre,
                                             usuario_id=session.get("user_id"))
            criadas.append({"nome": conta["nome"], **gravada, "avisos": validacao["avisos"]})
        return _ok({"criadas": criadas, "recusadas": recusadas}, 201 if criadas else 200)

    return _transacao(run, "golden criar")


@bp.route("/api/golden/<int:conta_id>", methods=["PATCH", "DELETE"])
@centralcomm_required_api
def api_golden_alterar(conta_id):
    payload = request.get_json(silent=True) or {}

    def run(cursor):
        if request.method == "DELETE":
            cursor.execute("DELETE FROM cadu_golden_circle WHERE id = %s RETURNING id", [conta_id])
        else:
            sets, params = _campos_alvo(payload)
            if not sets:
                raise prospeccao.ProspeccaoError("Nada para atualizar.")
            cursor.execute(f"UPDATE cadu_golden_circle SET {', '.join(sets)} WHERE id = %s RETURNING id", [*params, conta_id])
        if not cursor.fetchone():
            return _erro("Conta não encontrada.", 404)
        return _ok({"id": conta_id})

    return _transacao(run, "golden alterar")


def _lead_para_busca(cursor, lead_id):
    cursor.execute("SELECT id, empresa, nome, email, url_site, dominio FROM cadu_leads WHERE id = %s", [lead_id])
    lead = cursor.fetchone()
    if not lead:
        raise prospeccao.ProspeccaoError("Lead não encontrado.")
    dominio = lead["dominio"] or prospeccao.normalizar_dominio(lead["url_site"])
    if not dominio:
        email_dom = prospeccao.normalizar_dominio(lead["email"])
        dominio = email_dom if email_dom not in prospeccao.FREE_EMAIL_DOMAINS else ""
    return lead, dominio


_COLUNAS_CASAMENTO = "id, nome, email, linkedin_url, origem_dado, origem_ref, apollo_person_id, cargo, papel, senioridade"


def _contatos_do_lead(cursor, lead_id):
    cursor.execute(f"SELECT {_COLUNAS_CASAMENTO} FROM cadu_lead_contatos WHERE id_lead = %s ORDER BY id", [lead_id])
    return [dict(r) for r in cursor.fetchall()]


def _pessoa_do_candidato(cand):
    return {"nome": cand["nome"], "email": cand.get("email"), "linkedin_url": cand.get("linkedin_url"),
            "apollo_id": cand["provedor_ref"] if cand["provedor"] == "apollo" else None}


def _candidatos(cursor, lead_id):
    """Pendentes de revisão; quem já parece estar na base vem com `existente` (id e nome do contato)."""
    contatos = _contatos_do_lead(cursor, lead_id)
    cursor.execute(
        """
        SELECT id, provedor, provedor_ref, nome, cargo, papel_sugerido, senioridade_sugerida, email, linkedin_url,
               payload, status, created_at
          FROM cadu_lead_contato_candidatos
         WHERE id_lead = %s AND status = 'pendente'
         ORDER BY CASE senioridade_sugerida WHEN 'c_level' THEN 0 WHEN 'diretor' THEN 1 WHEN 'gerente' THEN 2
                  WHEN 'coordenador' THEN 3 ELSE 4 END, nome
        """,
        [lead_id],
    )
    lista = []
    for r in cursor.fetchall():
        item = {k: _json_safe(v) for k, v in dict(r).items()}
        existente = prospeccao.achar_existente(_pessoa_do_candidato(item), contatos)
        item["existente"] = {"id": existente["id"], "nome": existente["nome"]} if existente else None
        lista.append(item)
    return lista


@bp.route("/api/leads/<int:lead_id>/candidatos")
@centralcomm_required_api
def api_candidatos(lead_id):
    return _transacao(lambda cursor: _ok({"candidatos": _candidatos(cursor, lead_id)}), "candidatos")


@bp.route("/api/leads/<int:lead_id>/descobrir", methods=["POST"])
@centralcomm_required_api
def api_descobrir(lead_id):
    """Busca pessoas (Apollo grátis ou web) e guarda como candidatos para revisão."""
    fonte = (request.get_json(silent=True) or {}).get("fonte")
    if fonte not in ("apollo", "web"):
        return _erro("Fonte inválida.")

    conn = db.get_db()
    registro = []
    try:
        with conn.cursor() as cursor:
            lead, dominio = _lead_para_busca(cursor, lead_id)
        conn.rollback()  # só leitura; libera a conexão antes da chamada externa
        if fonte == "apollo":
            if not dominio:
                raise prospeccao.ProspeccaoError("Preencha o site ou domínio da empresa para buscar no Apollo.")
            encontrados, total = prospeccao.apollo_buscar_pessoas(resolve_apollo_api_key(), dominio, registro=registro)
        else:
            encontrados, total = prospeccao.web_buscar_pessoas(resolve_firecrawl_api_key(), lead["empresa"] or lead["nome"]), None
    except prospeccao.ProspeccaoError as exc:
        _gravar_chamadas_apollo(registro, lead_id=lead_id)
        return _erro(str(exc), 400)
    _gravar_chamadas_apollo(registro, lead_id=lead_id)

    def run(cursor):
        contatos = _contatos_do_lead(cursor, lead_id)
        inseridos = 0
        for c in encontrados:
            if not c.get("provedor_ref"):
                continue
            # Quem já está na base só volta como sugestão se o Apollo/web tiver algo a acrescentar.
            existente = prospeccao.achar_existente(_pessoa_do_candidato(c), contatos)
            if existente and existente["linkedin_url"] and (c["provedor"] != "apollo" or existente["apollo_person_id"]
                                                            or (existente["origem_dado"] == "apollo" and existente["origem_ref"])):
                continue
            cursor.execute(
                """
                INSERT INTO cadu_lead_contato_candidatos
                    (id_lead, provedor, provedor_ref, nome, cargo, papel_sugerido, senioridade_sugerida,
                     linkedin_url, payload, buscado_por)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id_lead, provedor, provedor_ref) WHERE provedor_ref IS NOT NULL DO NOTHING
                RETURNING id
                """,
                [lead_id, c["provedor"], c["provedor_ref"], c["nome"][:200], (c.get("cargo") or "")[:200] or None,
                 c["papel_sugerido"], c["senioridade_sugerida"], c.get("linkedin_url"),
                 db.Json(c.get("payload") or {}), session.get("user_id")],
            )
            inseridos += 1 if cursor.fetchone() else 0
        return _ok({"encontrados": len(encontrados), "novos": inseridos, "total_fonte": total,
                    "candidatos": _candidatos(cursor, lead_id)})

    return _transacao(run, f"descobrir {fonte}")


def _registrar_atividade(cursor, lead_id, tipo, descricao, id_contato=None):
    cursor.execute(
        """
        INSERT INTO cadu_lead_atividades (id_lead, tipo, descricao, id_contato, id_usuario, usuario_nome)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        [lead_id, tipo, descricao, id_contato, session.get("user_id"), session.get("user_name")],
    )


@bp.route("/api/candidatos/<int:candidato_id>/<acao>", methods=["POST"])
@centralcomm_required_api
def api_candidato_acao(candidato_id, acao):
    """aprovar (vira contato; com revelar=true, gasta crédito do Apollo), vincular (completa quem já está na base)
    ou descartar. Se a pessoa já existe no lead (antes ou depois de revelar), completa a ficha dela em vez de duplicar."""
    if acao not in ("aprovar", "vincular", "descartar"):
        return _erro("Ação inválida.", 404)
    payload = request.get_json(silent=True) or {}
    registro, gravar = [], {}

    def run(cursor):
        cursor.execute("SELECT * FROM cadu_lead_contato_candidatos WHERE id = %s FOR UPDATE", [candidato_id])
        cand = cursor.fetchone()
        if not cand:
            return _erro("Candidato não encontrado.", 404)
        if cand["status"] != "pendente":
            return _erro("Este candidato já foi revisado.", 409)
        if acao == "descartar":
            cursor.execute(
                "UPDATE cadu_lead_contato_candidatos SET status = 'descartado', revisado_por = %s, revisado_em = NOW() WHERE id = %s",
                [session.get("user_id"), candidato_id],
            )
            return _ok({"id": candidato_id})

        contatos = _contatos_do_lead(cursor, cand["id_lead"])
        existente = prospeccao.achar_existente(_pessoa_do_candidato(cand), contatos)
        if acao == "vincular" and not existente:
            return _erro("Não achei esta pessoa entre os contatos do lead.", 409)
        revelado = {}
        tem_email, tem_celular = prospeccao.flags_apollo(cand["payload"]) if cand["provedor"] == "apollo" else (None, None)
        if payload.get("revelar") and cand["provedor"] == "apollo" and tem_email is not False:
            gravar["lead_id"] = cand["id_lead"]
            revelado = prospeccao.apollo_revelar(resolve_apollo_api_key(), apollo_id=cand["provedor_ref"], registro=registro)
            if not existente:  # com nome completo, e-mail e LinkedIn dá para reconhecer quem o nome mascarado escondia
                existente = prospeccao.achar_existente(
                    {"nome": revelado.get("nome"), "email": revelado.get("email"), "linkedin_url": revelado.get("linkedin_url"),
                     "apollo_id": cand["provedor_ref"]}, contatos)
        papel = payload.get("papel") if payload.get("papel") in dict(PAPEIS) else cand["papel_sugerido"]
        apollo_id = cand["provedor_ref"] if cand["provedor"] == "apollo" else None
        nome_novo = revelado.get("nome") or cand["nome"]
        origem = "Apollo" if cand["provedor"] == "apollo" else "busca na web"

        if existente:
            # Completa só o que falta; o nome só muda se o da base estiver mascarado.
            cursor.execute(
                """
                UPDATE cadu_lead_contatos
                   SET nome = CASE WHEN nome LIKE '%%*%%' AND %(nome)s::text NOT LIKE '%%*%%' THEN %(nome)s::text ELSE nome END,
                       cargo = COALESCE(NULLIF(cargo, ''), %(cargo)s::text),
                       email_status = CASE WHEN NULLIF(email, '') IS NULL AND %(email)s::text IS NOT NULL THEN %(email_status)s::text ELSE email_status END,
                       email = COALESCE(NULLIF(email, ''), %(email)s::text),
                       linkedin_url = COALESCE(NULLIF(linkedin_url, ''), %(linkedin)s::text),
                       papel = COALESCE(papel, %(papel)s::text), senioridade = COALESCE(senioridade, %(senioridade)s::text),
                       apollo_person_id = COALESCE(apollo_person_id, %(apollo_id)s::text),
                       apollo_tem_email = COALESCE(%(tem_email)s::boolean, apollo_tem_email),
                       apollo_tem_celular = COALESCE(%(tem_celular)s::boolean, apollo_tem_celular),
                       enriquecido_em = CASE WHEN %(revelou)s::boolean THEN CURRENT_TIMESTAMP ELSE enriquecido_em END,
                       apollo_revelado_em = CASE WHEN %(revelou)s::boolean THEN CURRENT_TIMESTAMP ELSE apollo_revelado_em END,
                       updated_at = CURRENT_TIMESTAMP
                 WHERE id = %(id)s
                RETURNING email
                """,
                {"nome": nome_novo[:200], "cargo": (revelado.get("cargo") or cand["cargo"] or "")[:150] or None,
                 "email": revelado.get("email"), "email_status": revelado.get("email_status"),
                 "linkedin": revelado.get("linkedin_url") or cand["linkedin_url"], "papel": papel,
                 "senioridade": cand["senioridade_sugerida"], "apollo_id": apollo_id, "revelou": bool(revelado),
                 "tem_email": tem_email, "tem_celular": tem_celular, "id": existente["id"]},
            )
            email_final = cursor.fetchone()["email"]
            contato_id = existente["id"]
            _registrar_atividade(cursor, cand["id_lead"], "edicao",
                                 f"Dados do {origem} somados a {existente['nome']} (já estava na base).", contato_id)
        else:
            cursor.execute(
                """
                INSERT INTO cadu_lead_contatos
                    (id_lead, nome, cargo, email, papel, senioridade, linkedin_url, origem_dado, origem_ref,
                     apollo_person_id, email_status, enriquecido_em, apollo_revelado_em, apollo_tem_email, apollo_tem_celular,
                     adicionado_por)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [cand["id_lead"], nome_novo[:200], (revelado.get("cargo") or cand["cargo"] or "")[:150] or None,
                 revelado.get("email"), papel, cand["senioridade_sugerida"],
                 revelado.get("linkedin_url") or cand["linkedin_url"], cand["provedor"], cand["provedor_ref"], apollo_id,
                 revelado.get("email_status"), datetime.now() if revelado else None, datetime.now() if revelado else None,
                 tem_email, tem_celular, session.get("user_id")],
            )
            contato_id = cursor.fetchone()["id"]
            email_final = revelado.get("email")
            _registrar_atividade(cursor, cand["id_lead"], "contato_add", f"Contato adicionado via {origem}: {nome_novo}", contato_id)
        gravar["contato_id"] = contato_id
        cursor.execute(
            """
            UPDATE cadu_lead_contato_candidatos
               SET status = 'aprovado', id_contato = %s, email = %s, revisado_por = %s, revisado_em = NOW()
             WHERE id = %s
            """,
            [contato_id, revelado.get("email"), session.get("user_id"), candidato_id],
        )
        return _ok({"id_contato": contato_id, "email": email_final, "revelado": bool(revelado),
                    "mesclado_com": existente["nome"] if existente else None}, 201)

    resposta = _transacao(run, f"candidato {acao}")
    _gravar_chamadas_apollo(registro, **gravar)  # o id do contato só vale se a transação gravou; senão fica só o lead
    return resposta


def _motivo_sem_email_apollo(contato):
    """Por que consultar o Apollo de novo provavelmente gasta crédito sem trazer e-mail (None = pode consultar)."""
    if contato.get("email") and contato.get("email_status") != "arriscado":
        return None
    if contato.get("apollo_revelado_em") and not contato.get("email"):
        return "O Apollo já foi consultado e não tinha e-mail desta pessoa. Consultar de novo usa outro crédito."
    if contato.get("apollo_tem_email") is False:
        return "Na busca, o Apollo disse que não tem e-mail desta pessoa. Consultar mesmo assim usa 1 crédito."
    return None


@bp.route("/api/contatos/<int:contato_id>/revelar", methods=["POST"])
@centralcomm_required_api
def api_contato_revelar(contato_id):
    """Busca e-mail e LinkedIn do contato no Apollo (consome crédito do plano).

    O Apollo cobra 1 crédito pelos dados do perfil mesmo sem e-mail. Se a busca grátis já disse que não há e-mail,
    ou se uma consulta anterior voltou sem e-mail, só consulta com `forcar` (a tela pede confirmação)."""
    forcar = bool((request.get_json(silent=True) or {}).get("forcar"))
    registro = []

    def run(cursor):
        cursor.execute(
            """
            SELECT c.*, l.dominio, l.url_site FROM cadu_lead_contatos c JOIN cadu_leads l ON l.id = c.id_lead
             WHERE c.id = %s FOR UPDATE OF c
            """,
            [contato_id],
        )
        contato = cursor.fetchone()
        if not contato:
            return _erro("Contato não encontrado.", 404)
        motivo = _motivo_sem_email_apollo(contato)
        if motivo and not forcar:
            return _ok({"email": None, "encontrou_email": False, "bloqueado": True, "motivo": motivo})
        dominio = contato["dominio"] or prospeccao.normalizar_dominio(contato["url_site"])
        revelado = prospeccao.apollo_revelar(
            resolve_apollo_api_key(), registro=registro,
            apollo_id=contato["apollo_person_id"] or (contato["origem_ref"] if contato["origem_dado"] == "apollo" else None),
            linkedin_url=contato["linkedin_url"], nome=contato["nome"], dominio=dominio,
        )
        nome = revelado.get("nome") if revelado.get("nome") and "*" in (contato["nome"] or "") else contato["nome"]
        cursor.execute(
            """
            UPDATE cadu_lead_contatos
               SET nome = %s, email = COALESCE(%s, email), email_status = COALESCE(%s, email_status),
                   linkedin_url = COALESCE(linkedin_url, %s), cargo = COALESCE(cargo, %s),
                   apollo_person_id = COALESCE(apollo_person_id, %s), enriquecido_em = CURRENT_TIMESTAMP,
                   apollo_revelado_em = CURRENT_TIMESTAMP
             WHERE id = %s
            """,
            [nome, revelado.get("email"), revelado.get("email_status"), revelado.get("linkedin_url"),
             revelado.get("cargo"), revelado.get("apollo_id"), contato_id],
        )
        return _ok({"email": revelado.get("email"), "linkedin_url": revelado.get("linkedin_url"),
                    "encontrou_email": bool(revelado.get("email")), "motivo": revelado.get("motivo")})

    resposta = _transacao(run, "revelar contato")
    _gravar_chamadas_apollo(registro, contato_id=contato_id)
    return resposta


@bp.route("/api/contatos/<int:contato_id>/perfil", methods=["PATCH"])
@centralcomm_required_api
def api_contato_perfil(contato_id):
    """Papel, senioridade, influência e LinkedIn do contato (mapa do comitê de compra)."""
    payload = request.get_json(silent=True) or {}
    permitidos = {"papel": dict(PAPEIS), "senioridade": dict(SENIORIDADES), "influencia": dict(INFLUENCIAS)}
    sets, params = [], []
    for campo, valores in permitidos.items():
        if campo in payload:
            valor = payload[campo] or None
            if valor is not None and valor not in valores:
                return _erro(f"Valor inválido para {campo}.")
            sets.append(f"{campo} = %s")
            params.append(valor)
    if "linkedin_url" in payload:
        url = str(payload.get("linkedin_url") or "").strip()
        if url and not re.match(r"^https?://([a-z]+\.)?linkedin\.com/", url, re.I):
            return _erro("Informe um endereço do LinkedIn.")
        sets.append("linkedin_url = %s")
        params.append(url or None)
    if not sets:
        return _erro("Nada para atualizar.")

    def run(cursor):
        cursor.execute(f"UPDATE cadu_lead_contatos SET {', '.join(sets)} WHERE id = %s RETURNING id", [*params, contato_id])
        if not cursor.fetchone():
            return _erro("Contato não encontrado.", 404)
        return _ok({"id": contato_id})

    return _transacao(run, "perfil contato")


def _lead_e_contatos(cursor, lead_id, travar=False):
    cursor.execute(f"SELECT id, nome, empresa, email, telefone, cargo, dominio, url_site FROM cadu_leads WHERE id = %s{' FOR UPDATE' if travar else ''}", [lead_id])
    lead = cursor.fetchone()
    if not lead:
        raise prospeccao.ProspeccaoError("Lead não encontrado.")
    return dict(lead), _contatos_do_lead(cursor, lead_id)


@bp.route("/api/leads/<int:lead_id>/sugestoes")
@centralcomm_required_api
def api_sugestoes_lead(lead_id):
    """O que o próprio formulário permite completar: domínio, nome da empresa e a pessoa em Contatos."""
    def run(cursor):
        lead, contatos = _lead_e_contatos(cursor, lead_id)
        return _ok(prospeccao.sugestoes_do_lead(lead, contatos))

    return _transacao(run, "sugestões do lead")


@bp.route("/api/leads/<int:lead_id>/completar", methods=["POST"])
@centralcomm_required_api
def api_completar_lead(lead_id):
    """Aplica as sugestões escolhidas. Só preenche o que está vazio; o nome da empresa pode vir editado."""
    payload = request.get_json(silent=True) or {}

    def run(cursor):
        lead, contatos = _lead_e_contatos(cursor, lead_id, travar=True)
        sugestoes = prospeccao.sugestoes_do_lead(lead, contatos)
        feito = []
        if payload.get("dominio") and sugestoes["dominio"]:
            cursor.execute("UPDATE cadu_leads SET dominio = %s WHERE id = %s AND COALESCE(dominio, '') = ''", [sugestoes["dominio"], lead_id])
            feito.append(f"domínio {sugestoes['dominio']}")
        empresa = str(payload.get("empresa") or "").strip()[:255]
        if empresa and not str(lead["empresa"] or "").strip():
            cursor.execute("UPDATE cadu_leads SET empresa = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", [empresa, lead_id])
            feito.append(f"empresa {empresa}")
        contato_id = None
        if payload.get("contato") and sugestoes["contato"]:
            c = sugestoes["contato"]
            principal = not contatos
            cursor.execute(
                """
                INSERT INTO cadu_lead_contatos (id_lead, nome, email, telefone, cargo, is_principal, origem_dado, adicionado_por)
                VALUES (%s, %s, %s, %s, %s, %s, 'site', %s) RETURNING id
                """,
                [lead_id, c["nome"], c["email"], c["telefone"], c["cargo"], principal, session.get("user_id")],
            )
            contato_id = cursor.fetchone()["id"]
            feito.append(f"contato {c['nome']}")
        if not feito:
            return _erro("Nada para completar.")
        _registrar_atividade(cursor, lead_id, "edicao", f"Completado com o formulário: {', '.join(feito)}.", contato_id)
        return _ok({"feito": feito, "id_contato": contato_id})

    return _transacao(run, "completar lead")


@bp.route("/api/leads/<int:lead_id>/duplicados")
@centralcomm_required_api
def api_duplicados(lead_id):
    """Pares de contatos do lead que parecem a mesma pessoa (para mesclar)."""
    def run(cursor):
        pares = prospeccao.pares_duplicados(_contatos_do_lead(cursor, lead_id))
        campos = ("id", "nome", "email", "cargo", "origem_dado")
        return _ok({"pares": [[{k: a[k] for k in campos}, {k: b[k] for k in campos}] for a, b in pares]})

    return _transacao(run, "duplicados")


def _completude(c):
    return sum(1 for campo in ("email", "telefone", "linkedin_url", "cargo", "papel", "senioridade", "apollo_person_id") if c.get(campo)) \
        + (2 if c.get("email_status") == "valido" else 0) + (1 if c.get("is_principal") else 0) - (3 if "*" in (c.get("nome") or "") else 0)


@bp.route("/api/contatos/<int:contato_id>/mesclar", methods=["POST"])
@centralcomm_required_api
def api_mesclar_contatos(contato_id):
    """Junta dois contatos do mesmo lead: fica o mais completo, o outro passa histórico, cadências e mensagens e some."""
    outro_id = _int((request.get_json(silent=True) or {}).get("id_duplicado"))
    if not outro_id or outro_id == contato_id:
        return _erro("Escolha o contato repetido.")

    def run(cursor):
        cursor.execute("SELECT * FROM cadu_lead_contatos WHERE id IN (%s, %s) ORDER BY id FOR UPDATE", [contato_id, outro_id])
        rows = [dict(r) for r in cursor.fetchall()]
        if len(rows) != 2:
            return _erro("Contato não encontrado.", 404)
        if rows[0]["id_lead"] != rows[1]["id_lead"]:
            return _erro("Os contatos são de leads diferentes.", 409)
        fica, sai = sorted(rows, key=lambda c: (-_completude(c), c["id"]))
        # Campos vazios de quem fica são preenchidos com os de quem sai; o nome mascarado perde para o completo.
        cursor.execute(
            """
            UPDATE cadu_lead_contatos f
               SET nome = CASE WHEN f.nome LIKE '%%*%%' AND s.nome NOT LIKE '%%*%%' THEN s.nome ELSE f.nome END,
                   cargo = COALESCE(NULLIF(f.cargo, ''), s.cargo), departamento = COALESCE(NULLIF(f.departamento, ''), s.departamento),
                   email_status = CASE WHEN NULLIF(f.email, '') IS NULL THEN s.email_status ELSE f.email_status END,
                   email = COALESCE(NULLIF(f.email, ''), s.email), telefone = COALESCE(NULLIF(f.telefone, ''), s.telefone),
                   telefone_status = COALESCE(f.telefone_status, s.telefone_status),
                   celulares = NULLIF(COALESCE(f.celulares, '[]'::jsonb) || COALESCE((
                       SELECT jsonb_agg(x) FROM jsonb_array_elements(s.celulares) x
                        WHERE NOT COALESCE(f.celulares, '[]'::jsonb) @> jsonb_build_array(jsonb_build_object('numero', x ->> 'numero'))), '[]'::jsonb), '[]'::jsonb),
                   apollo_tem_email = COALESCE(f.apollo_tem_email, s.apollo_tem_email),
                   apollo_tem_celular = COALESCE(f.apollo_tem_celular, s.apollo_tem_celular),
                   apollo_revelado_em = GREATEST(f.apollo_revelado_em, s.apollo_revelado_em),
                   linkedin_url = COALESCE(NULLIF(f.linkedin_url, ''), s.linkedin_url),
                   papel = COALESCE(f.papel, s.papel), senioridade = COALESCE(f.senioridade, s.senioridade),
                   influencia = COALESCE(f.influencia, s.influencia), apollo_person_id = COALESCE(f.apollo_person_id, s.apollo_person_id),
                   is_principal = COALESCE(f.is_principal, FALSE) OR COALESCE(s.is_principal, FALSE),
                   principal = COALESCE(f.principal, FALSE) OR COALESCE(s.principal, FALSE),
                   notas = NULLIF(concat_ws(E'\n', NULLIF(f.notas, ''), NULLIF(s.notas, '')), ''),
                   updated_at = CURRENT_TIMESTAMP
              FROM cadu_lead_contatos s
             WHERE f.id = %s AND s.id = %s
            """,
            [fica["id"], sai["id"]],
        )
        # Cadência ativa repetida (mesmo modelo nas duas fichas) fica só a de quem fica.
        cursor.execute(
            """
            UPDATE cadu_lead_cadencia_inscricoes d SET status = 'cancelada', proxima_em = NULL, motivo_parada = 'Contato mesclado'
             WHERE d.id_contato = %s AND d.status IN ('ativa', 'pausada')
               AND EXISTS (SELECT 1 FROM cadu_lead_cadencia_inscricoes k
                            WHERE k.id_contato = %s AND k.id_cadencia = d.id_cadencia AND k.status IN ('ativa', 'pausada'))
            """,
            [sai["id"], fica["id"]],
        )
        for tabela in ("cadu_lead_cadencia_inscricoes", "cadu_lead_atividades", "cadu_lead_comunicacoes",
                       "cadu_lead_mensagem_eventos", "cadu_lead_contato_candidatos"):
            cursor.execute(f"UPDATE {tabela} SET id_contato = %s WHERE id_contato = %s", [fica["id"], sai["id"]])
        cursor.execute("DELETE FROM cadu_lead_contatos WHERE id = %s", [sai["id"]])
        email_sai = str(sai.get("email") or "").lower()
        extra = f" O e-mail {email_sai} ficou fora (o principal é {str(fica.get('email') or '').lower()})." \
            if email_sai and fica.get("email") and email_sai != str(fica["email"]).lower() else ""
        _registrar_atividade(cursor, fica["id_lead"], "edicao", f"Contatos mesclados: {sai['nome']} junto com {fica['nome']}.{extra}", fica["id"])
        return _ok({"id_contato": fica["id"], "removido": sai["id"]})

    return _transacao(run, "mesclar contatos")


@bp.route("/api/contatos/<int:contato_id>/dado-errado", methods=["POST"])
@centralcomm_required_api
def api_contato_dado_errado(contato_id):
    """E-mail ou celular que não é da pessoa: sai da ficha (fica no histórico) e libera digitar o certo.

    Para celular, `valor` diz qual dos números saiu (sem ele, é o do WhatsApp); se era o do WhatsApp, o próximo assume."""
    dados = request.get_json(silent=True) or {}
    campo = dados.get("campo")
    if campo not in ("email", "telefone"):
        return _erro("Campo inválido.")

    def run(cursor):
        cursor.execute("SELECT id, id_lead, nome, email, telefone, celulares FROM cadu_lead_contatos WHERE id = %s FOR UPDATE", [contato_id])
        contato = cursor.fetchone()
        if not contato:
            return _erro("Contato não encontrado.", 404)
        valor = contato[campo]
        if campo == "telefone" and dados.get("valor"):
            valor = str(dados["valor"])
        if not valor:
            return _erro("Este contato não tem esse dado.")
        if campo == "email":
            cursor.execute("UPDATE cadu_lead_contatos SET email = NULL, email_status = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = %s", [contato_id])
        else:
            errado = prospeccao.digitos(valor)[-11:]
            restantes = [c for c in contato["celulares"] or [] if prospeccao.digitos(c.get("numero"))[-11:] != errado]
            if contato["telefone"] and prospeccao.digitos(contato["telefone"])[-11:] != errado:
                principal = contato["telefone"]  # saiu um celular extra: o do WhatsApp continua
            else:
                principal = restantes[0]["numero"] if restantes else None
            cursor.execute(
                """
                UPDATE cadu_lead_contatos
                   SET telefone = %s, telefone_status = CASE WHEN %s::text IS NULL THEN NULL ELSE telefone_status END,
                       celulares = %s, updated_at = CURRENT_TIMESTAMP
                 WHERE id = %s
                """,
                [principal, principal, db.Json(restantes) if restantes else None, contato_id],
            )
        rotulo = "E-mail" if campo == "email" else "Celular"
        _registrar_atividade(cursor, contato["id_lead"], "edicao", f"{rotulo} {str(valor).lower()} de {contato['nome']} marcado como errado.", contato_id)
        return _ok({"id": contato_id})

    return _transacao(run, "dado errado")


@bp.route("/api/leads/<int:lead_id>/empresa", methods=["PATCH"])
@centralcomm_required_api
def api_lead_empresa(lead_id):
    """Dados de empresa do Leads v3 (domínio, CNPJ, grupo, prioridade) que a edição do v2 não grava."""
    payload = request.get_json(silent=True) or {}
    sets, params = [], []
    if "dominio" in payload:
        sets.append("dominio = %s")
        params.append(prospeccao.normalizar_dominio(payload.get("dominio")) or None)
    if "cnpj" in payload:
        cnpj = prospeccao.digitos(payload.get("cnpj"))
        if cnpj and len(cnpj) != 14:
            return _erro("CNPJ precisa ter 14 dígitos.")
        sets.append("cnpj = %s")
        params.append(cnpj or None)
    if "grupo_economico" in payload:
        sets.append("grupo_economico = %s")
        params.append(str(payload.get("grupo_economico") or "").strip()[:200] or None)
    if "prioridade_conta" in payload:
        prioridade = payload.get("prioridade_conta") or None
        if prioridade not in (None, "A", "B", "C"):
            return _erro("Prioridade inválida.")
        sets.append("prioridade_conta = %s")
        params.append(prioridade)
    if "canais_foco" in payload:
        canais = payload.get("canais_foco") or []
        if not isinstance(canais, list) or any(c not in CANAIS_FOCO for c in canais):
            return _erro("Canais inválidos.")
        sets.append("canais_foco = %s")
        params.append(canais or None)
    if "foco_conteudo" in payload:
        foco = payload.get("foco_conteudo") or {}
        if not isinstance(foco, dict):
            return _erro("Foco de conteúdo inválido.")
        limpo = {k: str(foco.get(k) or "").strip()[:1000] for k in ("topo", "meio", "tom", "evitar") if str(foco.get(k) or "").strip()}
        sets.append("foco_conteudo = %s")
        params.append(db.Json(limpo) if limpo else None)
    if not sets:
        return _erro("Nada para atualizar.")

    def run(cursor):
        cursor.execute(
            f"UPDATE cadu_leads SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s RETURNING id",
            [*params, lead_id],
        )
        if not cursor.fetchone():
            return _erro("Lead não encontrado.", 404)
        return _ok({"id": lead_id})

    return _transacao(run, "dados de empresa")


@bp.route("/api/contatos/<int:contato_id>/achar-email", methods=["POST"])
@centralcomm_required_api
def api_contato_achar_email(contato_id):
    """E-mail sem Apollo: padrão dos contatos do mesmo domínio, depois site/web (Firecrawl), e MX.

    Grava como palpite (email_status = 'arriscado'). O Apollo continua disponível como último recurso.
    """
    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.nome, c.email, l.id AS id_lead, l.dominio, l.url_site, l.email AS lead_email
                  FROM cadu_lead_contatos c JOIN cadu_leads l ON l.id = c.id_lead
                 WHERE c.id = %s
                """,
                [contato_id],
            )
            contato = cursor.fetchone()
            if not contato:
                conn.rollback()
                return _erro("Contato não encontrado.", 404)
            if contato["email"]:
                conn.rollback()
                return _ok({"email": contato["email"], "metodo": "ja_tinha"})
            dominio = contato["dominio"] or prospeccao.normalizar_dominio(contato["url_site"])
            if not dominio:
                email_dom = prospeccao.normalizar_dominio(contato["lead_email"])
                dominio = email_dom if email_dom not in prospeccao.FREE_EMAIL_DOMAINS else ""
            # Exemplos: qualquer contato com e-mail deste domínio, em qualquer lead.
            cursor.execute(
                """
                SELECT nome, lower(email) AS email FROM cadu_lead_contatos
                 WHERE %s <> '' AND lower(email) LIKE %s AND id <> %s
                 LIMIT 50
                """,
                [dominio, f"%@{dominio}", contato_id],
            )
            exemplos = [(r["nome"], r["email"]) for r in cursor.fetchall()]
        conn.rollback()  # leitura; libera a conexão antes das chamadas externas
    except Exception as exc:
        conn.rollback()
        if _sqlstate(exc) in _SQLSTATE_SEM_ESQUEMA:
            return _erro("A migração do Leads v3 ainda não foi aplicada neste banco.", 503)
        current_app.logger.error("leads-v3 achar e-mail: %s", exc)
        return _erro("Não foi possível buscar o e-mail.", 500)

    resultado = prospeccao.achar_email(contato["nome"], dominio, exemplos, firecrawl_key=resolve_firecrawl_api_key())
    if not resultado["email"]:
        return _ok({**resultado, "encontrou": False})

    def run(cursor):
        cursor.execute(
            """
            UPDATE cadu_lead_contatos
               SET email = %s, email_status = 'arriscado', enriquecido_em = CURRENT_TIMESTAMP
             WHERE id = %s AND COALESCE(email, '') = ''
            RETURNING id
            """,
            [resultado["email"], contato_id],
        )
        if cursor.fetchone():
            origem = "contatos da empresa" if resultado["metodo"] == "padrao_contatos" else "e-mails públicos do domínio"
            _registrar_atividade(cursor, contato["id_lead"], "edicao",
                                 f"E-mail sugerido para {contato['nome']} pelo padrão {resultado['padrao']} ({origem}).", contato_id)
        return _ok({**resultado, "encontrou": True})

    return _transacao(run, "achar e-mail")


# ─────────────────────────────────────────────────────
# Cadências por pessoa e Fila do dia
# ─────────────────────────────────────────────────────
def _linhas(rows):
    return [{k: _json_safe(v) for k, v in dict(r).items()} for r in rows]


@bp.route("/api/cadencias")
@centralcomm_required_api
def api_cadencias():
    return _transacao(lambda cursor: _ok({"modelos": _linhas(cadencias.listar_modelos(cursor))}), "modelos de cadência")


@bp.route("/api/cadencias", methods=["POST"])
@centralcomm_required_api
def api_criar_fluxo():
    dados = request.get_json(silent=True) or {}
    try:
        cadencias.normalizar_fluxo(dados)  # erro de preenchimento responde antes de abrir o banco
    except prospeccao.ProspeccaoError as exc:
        return _erro(str(exc))

    def run(cursor):
        return _ok({"id": cadencias.criar_fluxo(cursor, dados, usuario_id=session.get("user_id"))}, 201)

    return _transacao(run, "criar fluxo")


@bp.route("/api/cadencias/<int:fluxo_id>", methods=["PATCH", "DELETE"])
@centralcomm_required_api
def api_editar_fluxo(fluxo_id):
    dados = request.get_json(silent=True) or {}
    if request.method == "PATCH":
        try:
            cadencias.normalizar_fluxo(dados)
        except prospeccao.ProspeccaoError as exc:
            return _erro(str(exc))

    def run(cursor):
        if request.method == "DELETE":
            cadencias.arquivar_fluxo(cursor, fluxo_id)
            return _ok({"id": fluxo_id})
        return _ok(cadencias.atualizar_fluxo(cursor, fluxo_id, dados, usuario_id=session.get("user_id")))

    return _transacao(run, "editar fluxo")


@bp.route("/api/hoje")
@centralcomm_required_api
def api_hoje():
    """Fila do dia: passos de cadência vencidos até o fim de hoje."""
    executivo = _int(request.args.get("executivo"))
    return _transacao(lambda cursor: _ok({"passos": _linhas(cadencias.fila_do_dia(cursor, executivo=executivo))}), "fila do dia")


@bp.route("/api/leads/<int:lead_id>/cadencias")
@centralcomm_required_api
def api_cadencias_do_lead(lead_id):
    return _transacao(lambda cursor: _ok({"inscricoes": _linhas(cadencias.inscricoes_do_lead(cursor, lead_id))}), "cadências do lead")


@bp.route("/api/contatos/<int:contato_id>/cadencia", methods=["POST"])
@centralcomm_required_api
def api_inscrever_contato(contato_id):
    id_cadencia = _int((request.get_json(silent=True) or {}).get("id_cadencia"))

    def run(cursor):
        inscricao = cadencias.inscrever(cursor, contato_id, usuario_id=session.get("user_id"),
                                        usuario_nome=session.get("user_name"), id_cadencia=id_cadencia)
        if not inscricao:
            return _erro("Esta pessoa já está nessa cadência.", 409)
        return _ok({"id": inscricao}, 201)

    return _transacao(run, "inscrever contato")


@bp.route("/api/leads/<int:lead_id>/cadencia", methods=["POST"])
@centralcomm_required_api
def api_inscrever_lead(lead_id):
    """Inscreve todas as pessoas do lead que ainda não têm cadência ativa ou pausada (no fluxo escolhido ou pelo papel)."""
    id_cadencia = _int((request.get_json(silent=True) or {}).get("id_cadencia"))

    def run(cursor):
        cursor.execute(
            """
            SELECT c.id FROM cadu_lead_contatos c
             WHERE c.id_lead = %s
               AND NOT EXISTS (SELECT 1 FROM cadu_lead_cadencia_inscricoes i
                                WHERE i.id_contato = c.id AND i.status IN ('ativa', 'pausada'))
             ORDER BY c.is_principal DESC, c.id
            """,
            [lead_id],
        )
        ids = [r["id"] for r in cursor.fetchall()]
        criadas = [i for i in (cadencias.inscrever(cursor, cid, usuario_id=session.get("user_id"),
                                                   usuario_nome=session.get("user_name"), id_cadencia=id_cadencia) for cid in ids) if i]
        return _ok({"inscritas": len(criadas)}, 201 if criadas else 200)

    return _transacao(run, "inscrever lead")


@bp.route("/api/inscricoes/<int:inscricao_id>/<acao>", methods=["POST"])
@centralcomm_required_api
def api_inscricao_acao(inscricao_id, acao):
    """feito | pular | respondeu | pausar | retomar | cancelar."""
    if acao not in cadencias.ACOES:
        return _erro("Ação inválida.", 404)
    payload = request.get_json(silent=True) or {}
    nota = str(payload.get("nota") or "")[:300]

    def run(cursor):
        estado = cadencias.avancar(cursor, inscricao_id, acao, usuario_id=session.get("user_id"),
                                   usuario_nome=session.get("user_name"), nota=nota, id_gancho=_int(payload.get("id_gancho")))
        return _ok({k: _json_safe(v) for k, v in estado.items()})

    return _transacao(run, f"cadência {acao}")


@bp.route("/api/inscricoes/<int:inscricao_id>/trocar", methods=["POST"])
@centralcomm_required_api
def api_trocar_fluxo(inscricao_id):
    """Põe a pessoa em outro fluxo, começando no passo escolhido; fecha a cadência atual."""
    payload = request.get_json(silent=True) or {}
    id_cadencia = _int(payload.get("id_cadencia"))
    if not id_cadencia:
        return _erro("Escolha o fluxo.")

    def run(cursor):
        estado = cadencias.trocar_fluxo(cursor, inscricao_id, id_cadencia, passo=payload.get("passo") or 0,
                                        usuario_id=session.get("user_id"), usuario_nome=session.get("user_name"))
        return _ok({k: _json_safe(v) for k, v in estado.items()})

    return _transacao(run, "trocar fluxo")


@bp.route("/api/inscricoes/<int:inscricao_id>/passo", methods=["POST"])
@centralcomm_required_api
def api_ir_para_passo(inscricao_id):
    payload = request.get_json(silent=True) or {}
    if payload.get("passo") in (None, ""):
        return _erro("Escolha o passo.")

    def run(cursor):
        estado = cadencias.ir_para_passo(cursor, inscricao_id, payload.get("passo"),
                                         usuario_id=session.get("user_id"), usuario_nome=session.get("user_name"))
        return _ok({k: _json_safe(v) for k, v in estado.items()})

    return _transacao(run, "ir para passo")


@bp.route("/api/inscricoes/<int:inscricao_id>/adiar", methods=["POST"])
@centralcomm_required_api
def api_adiar_toque(inscricao_id):
    data = str((request.get_json(silent=True) or {}).get("data") or "")

    def run(cursor):
        estado = cadencias.adiar(cursor, inscricao_id, data, usuario_id=session.get("user_id"), usuario_nome=session.get("user_name"))
        return _ok({k: _json_safe(v) for k, v in estado.items()})

    return _transacao(run, "adiar toque")


@bp.route("/api/leads/<int:lead_id>/trocar-fluxo", methods=["POST"])
@centralcomm_required_api
def api_trocar_fluxo_do_lead(lead_id):
    payload = request.get_json(silent=True) or {}
    id_cadencia = _int(payload.get("id_cadencia"))
    if not id_cadencia:
        return _erro("Escolha o fluxo.")

    def run(cursor):
        n = cadencias.trocar_fluxo_do_lead(cursor, lead_id, id_cadencia, passo=payload.get("passo") or 0,
                                           usuario_id=session.get("user_id"), usuario_nome=session.get("user_name"))
        return _ok({"trocadas": n})

    return _transacao(run, "trocar fluxo da conta")


# ─────────────────────────────────────────────────────
# Cliente ↔ lead (CRM v3 e mesa de leads)
# ─────────────────────────────────────────────────────
def _auditar(acao, descricao, registro_id, registro_tipo):
    try:
        from .routes import registrar_auditoria

        registrar_auditoria(acao=acao, modulo="leads", descricao=descricao, registro_id=registro_id, registro_tipo=registro_tipo)
    except Exception as exc:  # auditoria não derruba a operação já gravada
        current_app.logger.warning("leads-v3: auditoria falhou: %s", exc)


@bp.route("/api/clientes/<int:cliente_id>/para-lead", methods=["GET", "POST"])
@centralcomm_required_api
def api_cliente_para_lead(cliente_id):
    """GET: prévia (PIs que bloqueiam, cotações que vão expirar, contatos). POST: envia o cliente para leads."""
    motivo = str((request.get_json(silent=True) or {}).get("motivo") or "")

    def run(cursor):
        if request.method == "GET":
            return _ok(_linhas_dict(clientes.previa_volta(cursor, cliente_id)))
        r = clientes.cliente_para_lead(cursor, cliente_id, usuario_id=session.get("user_id"),
                                       usuario_nome=session.get("user_name"), motivo=motivo)
        return _ok(r)

    resposta = _transacao(run, "cliente para lead")
    if request.method == "POST" and resposta[1] == 200:
        _auditar("voltar_lead", f"Cliente {cliente_id} voltou para leads", cliente_id, "tbl_cliente")
    return resposta


@bp.route("/api/leads/<int:lead_id>/reativar-cliente", methods=["POST"])
@centralcomm_required_api
def api_reativar_cliente(lead_id):
    """Lead que veio de um cliente volta a ser cliente no mesmo cadastro."""
    def run(cursor):
        return _ok(clientes.reativar_cliente(cursor, lead_id, usuario_id=session.get("user_id"), usuario_nome=session.get("user_name")))

    resposta = _transacao(run, "reativar cliente")
    if resposta[1] == 200:
        _auditar("converter", f"Lead {lead_id} voltou a ser cliente (cadastro reativado)", lead_id, "cadu_lead")
    return resposta


def _linhas_dict(valor):
    if isinstance(valor, dict):
        return {k: _linhas_dict(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_linhas_dict(v) for v in valor]
    return _json_safe(valor)


@bp.route("/api/leads/<int:lead_id>/golden")
@centralcomm_required_api
def api_golden_do_lead(lead_id):
    """Conta do Golden Circle do lead no trimestre (ou null): alvo, prazo e marco."""
    trimestre = request.args.get("trimestre") or prospeccao.trimestre_atual()

    def run(cursor):
        cursor.execute(
            """
            SELECT id, id_executivo, trimestre, nome_conta, objetivo, status, meta, valor_alvo, prazo, proximo_marco, papeis_alvo
              FROM cadu_golden_circle WHERE id_lead = %s AND trimestre = %s
             ORDER BY id LIMIT 1
            """,
            [lead_id, trimestre],
        )
        row = cursor.fetchone()
        return _ok({"conta": {k: _json_safe(v) for k, v in dict(row).items()} if row else None})

    return _transacao(run, "golden do lead")


MARCOS = ("primeira_conversa", "reuniao", "apresentacao", "proposta", "fechamento")


def _campos_alvo(payload):
    """Campos editáveis do alvo de uma conta do Golden Circle (validados)."""
    sets, params = [], []
    if "status" in payload:
        if payload["status"] not in STATUS_GOLDEN:
            raise prospeccao.ProspeccaoError("Status inválido.")
        sets.append("status = %s"); params.append(payload["status"])
    if "meta" in payload:
        sets.append("meta = %s"); params.append(str(payload.get("meta") or "").strip()[:1000] or None)
    if "valor_alvo" in payload:
        bruto = str(payload.get("valor_alvo") or "").strip().replace("R$", "").replace(" ", "")
        if "," in bruto:  # formato brasileiro: 1.234,56
            bruto = bruto.replace(".", "").replace(",", ".")
        try:
            valor = float(bruto) if bruto else None
        except ValueError:
            raise prospeccao.ProspeccaoError("Valor-alvo inválido.")
        sets.append("valor_alvo = %s"); params.append(valor)
    if "prazo" in payload:
        prazo = payload.get("prazo") or None
        if prazo and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(prazo)):
            raise prospeccao.ProspeccaoError("Prazo inválido.")
        sets.append("prazo = %s"); params.append(prazo)
    if "proximo_marco" in payload:
        marco = payload.get("proximo_marco") or None
        if marco is not None and marco not in MARCOS:
            raise prospeccao.ProspeccaoError("Marco inválido.")
        sets.append("proximo_marco = %s"); params.append(marco)
    if "papeis_alvo" in payload:
        papeis = payload.get("papeis_alvo") or []
        if not isinstance(papeis, list) or any(p not in dict(PAPEIS) for p in papeis):
            raise prospeccao.ProspeccaoError("Papéis inválidos.")
        sets.append("papeis_alvo = %s"); params.append(papeis)
    return sets, params


# ─────────────────────────────────────────────────────
# Operação: mensagens personalizadas, ganchos de pauta e tarefas
# ─────────────────────────────────────────────────────
class _Resposta(Exception):
    """Interrompe uma leitura devolvendo uma resposta pronta (ex.: 404)."""

    def __init__(self, resposta):
        super().__init__()
        self.resposta = resposta


def _ler(fn, contexto):
    """Roda fn(cursor) só lendo (sem commit). Devolve (resultado, None) ou (None, resposta de erro)."""
    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            resultado = fn(cursor)
        conn.rollback()
        return resultado, None
    except _Resposta as exc:
        conn.rollback()
        return None, exc.resposta
    except Exception as exc:
        conn.rollback()
        if _sqlstate(exc) in _SQLSTATE_SEM_ESQUEMA:
            return None, _erro("A migração do Leads v3 ainda não foi aplicada neste banco.", 503)
        current_app.logger.error("leads-v3 %s: %s", contexto, exc)
        return None, _erro("Não foi possível ler os dados.", 500)


_COLUNAS_GANCHO = "id, etapa, tipo, fato, numero, angulo, fonte_url, fonte_nome, data_fato, status, origem, created_at"


def _ganchos_usados(cursor, contato_id):
    """Ids dos ganchos já usados com a pessoa (gravados no evento do passo feito)."""
    cursor.execute(
        """
        SELECT DISTINCT (payload ->> 'id_gancho')::int AS id FROM cadu_lead_mensagem_eventos
         WHERE id_contato = %s AND evento = 'tarefa_feita' AND payload ->> 'id_gancho' ~ '^[0-9]+$'
        """,
        [contato_id],
    )
    return {r["id"] for r in cursor.fetchall()}


def _escolher_gancho(cursor, lead_id, etapa, usados, id_gancho=None):
    """O gancho pedido, ou o melhor da etapa: escolhido antes de sugerido, ainda não usado com a pessoa."""
    if id_gancho:
        cursor.execute(f"SELECT {_COLUNAS_GANCHO} FROM cadu_lead_ganchos WHERE id = %s AND id_lead = %s", [id_gancho, lead_id])
        return cursor.fetchone()
    cursor.execute(
        f"""
        SELECT {_COLUNAS_GANCHO} FROM cadu_lead_ganchos
         WHERE id_lead = %s AND status <> 'descartado'
         ORDER BY (id = ANY(%s::int[])) ASC, (etapa = %s) DESC, (status = 'escolhido') DESC, id
         LIMIT 1
        """,
        [lead_id, list(usados), etapa],
    )
    return cursor.fetchone()


@bp.route("/api/mensagens/gerar", methods=["POST"])
@centralcomm_required_api
def api_gerar_mensagem():
    """Mensagem para uma pessoa num canal e etapa (topo/meio), a partir de um gancho, com foco e histórico da empresa."""
    payload = request.get_json(silent=True) or {}
    contato_id = _int(payload.get("id_contato"))
    if not contato_id:
        return _erro("Escolha a pessoa.")
    etapa = payload.get("etapa") or "topo"
    id_inscricao = _int(payload.get("id_inscricao"))

    def ler(cursor):
        cursor.execute(
            """
            SELECT c.nome, c.cargo, c.papel, l.id AS id_lead, COALESCE(l.empresa, l.nome) AS empresa, l.segmento,
                   l.descricao_empresa, l.oportunidades_midia, l.foco_conteudo, l.contexto_mercado
              FROM cadu_lead_contatos c JOIN cadu_leads l ON l.id = c.id_lead WHERE c.id = %s
            """,
            [contato_id],
        )
        row = cursor.fetchone()
        if not row:
            raise _Resposta(_erro("Contato não encontrado.", 404))
        cursor.execute(
            """
            SELECT descricao FROM cadu_lead_atividades
             WHERE id_lead = %s AND tipo NOT IN ('status_change', 'atribuicao', 'edicao', 'importacao')
             ORDER BY created_at DESC LIMIT 6
            """,
            [row["id_lead"]],
        )
        historico = [r["descricao"] for r in cursor.fetchall()]
        usados = _ganchos_usados(cursor, contato_id)
        gancho = _escolher_gancho(cursor, row["id_lead"], etapa, usados, _int(payload.get("id_gancho")))
        ja_usados = []
        if usados:
            cursor.execute("SELECT fato FROM cadu_lead_ganchos WHERE id = ANY(%s::int[]) ORDER BY id DESC LIMIT 6", [list(usados)])
            ja_usados = [r["fato"] for r in cursor.fetchall()]
        cursor.execute("SELECT assinatura, dispositivo FROM cadu_lead_preferencias WHERE id_usuario = %s", [session.get("user_id")])
        prefs = cursor.fetchone() or {}
        fluxo = cadencias.contexto_do_passo(cursor, id_inscricao) if id_inscricao else None
        if fluxo and fluxo["id_contato"] != contato_id:
            fluxo = None
        return row, historico, gancho, ja_usados, prefs, fluxo

    lido, erro = _ler(ler, "gerar mensagem")
    if erro:
        return erro
    row, historico, gancho, ja_usados, prefs, fluxo = lido
    contexto = (row["contexto_mercado"] or {}).get("texto") if isinstance(row["contexto_mercado"], dict) else None
    try:
        resultado = mensagens.gerar_mensagem(
            mensagens.resolve_openrouter_key(),
            canal=payload.get("canal") or "email", etapa=etapa,
            objetivo=str(payload.get("objetivo") or "").strip()[:400],
            pessoa={"nome": row["nome"], "cargo": row["cargo"], "papel": row["papel"]},
            empresa={"nome": row["empresa"], "segmento": row["segmento"], "descricao": row["descricao_empresa"],
                     "oportunidades_midia": row["oportunidades_midia"]},
            foco=mensagens._resumo_foco(row["foco_conteudo"]), contexto=contexto, historico=historico,
            remetente=session.get("user_name"), gancho=dict(gancho) if gancho else None, ja_usados=ja_usados,
            assinatura=prefs.get("assinatura"), dispositivo=prefs.get("dispositivo") or "nenhum",
            fluxo=fluxo,
        )
    except prospeccao.ProspeccaoError as exc:
        return _erro(str(exc), 400)
    resultado["gancho"] = {k: _json_safe(v) for k, v in dict(gancho).items()} if gancho else None
    return _ok(resultado)


@bp.route("/api/leads/<int:lead_id>/contexto", methods=["POST"])
@centralcomm_required_api
def api_contexto_mercado(lead_id):
    """Pesquisa na web (Sonar Pro) e monta o dossiê: resumo da empresa e ganchos com fonte e data."""

    def ler(cursor):
        cursor.execute(
            """
            SELECT COALESCE(empresa, nome) AS empresa, dominio, url_site, segmento, descricao_empresa,
                   ARRAY(SELECT DISTINCT papel FROM cadu_lead_contatos WHERE id_lead = %s AND papel IS NOT NULL) AS papeis
              FROM cadu_leads WHERE id = %s
            """,
            [lead_id, lead_id],
        )
        lead = cursor.fetchone()
        if not lead:
            raise _Resposta(_erro("Lead não encontrado.", 404))
        return lead

    lead, erro = _ler(ler, "contexto de mercado")
    if erro:
        return erro
    try:
        dossie = mensagens.gerar_dossie(
            mensagens.resolve_openrouter_key(), empresa=lead["empresa"],
            dominio=lead["dominio"] or prospeccao.normalizar_dominio(lead["url_site"]), segmento=lead["segmento"],
            descricao=lead["descricao_empresa"], papeis=lead["papeis"] or [])
    except prospeccao.ProspeccaoError as exc:
        return _erro(str(exc), 400)

    def run(cursor):
        cursor.execute("UPDATE cadu_leads SET contexto_mercado = %s WHERE id = %s", [db.Json(dossie["contexto"]), lead_id])
        # A nova pesquisa substitui as sugestões antigas que ninguém escolheu nem usou (se trouxe ganchos).
        cursor.execute(
            """
            DELETE FROM cadu_lead_ganchos g
             WHERE g.id_lead = %s AND g.origem = 'pesquisa' AND g.status <> 'escolhido' AND %s
               AND NOT EXISTS (SELECT 1 FROM cadu_lead_mensagem_eventos e
                                WHERE e.id_lead = g.id_lead AND e.payload ->> 'id_gancho' = g.id::text)
            """,
            [lead_id, bool(dossie["ganchos"])],
        )
        cursor.execute("SELECT lower(left(fato, 80)) AS chave FROM cadu_lead_ganchos WHERE id_lead = %s", [lead_id])
        existentes = {r["chave"] for r in cursor.fetchall()}
        for g in dossie["ganchos"]:
            if g["fato"].lower()[:80] in existentes:
                continue
            cursor.execute(
                """
                INSERT INTO cadu_lead_ganchos (id_lead, etapa, tipo, fato, numero, angulo, fonte_url, fonte_nome, data_fato, criado_por)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [lead_id, g["etapa"], g["tipo"], g["fato"], g["numero"], g["angulo"], g["fonte_url"], g["fonte_nome"],
                 g["data_fato"], session.get("user_id")],
            )
        return _ok({"contexto": dossie["contexto"], "ganchos_novos": len(dossie["ganchos"])})

    return _transacao(run, "contexto de mercado")


@bp.route("/api/leads/<int:lead_id>/ganchos")
@centralcomm_required_api
def api_ganchos(lead_id):
    """Ganchos da empresa; com ?id_contato=, marca os já usados com a pessoa."""
    contato_id = _int(request.args.get("id_contato"))

    def ler(cursor):
        cursor.execute(
            f"""
            SELECT {_COLUNAS_GANCHO},
                   (SELECT COUNT(*) FROM cadu_lead_mensagem_eventos e
                     WHERE e.id_lead = g.id_lead AND e.evento = 'tarefa_feita' AND e.payload ->> 'id_gancho' = g.id::text) AS usos
              FROM cadu_lead_ganchos g
             WHERE g.id_lead = %s
             ORDER BY (status = 'descartado'), (status = 'escolhido') DESC, (etapa = 'topo') DESC, id
            """,
            [lead_id],
        )
        ganchos = [{k: _json_safe(v) for k, v in dict(r).items()} for r in cursor.fetchall()]
        usados = _ganchos_usados(cursor, contato_id) if contato_id else set()
        for g in ganchos:
            g["usado_com_pessoa"] = g["id"] in usados
        return ganchos

    ganchos, erro = _ler(ler, "ganchos")
    return erro or _ok({"ganchos": ganchos})


def _campos_gancho(payload, parcial):
    """Campos editáveis de um gancho. No cadastro manual o fato é obrigatório; a fonte, se vier, precisa ser link."""
    sets, params = [], []
    if "status" in payload:
        if payload["status"] not in ("sugerido", "escolhido", "descartado"):
            raise prospeccao.ProspeccaoError("Status inválido.")
        sets.append("status = %s"); params.append(payload["status"])
    if "etapa" in payload:
        if payload["etapa"] not in mensagens.ETAPAS_GANCHO:
            raise prospeccao.ProspeccaoError("Etapa inválida.")
        sets.append("etapa = %s"); params.append(payload["etapa"])
    if "tipo" in payload:
        if payload["tipo"] not in mensagens.TIPOS_GANCHO:
            raise prospeccao.ProspeccaoError("Tipo inválido.")
        sets.append("tipo = %s"); params.append(payload["tipo"])
    for campo, limite in (("fato", 600), ("numero", 120), ("angulo", 400), ("fonte_nome", 120), ("data_fato", 20)):
        if campo in payload:
            valor = str(payload.get(campo) or "").strip()[:limite] or None
            if campo == "fato" and not valor:
                raise prospeccao.ProspeccaoError("Escreva o fato.")
            sets.append(f"{campo} = %s"); params.append(valor)
    if "fonte_url" in payload:
        url = str(payload.get("fonte_url") or "").strip()
        if url and not url.startswith("http"):
            raise prospeccao.ProspeccaoError("A fonte precisa ser um link (https://…).")
        sets.append("fonte_url = %s"); params.append(url[:1000] or None)
    if not parcial and not str(payload.get("fato") or "").strip():
        raise prospeccao.ProspeccaoError("Escreva o fato.")
    return sets, params


@bp.route("/api/leads/<int:lead_id>/ganchos", methods=["POST"])
@centralcomm_required_api
def api_gancho_criar(lead_id):
    """Gancho escrito pelo executivo (já entra como escolhido)."""
    payload = request.get_json(silent=True) or {}

    def run(cursor):
        sets, params = _campos_gancho({**payload, "status": "escolhido"}, parcial=False)
        colunas = [s.split(" = ")[0] for s in sets]
        cursor.execute(
            f"""
            INSERT INTO cadu_lead_ganchos (id_lead, origem, criado_por, {', '.join(colunas)})
            SELECT %s, 'manual', %s, {', '.join(['%s'] * len(params))} WHERE EXISTS (SELECT 1 FROM cadu_leads WHERE id = %s)
            RETURNING id
            """,
            [lead_id, session.get("user_id"), *params, lead_id],
        )
        row = cursor.fetchone()
        return _ok({"id": row["id"]}, 201) if row else _erro("Lead não encontrado.", 404)

    return _transacao(run, "criar gancho")


@bp.route("/api/ganchos/<int:gancho_id>", methods=["PATCH"])
@centralcomm_required_api
def api_gancho_alterar(gancho_id):
    payload = request.get_json(silent=True) or {}

    def run(cursor):
        sets, params = _campos_gancho(payload, parcial=True)
        if not sets:
            return _erro("Nada para atualizar.")
        cursor.execute(
            f"UPDATE cadu_lead_ganchos SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s RETURNING id",
            [*params, gancho_id],
        )
        return _ok({"id": gancho_id}) if cursor.fetchone() else _erro("Gancho não encontrado.", 404)

    return _transacao(run, "alterar gancho")


@bp.route("/api/leads/<int:lead_id>/foco/sugerir", methods=["POST"])
@centralcomm_required_api
def api_sugerir_foco(lead_id):
    """Sugestão de foco (topo, meio, tom, evitar) a partir dos ganchos; a tela abre o formulário preenchido."""

    def ler(cursor):
        cursor.execute(
            """
            SELECT COALESCE(empresa, nome) AS empresa, segmento, descricao_empresa,
                   ARRAY(SELECT DISTINCT papel FROM cadu_lead_contatos WHERE id_lead = %s AND papel IS NOT NULL) AS papeis
              FROM cadu_leads WHERE id = %s
            """,
            [lead_id, lead_id],
        )
        lead = cursor.fetchone()
        if not lead:
            raise _Resposta(_erro("Lead não encontrado.", 404))
        cursor.execute(
            """
            SELECT etapa, tipo, fato, angulo FROM cadu_lead_ganchos
             WHERE id_lead = %s AND status <> 'descartado' ORDER BY (status = 'escolhido') DESC, id LIMIT 10
            """,
            [lead_id],
        )
        return lead, [dict(r) for r in cursor.fetchall()]

    lido, erro = _ler(ler, "sugerir foco")
    if erro:
        return erro
    lead, ganchos = lido
    try:
        foco = mensagens.sugerir_foco(mensagens.resolve_openrouter_key(), empresa=lead["empresa"], segmento=lead["segmento"],
                                      descricao=lead["descricao_empresa"], papeis=lead["papeis"] or [], ganchos=ganchos)
    except prospeccao.ProspeccaoError as exc:
        return _erro(str(exc), 400)
    return _ok({"foco": foco})


_COLUNAS_PREFS = "assinatura, dispositivo, modelo_assinatura, nome_assinatura, cargo, telefone, linkedin_url"


def _remetente_info(prefs):
    """O que a tela mostra do envio: de quem sai, o bloco de assinatura e se o e-mail de login pode enviar."""
    email = session.get("user_email")
    try:
        email_mail.validar_remetente(email)
        pode = True
    except prospeccao.ProspeccaoError:
        pode = False
    texto, _ = email_mail.assinatura(prefs, nome_usuario=session.get("user_name"))
    return {"remetente": {"nome": prefs.get("nome_assinatura") or session.get("user_name"), "email": email,
                          "pode_enviar": pode},
            "assinatura_texto": texto, "limite_diario": email_mail.LIMITE_DIARIO,
            "modelos": [{"id": k, "rotulo": v["rotulo"]} for k, v in email_mail.MODELOS_ASSINATURA.items()]}


@bp.route("/api/preferencias", methods=["GET", "PUT"])
@centralcomm_required_api
def api_preferencias():
    """Fecho, assinatura e 'Enviado do meu…' do executivo logado (entram no fim dos e-mails)."""
    usuario = session.get("user_id")
    if request.method == "GET":
        def ler(cursor):
            cursor.execute(f"SELECT {_COLUNAS_PREFS} FROM cadu_lead_preferencias WHERE id_usuario = %s", [usuario])
            return dict(cursor.fetchone() or {"assinatura": None, "dispositivo": "nenhum", "modelo_assinatura": "simples"})

        prefs, erro = _ler(ler, "preferências")
        return erro or _ok({**prefs, **_remetente_info(prefs)})

    payload = request.get_json(silent=True) or {}
    dispositivo = payload.get("dispositivo") or "nenhum"
    if dispositivo not in mensagens.DISPOSITIVOS:
        return _erro("Dispositivo inválido.")
    try:
        campos = email_mail.normalizar_preferencias(payload)
    except prospeccao.ProspeccaoError as exc:
        return _erro(str(exc))
    # Só grava o que veio: trocar o rodapé (só `dispositivo`) não apaga cargo, telefone nem LinkedIn.
    novos = {"assinatura": str(payload.get("assinatura") or "").strip()[:300] or None, "dispositivo": dispositivo, **campos}
    novos = {k: v for k, v in novos.items() if k in payload or k == "dispositivo"}

    def run(cursor):
        colunas = list(novos)
        cursor.execute(
            f"""
            INSERT INTO cadu_lead_preferencias (id_usuario, {", ".join(colunas)}) VALUES (%s, {", ".join(["%s"] * len(colunas))})
            ON CONFLICT (id_usuario) DO UPDATE SET {", ".join(f"{c} = EXCLUDED.{c}" for c in colunas)},
                                                   updated_at = CURRENT_TIMESTAMP
            """,
            [usuario, *novos.values()],
        )
        cursor.execute(f"SELECT {_COLUNAS_PREFS} FROM cadu_lead_preferencias WHERE id_usuario = %s", [usuario])
        prefs = dict(cursor.fetchone() or novos)
        return _ok({**prefs, **_remetente_info(prefs)})

    return _transacao(run, "preferências")


@bp.route("/api/inscricoes/<int:inscricao_id>/enviar-email", methods=["POST"])
@centralcomm_required_api
def api_enviar_email(inscricao_id):
    """Envia pela Brevo o e-mail revisado do passo, em nome do executivo, e marca o passo como feito."""
    payload = request.get_json(silent=True) or {}
    passo = payload.get("passo")
    if not isinstance(passo, int):
        return _erro("Passo inválido.")
    from .services.brevo_service import BrevoService

    def run(cursor):
        cursor.execute(f"SELECT {_COLUNAS_PREFS} FROM cadu_lead_preferencias WHERE id_usuario = %s", [session.get("user_id")])
        prefs = dict(cursor.fetchone() or {})
        estado = email_mail.enviar_passo(
            cursor, inscricao_id, assunto=payload.get("assunto"), texto=payload.get("texto"), passo=passo,
            usuario={"id": session.get("user_id"), "nome": session.get("user_name"), "email": session.get("user_email")},
            prefs=prefs, enviar_fn=BrevoService().enviar_email, id_gancho=_int(payload.get("id_gancho")),
            na_conversa=bool(payload.get("na_conversa")))
        return _ok({k: _json_safe(v) for k, v in estado.items()})

    return _transacao(run, "enviar e-mail")


@bp.route("/api/inscricoes/<int:inscricao_id>/email-previa", methods=["POST"])
@centralcomm_required_api
def api_previa_email(inscricao_id):
    """O e-mail do passo como vai sair: de, para, responder para, assunto (ou 'Re:' da conversa) e o HTML final."""
    payload = request.get_json(silent=True) or {}

    def ler(cursor):
        cursor.execute(f"SELECT {_COLUNAS_PREFS} FROM cadu_lead_preferencias WHERE id_usuario = %s", [session.get("user_id")])
        prefs = dict(cursor.fetchone() or {})
        try:
            p = email_mail.previa(
                cursor, inscricao_id, assunto=payload.get("assunto"), texto=str(payload.get("texto") or ""), prefs=prefs,
                usuario={"id": session.get("user_id"), "nome": session.get("user_name"), "email": session.get("user_email")},
                na_conversa=bool(payload.get("na_conversa")))
        except prospeccao.ProspeccaoError as exc:
            raise _Resposta(_erro(str(exc), 404))
        if p.get("conversa"):
            p["conversa"] = {k: _json_safe(v) for k, v in p["conversa"].items()}
        return p

    previa, erro = _ler(ler, "prévia do e-mail")
    return erro or _ok(previa)


def tarefas_pendentes(cursor, executivo=None):
    """Atividades com prazo até hoje e não concluídas (as criadas à mão, fora das cadências)."""
    filtro = "AND l.id_executivo = %(executivo)s" if executivo else ""
    cursor.execute(
        f"""
        SELECT a.id, a.id_lead, a.id_contato, a.tipo, a.descricao, a.data_prazo, a.usuario_nome,
               COALESCE(l.empresa, l.nome) AS empresa, c.nome AS contato_nome,
               EXISTS (SELECT 1 FROM cadu_golden_circle g WHERE g.id_lead = a.id_lead AND g.trimestre = %(trimestre)s) AS golden
          FROM cadu_lead_atividades a
          JOIN cadu_leads l ON l.id = a.id_lead
          LEFT JOIN cadu_lead_contatos c ON c.id = a.id_contato
         WHERE a.data_prazo IS NOT NULL AND a.data_prazo <= CURRENT_DATE AND COALESCE(a.concluida, FALSE) = FALSE {filtro}
         ORDER BY golden DESC, a.data_prazo, a.id
         LIMIT 200
        """,
        {"executivo": executivo, "trimestre": prospeccao.trimestre_atual()},
    )
    return cursor.fetchall()


@bp.route("/api/operacao")
@centralcomm_required_api
def api_operacao():
    """Visão da operação: pendências até hoje (passos e tarefas), próximos 14 dias e o que já foi feito hoje."""
    executivo = _int(request.args.get("executivo"))

    def run(cursor):
        return _ok({"passos": _linhas(cadencias.fila_do_dia(cursor, executivo=executivo)),
                    "tarefas": _linhas(tarefas_pendentes(cursor, executivo)),
                    "proximos": _linhas(cadencias.proximos_passos(cursor, executivo=executivo)),
                    "feitos": _linhas(cadencias.feitos_hoje(cursor, executivo=executivo)),
                    "agora": _json_safe(datetime.now())})  # relógio dos eventos da Brevo, para o "há 10 min"

    return _transacao(run, "operação")


# ─────────────────────────────────────────────────────
# Mesclar leads duplicados (tudo numa transação)
# ─────────────────────────────────────────────────────
# Tabelas que apontam para cadu_leads.id e precisam vir junto antes de apagar o duplicado.
_TABELAS_DO_LEAD = (
    "cadu_lead_atividades", "cadu_lead_comunicacoes", "cadu_lead_cadencia_inscricoes",
    "cadu_lead_mensagem_eventos", "cadu_golden_circle",
)
_CAMPOS_COMPLETAR = ("email", "telefone", "cargo", "url_site", "dominio", "cnpj", "segmento", "descricao_empresa",
                     "porte_estimado", "grupo_economico", "id_executivo")


@bp.route("/api/leads/<int:lead_id>/mesclar", methods=["POST"])
@centralcomm_required_api
def api_mesclar(lead_id):
    """Incorpora o lead duplicado neste: move pessoas, histórico, comunicações, cadências, candidatos e
    Golden Circle; completa campos vazios com os do duplicado; depois apaga o duplicado."""
    outro = _int((request.get_json(silent=True) or {}).get("id_duplicado"))
    if not outro or outro == lead_id:
        return _erro("Escolha outro lead para mesclar.")

    def run(cursor):
        cursor.execute("SELECT * FROM cadu_leads WHERE id = ANY(%s) FOR UPDATE", [[lead_id, outro]])
        rows = {r["id"]: r for r in cursor.fetchall()}
        if lead_id not in rows or outro not in rows:
            return _erro("Lead não encontrado.", 404)
        principal, duplicado = rows[lead_id], rows[outro]
        completar = [c for c in _CAMPOS_COMPLETAR if c in principal and not principal[c] and duplicado.get(c)]
        if completar:
            cursor.execute(
                f"UPDATE cadu_leads SET {', '.join(f'{c} = %s' for c in completar)} WHERE id = %s",
                [*[duplicado[c] for c in completar], lead_id],
            )
        cursor.execute("UPDATE cadu_lead_contatos SET id_lead = %s, is_principal = FALSE WHERE id_lead = %s", [lead_id, outro])
        # Candidatos: o índice único (lead, provedor, ref) não deixa trazer o que já existe aqui.
        cursor.execute(
            """
            DELETE FROM cadu_lead_contato_candidatos d
             WHERE d.id_lead = %s AND d.provedor_ref IS NOT NULL
               AND EXISTS (SELECT 1 FROM cadu_lead_contato_candidatos p
                            WHERE p.id_lead = %s AND p.provedor = d.provedor AND p.provedor_ref = d.provedor_ref)
            """,
            [outro, lead_id],
        )
        cursor.execute("UPDATE cadu_lead_contato_candidatos SET id_lead = %s WHERE id_lead = %s", [lead_id, outro])
        for tabela in _TABELAS_DO_LEAD:
            cursor.execute(f"UPDATE {tabela} SET id_lead = %s WHERE id_lead = %s", [lead_id, outro])
        cursor.execute("DELETE FROM cadu_lead_links_uteis WHERE id_lead = %s", [outro])
        cursor.execute("DELETE FROM cadu_leads WHERE id = %s", [outro])
        nome = duplicado.get("empresa") or duplicado.get("nome") or f"#{outro}"
        _registrar_atividade(cursor, lead_id, "edicao", f"Lead duplicado mesclado: {nome} (#{outro}).")
        return _ok({"id": lead_id, "removido": outro, "campos_completados": completar})

    return _transacao(run, "mesclar")


# ─────────────────────────────────────────────────────
# Análise: números das cadências e do Golden Circle (complementa /api/leads/analise)
# ─────────────────────────────────────────────────────
@bp.route("/api/analise")
@centralcomm_required_api
def api_analise_v3():
    inicio = request.args.get("data_inicio") or None
    fim = request.args.get("data_fim") or None
    executivo = _int(request.args.get("id_executivo"))
    for valor in (inicio, fim):
        if valor and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
            return _erro("Data inválida.")
    trimestre = prospeccao.trimestre_atual()

    def run(cursor):
        filtro = "AND COALESCE(i.id_executivo, l.id_executivo) = %(executivo)s" if executivo else ""
        cursor.execute(
            f"""
            SELECT e.canal,
                   COUNT(*) FILTER (WHERE e.evento = 'tarefa_feita') AS feitos,
                   COUNT(*) FILTER (WHERE e.evento = 'respondeu') AS respostas
              FROM cadu_lead_mensagem_eventos e
              JOIN cadu_leads l ON l.id = e.id_lead
              LEFT JOIN cadu_lead_cadencia_inscricoes i ON i.id = e.id_inscricao
             WHERE (%(inicio)s::date IS NULL OR e.ocorreu_em >= %(inicio)s::date)
               AND (%(fim)s::date IS NULL OR e.ocorreu_em < %(fim)s::date + 1) {filtro}
             GROUP BY e.canal ORDER BY e.canal
            """,
            {"inicio": inicio, "fim": fim, "executivo": executivo},
        )
        canais = _linhas(cursor.fetchall())
        cursor.execute(
            f"""
            SELECT COUNT(*) FILTER (WHERE i.status = 'ativa') AS ativas,
                   COUNT(*) FILTER (WHERE i.status = 'respondeu') AS responderam,
                   COUNT(*) FILTER (WHERE i.status = 'concluida') AS concluidas,
                   COUNT(*) AS total
              FROM cadu_lead_cadencia_inscricoes i JOIN cadu_leads l ON l.id = i.id_lead
             WHERE TRUE {filtro}
            """,
            {"executivo": executivo},
        )
        inscricoes = {k: _json_safe(v) for k, v in dict(cursor.fetchone() or {}).items()}
        filtro_gc = "AND gc.id_executivo = %(executivo)s" if executivo else ""
        cursor.execute(
            f"""
            SELECT COUNT(*) AS contas,
                   COUNT(*) FILTER (WHERE gc.status NOT IN ('planejada', 'pausada', 'perdida')) AS em_andamento,
                   COUNT(*) FILTER (WHERE gc.status = 'ganha') AS ganhas,
                   COUNT(*) FILTER (WHERE NOT EXISTS (
                       SELECT 1 FROM unnest(gc.papeis_alvo) p
                        WHERE NOT EXISTS (SELECT 1 FROM cadu_lead_contatos c WHERE c.id_lead = gc.id_lead AND c.papel = p))) AS cobertas,
                   COALESCE(SUM(gc.valor_alvo), 0) AS valor_alvo
              FROM cadu_golden_circle gc
             WHERE gc.trimestre = %(trimestre)s {filtro_gc}
            """,
            {"trimestre": trimestre, "executivo": executivo},
        )
        golden = {k: _json_safe(v) for k, v in dict(cursor.fetchone() or {}).items()}
        # Funil separado por origem: o site (formulários) nunca se mistura com o que a equipe adicionou.
        filtro_lead = "AND l.id_executivo = %(executivo)s" if executivo else ""
        cursor.execute(
            f"""
            SELECT CASE WHEN l.fonte = 'site' THEN 'site' ELSE 'equipe' END AS origem,
                   COUNT(*) AS entraram,
                   COUNT(*) FILTER (WHERE l.status NOT IN ('inbox', 'nao_qualificado', 'fechado_perdido')) AS avancaram,
                   COUNT(*) FILTER (WHERE l.status = 'inbox') AS no_inbox,
                   COUNT(*) FILTER (WHERE l.convertido_cliente_id IS NOT NULL OR l.status = 'fechado_ganho') AS convertidos,
                   COUNT(*) FILTER (WHERE l.status = 'nao_qualificado') AS desqualificados,
                   COUNT(*) FILTER (WHERE l.status = 'fechado_perdido') AS perdidos,
                   COUNT(*) FILTER (WHERE l.id_executivo IS NULL) AS sem_responsavel,
                   COALESCE(SUM(l.valor_fechado) FILTER (WHERE l.status = 'fechado_ganho' OR l.convertido_cliente_id IS NOT NULL), 0) AS receita,
                   ROUND(AVG(EXTRACT(EPOCH FROM (pc.primeiro - l.created_at)) / 3600)
                         FILTER (WHERE pc.primeiro IS NOT NULL)::numeric, 1) AS horas_primeiro_contato,
                   ROUND(AVG(EXTRACT(EPOCH FROM (l.data_conversao - l.created_at)) / 86400)
                         FILTER (WHERE l.data_conversao IS NOT NULL)::numeric, 1) AS dias_ate_converter
              FROM cadu_leads l
              -- 1º contato: o que vier antes entre contatado_em (só a etapa antiga "contato" do site preenche),
              -- a primeira atividade registrada à mão e o primeiro toque de cadência.
              LEFT JOIN LATERAL (
                  SELECT LEAST(
                      l.contatado_em,
                      (SELECT MIN(a.created_at) FROM cadu_lead_atividades a
                        WHERE a.id_lead = l.id AND a.tipo = ANY(%(tipos)s)
                          AND a.descricao NOT LIKE 'Cadência %% iniciada%%'),
                      (SELECT MIN(e.ocorreu_em) FROM cadu_lead_mensagem_eventos e
                        WHERE e.id_lead = l.id AND e.evento = 'tarefa_feita')
                  ) AS primeiro
              ) pc ON TRUE
             WHERE (%(inicio)s::date IS NULL OR l.created_at >= %(inicio)s::date)
               AND (%(fim)s::date IS NULL OR l.created_at < %(fim)s::date + 1) {filtro_lead}
             GROUP BY 1
            """,
            {"inicio": inicio, "fim": fim, "executivo": executivo, "tipos": list(TIPOS_HUMANOS)},
        )
        funil = {r["origem"]: {k: _json_safe(v) for k, v in dict(r).items() if k != "origem"} for r in cursor.fetchall()}
        return _ok({"canais": canais, "inscricoes": inscricoes, "golden": {**golden, "trimestre": trimestre}, "funil": funil})

    return _transacao(run, "análise v3")


# ─────────────────────────────────────────────────────
# Diagnóstico do Apollo: registro das chamadas e checagem grátis
# ─────────────────────────────────────────────────────
_SEM_SESSAO = object()


def _gravar_chamadas_apollo(registro, *, lead_id=None, contato_id=None, usuario_id=_SEM_SESSAO):
    """Grava cada chamada anotada em cadu_apollo_chamadas, numa transação própria.

    Roda depois da transação da rota (com ela já encerrada). Falha aqui nunca derruba a rota: sem a tabela
    (migração não aplicada) ou com erro, só registra no log da aplicação."""
    if not registro:
        return
    usuario = session.get("user_id") if usuario_id is _SEM_SESSAO else usuario_id
    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            for c in registro:
                cursor.execute(
                    """
                    INSERT INTO cadu_apollo_chamadas
                        (endpoint, id_lead, id_contato, http_status, pago, erro, pedido, resumo, resposta, usuario_id)
                    VALUES (%s, COALESCE(%s, (SELECT id_lead FROM cadu_lead_contatos WHERE id = %s)),
                            (SELECT id FROM cadu_lead_contatos WHERE id = %s), %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [c["endpoint"], lead_id, contato_id, contato_id, c["http_status"], c["pago"], c["erro"],
                     db.Json(c["pedido"]) if c["pedido"] is not None else None, db.Json(c["resumo"]),
                     db.Json(c["resposta"]) if c["resposta"] is not None else None, usuario],
                )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        current_app.logger.warning("leads-v3 registro apollo (%s): %s", ", ".join(c["endpoint"] for c in registro), exc)


@bp.route("/api/contatos/<int:contato_id>/apollo-chamadas")
@centralcomm_required_api
def api_contato_apollo_chamadas(contato_id):
    """Últimas chamadas ao Apollo desta pessoa (e as buscas da empresa dela), para ver o que o Apollo devolveu."""
    def run(cursor):
        # As da pessoa e as da empresa têm limites separados: buscas repetidas não empurram as da pessoa para fora.
        cursor.execute(
            """
            (SELECT id, criado_em, endpoint, http_status, pago, erro, resumo, resposta
               FROM cadu_apollo_chamadas WHERE id_contato = %s ORDER BY criado_em DESC, id DESC LIMIT 25)
            UNION ALL
            (SELECT id, criado_em, endpoint, http_status, pago, erro, resumo, NULL::jsonb
               FROM cadu_apollo_chamadas
              WHERE id_contato IS NULL AND id_lead = (SELECT id_lead FROM cadu_lead_contatos WHERE id = %s)
              ORDER BY criado_em DESC, id DESC LIMIT 10)
            ORDER BY criado_em DESC, id DESC
            """,
            [contato_id, contato_id],
        )
        return _ok({"chamadas": _linhas(cursor.fetchall())})

    return _transacao(run, "chamadas apollo")


@bp.route("/api/leads/<int:lead_id>/apollo-checar", methods=["POST"])
@centralcomm_required_api
def api_lead_apollo_checar(lead_id):
    """Checa pela busca grátis o que o Apollo tem hoje de cada contato do Apollo deste lead. Não cobra crédito.

    Atualiza apollo_tem_email e apollo_tem_celular de quem aparece na busca. Contato sem id do Apollo
    (digitado, importado ou da web) não dá para checar sem revelar, e fica de fora."""
    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            lead, dominio = _lead_para_busca(cursor, lead_id)
            cursor.execute(
                """
                SELECT id, COALESCE(apollo_person_id, CASE WHEN origem_dado = 'apollo' THEN origem_ref END) AS apollo_id
                  FROM cadu_lead_contatos WHERE id_lead = %s
                """,
                [lead_id],
            )
            contatos = [r for r in cursor.fetchall() if r["apollo_id"]]
        conn.rollback()
    except prospeccao.ProspeccaoError as exc:
        conn.rollback()
        return _erro(str(exc), 400)
    except Exception as exc:
        conn.rollback()
        if _sqlstate(exc) in _SQLSTATE_SEM_ESQUEMA:
            return _erro("A migração do Leads v3 ainda não foi aplicada neste banco.", 503)
        current_app.logger.error("leads-v3 checar apollo: %s", exc)
        return _erro("Não foi possível checar no Apollo.", 500)
    if not dominio:
        return _erro("Preencha o site ou domínio da empresa para checar no Apollo.")
    if not contatos:
        return _ok({"checados": 0, "achados": 0, "com_email": 0, "com_celular": 0, "fora_da_busca": 0})
    registro = []
    try:
        achados = prospeccao.apollo_checar_pessoas(resolve_apollo_api_key(), dominio,
                                                   {c["apollo_id"] for c in contatos}, registro=registro)
    except prospeccao.ProspeccaoError as exc:
        return _erro(str(exc), 400)
    finally:
        _gravar_chamadas_apollo(registro, lead_id=lead_id)

    def run(cursor):
        for c in contatos:
            if c["apollo_id"] not in achados:
                continue
            tem_email, tem_celular = achados[c["apollo_id"]]
            # O que a busca diz agora vale mais que o que dizia antes; "talvez" (None) não apaga um sim/não.
            cursor.execute(
                """
                UPDATE cadu_lead_contatos
                   SET apollo_tem_email = COALESCE(%s, apollo_tem_email), apollo_tem_celular = COALESCE(%s, apollo_tem_celular)
                 WHERE id = %s
                """,
                [tem_email, tem_celular, c["id"]],
            )
        vistos = [achados[c["apollo_id"]] for c in contatos if c["apollo_id"] in achados]
        return _ok({"checados": len(contatos), "achados": len(vistos),
                    "com_email": sum(1 for e, _ in vistos if e), "com_celular": sum(1 for _, t in vistos if t),
                    "fora_da_busca": len(contatos) - len(vistos)})

    return _transacao(run, "checar apollo")


# ─────────────────────────────────────────────────────
# Celular pelo Apollo: pedido + webhook assinado
# ─────────────────────────────────────────────────────
def _assinatura_contato(contato_id):
    """HMAC do id do contato com a SECRET_KEY: só quem recebeu a URL do pedido consegue chamar o webhook."""
    chave = str(current_app.config.get("SECRET_KEY") or "").encode()
    return hmac.new(chave, f"apollo-telefone:{contato_id}".encode(), hashlib.sha256).hexdigest()[:40]


def _url_webhook_celular(contato_id):
    """URL pública fixa (LEADS_V3_WEBHOOK_BASE_URL, padrão https://ai.centralcomm.media), não o host de quem clicou:
    o Apollo precisa de um endereço HTTPS aberto e estável. Sem a configuração, cai no host da requisição."""
    caminho = url_for("leads_v3.webhook_apollo_celular", contato_id=contato_id, token=_assinatura_contato(contato_id))
    base = str(current_app.config.get("LEADS_V3_WEBHOOK_BASE_URL") or "").rstrip("/")
    return f"{base}{caminho}" if base else url_for(
        "leads_v3.webhook_apollo_celular", contato_id=contato_id, token=_assinatura_contato(contato_id), _external=True, _scheme="https")


@bp.route("/api/contatos/<int:contato_id>/celular", methods=["POST"])
@centralcomm_required_api
def api_contato_pedir_celular(contato_id):
    """Pede o celular ao Apollo; o número chega minutos depois pelo webhook.

    O pedido cobra 1 crédito pelos dados do perfil (e o e-mail que vier é guardado, já que foi pago); o celular
    só cobra se vier. Se a busca grátis disse que não há telefone, só pede com `forcar` (a tela confirma)."""
    forcar = bool((request.get_json(silent=True) or {}).get("forcar"))
    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.id_lead, c.nome, c.linkedin_url, c.origem_dado, c.origem_ref, c.apollo_person_id, c.telefone,
                       c.email, c.apollo_tem_celular, c.telefone_status, l.dominio, l.url_site
                  FROM cadu_lead_contatos c JOIN cadu_leads l ON l.id = c.id_lead WHERE c.id = %s
                """,
                [contato_id],
            )
            contato = cursor.fetchone()
        conn.rollback()
    except Exception as exc:
        conn.rollback()
        if _sqlstate(exc) in _SQLSTATE_SEM_ESQUEMA:
            return _erro("A migração do Leads v3 ainda não foi aplicada neste banco.", 503)
        current_app.logger.error("leads-v3 pedir celular: %s", exc)
        return _erro("Não foi possível pedir o celular.", 500)
    if not contato:
        return _erro("Contato não encontrado.", 404)
    if not forcar and (contato["apollo_tem_celular"] is False or contato["telefone_status"] == "sem_numero"):
        motivo = ("O Apollo já respondeu que não tem celular desta pessoa. Pedir de novo usa outro crédito."
                  if contato["telefone_status"] == "sem_numero" else
                  "Na busca, o Apollo disse que não tem telefone desta pessoa. Pedir mesmo assim usa 1 crédito.")
        return _ok({"status": None, "bloqueado": True, "motivo": motivo})
    webhook = _url_webhook_celular(contato_id)
    registro = []
    try:
        revelado = prospeccao.apollo_pedir_celular(
            resolve_apollo_api_key(), webhook, registro=registro,
            apollo_id=contato["apollo_person_id"] or (contato["origem_ref"] if contato["origem_dado"] == "apollo" else None),
            linkedin_url=contato["linkedin_url"], nome=contato["nome"],
            dominio=contato["dominio"] or prospeccao.normalizar_dominio(contato["url_site"]),
        )
    except prospeccao.ProspeccaoError as exc:
        return _erro(str(exc), 400)
    finally:
        _gravar_chamadas_apollo(registro, contato_id=contato_id)

    def run(cursor):
        # O e-mail veio junto (e foi cobrado): entra se a ficha não tem um, ou se o que tem é só palpite.
        cursor.execute(
            """
            UPDATE cadu_lead_contatos
               SET telefone_status = 'pedido', telefone_pedido_em = CURRENT_TIMESTAMP, apollo_person_id = %s,
                   apollo_revelado_em = CURRENT_TIMESTAMP,
                   email_status = CASE WHEN %s::text IS NOT NULL AND (COALESCE(email, '') = '' OR email_status = 'arriscado')
                                       THEN %s::text ELSE email_status END,
                   email = CASE WHEN %s::text IS NOT NULL AND (COALESCE(email, '') = '' OR email_status = 'arriscado')
                                THEN %s::text ELSE email END
             WHERE id = %s
            RETURNING email
            """,
            [revelado["apollo_id"], revelado.get("email"), revelado.get("email_status"),
             revelado.get("email"), revelado.get("email"), contato_id],
        )
        email = cursor.fetchone()["email"]
        if revelado.get("email") and email == revelado["email"] and email != contato["email"]:
            _registrar_atividade(cursor, contato["id_lead"], "edicao",
                                 f"E-mail de {contato['nome']} veio do Apollo junto com o pedido de celular.", contato_id)
        novo = bool(revelado.get("email")) and email == revelado["email"] and email != contato["email"]
        return _ok({"status": "pedido", "email": email if novo else None})

    return _transacao(run, "pedir celular")


@bp.route("/api/contatos/<int:contato_id>/celular-principal", methods=["PATCH"])
@centralcomm_required_api
def api_contato_celular_principal(contato_id):
    """Escolhe, entre os celulares da pessoa, o que vai para o WhatsApp (fica em telefone)."""
    numero = prospeccao.celular_br((request.get_json(silent=True) or {}).get("numero"))
    if not numero:
        return _erro("Escolha um celular.")

    def run(cursor):
        cursor.execute("SELECT id, id_lead, nome, celulares FROM cadu_lead_contatos WHERE id = %s FOR UPDATE", [contato_id])
        contato = cursor.fetchone()
        if not contato:
            return _erro("Contato não encontrado.", 404)
        if numero not in [c.get("numero") for c in contato["celulares"] or []]:
            return _erro("Este celular não está na ficha.", 409)
        cursor.execute("UPDATE cadu_lead_contatos SET telefone = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", [numero, contato_id])
        _registrar_atividade(cursor, contato["id_lead"], "edicao", f"WhatsApp de {contato['nome']} passa a ser {numero}.", contato_id)
        return _ok({"telefone": numero})

    return _transacao(run, "celular principal")


@bp.route("/webhooks/apollo/celular/<int:contato_id>", methods=["POST"])
def webhook_apollo_celular(contato_id):
    """Recebe do Apollo o celular pedido. Sem sessão: a assinatura na URL autentica."""
    token = request.args.get("token") or ""
    if not hmac.compare_digest(token, _assinatura_contato(contato_id)):
        return jsonify({"ok": False}), 403
    payload = request.get_json(silent=True) or {}
    _gravar_chamadas_apollo([prospeccao.anotar_webhook_celular(payload)], contato_id=contato_id, usuario_id=None)

    def run(cursor):
        cursor.execute("SELECT id, id_lead, nome, apollo_person_id, telefone, celulares FROM cadu_lead_contatos WHERE id = %s FOR UPDATE", [contato_id])
        contato = cursor.fetchone()
        if not contato:
            return jsonify({"ok": True})  # contato apagado depois do pedido: nada a fazer
        # Só celular: fixo e telefone da empresa ficam fora. O Apollo pode repetir a chamada, então junta sem duplicar.
        novos = prospeccao.celulares_do_webhook(payload, contato["apollo_person_id"])
        if novos:
            lista = prospeccao.juntar_celulares(contato["celulares"], novos)
            principal = contato["telefone"] if prospeccao.celular_br(contato["telefone"]) else lista[0]["numero"]
            cursor.execute(
                """
                UPDATE cadu_lead_contatos
                   SET telefone = %s, celulares = %s, telefone_status = 'encontrado', enriquecido_em = CURRENT_TIMESTAMP
                 WHERE id = %s
                """,
                [principal, db.Json(lista), contato_id],
            )
            chegaram = len(lista) - len(contato["celulares"] or [])
            if chegaram:
                texto = f"Celular de {contato['nome']} encontrado" if chegaram == 1 else f"{chegaram} celulares de {contato['nome']} encontrados"
                cursor.execute(
                    """
                    INSERT INTO cadu_lead_atividades (id_lead, tipo, descricao, id_contato, usuario_nome)
                    VALUES (%s, 'edicao', %s, %s, 'Apollo')
                    """,
                    [contato["id_lead"], f"{texto} no Apollo.", contato_id],
                )
        elif not contato["celulares"]:
            cursor.execute("UPDATE cadu_lead_contatos SET telefone_status = 'sem_numero' WHERE id = %s", [contato_id])
        else:
            cursor.execute("UPDATE cadu_lead_contatos SET telefone_status = 'encontrado' WHERE id = %s", [contato_id])
        return jsonify({"ok": True})

    return _transacao(run, "webhook celular apollo")


# ─────────────────────────────────────────────────────
# Análise semanal: site × equipe × executivos
# ─────────────────────────────────────────────────────
TIPOS_HUMANOS = ("ligacao", "whatsapp", "email_enviado", "reuniao", "follow_up", "apresentacao", "proposta_enviada", "nota")


def _semanas(inicio, fim):
    """Segundas-feiras de inicio..fim (semana ISO), para preencher semanas sem movimento com zero."""
    from datetime import timedelta
    seg = inicio - timedelta(days=inicio.weekday())
    out = []
    while seg <= fim:
        out.append(seg.isoformat())
        seg += timedelta(days=7)
    return out


@bp.route("/api/analise/semanal")
@centralcomm_required_api
def api_analise_semanal():
    from datetime import timedelta
    hoje = date.today()
    try:
        fim = date.fromisoformat(request.args.get("data_fim") or hoje.isoformat())
        inicio = date.fromisoformat(request.args.get("data_inicio") or (fim - timedelta(weeks=12)).isoformat())
    except ValueError:
        return _erro("Data inválida.")
    if inicio > fim or (fim - inicio).days > 400:
        return _erro("Período inválido (máximo de 400 dias).")
    executivo = _int(request.args.get("id_executivo"))
    p = {"inicio": inicio, "fim": fim + timedelta(days=1), "executivo": executivo, "tipos": list(TIPOS_HUMANOS)}

    def run(cursor):
        semanas = _semanas(inicio, fim)
        filtro_lead = "AND l.id_executivo = %(executivo)s" if executivo else ""
        # Leads do site por semana de entrada (o estado atual mostra o que aconteceu com cada leva).
        cursor.execute(
            f"""
            SELECT date_trunc('week', l.created_at)::date AS semana, COUNT(*) AS entraram,
                   COUNT(*) FILTER (WHERE l.status NOT IN ('inbox', 'nao_qualificado')) AS avancaram,
                   COUNT(*) FILTER (WHERE l.status = 'nao_qualificado') AS desqualificados,
                   COUNT(*) FILTER (WHERE l.convertido_cliente_id IS NOT NULL OR l.status = 'fechado_ganho') AS convertidos,
                   COUNT(*) FILTER (WHERE l.id_executivo IS NULL) AS sem_responsavel
              FROM cadu_leads l
             WHERE l.fonte = 'site' AND l.created_at >= %(inicio)s AND l.created_at < %(fim)s {filtro_lead}
             GROUP BY 1
            """,
            p,
        )
        site = {r["semana"].isoformat(): r for r in cursor.fetchall()}
        # Leads adicionados pela equipe (qualquer fonte que não seja o site), por executivo e semana.
        cursor.execute(
            f"""
            SELECT date_trunc('week', l.created_at)::date AS semana, l.id_executivo, COUNT(*) AS n
              FROM cadu_leads l
             WHERE COALESCE(l.fonte, '') <> 'site' AND l.created_at >= %(inicio)s AND l.created_at < %(fim)s {filtro_lead}
             GROUP BY 1, 2
            """,
            p,
        )
        adicionados = cursor.fetchall()
        # Atividades registradas pelo executivo (sem os eventos automáticos).
        filtro_usuario = "AND a.id_usuario = %(executivo)s" if executivo else ""
        cursor.execute(
            f"""
            SELECT date_trunc('week', a.created_at)::date AS semana, a.id_usuario AS id_executivo, COUNT(*) AS n
              FROM cadu_lead_atividades a
             WHERE a.tipo = ANY(%(tipos)s) AND a.id_usuario IS NOT NULL
               AND a.created_at >= %(inicio)s AND a.created_at < %(fim)s {filtro_usuario}
               -- Os registros que a cadência grava (início e passos) já contam como toques.
               AND a.descricao NOT LIKE 'Cadência %% iniciada%%' AND a.descricao NOT LIKE '%%(cadência %%'
             GROUP BY 1, 2
            """,
            p,
        )
        atividades = cursor.fetchall()
        # Toques e respostas de cadência, pelo executivo da inscrição.
        filtro_insc = "AND COALESCE(i.id_executivo, l.id_executivo) = %(executivo)s" if executivo else ""
        cursor.execute(
            f"""
            SELECT date_trunc('week', e.ocorreu_em)::date AS semana, COALESCE(i.id_executivo, l.id_executivo) AS id_executivo,
                   COUNT(*) FILTER (WHERE e.evento = 'tarefa_feita') AS toques,
                   COUNT(*) FILTER (WHERE e.evento = 'respondeu') AS respostas
              FROM cadu_lead_mensagem_eventos e
              JOIN cadu_leads l ON l.id = e.id_lead
              LEFT JOIN cadu_lead_cadencia_inscricoes i ON i.id = e.id_inscricao
             WHERE e.ocorreu_em >= %(inicio)s AND e.ocorreu_em < %(fim)s {filtro_insc}
             GROUP BY 1, 2
            """,
            p,
        )
        cadencia = cursor.fetchall()

        def zero_site():
            return {"entraram": 0, "avancaram": 0, "desqualificados": 0, "convertidos": 0, "sem_responsavel": 0}

        serie_site = [{"semana": s, **{k: int(v) for k, v in (site.get(s) or zero_site()).items() if k != "semana"}} for s in semanas]
        por_exec = {}

        def soma(rows, campo_origem, campo_destino):
            for r in rows:
                chave = r["id_executivo"]
                linha = por_exec.setdefault(chave, {m: {s: 0 for s in semanas} for m in ("adicionados", "atividades", "toques", "respostas")})
                semana = r["semana"].isoformat()
                if semana in linha[campo_destino]:
                    linha[campo_destino][semana] += int(r[campo_origem] or 0)

        soma(adicionados, "n", "adicionados")
        soma(atividades, "n", "atividades")
        soma(cadencia, "toques", "toques")
        soma(cadencia, "respostas", "respostas")
        executivos = [{"id_executivo": k, **{m: [v[s] for s in semanas] for m, v in linhas.items()}}
                      for k, linhas in por_exec.items()]
        equipe = [sum(int(r["n"]) for r in adicionados if r["semana"].isoformat() == s) for s in semanas]
        return _ok({"semanas": semanas, "site": serie_site, "adicionados_equipe": equipe, "executivos": executivos})

    return _transacao(run, "análise semanal")
