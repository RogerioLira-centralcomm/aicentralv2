"""CRM v3 — rotas de API e página.

Fase 3 (auth): todas as rotas exigem sessão. A página `/crm-v3/` usa
`@login_required` (redireciona para /login); os endpoints `/crm-v3/api/*` usam
`@login_required_api` (retornam 401 JSON) para permitir chamadas fetch.
"""

from flask import Blueprint, current_app, g, jsonify, render_template, request, session, url_for

from .auth import admin_required_api, login_required, login_required_api
from .cotacao_tipos import normalizar_tipo_comercial
from .crm_v3_helpers import normalizar_telefone, parse_texto_contatos, texto_sem_markdown
from .crm_v3_repository import StoreUnavailable, get_store, store_diagnostic


class _LazyStore:
    """Proxy que resolve o store por request (via Flask `g`).

    Motivos para não segurar `store = get_store()` no import:
    - Se o smoke test falhar durante o boot do worker (banco ainda
      subindo, alguma coluna faltando), o processo travaria em erro
      até restart. Com o proxy, cada request reavalia — a recuperação
      é automática assim que o banco volta.
    - Debug fica mais transparente: o diagnostic é preenchido no request
      atual e reflete o que o usuário está vendo agora.

    Se `get_store()` lançar `StoreUnavailable`, o proxy propaga a
    exceção para o handler que traduz em 503 (nunca mais mascara com
    mock em produção).
    """

    def __getattr__(self, name):
        try:
            if not hasattr(g, "_crm_v3_store"):
                g._crm_v3_store = get_store()
            return getattr(g._crm_v3_store, name)
        except StoreUnavailable:
            # Propaga direto para o @bp.errorhandler(StoreUnavailable) —
            # antes o `except RuntimeError` abaixo capturava por acidente
            # (StoreUnavailable herda de RuntimeError) e tentava resolver
            # o store de novo, gerando confusão nos logs.
            raise
        except RuntimeError:
            # `flask.g` só existe dentro de contexto de request.
            return getattr(get_store(), name)


store = _LazyStore()


def _store_unavailable_response(exc: StoreUnavailable):
    """Traduz `StoreUnavailable` em 503 JSON com o motivo.

    Formato compatível com `_err(...)` mas HTTP 503 (Service Unavailable):
    o frontend detecta e mostra banner "Banco indisponível" em vez de
    renderizar clientes fictícios.
    """
    diag = store_diagnostic()
    return jsonify({
        "success": False,
        "error": "Banco indisponível. O CRM v3 e o CRM legado usam a mesma base — verifique o Postgres.",
        "reason": diag.get("reason"),
        "db_error": diag.get("db_error") or str(exc),
        "store_unavailable": True,
    }), 503

bp = Blueprint("crm_v3", __name__, url_prefix="/crm-v3")


@bp.errorhandler(StoreUnavailable)
def _handle_store_unavailable(exc):
    """Handler central: qualquer rota do CRM v3 que falhar ao acessar
    o banco cai aqui. Para APIs devolvemos 503 JSON; para a página
    HTML renderizamos o `crm_v3.html` com o banner de erro visível
    (o template já trata `store_mode='unavailable'`).
    """
    if request.path.startswith("/crm-v3/api/"):
        return _store_unavailable_response(exc)
    # Página HTML: render sem executivos e com banner de erro.
    diag = store_diagnostic()
    return render_template(
        "crm_v3.html",
        executivos=[],
        usuario_atual=_executivo_from_session(),
        store_mode="unavailable",
        store_diag=diag,
    ), 503


@bp.errorhandler(Exception)
def _handle_any_exception(exc):
    """Handler defensivo (set/2026): converte qualquer erro do CRM v3
    em um 500 informativo E grava o traceback no log da aplicação.

    Antes um 500 do repository podia sumir silenciosamente porque o
    Flask, em produção, esconde tracebacks. Agora todo 500 do CRM v3:
      - vira uma entrada `ERROR` completa em `logs/aicentral.log`
      - retorna JSON com `error_type` (para clientes API)
      - continua renderizando a página com banner de erro (para HTML)

    HTTPExceptions (401, 403, 404) são deixadas passar para o handler
    padrão do Flask — não queremos transformar auth-required em 500.
    """
    from werkzeug.exceptions import HTTPException
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, StoreUnavailable):
        return _handle_store_unavailable(exc)

    import logging
    import traceback as _tb
    tb_str = _tb.format_exc()
    logging.getLogger("aicentral.crm_v3").error(
        "[crm_v3] 500 em %s %s: %s\n%s",
        request.method, request.path, exc, tb_str,
    )
    # Também escreve no stderr — durante `python3 run.py` em dev o
    # traceback aparece direto no terminal do Flask.
    import sys as _sys
    print(f"[crm_v3] 500 em {request.method} {request.path}: {exc}", file=_sys.stderr)
    print(tb_str, file=_sys.stderr)

    is_admin = session.get("user_type") in ("admin", "superadmin")
    if request.path.startswith("/crm-v3/api/"):
        payload = {
            "success": False,
            "error": "Erro interno no CRM v3. Verifique os logs.",
            "error_type": type(exc).__name__,
        }
        if is_admin:
            # Para admin, incluímos a mensagem exata e a última linha do
            # traceback para diagnosticar sem abrir o log do gunicorn.
            payload["error_message"] = str(exc)[:500]
            payload["traceback_tail"] = "\n".join(tb_str.splitlines()[-8:])
        return jsonify(payload), 500

    # Página HTML: renderiza com banner de erro. Reaproveita o mesmo
    # template usado quando o banco está indisponível.
    diag = store_diagnostic()
    diag = dict(diag)
    diag["db_error"] = f"{type(exc).__name__}: {str(exc)[:240]}"
    return render_template(
        "crm_v3.html",
        executivos=[],
        usuario_atual=_executivo_from_session(),
        store_mode="unavailable",
        store_diag=diag,
    ), 500


def _executivo_from_session():
    """Retorna dict {'id', 'nome'} do usuário logado, ou defaults do mock.

    Usado como executivo/responsável padrão em criação de atividade/objetivo/nota.
    """
    return {
        "id": session.get("user_id"),
        "nome": session.get("user_name") or session.get("user_email") or "Executivo",
    }


def _can_access_crm_v3():
    """Regra mínima de acesso: precisa ter sessão. Restringir por is_centralcomm
    ou tipo de usuário é feito na camada de repositório (Fase 3).
    """
    return "user_id" in session


def _ok(data=None, **extra):
    body = {"success": True}
    if data is not None:
        body["data"] = data
    body.update(extra)
    return jsonify(body)


def _err(message, status=400):
    return jsonify({"success": False, "error": message}), status


def _cotacao_redirect_url(cotacao):
    if not cotacao or not cotacao.get("id"):
        return None
    try:
        return url_for("cotacoes.cotacao_abrir", cotacao_id=cotacao["id"])
    except Exception:  # blueprint reduzido em testes e desenvolvimento
        return f"/cotacoes/{cotacao['id']}/abrir"


def _cotacao_com_url(cotacao):
    if not isinstance(cotacao, dict):
        return cotacao
    cotacao["detalhes_url"] = _cotacao_redirect_url(cotacao)
    return cotacao


@bp.route("/")
@login_required
def crm_v3():
    # Executivos reais para o combo do topo. Ver docs/crm-v3-api.md.
    # Falha em silêncio (lista vazia) se o Postgres não estiver acessível —
    # o template ainda renderiza e o usuário só vê "Executivo: todos".
    executivos = []
    try:
        from . import db as _db  # import lazy para permitir ambientes sem libpq
        executivos = _db.obter_vendedores_centralcomm() or []
    except Exception:  # noqa: BLE001 — best effort para não quebrar a página
        executivos = []
    # Usuário logado é o executivo "default" do combo. O JS usa esse valor
    # para pré-selecionar a base de clientes dele quando não há preferência
    # anterior no localStorage.
    usuario_atual = _executivo_from_session()
    # Força o proxy a resolver o store agora, para preencher o
    # diagnostic (mode/reason) já disponível no primeiro render.
    try:
        store.list_clientes  # noqa: B018 — acessa lazy pra disparar smoke test
    except Exception:  # noqa: BLE001
        pass
    diag = store_diagnostic()
    return render_template(
        "crm_v3.html",
        executivos=executivos,
        usuario_atual=usuario_atual,
        store_mode=diag.get("mode") or "unknown",
        store_diag=diag,
    )


@bp.route("/api/_debug/store")
@admin_required_api
def api_debug_store():
    """Retorna o diagnóstico atual do store do CRM v3.

    Uso: abrir /crm-v3/api/_debug/store logado como admin para saber se
    o CRM está servindo dados do banco real ou do mock, e por quê.
    A intenção é dar ao time comercial/operações uma resposta imediata
    quando aparecem "clientes fictícios" na tela em vez de investigar
    logs do gunicorn.
    """
    # Força uma resolução fresca (não pega o cache do request atual).
    fresh = get_store()
    diag = store_diagnostic()
    sample = []
    try:
        clientes = fresh.list_clientes() or []
        sample = [
            {
                "id": c.get("id"),
                "nome": c.get("nome"),
                "responsavel": c.get("responsavel"),
            }
            for c in clientes[:3]
        ]
    except Exception as e:  # noqa: BLE001
        diag["list_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    return _ok(diag, sample=sample, total_sample=len(sample))


@bp.route("/api/clientes")
@login_required_api
def api_clientes():
    clientes = store.list_clientes()
    return _ok(clientes, clientes=clientes)


@bp.route("/api/lookups")
@login_required_api
def api_lookups():
    """Agregador dos combos "de dominio" usados pelos drawers/modais.

    Consolidação de set/2026: antes cada combo estava hardcoded no
    template (tipos, UF, executivos "Luisa Santana", etc.). Agora um
    único GET traz tudo em uma resposta cacheável no cliente.

    Response:
      { tipos_cliente, estados, setores, cargos, executivos,
        plataformas, classificacoes }
    """
    data = store.list_lookups()
    # Achata tudo no root do body (`body.tipos_cliente`, etc). O JS
    # lê direto sem indireção — vale para todos os drawers/modais.
    return _ok(**data)


@bp.route("/api/agencias")
@login_required_api
def api_agencias():
    """Lista TODAS as agências reais da base (não paginado).

    Usada pelo drawer 'Editar cliente' → seção "Vínculos com agência"
    para popular o <select>. Antes o frontend derivava a lista de
    state.clientes (paginado), o que fazia aparecer só 2-3 agências
    mesmo quando a base tinha dezenas.
    """
    agencias = store.list_agencias()
    return _ok(agencias, agencias=agencias)


@bp.route("/api/clientes/<cliente_id>")
@login_required_api
def api_cliente_detail(cliente_id):
    cliente = store.get_cliente(cliente_id)
    if not cliente:
        return _err("Cliente não encontrado", 404)
    return _ok(cliente, cliente=cliente)


@bp.route("/api/agencia/<agencia_id>/clientes")
@login_required_api
def api_agencia_clientes(agencia_id):
    """Lista clientes finais vinculados a uma agência (paridade com /crm)."""
    cliente = store.get_cliente(agencia_id)
    if not cliente:
        return _err("Agência não encontrada", 404)
    if not cliente.get("is_agencia"):
        return _err("Cliente informado não é agência", 400)
    filhos_ids = cliente.get("clientes_finais_ids") or []
    filhos = [store.get_cliente(fid) for fid in filhos_ids]
    filhos = [f for f in filhos if f]
    return _ok(filhos, clientes=filhos, total=len(filhos))


@bp.route(
    "/api/agencias/<agencia_id>/clientes/<cliente_id>",
    methods=["POST", "DELETE"],
)
@login_required_api
def api_agencia_cliente_vinculo(agencia_id, cliente_id):
    """Inclui ou retira um cliente final da carteira da agência."""
    try:
        payload = store.set_agencia_cliente_vinculo(
            agencia_id, cliente_id, request.method == "POST"
        )
        return _ok(
            payload,
            agencia=payload["agencia"],
            cliente=payload["cliente"],
            clientes=payload["clientes"],
            total=len(payload["clientes"]),
        )
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/cep/<cep>")
@login_required_api
def api_cep(cep):
    """Proxy autenticado do ViaCEP — mesma fonte do cadastro de
    clientes (`cliente_form.js` / `clientes.html`).
    """
    digits = "".join(ch for ch in (cep or "") if ch.isdigit())
    if len(digits) != 8 or digits == digits[0] * 8:
        return _err("CEP inválido")
    import requests
    try:
        resp = requests.get(
            "https://viacep.com.br/ws/{}/json/".format(digits),
            timeout=8,
        )
        data = resp.json() if resp.ok else {}
    except Exception:  # noqa: BLE001
        return _err("Não foi possível consultar o CEP", 502)
    if not isinstance(data, dict) or data.get("erro"):
        return _err("CEP não encontrado", 404)
    return _ok({
        "cep": digits,
        "logradouro": data.get("logradouro") or "",
        "bairro": data.get("bairro") or "",
        "cidade": data.get("localidade") or "",
        "uf": (data.get("uf") or "").upper(),
        "complemento": data.get("complemento") or "",
    })


@bp.route("/api/clientes", methods=["POST"])
@login_required_api
def api_create_cliente():
    try:
        data = request.get_json(silent=True) or {}
        cliente = store.create_cliente(data)
        return _ok(cliente, cliente=cliente), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/clientes/<cliente_id>", methods=["PATCH"])
@login_required_api
def api_update_cliente(cliente_id):
    try:
        cliente = store.update_cliente(cliente_id, request.get_json(silent=True) or {})
        if cliente is None:
            return _err("Cliente não encontrado", 404)
        return _ok(cliente, cliente=cliente)
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/clientes/<cliente_id>/contatos")
@login_required_api
def api_contatos(cliente_id):
    contatos = store.list_contatos(cliente_id)
    if contatos is None:
        return _err("Cliente não encontrado", 404)
    return _ok(contatos, contatos=contatos)


@bp.route("/api/clientes/<cliente_id>/contatos", methods=["POST"])
@login_required_api
def api_create_contato(cliente_id):
    try:
        data = request.get_json(silent=True) or {}
        contato = store.create_contato(cliente_id, data)
        if contato is None:
            return _err("Cliente não encontrado", 404)
        return _ok(contato, contato=contato), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/contatos/<contato_id>", methods=["PATCH"])
@login_required_api
def api_update_contato(contato_id):
    data = request.get_json(silent=True) or {}
    contato, cliente_id = store.update_contato(contato_id, data)
    if not contato:
        return _err("Contato não encontrado", 404)
    return _ok(contato, contato=contato, cliente_id=cliente_id)


@bp.route("/api/clientes/<cliente_id>/atividades")
@login_required_api
def api_atividades(cliente_id):
    items = store.list_atividades(cliente_id)
    if items is None:
        return _err("Cliente não encontrado", 404)
    return _ok(items, atividades=items)


def _meeting_draft(activity, payload):
    from datetime import datetime, timedelta
    from email.utils import parseaddr
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    if activity.get("tipo") != "reuniao":
        raise ValueError("A agenda Google exige uma atividade do tipo reunião.")
    date_value = activity.get("data")
    time_value = activity.get("hora")
    if not date_value or not time_value:
        raise ValueError("Informe data e hora para agendar a reunião.")
    timezone = str(payload.get("timezone") or "America/Sao_Paulo").strip()
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Fuso horário inválido.") from exc
    try:
        starts_at = datetime.fromisoformat(f"{date_value}T{time_value}").replace(tzinfo=tz)
        duration = int(payload.get("duration_minutes") or 30)
    except (TypeError, ValueError) as exc:
        raise ValueError("Data, hora ou duração inválida.") from exc
    if duration < 15 or duration > 480:
        raise ValueError("A duração deve ficar entre 15 e 480 minutos.")

    attendees = []
    seen = set()
    for raw in (payload.get("attendees") or [])[:50]:
        if not isinstance(raw, dict):
            continue
        email = parseaddr(str(raw.get("email") or "").strip())[1].lower()
        if not email or "@" not in email or email in seen:
            continue
        seen.add(email)
        source = raw.get("source") if raw.get("source") in (
            "contact", "manual", "internal"
        ) else "manual"
        attendees.append({
            "name": texto_sem_markdown(raw.get("name") or "").strip()[:255],
            "email": email[:320],
            "source": source,
        })
    return store.save_activity_meeting(
        activity["id"],
        session["user_id"],
        starts_at,
        starts_at + timedelta(minutes=duration),
        timezone,
        attendees,
    )


def _sync_meeting(activity, meeting):
    from .services import google_calendar

    if str(meeting.get("user_id")) != str(session.get("user_id")):
        raise PermissionError("Somente o organizador pode sincronizar esta reunião.")
    connection = store.get_google_connection(session["user_id"], include_token=True)
    if not connection or connection.get("status") != "connected":
        return store.update_activity_meeting_sync(
            activity["id"], "error",
            error="Conecte o Google Calendar no seu perfil para criar o Meet.",
        )
    store.update_activity_meeting_sync(activity["id"], "syncing", error=None)
    try:
        result = google_calendar.sync_event(
            activity, meeting, connection["encrypted_refresh_token"]
        )
        return store.update_activity_meeting_sync(
            activity["id"],
            "synced",
            event_id=result["event_id"],
            meet_url=result.get("meet_url"),
            error=None,
        )
    except google_calendar.GoogleCalendarError as exc:
        current_app.logger.warning(
            "Falha Google Calendar atividade=%s: %s", activity["id"], exc
        )
        return store.update_activity_meeting_sync(
            activity["id"], "error", error=str(exc)[:1000]
        )


def _apply_meeting_payload(activity, data):
    payload = data.get("meeting")
    if not isinstance(payload, dict):
        return None
    meeting = _meeting_draft(activity, payload)
    if payload.get("sync_google"):
        meeting = _sync_meeting(activity, meeting)
    return meeting


@bp.route("/api/clientes/<cliente_id>/atividades", methods=["POST"])
@login_required_api
def api_create_atividade(cliente_id):
    try:
        data = request.get_json(silent=True) or {}
        ativ = store.create_atividade(cliente_id, data)
        if ativ is None:
            return _err("Cliente não encontrado", 404)
        meeting = _apply_meeting_payload(ativ, data)
        if meeting:
            ativ["meeting"] = meeting
        return _ok(ativ, atividade=ativ, meeting=meeting), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/clientes/<cliente_id>/atividades/sequencia", methods=["POST"])
@login_required_api
def api_create_atividade_sequence(cliente_id):
    """Cria a sequência completa ou nenhuma atividade."""
    try:
        sequencia = store.create_activity_sequence(
            cliente_id, request.get_json(silent=True) or {}
        )
        if sequencia is None:
            return _err("Cliente não encontrado", 404)
        return _ok(sequencia, sequencia=sequencia), 201
    except ValueError as e:
        return _err(str(e))
    except Exception:
        current_app.logger.exception("Falha transacional ao criar sequência")
        return _err("Não foi possível criar a sequência; nenhuma atividade foi salva.", 500)


@bp.route("/api/clientes/<cliente_id>/ia/historico")
@login_required_api
def api_ai_history(cliente_id):
    items = store.list_ai_history(
        cliente_id,
        limit=request.args.get("limit", 20),
        atividade_id=request.args.get("atividade_id") or None,
    )
    if items is None:
        return _err("Cliente não encontrado", 404)
    return _ok(items, historico=items)


@bp.route("/api/ia/historico/<interaction_id>/aplicar", methods=["PATCH"])
@login_required_api
def api_apply_ai_history(interaction_id):
    data = request.get_json(silent=True) or {}
    ok = store.mark_ai_interaction_applied(
        interaction_id, atividade_id=data.get("atividade_id")
    )
    if not ok:
        return _err("Interação não encontrada ou migration não aplicada", 404)
    return _ok(applied=True)


@bp.route("/api/ia/historico/<interaction_id>", methods=["PATCH"])
@login_required_api
def api_update_ai_history(interaction_id):
    updated = store.update_ai_interaction(
        interaction_id, request.get_json(silent=True) or {}
    )
    if not updated:
        return _err("Interação não encontrada ou texto vazio", 404)
    return _ok(updated, historico=updated)


@bp.route("/api/ia/historico/<interaction_id>", methods=["DELETE"])
@login_required_api
def api_delete_ai_history(interaction_id):
    if not store.delete_ai_interaction(interaction_id):
        return _err("Interação não encontrada ou migration não aplicada", 404)
    return _ok(deleted=True)


@bp.route("/api/ia/modelo-estilo", methods=["GET"])
@login_required_api
def api_get_style_model():
    modelo = store.get_style_model()
    return _ok(modelo or {}, modelo=modelo)


@bp.route("/api/ia/modelo-estilo", methods=["PUT"])
@login_required_api
def api_put_style_model():
    data = request.get_json(silent=True) or {}
    texto = str(data.get("texto") or "").strip()
    assunto = str(data.get("assunto") or "").strip()
    if assunto:
        texto = f"Assunto: {assunto}\n\n{texto}".strip()
    if not texto:
        return _err("Informe o texto do modelo", 400)
    data = dict(data)
    data["texto"] = _generalizar_modelo_estilo(texto, {
        "contato": data.get("contato_nome"),
        "executivo": data.get("executivo_nome"),
        "cliente": data.get("cliente_nome"),
        "agencia": data.get("agencia_nome"),
    })
    modelo = store.upsert_style_model(data)
    if not modelo:
        return _err("Não foi possível salvar o modelo", 503)
    return _ok(modelo, modelo=modelo)


@bp.route("/api/ia/modelo-estilo", methods=["DELETE"])
@login_required_api
def api_delete_style_model():
    store.delete_style_model()
    return _ok(deleted=True)


@bp.route("/api/atividades/<atividade_id>", methods=["PATCH"])
@login_required_api
def api_update_atividade(atividade_id):
    try:
        data = request.get_json(silent=True) or {}
        ativ, cliente_id = store.update_atividade(atividade_id, data)
        if not ativ:
            return _err("Atividade não encontrada", 404)
        meeting = _apply_meeting_payload(ativ, data)
        if meeting:
            ativ["meeting"] = meeting
        return _ok(ativ, atividade=ativ, cliente_id=cliente_id, meeting=meeting)
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/atividades/<atividade_id>/reuniao")
@login_required_api
def api_get_activity_meeting(atividade_id):
    activity = store.get_atividade(atividade_id)
    if not activity:
        return _err("Atividade não encontrada", 404)
    meeting = store.get_activity_meeting(atividade_id)
    return _ok(meeting, meeting=meeting)


@bp.route("/api/atividades/<atividade_id>/reuniao/sincronizar", methods=["POST"])
@login_required_api
def api_sync_activity_meeting(atividade_id):
    activity = store.get_atividade(atividade_id)
    meeting = store.get_activity_meeting(atividade_id)
    if not activity or not meeting:
        return _err("Reunião não encontrada", 404)
    try:
        synced = _sync_meeting(activity, meeting)
        return _ok(synced, meeting=synced)
    except PermissionError as exc:
        return _err(str(exc), 403)


@bp.route("/api/atividades/<atividade_id>/reuniao/evento", methods=["DELETE"])
@login_required_api
def api_cancel_activity_meeting(atividade_id):
    from .services import google_calendar

    meeting = store.get_activity_meeting(atividade_id)
    if not meeting:
        return _err("Reunião não encontrada", 404)
    if str(meeting.get("user_id")) != str(session.get("user_id")):
        return _err("Somente o organizador pode cancelar esta reunião.", 403)
    connection = store.get_google_connection(session["user_id"], include_token=True)
    if meeting.get("google_event_id") and connection:
        try:
            google_calendar.cancel_event(
                meeting, connection["encrypted_refresh_token"]
            )
        except google_calendar.GoogleCalendarError as exc:
            store.update_activity_meeting_sync(
                atividade_id, "error", error=str(exc)[:1000]
            )
            return _err(str(exc), 502)
    cancelled = store.update_activity_meeting_sync(
        atividade_id, "cancelled", error=None
    )
    return _ok(cancelled, meeting=cancelled)


@bp.route("/api/atividades/<atividade_id>", methods=["DELETE"])
@login_required_api
def api_delete_atividade(atividade_id):
    ok, cliente_id = store.delete_atividade(atividade_id)
    if not ok:
        return _err("Atividade não encontrada", 404)
    return _ok(cliente_id=cliente_id)


@bp.route("/api/clientes/<cliente_id>/objetivos")
@login_required_api
def api_objetivos(cliente_id):
    items = store.list_objetivos(cliente_id)
    if items is None:
        return _err("Cliente não encontrado", 404)
    return _ok(items, objetivos=items)


@bp.route("/api/clientes/<cliente_id>/objetivos", methods=["POST"])
@login_required_api
def api_create_objetivo(cliente_id):
    try:
        objetivo = store.create_objetivo(cliente_id, request.get_json(silent=True) or {})
        if objetivo is None:
            return _err("Cliente não encontrado", 404)
        return _ok(objetivo, objetivo=objetivo), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/objetivos/<objetivo_id>", methods=["PATCH"])
@login_required_api
def api_update_objetivo(objetivo_id):
    try:
        objetivo, cliente_id = store.update_objetivo(
            objetivo_id, request.get_json(silent=True) or {}
        )
        if objetivo is None:
            return _err("Objetivo não encontrado", 404)
        return _ok(objetivo, objetivo=objetivo, cliente_id=cliente_id)
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/objetivos/<objetivo_id>", methods=["DELETE"])
@login_required_api
def api_delete_objetivo(objetivo_id):
    ok, cliente_id = store.delete_objetivo(objetivo_id)
    if not ok:
        return _err("Objetivo não encontrado", 404)
    return _ok(cliente_id=cliente_id)


@bp.route("/api/clientes/<cliente_id>/cotacoes")
@login_required_api
def api_cotacoes(cliente_id):
    items = store.list_cotacoes(cliente_id)
    if items is None:
        return _err("Cliente não encontrado", 404)
    items = [_cotacao_com_url(item) for item in items]
    return _ok(items, cotacoes=items)


@bp.route("/api/clientes/<cliente_id>/incentivos")
@login_required_api
def api_incentivos_agencia(cliente_id):
    """Faixas de incentivo PI da agência (sidebar Info → Perfil comercial).

    Só retorna dados quando existe cadastro em cadu_pi_incentivos para a
    agência resolvida (própria ou vinculada). Caso contrário incentivo=null
    e a UI não exibe bloco extra.
    """
    payload = store.get_incentivo_agencia(cliente_id)
    if payload is None:
        return _err("Cliente não encontrado", 404)
    incentivo = payload.get("incentivo")
    if incentivo:
        incentivo["link"] = url_for("incentivos_lista")
    return _ok(incentivo=incentivo)


@bp.route("/api/clientes/<cliente_id>/cotacoes", methods=["POST"])
@login_required_api
def api_create_cotacao(cliente_id):
    """Cria o cabeçalho da cotação (Caminho A).

    Mídia devolve a montagem atual; os demais tipos devolvem somente a
    edição de cabeçalho enquanto seus módulos próprios não existem.
    """
    try:
        cotacao = store.create_cotacao(cliente_id, request.get_json(silent=True) or {})
        if cotacao is None:
            return _err("Cliente não encontrado", 404)
        cotacao = _cotacao_com_url(cotacao)
        redirect_url = cotacao.get("detalhes_url")
        payload = {"cotacao": cotacao}
        if redirect_url:
            payload["redirect_url"] = redirect_url
        return _ok(cotacao, **payload), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/cotacoes/<cotacao_id>", methods=["PATCH"])
@login_required_api
def api_update_cotacao(cotacao_id):
    try:
        cotacao, cliente_id = store.update_cotacao(
            cotacao_id, request.get_json(silent=True) or {}
        )
        if cotacao is None:
            return _err("Cotação não encontrada", 404)
        cotacao = _cotacao_com_url(cotacao)
        return _ok(
            cotacao,
            cotacao=cotacao,
            cliente_id=cliente_id,
            redirect_url=cotacao.get("detalhes_url"),
        )
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/cotacoes/<cotacao_id>/briefing", methods=["POST"])
@login_required_api
def api_upload_cotacao_briefing(cotacao_id):
    cotacao = store.get_cotacao(cotacao_id)
    if not cotacao:
        return _err("Cotação não encontrada", 404)
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        return _err("Selecione um arquivo de briefing")
    from .cotacoes_routes import (
        BRIEFING_EXTENSOES_PERMITIDAS,
        BRIEFING_MAX_BYTES,
        DESCRICAO_ANEXO_BRIEFING,
        _salvar_file_storage_como_anexo_cotacao,
    )
    import os

    extensao = os.path.splitext(arquivo.filename)[1].lower()
    if extensao not in BRIEFING_EXTENSOES_PERMITIDAS:
        return _err("Formato de briefing não permitido")
    arquivo.seek(0, os.SEEK_END)
    tamanho = arquivo.tell()
    arquivo.seek(0)
    if tamanho > BRIEFING_MAX_BYTES:
        return _err("Briefing excede o limite de 10 MB")
    anexo_id = _salvar_file_storage_como_anexo_cotacao(
        int(cotacao_id),
        arquivo,
        DESCRICAO_ANEXO_BRIEFING,
        session.get("user_id"),
    )
    return _ok(anexo_id=anexo_id)


@bp.route("/api/cotacoes/<cotacao_id>", methods=["DELETE"])
@login_required_api
def api_delete_cotacao(cotacao_id):
    ok, cliente_id = store.delete_cotacao(cotacao_id)
    if not ok:
        return _err("Cotação não encontrada", 404)
    return _ok(cliente_id=cliente_id)


@bp.route("/api/clientes/<cliente_id>/notas")
@login_required_api
def api_notas(cliente_id):
    notas = store.list_notas(cliente_id)
    if notas is None:
        return _err("Cliente não encontrado", 404)
    return _ok(notas, notas=notas)


@bp.route("/api/clientes/<cliente_id>/notas", methods=["POST"])
@login_required_api
def api_create_nota(cliente_id):
    try:
        nota = store.create_nota(cliente_id, request.get_json(silent=True) or {})
        if nota is None:
            return _err("Cliente não encontrado", 404)
        return _ok(nota, nota=nota), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/notas/<nota_id>", methods=["PATCH"])
@login_required_api
def api_update_nota(nota_id):
    try:
        nota, cliente_id = store.update_nota(nota_id, request.get_json(silent=True) or {})
        if nota is None:
            return _err("Nota não encontrada", 404)
        return _ok(nota, nota=nota, cliente_id=cliente_id)
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/notas/<nota_id>", methods=["DELETE"])
@login_required_api
def api_delete_nota(nota_id):
    ok, cliente_id = store.delete_nota(nota_id)
    if not ok:
        return _err("Nota não encontrada", 404)
    return _ok(cliente_id=cliente_id)


@bp.route("/api/contatos/parse-texto", methods=["POST"])
@login_required_api
def api_parse_texto():
    data = request.get_json(silent=True) or {}
    texto = data.get("texto") or ""
    contatos = parse_texto_contatos(texto)
    return _ok(contatos, contatos=contatos, message="" if contatos else "Nenhum contato reconhecido no texto.")


@bp.route("/api/clientes/<cliente_id>/contatos/importar", methods=["POST"])
@login_required_api
def api_import_contatos(cliente_id):
    try:
        data = request.get_json(silent=True) or {}
        rows = data.get("contatos") or []
        if not rows:
            return _err("Nenhum contato para importar")
        created = store.import_contatos(cliente_id, rows)
        if created is None:
            return _err("Cliente não encontrado", 404)
        return _ok(created, importados=len(created), contatos=created)
    except ValueError as e:
        return _err(str(e))


# =============================================================================
# Web Scout — Fase B do plano macro (set/2026)
# -----------------------------------------------------------------------------
# Extrai og:image + metadata do site oficial do cliente via Firecrawl e
# cacheia em `cliente_web_info` (migration create_cliente_web_info.sql).
# Substitui a cascata frágil de favicons (Clearbit/Google/DDG) que
# retornava globos genéricos para clientes fora do catálogo global.
#
# - GET /api/clientes/<id>/web-info:
#       Só lê do cache. Retorna 404 se ainda não há registro (frontend
#       deve exibir estado "sem dados" e oferecer botão Atualizar).
# - POST /api/clientes/<id>/web-info/refresh:
#       Faz o scrape agora (síncrono, timeout 30s) e retorna o novo
#       registro. Body opcional `{ "dominio": "cliente.com.br" }` — se
#       ausente, deriva de `cliente.site_url` (fallback nos contatos
#       na Fase C). Nunca lança 500: falhas do Firecrawl viram
#       registros com `status: 'erro'` + `erro_mensagem`, permitindo
#       à UI mostrar o motivo real (timeout, 403, domínio inválido).
# =============================================================================


@bp.route("/api/clientes/<cliente_id>/web-info")
@login_required_api
def api_web_info_get(cliente_id):
    from .crm_v3_web_scout import obter_web_info
    try:
        info = obter_web_info(cliente_id)
    except Exception:
        current_app.logger.exception("web-info GET falhou para cliente %s", cliente_id)
        info = None
    # 200 mesmo sem cache: 404/500 quebrava a aba Web e o restante do CRM.
    return _ok(info, web_info=info)


@bp.route("/api/clientes/<cliente_id>/web-info/refresh", methods=["POST"])
@login_required_api
def api_web_info_refresh(cliente_id):
    from .crm_v3_web_scout import obter_web_info, refresh_web_info, _normalizar_dominio
    cliente = {}
    try:
        cliente = store.get_cliente(cliente_id) or {}
    except Exception:
        current_app.logger.exception("web-info refresh: get_cliente falhou para %s", cliente_id)
        cliente = {}
    data = request.get_json(silent=True) or {}
    cached = obter_web_info(cliente_id) or {}
    dominio = _normalizar_dominio(
        data.get("dominio")
        or cliente.get("site_url")
        or cached.get("dominio")
        or ""
    )
    if not dominio:
        return _err("Informe o site nesta aba para buscar as informações.")
    try:
        info = refresh_web_info(cliente_id, dominio)
    except Exception as e:
        current_app.logger.exception("web-info refresh falhou para cliente %s", cliente_id)
        info = {
            "status": "erro",
            "dominio": dominio,
            "erro_mensagem": str(e)[:500] or "Falha ao buscar o site",
        }
    return _ok(info, web_info=info)


# =============================================================================
# IA — Fase 3
# -----------------------------------------------------------------------------
# Rotas /crm-v3/api/ia/* usam OpenRouter via `_call_openrouter` do
# módulo real `crm.ia_routes`. Texto da atividade (roteiro, e-mail, WhatsApp)
# usa GPT-4o mini — melhor em seguir o registro e o tom comercial.
# OCR/multimodal permanece em Gemini. Sem chave ou com falha, cai no
# fallback determinístico e a resposta traz `source: 'fallback'`.
# =============================================================================

import os
from datetime import date, timedelta

CRM_V3_ACTIVITY_MODEL = os.getenv("CRM_V3_ACTIVITY_MODEL", "openai/gpt-4o-mini")


def _openrouter_available() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def _call_openrouter(system_prompt: str, user_content: str, max_tokens: int = 1000, temperature: float = 0.7):
    """Wrapper defensivo em torno de `crm.ia_routes._call_openrouter`.

    Retorna a string de resposta ou levanta a exceção original. Evita duplicar
    a lógica HTTP: reaproveitamos o mesmo cliente OpenRouter do CRM oficial.
    """
    from .crm.ia_routes import _call_openrouter as _real_call  # type: ignore
    return _real_call(
        system_prompt,
        user_content,
        max_tokens=max_tokens,
        temperature=temperature,
        model=CRM_V3_ACTIVITY_MODEL,
    )


def _call_openrouter_multimodal(system_prompt: str, text_prompt: str, image_data_url: str,
                                 max_tokens: int = 2000, temperature: float = 0.1):
    """Chamada multimodal do OpenRouter (texto + imagem) para Gemini 2.5 Flash.

    O helper regular (`_call_openrouter`) só aceita user_content string —
    formato antigo do OpenAI. Para input multimodal, precisamos passar
    `content` como array de parts com `type: 'image_url'`. Como a API
    OpenRouter é compatível com OpenAI, o payload é idêntico.

    `image_data_url` deve ser um data URL RFC 2397 completo, ex:
        "data:image/png;base64,iVBORw0KGgoAAAANS..."
    ou uma URL http/https pública. O modelo Gemini aceita ambos, mas
    priorizamos data URL para não expor a imagem em CDN externo.

    Escolha do modelo: mantemos `google/gemini-2.5-flash` (o mesmo
    padrão do resto do CRM v3) por ser barato (~$0.075 / M tokens
    input) e multimodal nativo. Alternativas mais precisas
    (`google/gemini-2.5-pro`) custam ~15x mais.

    Retorna a string bruta da resposta ou levanta a exceção original.
    """
    import requests as http_requests

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY não configurada")

    payload = {
        "model": "google/gemini-2.5-flash",
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text_prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            },
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    resp = http_requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://centralcomm.media",
            "X-Title": "CentralComm AI - CRM v3 OCR",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=90,  # OCR de imagens grandes pode levar até ~30s
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _contato_para_ia(data: dict, cliente_id: str):
    """Contato escolhido no drawer. Sem seleção, não reaproveita outra pessoa."""
    contato_id = str(data.get("contato_id") or "").strip()
    contatos = store.list_contatos(cliente_id) or [] if cliente_id else []
    if contato_id:
        for c in contatos:
            if str(c.get("id")) == contato_id:
                return c, contatos
    return {}, contatos


def _texto_ia_limpo(texto) -> str:
    return texto_sem_markdown(texto or "")


def _dados_canal_contato(contato: dict) -> dict:
    contato = contato or {}
    return {
        "telefone": normalizar_telefone(
            contato.get("telefone") or contato.get("telefone_secundario")
        ),
        "email": str(contato.get("email") or "").strip().lower(),
    }


def _contexto_ia(data: dict, profile: str) -> dict:
    cliente_id = str(data.get("cliente_id") or "").strip()
    if not cliente_id:
        return {}
    contexto_executivo = _texto_ia_limpo(
        data.get("contexto_executivo")
    )[:2000]
    try:
        contexto = store.get_ai_context(
            cliente_id, profile=profile, contato_id=data.get("contato_id")
        ) or {}
        if contexto_executivo:
            contexto["contexto_informado_pelo_executivo"] = contexto_executivo
        return contexto
    except Exception as exc:  # pragma: no cover - proteção para bases antigas
        current_app.logger.exception(
            "Falha ao montar contexto IA profile=%s cliente=%s: %s",
            profile, cliente_id, exc,
        )
        return (
            {"contexto_informado_pelo_executivo": contexto_executivo}
            if contexto_executivo else {}
        )


def _contexto_ia_json(data: dict, profile: str) -> str:
    import json
    return json.dumps(_contexto_ia(data, profile), ensure_ascii=False, default=str)


def _parse_ia_json(raw: str, required=()) -> dict:
    """Normaliza fences, valida objeto JSON e campos obrigatórios."""
    import json
    texto = (raw or "").strip()
    if texto.startswith("```"):
        texto = texto.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    parsed = json.loads(texto)
    if not isinstance(parsed, dict):
        raise ValueError("Resposta da IA não é um objeto JSON")
    missing = [key for key in required if parsed.get(key) in (None, "")]
    if missing:
        raise ValueError("Campos ausentes na resposta da IA: " + ", ".join(missing))
    return parsed


def _log_provider_failure(funcao: str, exc: Exception) -> None:
    from flask import has_app_context
    if not has_app_context():
        return
    current_app.logger.warning(
        "OpenRouter falhou em crm_v3/%s: %s: %s",
        funcao, type(exc).__name__, str(exc)[:500],
        exc_info=True,
    )


def _registrar_saida_ia(data: dict, funcao: str, saida: dict) -> dict:
    cliente_id = str(data.get("cliente_id") or "").strip()
    if not cliente_id:
        return saida
    try:
        payload = dict(saida)
        if data.get("atividade_id"):
            payload["atividade_id"] = data.get("atividade_id")
        if saida.get("source") == "openrouter":
            payload.setdefault("modelo", CRM_V3_ACTIVITY_MODEL)
        history_id = store.register_ai_interaction(cliente_id, funcao, payload)
        if history_id:
            saida["history_id"] = history_id
    except Exception as exc:  # compatível sem migration
        current_app.logger.info("Histórico IA indisponível: %s", exc)
    return saida


def _nome_executivo_sessao() -> str:
    try:
        return (session.get("user_name") or "").strip()
    except Exception:
        return ""


CANAIS_MIDIA = (
    "Netflix", "Spotify", "Serasa", "Disney", "HBO", "Amazon", "iFood", "Uber", "99", "Logan",
)


def _nome_destinatario(data: dict, cliente=None, contato=None):
    """Destinatário da conversa: contato do cliente ou equipe/empresa. Nunca o logado."""
    cliente = cliente or {}
    contato = contato or {}
    nome_contato = texto_sem_markdown(
        data.get("destinatario") or data.get("contato_nome") or contato.get("nome") or ""
    ).strip()
    nome_cliente = (
        cliente.get("nome") or data.get("cliente_nome") or "o cliente"
    ).strip()
    if nome_contato:
        return nome_contato, True
    return f"equipe da {nome_cliente}", False


def _nome_responsavel_interno(data: dict, cliente=None) -> str:
    return texto_sem_markdown(
        data.get("responsavel_interno")
        or data.get("executivo_nome")
        or _nome_executivo_sessao()
        or (cliente or {}).get("responsavel")
        or "Equipe CentralComm"
    ).strip()


def _ancora_conversa(data: dict, cliente=None, contato=None) -> dict:
    """Dados da conversa atual — uso interno do prompt, nunca como jargão ao cliente."""
    cliente = cliente or {}
    contato = contato or {}
    eh_agencia = bool(cliente.get("is_agencia"))
    clientes_agencia = [
        (item.get("nome") or "").strip()
        for item in (cliente.get("clientes_finais") or [])
        if (item.get("nome") or "").strip()
    ][:12]
    destinatario, tem_contato = _nome_destinatario(data, cliente, contato)
    return {
        "tipo": (data.get("tipo") or "atividade").strip(),
        "titulo": texto_sem_markdown(data.get("titulo") or "").strip(),
        "registro": texto_sem_markdown(
            data.get("notas_executivo") or data.get("descricao") or ""
        ).strip()[:1000],
        "contato": destinatario if tem_contato else "",
        "destinatario": destinatario,
        "tem_contato": tem_contato,
        "responsavel_interno": _nome_responsavel_interno(data, cliente),
        "executivo": texto_sem_markdown(
            data.get("executivo_nome")
            or _nome_executivo_sessao()
            or cliente.get("responsavel")
            or ""
        ).strip(),
        "cliente": (cliente.get("nome") or "").strip(),
        "agencia": (
            (cliente.get("nome") or "").strip() if eh_agencia
            else (cliente.get("agencia_nome") or data.get("agencia_nome") or "")
        ).strip(),
        "eh_agencia": eh_agencia,
        "clientes_agencia": clientes_agencia or [
            item for item in (data.get("clientes_agencia") or []) if str(item).strip()
        ][:12],
        "canal": texto_sem_markdown(data.get("canal_produto") or "").strip(),
    }


def _regras_texto_externo() -> str:
    return (
        "O destinatário não pode perceber que isto é uma atividade, tarefa ou item "
        "agendado no CRM. Não cite atividade, prazo interno, cadastro, sistema, "
        "pipeline ou follow-up administrativo. Fale como conversa comercial ao vivo.\n"
        "O assunto da conversa é o título e o registro do executivo. "
        "Puxe a solução da CentralComm a partir desse assunto "
        "(ex.: formatos interativos e métricas de atenção para o mercado imobiliário). "
        "Não caia em descoberta genérica nem em 'entender necessidades', "
        "salvo se o foco for explicitamente esse.\n"
        "Ancore cerca de 75% do texto no título, no registro e nos nomes reais "
        "(contato, executivo, cliente, agência e clientes da agência).\n"
        "Canal ou produto só entra se estiver no registro, no título ou no foco. "
        "A CentralComm como casa só entra quando o foco for apresentar a empresa.\n"
        "O responsável interno (usuário logado) nunca é o destinatário da saudação."
    )


def _regras_destinatario(ancora=None) -> str:
    ancora = ancora or {}
    if ancora.get("tem_contato") and ancora.get("destinatario"):
        return (
            f"Saudação: use o nome do contato ({ancora['destinatario']}). "
            "Não use o responsável interno como destinatário."
        )
    alvo = ancora.get("destinatario") or "equipe do cliente"
    return (
        f"Não há contato selecionado. Trate o destinatário como a empresa/equipe ({alvo}). "
        "Não invente nome de pessoa nem reaproveite o responsável interno. "
        "Exemplo: Olá, equipe da AGÊNCIA INDIE. Tudo bem?"
    )


def _bloco_ancora(ancora: dict) -> str:
    linhas = [
        "CONTEXTO INTERNO DA CONVERSA (não repetir estes rótulos ao cliente):",
        f"Tipo de abordagem: {ancora.get('tipo') or 'conversa'}",
        f"Assunto: {ancora.get('titulo') or '(sem título)'}",
        f"Cliente: {ancora.get('cliente') or '(não informado)'}",
        f"Destinatário: {ancora.get('destinatario') or '(equipe/empresa)'}",
        f"Contato selecionado: {'sim' if ancora.get('tem_contato') else 'não'}",
        f"Responsável interno: {ancora.get('responsavel_interno') or '(não informado)'}",
        f"Executivo: {ancora.get('executivo') or '(não informado)'}",
    ]
    if ancora.get("agencia"):
        linhas.append(f"Agência: {ancora['agencia']}")
    if ancora.get("clientes_agencia"):
        linhas.append("Clientes da agência: " + ", ".join(ancora["clientes_agencia"]))
    if ancora.get("canal"):
        linhas.append(f"Canal ou produto: {ancora['canal']}")
    if ancora.get("registro"):
        linhas.append(f"Registro do executivo:\n{ancora['registro']}")
    return "\n".join(linhas) + "\n"


def _generalizar_modelo_estilo(texto, nomes) -> str:
    """Troca nomes reais por {{contato}}, {{executivo}}, {{cliente}}, {{agencia}}."""
    import re
    texto = texto_sem_markdown(texto or "")
    pares = []
    for chave in ("contato", "executivo", "cliente", "agencia"):
        valor = texto_sem_markdown((nomes or {}).get(chave) or "").strip()
        if len(valor) >= 3:
            pares.append((chave, valor))
    pares.sort(key=lambda item: len(item[1]), reverse=True)
    vistos = set()
    for chave, valor in pares:
        marca = valor.casefold()
        if marca in vistos:
            continue
        vistos.add(marca)
        texto = re.sub(
            r"(?<!\w)" + re.escape(valor) + r"(?!\w)",
            "{{" + chave + "}}",
            texto,
            flags=re.IGNORECASE,
        )
    return texto.strip()


def _variaveis_estilo(ancora=None) -> dict:
    ancora = ancora or {}
    cliente = (ancora.get("cliente") or "o cliente").strip()
    return {
        "contato": (
            ancora.get("contato")
            or ancora.get("destinatario")
            or f"equipe da {cliente}"
        ).strip(),
        "executivo": (ancora.get("executivo") or "Equipe CentralComm").strip(),
        "cliente": cliente,
        "agencia": (ancora.get("agencia") or cliente).strip(),
    }


def _bloco_modelo_estilo(ancora=None) -> str:
    try:
        modelo = store.get_style_model() or {}
    except Exception:
        modelo = {}
    texto = texto_sem_markdown(modelo.get("texto") or "").strip()[:4000]
    if not texto:
        return ""
    linhas = [
        "MODELO (preencha as variáveis; mantenha estrutura, tom e extensão; "
        "não copie fatos do exemplo; use o registro e as pessoas desta conversa):",
        texto,
        "",
        "VARIÁVEIS DESTA CONVERSA:",
    ]
    for chave, valor in _variaveis_estilo(ancora).items():
        if valor:
            linhas.append(f"{chave}={valor}")
    return "\n".join(linhas) + "\n"


def _roteiro_fallback(titulo, tipo, cliente, contato=None, foco="", tom="") -> str:
    nome = (cliente or {}).get("nome") or "o cliente"
    tipo_label = {
        "ligacao": "ligação",
        "reuniao": "reunião",
        "email": "e-mail",
        "whatsapp": "WhatsApp",
        "doc": "documento",
        "planejamento": "planejamento",
    }.get((tipo or "").lower(), "atividade")
    assunto = (titulo or f"esta {tipo_label}").strip()
    quem = ((contato or {}).get("nome") or "").strip()
    alvo = f"{quem} ({nome})" if quem else nome
    foco_label = {
        "apresentar_solucao": "apresentar a solução descrita no registro e no título",
        "apresentar_empresa": "apresentar a CentralComm quando isso for o pedido explícito",
        "entender_necessidades": "entender necessidades e prioridades",
        "apresentar_proposta": "apresentar a proposta",
        "follow_up": "realizar o follow-up",
        "falar_sobre_canal": "falar sobre o canal ou produto escolhido",
        "outro": "conduzir o objetivo informado",
    }.get(foco, "apresentar a solução descrita no registro e no título")
    tom_label = {
        "institucional": "institucional",
        "consultivo": "consultivo",
        "direto": "direto e objetivo",
        "informal": "próximo e informal",
    }.get(tom, "consultivo")
    return (
        f"Objetivo: executar “{assunto}” com {alvo}.\n\n"
        "Roteiro:\n"
        f"- Abrir em tom {tom_label} e contextualizar por que estamos falando agora.\n"
        f"- Direcionar a conversa para {foco_label}.\n"
        "- Confirmar interesse e restrições (prazo, verba, aprovação).\n"
        "- Apresentar o ponto combinado e checar objeções.\n"
        "- Combinar um próximo passo com data.\n\n"
        "Fechamento: registrar o resultado nesta atividade (combinado / bloqueio / recusa)."
    )


def _abordagem_ligacao_fallback(titulo, cliente, contato=None, data=None) -> dict:
    nome_cliente = (cliente or {}).get("nome") or "o cliente"
    destinatario, tem_contato = _nome_destinatario(data or {}, cliente, contato)
    objetivo = (titulo or "retomar o relacionamento comercial").strip()
    if tem_contato:
        abertura = (
            f"Olá {destinatario}, aqui é da CentralComm. "
            f"Queria falar com você sobre {objetivo.lower()}."
        )
    else:
        abertura = (
            f"Olá, {destinatario}. Tudo bem? "
            f"Estou entrando em contato para conversar sobre {objetivo.lower()} "
            f"que podemos gerar mais engajamento nas campanhas da marca."
        )
    perguntas = [
        f"Como este tema está sendo tratado hoje na {nome_cliente}?",
        "Quais prioridades ou resultados precisam ser atendidos primeiro?",
        "Existe alguma restrição de prazo, verba ou aprovação que devemos considerar?",
        "Quem mais precisa participar da próxima conversa?",
        "Qual próximo passo faria sentido combinarmos agora?",
    ]
    fechamento = (
        "Recapitule o que foi entendido, confirme responsáveis e combine "
        "uma próxima ação com data."
    )
    texto = (
        f"Abertura:\n{abertura}\n\nPerguntas:\n- "
        + "\n- ".join(perguntas)
        + f"\n\nFechamento:\n{fechamento}"
    )
    return {
        "objetivo": objetivo,
        "abertura": abertura,
        "perguntas": perguntas,
        "objecoes_a_explorar": [
            "Prioridade concorrente ou ausência de urgência.",
            "Prazo, verba ou processo de aprovação ainda indefinidos.",
        ],
        "pontos_de_atencao": [
            "Ouvir antes de apresentar a solução.",
            "Não presumir orçamento ou decisão.",
        ],
        "fechamento": fechamento,
        "texto": texto,
    }


def _montar_roteiro(data: dict) -> dict:
    """Gera roteiro ancorado no título e no registro da atividade."""
    titulo = texto_sem_markdown(data.get("titulo") or "").strip()
    tipo = (data.get("tipo") or "atividade").strip()
    formato = (data.get("formato") or "").strip().lower()
    foco = (data.get("foco") or "apresentar_solucao").strip().lower()
    tom = (data.get("tom") or "").strip().lower()
    instrucoes = texto_sem_markdown(data.get("instrucoes") or "").strip()[:500]
    canal_produto = texto_sem_markdown(data.get("canal_produto") or "").strip()
    foco_label = {
        "apresentar_solucao": "Apresentar a solução do registro",
        "apresentar_empresa": "Apresentar a CentralComm",
        "entender_necessidades": "Entender necessidades",
        "apresentar_proposta": "Apresentar proposta",
        "follow_up": "Follow-up",
        "falar_sobre_canal": f"Falar sobre {canal_produto}" if canal_produto else "Falar sobre um canal ou produto",
        "outro": "Outro objetivo informado",
    }.get(foco, "Apresentar a solução do registro")
    tom_label = {
        "institucional": "Institucional",
        "consultivo": "Consultivo",
        "direto": "Direto e objetivo",
        "informal": "Mais informal",
    }.get(tom, "Consultivo")
    cliente_id = data.get("cliente_id") or ""
    cliente = store.get_cliente(cliente_id) if cliente_id else None
    contato, _ = _contato_para_ia(data, cliente_id)
    ancora = _ancora_conversa(data, cliente, contato)

    if _openrouter_available():
        try:
            user = (
                f"{_bloco_ancora(ancora)}\n"
                f"{_bloco_modelo_estilo(ancora)}"
                "APOIO COMERCIAL (usar só se confirmar o registro):\n"
                f"{_contexto_ia_json(data, 'roteiro')}\n\n"
                f"Formato: {formato or tipo or 'roteiro'}\n"
                f"Foco: {foco_label}\n"
                f"Tom: {tom_label}\n"
            )
            if instrucoes:
                user += f"Ajuste do executivo:\n{instrucoes}\n"
            system_prompt = (
                "Você é o copiloto comercial da CentralComm, especialista em venda de mídia.\n"
                "Crie um guia prático para ligação ou reunião, não uma mensagem pronta.\n"
                f"{_regras_texto_externo()}\n"
                f"{_regras_destinatario(ancora)}\n"
                "Não invente dados. Retorne APENAS JSON válido no formato "
                '{"abertura":"abertura curta e natural",'
                '"objetivo":"resultado esperado desta conversa",'
                '"perguntas":["pergunta aberta e específica"],'
                '"objecoes_a_explorar":["objeção que deve ser investigada, sem presumir que existe"],'
                '"pontos_de_atencao":["ponto verificável"],'
                '"fechamento":"próximo passo objetivo",'
                '"motivo":"por que este roteiro é adequado agora",'
                '"contexto_utilizado":["dado verificável 1","dado verificável 2"]}. '
                "Crie de 4 a 6 perguntas. Sem markdown."
            )
            parsed = _parse_ia_json(
                _call_openrouter(system_prompt, user, max_tokens=650, temperature=0.35),
                required=("abertura", "perguntas", "fechamento", "motivo"),
            )
            perguntas = [
                _texto_ia_limpo(item)
                for item in (parsed.get("perguntas") or [])[:6]
                if _texto_ia_limpo(item)
            ]
            if not perguntas:
                perguntas = _abordagem_ligacao_fallback(
                    titulo, cliente, contato, data
                )["perguntas"]
            pontos = [
                _texto_ia_limpo(item)
                for item in (parsed.get("pontos_de_atencao") or [])[:4]
                if _texto_ia_limpo(item)
            ]
            objecoes = [
                _texto_ia_limpo(item)
                for item in (parsed.get("objecoes_a_explorar") or [])[:4]
                if _texto_ia_limpo(item)
            ]
            abertura = _texto_ia_limpo(parsed["abertura"])
            fechamento = _texto_ia_limpo(parsed["fechamento"])
            objetivo_saida = _texto_ia_limpo(parsed.get("objetivo")) or titulo
            texto = (
                f"Abertura:\n{abertura}\n\nPerguntas:\n- "
                + "\n- ".join(perguntas)
                + f"\n\nFechamento:\n{fechamento}"
            )
            return {
                "texto": texto,
                "objetivo": objetivo_saida,
                "abertura": abertura,
                "perguntas": perguntas,
                "objecoes_a_explorar": objecoes,
                "pontos_de_atencao": pontos,
                "fechamento": fechamento,
                "motivo": _texto_ia_limpo(parsed["motivo"]),
                "contexto_utilizado": [
                    _texto_ia_limpo(x) for x in (parsed.get("contexto_utilizado") or [])[:5]
                ],
                "source": "openrouter",
            }
        except Exception as exc:
            _log_provider_failure("gerar-roteiro", exc)
    fallback = _abordagem_ligacao_fallback(titulo, cliente, contato, data)
    return {
        **fallback,
        "motivo": "Roteiro seguro baseado no tipo, foco e classificação disponíveis.",
        "contexto_utilizado": ["cliente", "contato selecionado", "foco e tom"],
        "source": "fallback",
    }


@bp.route("/api/ia/melhorar-texto", methods=["POST"])
@login_required_api
def api_ia_melhorar_texto():
    data = request.get_json(silent=True) or {}
    texto = (data.get("descricao") or data.get("texto") or "").strip()
    if not texto:
        return _err("Informe o texto que deseja revisar", 400)
    if _openrouter_available():
        try:
            prompt = (
                f"CONTEXTO COMERCIAL:\n{_contexto_ia_json(data, 'roteiro')}\n\n"
                f"TEXTO ORIGINAL:\n{texto[:4000]}\n\n"
                "Preserve fatos e intenção. Corrija clareza, concisão, gramática e orientação "
                "ao próximo passo. Não transforme a mensagem em roteiro."
            )
            system_prompt = (
                "Você revisa textos comerciais em português sem inventar informações. "
                "Retorne APENAS JSON: "
                '{"texto":"versão revisada em texto puro","alteracoes":["mudança objetiva"]}.'
            )
            parsed = _parse_ia_json(
                _call_openrouter(system_prompt, prompt, max_tokens=900, temperature=0.25),
                required=("texto",),
            )
            revisado = _texto_ia_limpo(parsed["texto"])
            saida = {
                "texto": revisado,
                "texto_melhorado": revisado,
                "alteracoes": parsed.get("alteracoes") or [],
                "source": "openrouter",
            }
            return _ok(_registrar_saida_ia(data, "melhorar-texto", saida))
        except Exception as exc:
            _log_provider_failure("melhorar-texto", exc)
    revisado = _texto_ia_limpo(texto)
    return _ok(_registrar_saida_ia(data, "melhorar-texto", {
        "texto": revisado,
        "texto_melhorado": revisado,
        "alteracoes": [],
        "source": "fallback",
    }))


@bp.route("/api/ia/gerar-roteiro", methods=["POST"])
@login_required_api
def api_ia_gerar_roteiro():
    data = request.get_json(silent=True) or {}
    if not str(data.get("titulo") or "").strip():
        return _err("Informe o título da atividade para gerar o roteiro", 400)
    out = _montar_roteiro(data)
    contato, _ = _contato_para_ia(data, str(data.get("cliente_id") or ""))
    dados_canal = _dados_canal_contato(contato)
    return _ok(_registrar_saida_ia(data, "gerar-roteiro", {
        "texto": out["texto"],
        "descricao": out["texto"],
        "abertura": out.get("abertura"),
        "objetivo": out.get("objetivo"),
        "perguntas": out.get("perguntas") or [],
        "objecoes_a_explorar": out.get("objecoes_a_explorar") or [],
        "pontos_de_atencao": out.get("pontos_de_atencao") or [],
        "fechamento": out.get("fechamento"),
        "tipo": "reuniao" if str(data.get("tipo") or "").lower() == "reuniao" else "ligacao",
        "contato": contato,
        **dados_canal,
        "motivo": out.get("motivo"),
        "contexto_utilizado": out.get("contexto_utilizado") or [],
        "source": out["source"],
    }))


def _normalizar_sugestao_cotacao(sugestao, data, cliente):
    hoje = date.today()
    nome_cliente = (cliente or {}).get("nome") or "Cliente"
    tipo = normalizar_tipo_comercial(
        sugestao.get("tipo_comercial") or data.get("tipo_comercial"),
        estrito=False,
    )
    inicio = _texto_ia_limpo(sugestao.get("periodo_inicio")) or hoje.isoformat()
    fim = _texto_ia_limpo(sugestao.get("periodo_fim")) or (hoje + timedelta(days=30)).isoformat()
    budget = sugestao.get("budget_estimado")
    try:
        budget = float(budget) if budget not in (None, "") else None
    except (TypeError, ValueError):
        budget = None
    plataformas = sugestao.get("plataformas") or []
    if isinstance(plataformas, str):
        plataformas = [item.strip() for item in plataformas.split(",") if item.strip()]
    return {
        "tipo_comercial": tipo,
        "nome_campanha": _texto_ia_limpo(sugestao.get("nome_campanha"))
        or f"Proposta {nome_cliente}",
        "objetivo": _texto_ia_limpo(sugestao.get("objetivo"))
        or _texto_ia_limpo(data.get("objetivo")),
        "periodo_inicio": inicio,
        "periodo_fim": fim,
        "budget_estimado": budget,
        "plataformas": plataformas[:8],
        "apresentacao_dados": _texto_ia_limpo(sugestao.get("apresentacao_dados")),
        "motivo": _texto_ia_limpo(sugestao.get("motivo"))
        or "Estrutura inicial baseada nos dados disponíveis do cliente.",
        "contexto_utilizado": [
            _texto_ia_limpo(item)
            for item in (sugestao.get("contexto_utilizado") or [])[:5]
            if _texto_ia_limpo(item)
        ],
        "source": sugestao.get("source") or "fallback",
    }


@bp.route("/api/ia/sugerir-cotacao", methods=["POST"])
@login_required_api
def api_ia_sugerir_cotacao():
    data = request.get_json(silent=True) or {}
    cliente_id = str(data.get("cliente_id") or "").strip()
    cliente = store.get_cliente(cliente_id) if cliente_id else None
    if not cliente:
        return _err("Selecione o cliente antes de pedir uma sugestão")

    if _openrouter_available():
        try:
            system_prompt = (
                "Você prepara o início de uma proposta comercial da CENTRALCOMM. "
                "Use somente fatos presentes no contexto; não invente budget, canais ou briefing. "
                "Retorne APENAS JSON com: "
                '{"tipo_comercial":"midia|parceiros|formatos_interativos|dados",'
                '"nome_campanha":"...","objetivo":"...","periodo_inicio":"YYYY-MM-DD",'
                '"periodo_fim":"YYYY-MM-DD","budget_estimado":null,'
                '"plataformas":[],"apresentacao_dados":"...","motivo":"...",'
                '"contexto_utilizado":["..."]}.'
            )
            prompt = (
                f"CONTEXTO COMERCIAL:\n{_contexto_ia_json(data, 'next_action')}\n\n"
                "Prepare apenas um ponto de partida curto e revisável para o executivo."
            )
            sugestao = _parse_ia_json(
                _call_openrouter(system_prompt, prompt, max_tokens=750, temperature=0.25),
                required=("tipo_comercial", "nome_campanha", "motivo"),
            )
            sugestao["source"] = "openrouter"
            normalizada = _normalizar_sugestao_cotacao(sugestao, data, cliente)
            return _ok(normalizada, sugestao=normalizada)
        except Exception as exc:
            _log_provider_failure("sugerir-cotacao", exc)

    classificacao = cliente.get("classificacao_cliente") or "sem classificação"
    fallback = _normalizar_sugestao_cotacao(
        {
            "tipo_comercial": data.get("tipo_comercial") or "midia",
            "nome_campanha": data.get("nome_campanha")
            or f"Proposta {cliente.get('nome') or 'cliente'}",
            "objetivo": data.get("objetivo") or "",
            "budget_estimado": data.get("budget_estimado") or None,
            "plataformas": data.get("plataformas") or [],
            "apresentacao_dados": data.get("apresentacao_dados") or "",
            "motivo": (
                "O rascunho mantém apenas os dados confirmados e abre espaço "
                "para completar escopo e cálculo na próxima tela."
            ),
            "contexto_utilizado": [
                "cliente selecionado",
                f"classificação: {classificacao}",
            ],
            "source": "fallback",
        },
        data,
        cliente,
    )
    return _ok(fallback, sugestao=fallback)


@bp.route("/api/ia/sugerir-atividade", methods=["POST"])
@login_required_api
def api_ia_sugerir_atividade():
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id") or ""
    cliente = store.get_cliente(cliente_id) if cliente_id else None

    if _openrouter_available() and cliente:
        try:
            contexto = _contexto_ia_json(data, "next_action")
            canais = ", ".join(CANAIS_MIDIA)
            system_prompt = (
                "Você é o copiloto comercial da CENTRALCOMM, especialista em mídia digital.\n"
                "Escolha UMA próxima melhor ação. Prefira um canal de mídia ainda não "
                f"trabalhado neste cliente quando fizer sentido. Canais: {canais}.\n"
                "O título deve parecer assunto comercial (ex.: 'Apresentar Netflix'), "
                "nunca 'atividade agendada' ou jargão de CRM.\n"
                "Responda APENAS em JSON com: "
                '{"tipo":"...","titulo":"...","descricao":"...",'
                '"canal_produto":"Netflix|Spotify|Serasa|...|",'
                '"prioridade":"Alta|Média|Baixa","motivo":"...",'
                '"acao_sugerida":"verbo + resultado","contexto_utilizado":["..."]}\n'
                "Tipos válidos: ligacao, reuniao, email, whatsapp, planejamento, atividade\n"
                "Texto puro, sem markdown. Não invente datas, pessoas ou oportunidades."
            )
            sugestao = _parse_ia_json(
                _call_openrouter(system_prompt, contexto, max_tokens=500, temperature=0.35),
                required=("tipo", "titulo", "descricao", "prioridade", "motivo"),
            )
            hoje = date.today()
            delta = {"Prospecção": 1, "Ativo": 3, "Geladeira": 14}.get(
                cliente.get("classificacao_cliente") or "Prospecção", 2
            )
            sugestao.setdefault("data_sugerida", (hoje + timedelta(days=delta)).isoformat())
            sugestao["titulo"] = _texto_ia_limpo(sugestao.get("titulo"))
            sugestao["descricao"] = _texto_ia_limpo(sugestao.get("descricao"))
            sugestao["motivo"] = _texto_ia_limpo(sugestao.get("motivo"))
            canal = _texto_ia_limpo(sugestao.get("canal_produto"))
            if canal not in CANAIS_MIDIA:
                canal = next((item for item in CANAIS_MIDIA if item.lower() in sugestao["titulo"].lower()), "")
            sugestao["canal_produto"] = canal
            sugestao["source"] = "openrouter"
            return _ok(_registrar_saida_ia(data, "sugerir-atividade", sugestao))
        except Exception as exc:  # pragma: no cover
            _log_provider_failure("sugerir-atividade", exc)

    # Fallback determinístico
    classificacao = (cliente or {}).get("classificacao_cliente") or "Prospecção"
    responsavel = (cliente or {}).get("responsavel") or "Executivo"
    hoje = date.today()
    delta = {"Prospecção": 1, "Ativo": 3, "Geladeira": 14}.get(classificacao, 2)
    sugestao = {
        "titulo": "Apresentar Netflix",
        "descricao": (
            f"Conversar com {((cliente or {}).get('nome') or 'o cliente')} sobre Netflix "
            f"e encaixe de mídia. Responsável: {responsavel}."
        ),
        "canal_produto": "Netflix",
        "tipo": "ligacao" if classificacao != "Ativo" else "reuniao",
        "prioridade": "Alta" if classificacao == "Prospecção" else "Média",
        "motivo": (
            f"O cliente está classificado como {classificacao} e precisa de "
            "um próximo passo comercial explícito."
        ),
        "acao_sugerida": "Retomar contato e combinar o próximo marco",
        "contexto_utilizado": ["classificação do cliente", "responsável comercial"],
        "data_sugerida": (hoje + timedelta(days=delta)).isoformat(),
        "source": "fallback",
    }
    return _ok(_registrar_saida_ia(data, "sugerir-atividade", sugestao))


@bp.route("/api/ia/sugerir-data", methods=["POST"])
@login_required_api
def api_ia_sugerir_data():
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id") or ""
    cliente = store.get_cliente(cliente_id) if cliente_id else None
    classificacao = (cliente or {}).get("classificacao_cliente") or "Prospecção"
    hoje = date.today()
    delta = {"Prospecção": 1, "Ativo": 3, "Geladeira": 14}.get(classificacao, 2)
    tipo = (data.get("tipo") or "atividade").strip()
    titulo = texto_sem_markdown(data.get("titulo") or "").strip()
    registro = texto_sem_markdown(
        data.get("notas_executivo") or data.get("descricao") or ""
    ).strip()[:600]

    if _openrouter_available() and cliente:
        try:
            parsed = _parse_ia_json(
                _call_openrouter(
                    "Você sugere uma data comercial coerente com o tipo de atividade "
                    "e o registro. Não use um intervalo fixo. Responda APENAS JSON: "
                    '{"data":"YYYY-MM-DD","data_prazo":"YYYY-MM-DD","motivo":"..."}.',
                    (
                        f"Hoje: {hoje.isoformat()}\n"
                        f"Tipo: {tipo}\nTítulo: {titulo or '(sem título)'}\n"
                        f"Registro: {registro or '(vazio)'}\n"
                        f"Cliente: {(cliente or {}).get('nome') or ''}\n"
                        f"Classificação: {classificacao}\n"
                    ),
                    max_tokens=220,
                    temperature=0.2,
                ),
                required=("data",),
            )
            sugerida = _texto_ia_limpo(parsed.get("data"))
            prazo = _texto_ia_limpo(parsed.get("data_prazo")) or sugerida
            date.fromisoformat(sugerida)
            date.fromisoformat(prazo)
            saida = {
                "data": sugerida,
                "data_prazo": prazo,
                "motivo": _texto_ia_limpo(parsed.get("motivo")) or "Data sugerida pelo assistente.",
                "source": "openrouter",
            }
            return _ok(saida)
        except Exception as exc:
            _log_provider_failure("sugerir-data", exc)

    sugerida = (hoje + timedelta(days=delta)).isoformat()
    saida = {
        "data": sugerida,
        "data_prazo": sugerida,
        "motivo": (
            f"Sugestão com base na classificação {classificacao} "
            f"e no tipo {tipo}."
        ),
        "source": "fallback",
    }
    return _ok(saida)


@bp.route("/api/ia/touchpoints", methods=["POST"])
@login_required_api
def api_ia_touchpoints():
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id") or ""
    cliente = store.get_cliente(cliente_id) if cliente_id else None

    if _openrouter_available() and cliente:
        try:
            classificacao = cliente.get("classificacao_cliente") or "Prospecção"
            contexto = _contexto_ia_json(data, "touchpoints")
            system_prompt = (
                "Você é estrategista de cadência comercial para venda de mídia. "
                "Crie 3 a 4 passos que evoluam a conversa, sem repetir mensagens. "
                "Use o estágio da cotação, última interação e objetivo aberto. "
                "Responda APENAS em JSON: "
                '{"touchpoints":[{"titulo":"...","descricao":"...",'
                '"tipo":"email|whatsapp|ligacao|reuniao","prioridade":"Alta|Média|Baixa",'
                '"dias":1,"motivo":"..."}],"motivo":"lógica da sequência"}. '
                "Texto puro e sem dados inventados."
            )
            parsed = _parse_ia_json(
                _call_openrouter(system_prompt, contexto, max_tokens=900, temperature=0.4),
                required=("touchpoints",),
            )
            if not isinstance(parsed.get("touchpoints"), list):
                raise ValueError("touchpoints precisa ser uma lista")
            hoje = date.today()
            for tp in parsed.get("touchpoints", [])[:4]:
                dias = int(tp.pop("dias", 1) or 1)
                tp["data_sugerida"] = (hoje + timedelta(days=dias)).isoformat()
                tp.setdefault("hora", "09:00")
                tp["titulo"] = _texto_ia_limpo(tp.get("titulo"))
                tp["descricao"] = _texto_ia_limpo(tp.get("descricao"))
            parsed["classificacao"] = classificacao
            parsed["source"] = "openrouter"
            return _ok(_registrar_saida_ia(data, "touchpoints", parsed))
        except Exception as exc:  # pragma: no cover
            _log_provider_failure("touchpoints", exc)

    classificacao = (cliente or {}).get("classificacao_cliente") or "Prospecção"
    cadencia = {
        "Prospecção": [1, 3, 7, 14],
        "Ativo": [7, 14, 30],
        "Geladeira": [14, 45, 90],
    }.get(classificacao, [1, 3, 7, 14])
    tipos = ["email", "whatsapp", "ligacao", "reuniao"]
    hoje = date.today()
    nome_cliente = (cliente or {}).get("nome") or "cliente"
    touchpoints = []
    for idx, dias in enumerate(cadencia):
        touchpoints.append(
            {
                "titulo": f"Touchpoint #{idx + 1} — {nome_cliente}",
                "descricao": f"D+{dias}: manter cliente aquecido e mover para próximo estágio.",
                "tipo": tipos[idx % len(tipos)],
                "prioridade": "Média",
                "data_sugerida": (hoje + timedelta(days=dias)).isoformat(),
                "hora": "09:00",
            }
        )
    return _ok(_registrar_saida_ia(data, "touchpoints", {
        "touchpoints": touchpoints,
        "classificacao": classificacao,
        "motivo": f"Cadência padrão segura para clientes em {classificacao}.",
        "source": "fallback",
    }))


@bp.route("/api/ia/gerar-comunicacao", methods=["POST"])
@login_required_api
def api_ia_gerar_comunicacao():
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id") or ""
    cliente = store.get_cliente(cliente_id) if cliente_id else None
    tipo = (data.get("formato") or data.get("tipo") or "email").strip().lower()
    if tipo not in ("email", "whatsapp"):
        tipo = "whatsapp" if "whats" in tipo else "email"
    tamanho = (data.get("tamanho") or "medio").strip().lower()
    objetivo = texto_sem_markdown(
        data.get("objetivo") or data.get("titulo") or data.get("descricao") or ""
    ).strip()

    contato_principal, contatos = _contato_para_ia(data, cliente_id)
    dados_canal = _dados_canal_contato(contato_principal)

    if _openrouter_available() and cliente and objetivo:
        try:
            destinatario, _tem_contato = _nome_destinatario(data, cliente, contato_principal)
            responsavel = _nome_responsavel_interno(data, cliente)
            contexto = _contexto_ia_json(data, "comunicacao")
            ancora = _ancora_conversa(data, cliente, contato_principal)
            system_prompt = (
                "Você redige comunicação comercial da CENTRALCOMM, especialista em mídia digital. "
                f"{_regras_texto_externo()} "
                f"{_regras_destinatario(ancora)} "
                "A mensagem deve usar apenas fatos do contexto e exigir revisão humana. "
                "Para WhatsApp, use até 3 parágrafos curtos. Para e-mail, inclua assunto separado. "
                "Retorne APENAS JSON: "
                '{"assunto":"vazio para WhatsApp","mensagem":"texto puro",'
                '"motivo":"por que esta abordagem","contexto_utilizado":["..."]}.'
            )
            user_prompt = (
                f"{_bloco_ancora(ancora)}\n"
                f"{_bloco_modelo_estilo(ancora)}"
                f"Canal: {tipo}\nTamanho: {tamanho}\nObjetivo: {objetivo}\n"
                f"Destinatário: {destinatario}\nAssinatura: {responsavel}\n"
                f"Apoio comercial:\n{contexto}"
            )
            parsed = _parse_ia_json(
                _call_openrouter(system_prompt, user_prompt, max_tokens=1000, temperature=0.4),
                required=("mensagem",),
            )
            assunto = _texto_ia_limpo(parsed.get("assunto"))
            if tipo == "email" and not assunto:
                assunto = f"Follow-up comercial — {cliente.get('nome')}"
            saida = {
                "assunto": assunto,
                "mensagem": _texto_ia_limpo(parsed["mensagem"]),
                "motivo": _texto_ia_limpo(parsed.get("motivo")),
                "contexto_utilizado": parsed.get("contexto_utilizado") or [],
                "tipo": tipo,
                "contato": contato_principal,
                **dados_canal,
                "source": "openrouter",
            }
            return _ok(_registrar_saida_ia(data, "gerar-comunicacao", saida))
        except Exception as exc:  # pragma: no cover
            _log_provider_failure("gerar-comunicacao", exc)

    # Fallback determinístico
    nome_cliente = (cliente or {}).get("nome") or "cliente"
    responsavel = _nome_responsavel_interno(data, cliente)
    destinatario, tem_contato = _nome_destinatario(data, cliente, contato_principal)
    assunto = f"Follow-up comercial — {nome_cliente}"
    contexto_atividade = objetivo or "retomar o relacionamento comercial"
    saudacao = destinatario if tem_contato else destinatario
    if tipo == "whatsapp":
        mensagem = (
            f"Oi {saudacao}, aqui é {responsavel} da CentralComm.\n\n"
            f"Queria falar sobre {contexto_atividade}. "
            f"Preparei este contato considerando o momento da {nome_cliente} "
            "e gostaria de alinhar o próximo passo.\n\n"
            "Faz sentido conversarmos rapidamente esta semana?"
        )
    else:
        mensagem = (
            f"Olá, {destinatario}.\n\n"
            f"Aqui é {responsavel}, da CentralComm.\n\n"
            f"Estou entrando em contato para tratar de {contexto_atividade}. "
            f"Considerei o momento comercial da {nome_cliente} e organizei os pontos "
            "principais para avançarmos com clareza.\n\n"
            "Gostaria de entender sua disponibilidade e combinar o próximo passo. "
            "Podemos reservar uma conversa breve nesta semana?\n\n"
            "Abraço,\n"
            f"{responsavel}\nCentralComm"
        )
    return _ok(_registrar_saida_ia(data, "gerar-comunicacao", {
        "assunto": assunto,
        "mensagem": mensagem,
        "motivo": "Modelo local seguro para retomada comercial.",
        "contexto_utilizado": ["cliente", "contato selecionado", "canal"],
        "tipo": tipo,
        "contato": contato_principal,
        **dados_canal,
        "source": "fallback",
    }))


@bp.route("/api/ia/sugerir-objetivos", methods=["POST"])
@login_required_api
def api_ia_sugerir_objetivos():
    """Sugere 3-5 objetivos comerciais para o próximo mês.

    Paridade com /crm/api/ia/sugerir-objetivos. Cai em fallback determinístico
    se OPENROUTER_API_KEY não estiver definida.
    """
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id") or ""
    cliente = store.get_cliente(cliente_id) if cliente_id else None
    if not cliente:
        return _err("Cliente não encontrado", 404)

    if _openrouter_available():
        try:
            contexto = _contexto_ia_json(data, "objetivos")
            system_prompt = (
                "Você é consultor comercial da CENTRALCOMM, especialista em mídia. "
                "Sugira 3 a 5 objetivos mensuráveis que não dupliquem objetivos abertos "
                "e que avancem oportunidades, decisores ou expansão de canais. "
                "Retorne APENAS JSON: "
                '{"objetivos":[{"texto":"verbo + resultado verificável",'
                '"prazo_dias":30,"motivo":"..."}]}.'
            )
            parsed = _parse_ia_json(
                _call_openrouter(system_prompt, contexto, max_tokens=800, temperature=0.4),
                required=("objetivos",),
            )
            objetivos = parsed.get("objetivos")
            if not isinstance(objetivos, list):
                raise ValueError("objetivos precisa ser uma lista")
            normalizados = []
            for item in objetivos[:5]:
                if isinstance(item, str):
                    item = {"texto": item}
                texto = _texto_ia_limpo(item.get("texto"))
                if texto:
                    normalizados.append({
                        "texto": texto,
                        "prazo_dias": max(1, min(int(item.get("prazo_dias") or 30), 180)),
                        "motivo": _texto_ia_limpo(item.get("motivo")),
                    })
            return _ok(_registrar_saida_ia(data, "sugerir-objetivos", {
                "objetivos": normalizados, "source": "openrouter",
            }))
        except Exception as exc:  # pragma: no cover
            _log_provider_failure("sugerir-objetivos", exc)

    # Fallback
    nome = cliente.get("nome") or "cliente"
    objetivos = [
        {"texto": f"Retomar contato com decisor principal de {nome} nesta semana", "prazo_dias": 7, "motivo": "Reativar a conversa comercial."},
        {"texto": f"Apresentar portfólio de mídia programática para {nome}", "prazo_dias": 14, "motivo": "Criar oportunidade de expansão."},
        {"texto": f"Levar case de performance similar ao segmento de {nome}", "prazo_dias": 21, "motivo": "Reduzir risco percebido."},
        {"texto": f"Agendar reunião de planejamento comercial trimestral com {nome}", "prazo_dias": 30, "motivo": "Definir próximos investimentos."},
    ]
    return _ok(_registrar_saida_ia(data, "sugerir-objetivos", {
        "objetivos": objetivos, "source": "fallback",
    }))


@bp.route("/api/ia/extrair-contatos", methods=["POST"])
@login_required_api
def api_ia_extrair_contatos():
    """Extrai contatos estruturados de texto livre (paridade com crm/ia_routes)."""
    data = request.get_json(silent=True) or {}
    texto = (data.get("texto") or "").strip()
    if not texto:
        return _err("Texto obrigatório", 400)

    if _openrouter_available():
        try:
            import json as json_mod
            system_prompt = (
                "Você é um extrator de dados de contatos profissionais. "
                "Retorne APENAS um array JSON válido com objetos "
                "{\"nome\":\"...\",\"email\":\"...\",\"telefone\":\"...\","
                "\"telefone2\":\"...\",\"cargo\":\"...\"}. "
                "Nome e email são obrigatórios."
            )
            resp = _call_openrouter(system_prompt, texto, max_tokens=2000, temperature=0.1).strip()
            if resp.startswith("```"):
                resp = resp.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            contatos = json_mod.loads(resp)
            if not isinstance(contatos, list):
                raise ValueError("Resposta da IA não é um array JSON")
            limpos = []
            for c in contatos:
                nome = (c.get("nome") or "").strip()
                email = (c.get("email") or "").strip().lower()
                if nome and email and "@" in email:
                    limpos.append({
                        "nome": nome,
                        "email": email,
                        "telefone": (c.get("telefone") or "").strip(),
                        "telefone2": (c.get("telefone2") or "").strip(),
                        "cargo": (c.get("cargo") or "").strip(),
                    })
            return _ok({"contatos": limpos, "source": "openrouter"})
        except Exception as exc:  # pragma: no cover
            _log_provider_failure("extrair-contatos", exc)

    # Fallback: usa o parser determinístico local
    contatos = parse_texto_contatos(texto)
    return _ok({"contatos": contatos, "source": "fallback"})


# ---------------------------------------------------------------------------
# OCR de contatos — Gemini 2.5 Flash multimodal
# ---------------------------------------------------------------------------
# Usada pelo modal "Importar contatos" quando o usuário arrasta / cola /
# faz upload de um print (WhatsApp, LinkedIn, cartão de visita, e-mail
# assinatura). O modelo Gemini 2.5 Flash é multimodal nativo e cobre bem
# o custo/benefício (~$0.075/M input tokens). Se falhar (chave ausente,
# imagem inválida, modelo saiu do ar), a rota devolve 4xx/5xx com a
# mensagem real — o frontend renderiza o erro no modal e o usuário
# pode cair de volta no fluxo "colar texto".
#
# Contrato:
#   Request:
#     multipart/form-data
#       - file: arquivo de imagem (png/jpg/jpeg/webp/heic)
#     OU
#     application/json
#       - image_base64: string (data URL ou base64 puro)
#       - mime_type: string opcional (default image/png)
#   Response 200:
#     {
#       success: true,
#       data: { contatos: [{nome,email,telefone,cargo}, ...],
#               source: "openrouter" | "fallback",
#               raw_text: string  // texto do OCR bruto p/ usuário revisar }
#     }
# ---------------------------------------------------------------------------
_OCR_MIMES_ACEITOS = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/heic", "image/heif"}
_OCR_TAMANHO_MAX_BYTES = 8 * 1024 * 1024  # 8 MB — limita custo e latência


@bp.route("/api/ia/ocr-contatos", methods=["POST"])
@login_required_api
def api_ia_ocr_contatos():
    """Extrai contatos de uma imagem (print, foto de cartão, assinatura)."""
    import base64
    import json as json_mod

    if not _openrouter_available():
        return _err(
            "OpenRouter não configurado — o servidor não tem OPENROUTER_API_KEY. "
            "Cole os contatos como texto no formato Nome;email;telefone;cargo.",
            503,
        )

    # -------------------------------------------------------------
    # 1) Coleta a imagem: multipart/form-data OU JSON com base64.
    #    Preferimos multipart (menos overhead que base64 no wire),
    #    mas aceitamos JSON para o caso do frontend usar clipboard
    #    API (que já entrega Blob → base64 mais fácil).
    # -------------------------------------------------------------
    image_bytes: bytes = b""
    mime_type: str = ""

    if request.files and "file" in request.files:
        f = request.files["file"]
        image_bytes = f.read()
        mime_type = (f.mimetype or "").lower() or "image/png"
    else:
        data = request.get_json(silent=True) or {}
        b64 = (data.get("image_base64") or "").strip()
        if not b64:
            return _err("Envie um arquivo (multipart 'file') ou 'image_base64' (JSON)", 400)
        # Aceita data URL completo (data:image/png;base64,XXXX) ou só o base64.
        if b64.startswith("data:"):
            try:
                header, b64_payload = b64.split(",", 1)
                mime_type = header.split(";")[0].replace("data:", "").strip().lower()
            except ValueError:
                return _err("Data URL inválido", 400)
            b64 = b64_payload
        try:
            image_bytes = base64.b64decode(b64, validate=True)
        except Exception:
            return _err("Base64 inválido", 400)
        if not mime_type:
            mime_type = (data.get("mime_type") or "image/png").strip().lower()

    if not image_bytes:
        return _err("Imagem vazia", 400)
    if len(image_bytes) > _OCR_TAMANHO_MAX_BYTES:
        return _err(f"Imagem muito grande (máximo {_OCR_TAMANHO_MAX_BYTES // (1024*1024)} MB)", 400)
    if mime_type not in _OCR_MIMES_ACEITOS:
        return _err(f"Formato não suportado: {mime_type}. Use PNG, JPEG, WEBP ou HEIC.", 400)

    # -------------------------------------------------------------
    # 2) Monta o data URL e chama o Gemini 2.5 Flash.
    # -------------------------------------------------------------
    data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    system_prompt = (
        "Você é um extrator de contatos profissionais a partir de imagens. "
        "A imagem pode ser: print de WhatsApp/Telegram, print de LinkedIn, foto "
        "de cartão de visita, assinatura de e-mail, planilha, ou qualquer outra "
        "fonte visual com informações de contato. "
        "Extraia TODOS os contatos visíveis. Para cada contato retorne:\n"
        "  - nome (obrigatório)\n"
        "  - email (obrigatório se aparecer; senão string vazia)\n"
        "  - telefone (formato brasileiro com DDD, ex: 11999999999; string vazia se ausente)\n"
        "  - cargo (função/posição na empresa; string vazia se ausente)\n\n"
        "REGRAS:\n"
        "1. NÃO invente dados. Se algo não aparece na imagem, deixe string vazia.\n"
        "2. Nomes soltos sem contexto de contato (ex: nome da empresa, título de post) "
        "   NÃO contam como contato.\n"
        "3. Se o telefone tiver +55, DDI ou espaços, normalize para dígitos com DDD "
        "   (ex: '+55 (11) 99999-9999' -> '11999999999').\n"
        "4. Se aparecerem múltiplos contatos, retorne todos.\n"
        "5. Ignore rodapés de LGPD, disclaimer legais, endereços da empresa.\n\n"
        "RETORNE APENAS JSON VÁLIDO, sem texto antes ou depois, sem markdown fences. "
        'Formato: {"contatos":[{"nome":"","email":"","telefone":"","cargo":""}, ...]}. '
        'Se nenhum contato for encontrado, retorne {"contatos":[]}.'
    )
    text_prompt = "Extraia os contatos desta imagem seguindo o formato JSON pedido."

    try:
        resp_raw = _call_openrouter_multimodal(
            system_prompt=system_prompt,
            text_prompt=text_prompt,
            image_data_url=data_url,
            max_tokens=3000,
            temperature=0.1,
        )
    except Exception as e:
        return _err(f"Falha ao chamar Gemini: {e}", 502)

    # -------------------------------------------------------------
    # 3) Parseia o JSON. Alguns modelos ainda envolvem em ```json...```
    #    apesar do "sem markdown fences" — normalizamos aqui.
    # -------------------------------------------------------------
    resp_text = (resp_raw or "").strip()
    if resp_text.startswith("```"):
        # Remove primeira linha (```json) e último ```.
        resp_text = resp_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        parsed = json_mod.loads(resp_text)
    except Exception:
        # A UI ainda mostra utilidade: passa o texto bruto pro usuário
        # colar como está (fallback para o parser regex local).
        return _ok({
            "contatos": [],
            "raw_text": resp_text,
            "source": "openrouter-raw",
            "message": "Não foi possível estruturar automaticamente. Revise o texto abaixo.",
        })

    contatos_raw = parsed.get("contatos") if isinstance(parsed, dict) else parsed
    if not isinstance(contatos_raw, list):
        return _ok({"contatos": [], "raw_text": resp_text, "source": "openrouter-empty"})

    # -------------------------------------------------------------
    # 4) Sanitiza cada contato: strip, lowercase de email, dígitos
    #    puros no telefone. Descarta linhas sem nome.
    # -------------------------------------------------------------
    import re as _re
    limpos = []
    for c in contatos_raw:
        if not isinstance(c, dict):
            continue
        nome = (c.get("nome") or "").strip()
        if not nome:
            continue
        email = (c.get("email") or "").strip().lower()
        telefone_raw = (c.get("telefone") or "").strip()
        # Deixa só dígitos e remove código do país 55 duplicado se
        # o modelo insistir em '5511...'. Ficamos com o formato que
        # o crm_v3_helpers.parse_texto_contatos usa (DDD+numero).
        telefone = _re.sub(r"\D+", "", telefone_raw)
        if telefone.startswith("55") and len(telefone) > 11:
            telefone = telefone[2:]
        cargo = (c.get("cargo") or "").strip()
        limpos.append({
            "nome": nome,
            "email": email,
            "telefone": telefone,
            "cargo": cargo,
        })

    return _ok({
        "contatos": limpos,
        "raw_text": resp_text,
        "source": "openrouter",
        "message": (
            f"{len(limpos)} contato(s) reconhecido(s)." if limpos
            else "Nenhum contato foi identificado na imagem."
        ),
    })
