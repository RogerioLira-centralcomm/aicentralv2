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
    leads.sort(key=lambda l: not l["golden"])  # estável: Golden Circle no topo, resto na ordem do dashboard
    return _ok({"leads": leads, "total": len(leads)})


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


def _candidatos(cursor, lead_id):
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
    return [{k: _json_safe(v) for k, v in dict(r).items()} for r in cursor.fetchall()]


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
    try:
        with conn.cursor() as cursor:
            lead, dominio = _lead_para_busca(cursor, lead_id)
        conn.rollback()  # só leitura; libera a conexão antes da chamada externa
        if fonte == "apollo":
            if not dominio:
                raise prospeccao.ProspeccaoError("Preencha o site ou domínio da empresa para buscar no Apollo.")
            encontrados, total = prospeccao.apollo_buscar_pessoas(resolve_apollo_api_key(), dominio)
        else:
            encontrados, total = prospeccao.web_buscar_pessoas(resolve_firecrawl_api_key(), lead["empresa"] or lead["nome"]), None
    except prospeccao.ProspeccaoError as exc:
        return _erro(str(exc), 400)

    def run(cursor):
        cursor.execute("SELECT lower(nome) AS nome, lower(COALESCE(linkedin_url, '')) AS linkedin FROM cadu_lead_contatos WHERE id_lead = %s", [lead_id])
        existentes = cursor.fetchall()
        nomes = {r["nome"] for r in existentes}
        linkedins = {r["linkedin"] for r in existentes if r["linkedin"]}
        inseridos = 0
        for c in encontrados:
            if not c.get("provedor_ref") or c["nome"].lower() in nomes or (c.get("linkedin_url") or "").lower() in linkedins:
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
    """aprovar (vira contato; com revelar=true, gasta crédito do Apollo) ou descartar."""
    if acao not in ("aprovar", "descartar"):
        return _erro("Ação inválida.", 404)
    payload = request.get_json(silent=True) or {}

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

        revelado = {}
        if payload.get("revelar") and cand["provedor"] == "apollo":
            revelado = prospeccao.apollo_revelar(resolve_apollo_api_key(), apollo_id=cand["provedor_ref"])
        papel = payload.get("papel") if payload.get("papel") in dict(PAPEIS) else cand["papel_sugerido"]
        cursor.execute(
            """
            INSERT INTO cadu_lead_contatos
                (id_lead, nome, cargo, email, papel, senioridade, linkedin_url, origem_dado, origem_ref,
                 email_status, enriquecido_em, adicionado_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            [cand["id_lead"], (revelado.get("nome") or cand["nome"])[:200], (revelado.get("cargo") or cand["cargo"] or "")[:150] or None,
             revelado.get("email"), papel, cand["senioridade_sugerida"],
             revelado.get("linkedin_url") or cand["linkedin_url"], cand["provedor"], cand["provedor_ref"],
             revelado.get("email_status"), datetime.now() if revelado else None, session.get("user_id")],
        )
        contato_id = cursor.fetchone()["id"]
        cursor.execute(
            """
            UPDATE cadu_lead_contato_candidatos
               SET status = 'aprovado', id_contato = %s, email = %s, revisado_por = %s, revisado_em = NOW()
             WHERE id = %s
            """,
            [contato_id, revelado.get("email"), session.get("user_id"), candidato_id],
        )
        origem = "Apollo" if cand["provedor"] == "apollo" else "busca na web"
        _registrar_atividade(cursor, cand["id_lead"], "contato_add", f"Contato adicionado via {origem}: {cand['nome']}", contato_id)
        return _ok({"id_contato": contato_id, "email": revelado.get("email"), "revelado": bool(revelado)}, 201)

    return _transacao(run, f"candidato {acao}")


@bp.route("/api/contatos/<int:contato_id>/revelar", methods=["POST"])
@centralcomm_required_api
def api_contato_revelar(contato_id):
    """Busca e-mail e LinkedIn do contato no Apollo (consome crédito do plano)."""
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
        dominio = contato["dominio"] or prospeccao.normalizar_dominio(contato["url_site"])
        revelado = prospeccao.apollo_revelar(
            resolve_apollo_api_key(),
            apollo_id=contato["origem_ref"] if contato["origem_dado"] == "apollo" else None,
            linkedin_url=contato["linkedin_url"], nome=contato["nome"], dominio=dominio,
        )
        nome = revelado.get("nome") if revelado.get("nome") and "*" in (contato["nome"] or "") else contato["nome"]
        cursor.execute(
            """
            UPDATE cadu_lead_contatos
               SET nome = %s, email = COALESCE(%s, email), email_status = COALESCE(%s, email_status),
                   linkedin_url = COALESCE(linkedin_url, %s), cargo = COALESCE(cargo, %s),
                   enriquecido_em = CURRENT_TIMESTAMP
             WHERE id = %s
            """,
            [nome, revelado.get("email"), revelado.get("email_status"), revelado.get("linkedin_url"),
             revelado.get("cargo"), contato_id],
        )
        return _ok({"email": revelado.get("email"), "linkedin_url": revelado.get("linkedin_url"),
                    "encontrou_email": bool(revelado.get("email")), "motivo": revelado.get("motivo")})

    return _transacao(run, "revelar contato")


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
    """Inscreve todas as pessoas do lead que ainda não têm cadência ativa ou pausada (modelo pelo papel)."""
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
                                                   usuario_nome=session.get("user_name")) for cid in ids) if i]
        return _ok({"inscritas": len(criadas)}, 201 if criadas else 200)

    return _transacao(run, "inscrever lead")


@bp.route("/api/inscricoes/<int:inscricao_id>/<acao>", methods=["POST"])
@centralcomm_required_api
def api_inscricao_acao(inscricao_id, acao):
    """feito | pular | respondeu | pausar | retomar | cancelar."""
    if acao not in cadencias.ACOES:
        return _erro("Ação inválida.", 404)
    nota = str((request.get_json(silent=True) or {}).get("nota") or "")[:300]

    def run(cursor):
        estado = cadencias.avancar(cursor, inscricao_id, acao, usuario_id=session.get("user_id"),
                                   usuario_nome=session.get("user_name"), nota=nota)
        return _ok({k: _json_safe(v) for k, v in estado.items()})

    return _transacao(run, f"cadência {acao}")


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
# Operação: mensagens personalizadas, contexto de mercado e tarefas
# ─────────────────────────────────────────────────────
@bp.route("/api/mensagens/gerar", methods=["POST"])
@centralcomm_required_api
def api_gerar_mensagem():
    """Mensagem para uma pessoa num canal e etapa (topo/meio), com foco, contexto e histórico da empresa."""
    payload = request.get_json(silent=True) or {}
    contato_id = _int(payload.get("id_contato"))
    if not contato_id:
        return _erro("Escolha a pessoa.")
    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
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
                conn.rollback()
                return _erro("Contato não encontrado.", 404)
            cursor.execute(
                """
                SELECT descricao FROM cadu_lead_atividades
                 WHERE id_lead = %s AND tipo NOT IN ('status_change', 'atribuicao', 'edicao', 'importacao')
                 ORDER BY created_at DESC LIMIT 6
                """,
                [row["id_lead"]],
            )
            historico = [r["descricao"] for r in cursor.fetchall()]
        conn.rollback()
    except Exception as exc:
        conn.rollback()
        if _sqlstate(exc) in _SQLSTATE_SEM_ESQUEMA:
            return _erro("A migração do Leads v3 ainda não foi aplicada neste banco.", 503)
        current_app.logger.error("leads-v3 gerar mensagem: %s", exc)
        return _erro("Não foi possível preparar a mensagem.", 500)

    contexto = (row["contexto_mercado"] or {}).get("texto") if isinstance(row["contexto_mercado"], dict) else None
    try:
        resultado = mensagens.gerar_mensagem(
            mensagens.resolve_openrouter_key(),
            canal=payload.get("canal") or "email", etapa=payload.get("etapa") or "topo",
            objetivo=str(payload.get("objetivo") or "").strip()[:400],
            pessoa={"nome": row["nome"], "cargo": row["cargo"], "papel": row["papel"]},
            empresa={"nome": row["empresa"], "segmento": row["segmento"], "descricao": row["descricao_empresa"],
                     "oportunidades_midia": row["oportunidades_midia"]},
            foco=mensagens._resumo_foco(row["foco_conteudo"]), contexto=contexto, historico=historico,
            remetente=session.get("user_name"),
        )
    except prospeccao.ProspeccaoError as exc:
        return _erro(str(exc), 400)
    return _ok(resultado)


@bp.route("/api/leads/<int:lead_id>/contexto", methods=["POST"])
@centralcomm_required_api
def api_contexto_mercado(lead_id):
    """Pesquisa na web (Sonar) notícias, campanhas e tendências da empresa; guarda com as fontes."""
    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COALESCE(empresa, nome) AS empresa, dominio, url_site, segmento FROM cadu_leads WHERE id = %s", [lead_id])
            lead = cursor.fetchone()
        conn.rollback()
    except Exception as exc:
        conn.rollback()
        if _sqlstate(exc) in _SQLSTATE_SEM_ESQUEMA:
            return _erro("A migração do Leads v3 ainda não foi aplicada neste banco.", 503)
        return _erro("Não foi possível ler o lead.", 500)
    if not lead:
        return _erro("Lead não encontrado.", 404)
    try:
        contexto = mensagens.gerar_contexto_mercado(
            mensagens.resolve_openrouter_key(), empresa=lead["empresa"],
            dominio=lead["dominio"] or prospeccao.normalizar_dominio(lead["url_site"]), segmento=lead["segmento"])
    except prospeccao.ProspeccaoError as exc:
        return _erro(str(exc), 400)

    def run(cursor):
        cursor.execute("UPDATE cadu_leads SET contexto_mercado = %s WHERE id = %s", [db.Json(contexto), lead_id])
        return _ok(contexto)

    return _transacao(run, "contexto de mercado")


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
                    "feitos": _linhas(cadencias.feitos_hoje(cursor, executivo=executivo))})

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
        return _ok({"canais": canais, "inscricoes": inscricoes, "golden": {**golden, "trimestre": trimestre}})

    return _transacao(run, "análise v3")


# ─────────────────────────────────────────────────────
# Celular pelo Apollo: pedido + webhook assinado
# ─────────────────────────────────────────────────────
def _assinatura_contato(contato_id):
    """HMAC do id do contato com a SECRET_KEY: só quem recebeu a URL do pedido consegue chamar o webhook."""
    chave = str(current_app.config.get("SECRET_KEY") or "").encode()
    return hmac.new(chave, f"apollo-telefone:{contato_id}".encode(), hashlib.sha256).hexdigest()[:40]


@bp.route("/api/contatos/<int:contato_id>/celular", methods=["POST"])
@centralcomm_required_api
def api_contato_pedir_celular(contato_id):
    """Pede o celular ao Apollo; o número chega minutos depois pelo webhook."""
    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.nome, c.linkedin_url, c.origem_dado, c.origem_ref, c.apollo_person_id, c.telefone,
                       l.dominio, l.url_site
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
    webhook = url_for("leads_v3.webhook_apollo_celular", contato_id=contato_id, token=_assinatura_contato(contato_id),
                      _external=True, _scheme="https")
    try:
        apollo_id = prospeccao.apollo_pedir_celular(
            resolve_apollo_api_key(), webhook,
            apollo_id=contato["apollo_person_id"] or (contato["origem_ref"] if contato["origem_dado"] == "apollo" else None),
            linkedin_url=contato["linkedin_url"], nome=contato["nome"],
            dominio=contato["dominio"] or prospeccao.normalizar_dominio(contato["url_site"]),
        )
    except prospeccao.ProspeccaoError as exc:
        return _erro(str(exc), 400)

    def run(cursor):
        cursor.execute(
            """
            UPDATE cadu_lead_contatos
               SET telefone_status = 'pedido', telefone_pedido_em = CURRENT_TIMESTAMP, apollo_person_id = %s
             WHERE id = %s
            """,
            [apollo_id, contato_id],
        )
        return _ok({"status": "pedido"})

    return _transacao(run, "pedir celular")


@bp.route("/webhooks/apollo/celular/<int:contato_id>", methods=["POST"])
def webhook_apollo_celular(contato_id):
    """Recebe do Apollo o celular pedido. Sem sessão: a assinatura na URL autentica."""
    token = request.args.get("token") or ""
    if not hmac.compare_digest(token, _assinatura_contato(contato_id)):
        return jsonify({"ok": False}), 403
    payload = request.get_json(silent=True) or {}

    def run(cursor):
        cursor.execute("SELECT id, id_lead, nome, apollo_person_id FROM cadu_lead_contatos WHERE id = %s FOR UPDATE", [contato_id])
        contato = cursor.fetchone()
        if not contato:
            return jsonify({"ok": True})  # contato apagado depois do pedido: nada a fazer
        achado = prospeccao.melhor_celular(payload, contato["apollo_person_id"])
        if achado:
            cursor.execute(
                """
                UPDATE cadu_lead_contatos
                   SET telefone = CASE WHEN COALESCE(telefone, '') = '' THEN %s ELSE telefone END,
                       telefone_status = 'encontrado', enriquecido_em = CURRENT_TIMESTAMP
                 WHERE id = %s
                """,
                [achado["numero"], contato_id],
            )
            tipo = "celular" if achado["tipo"] == "mobile" else "telefone direto"
            cursor.execute(
                """
                INSERT INTO cadu_lead_atividades (id_lead, tipo, descricao, id_contato, usuario_nome)
                VALUES (%s, 'edicao', %s, %s, 'Apollo')
                """,
                [contato["id_lead"], f"{tipo.capitalize()} de {contato['nome']} encontrado no Apollo.", contato_id],
            )
        else:
            cursor.execute("UPDATE cadu_lead_contatos SET telefone_status = 'sem_numero' WHERE id = %s", [contato_id])
        return jsonify({"ok": True})

    return _transacao(run, "webhook celular apollo")
