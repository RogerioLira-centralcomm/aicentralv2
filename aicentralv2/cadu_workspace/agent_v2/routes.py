"""Versioned backend contract consumed by the future Conversations V2 UI."""

import secrets
from uuid import uuid4

from flask import Blueprint, Response, abort, current_app, jsonify, render_template, request, session, stream_with_context
from werkzeug.exceptions import HTTPException

from ...cadu_family import repository
from .request_context import resolve
from .response_policy import budget_for, policy_for
from .router import route_request
from .contracts import execution_mode_for
from ..mcp.registry import load_builtin_tools
from ..mcp.authorization import MAX_AGE_SECONDS, issue
from ..artifacts import create_draft, get_artifact, get_version, list_versions, patch_artifact
from .service import prepare as prepare_message, stream as stream_message
from . import journal, observability
from . import action_executor
from ..mcp.registry import ToolError
from ..conversations import attachments
from ...cadu_planner import docs


bp = Blueprint("cadu_agent_v2", __name__, url_prefix="/workspace/api/v2")
lab_bp = Blueprint("cadu_agent_v2_lab", __name__)


@lab_bp.get("/workspace/conversas-v2-lab")
def conversations_v2_lab():
    if not session.get("user_id"):
        abort(401)
    return render_template("cadu_workspace/conversations_v2_lab.html")


@lab_bp.get("/workspace/observabilidade")
def observability_page():
    if not session.get("user_id"):
        abort(401)
    if session.get("user_type") not in {"admin", "superadmin"}:
        abort(403)
    client_id = resolve().client_id
    return render_template("cadu_workspace/observability.html", telemetry=observability.dashboard(client_id))


@bp.before_request
def protect():
    if not session.get("user_id"):
        abort(401)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        token = session.get("family_csrf")
        if not token or not secrets.compare_digest(token, request.headers.get("X-CSRF-Token", "")):
            abort(403, description="Atualize a página e tente novamente.")


@bp.errorhandler(Exception)
def api_error(exc):
    if isinstance(exc, HTTPException):
        return jsonify(error=exc.description), exc.code
    current_app.logger.exception("Falha na API Cadu Conversations V2")
    return jsonify(error="Não foi possível concluir a operação."), 503


@bp.get("/capabilities")
def capabilities():
    current = resolve(surface=request.args.get("surface") or "conversations")
    return jsonify(runtime="v2", context=current.to_dict(), tools=load_builtin_tools().list(current))


@bp.post("/mcp-token")
def mcp_token():
    data = request.get_json(silent=True) or {}
    exposure = str(data.get("exposure") or "internal")
    if exposure not in {"internal", "customer_agent"}:
        abort(400, description="Perfil de agente inválido.")
    current = resolve(conversation_id=data.get("conversation_id"),
                      surface=str(data.get("surface") or "conversations"),
                      active_object=data.get("active_object"))
    return jsonify(token=issue(current, exposure), expires_in=MAX_AGE_SECONDS,
                   endpoint="/workspace/mcp", exposure=exposure, context=current.to_dict())


@bp.post("/route")
def route_preview():
    data = request.get_json(silent=True) or {}
    message = " ".join(str(data.get("message") or "").split())
    if not 1 <= len(message) <= 20000:
        abort(400, description="Informe uma mensagem de até 20.000 caracteres.")
    current = resolve(conversation_id=data.get("conversation_id"),
                      surface=str(data.get("surface") or "conversations"),
                      active_object=data.get("active_object"))
    route = route_request(message, current.surface, bool(current.project_ref))
    execution_mode = execution_mode_for(route, data.get("execution_mode") or data.get("depth") or data.get("mode"))
    return jsonify(
        route=route.to_dict(), execution_mode=execution_mode, context=current.to_dict(), policy=policy_for(route),
        budget=budget_for(route, execution_mode).__dict__,
    )


@bp.post("/conversations/messages")
def conversation_message():
    if not current_app.config.get("CADU_CONVERSATIONS_V2_ENABLED", False):
        abort(404)
    run = prepare_message(request.get_json(silent=True) or {})
    return Response(stream_with_context(stream_message(run)), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.post("/uploads")
def upload():
    current = resolve(surface="conversations")
    if not repository.family_table_available("cadu_family_chat_uploads"):
        abort(409, description="O armazenamento de anexos ainda não está disponível.")
    request.max_content_length = attachments.MAX_BYTES + 65536
    files = request.files.getlist("file")
    if len(files) != 1 or len(request.files) != 1:
        abort(400, description="Envie um arquivo de cada vez.")
    validated, kind, size = attachments.validate(files[0])
    from . import provider
    provider_id = provider.upload_file(validated, "user-" + str(current.user_id), "analysis")
    upload_id = str(uuid4())
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO cadu_family_chat_uploads
                (id, user_id, client_id, provider_id, name, kind)
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (upload_id, current.user_id, current.client_id, provider_id, validated.filename, kind))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return jsonify(file={"id": upload_id, "name": validated.filename, "kind": kind, "size": size}), 201


@bp.post("/resources/<uuid:resource_id>/editable-copy")
def resource_editable_copy(resource_id):
    current = resolve(surface="conversations")
    rows = repository.rows(
        """SELECT project_ref, source_id, title FROM cadu_project_resources
             WHERE id = %s AND organization_id = %s AND client_id = %s
               AND source_system = 'workspace' AND source_id LIKE 'file:%%'""",
        (str(resource_id), current.organization_id, current.client_id),
    )
    if not rows:
        abort(404, description="Arquivo indisponível para conversão.")
    resource = rows[0]
    source_id = str(resource["source_id"])[5:]
    project_ref = str(resource.get("project_ref") or "")
    if not source_id.isdigit() or not project_ref.startswith("ci:"):
        abort(409, description="Este arquivo não possui uma versão editável disponível.")
    sources = repository.rows(
        """SELECT nome_arquivo, extracted_text FROM cadu_ci_projeto_arquivos
             WHERE id = %s AND id_cliente = %s AND projeto_id = %s""",
        (int(source_id), current.client_id, project_ref[3:]),
    )
    text = str(sources[0].get("extracted_text") or "").strip() if sources else ""
    if not text:
        abort(409, description="O arquivo precisa terminar a indexação antes de virar documento editável.")
    document = docs.create_document(current.client_id, current.user_id, {
        "title": resource.get("title") or sources[0].get("nome_arquivo") or "Documento importado",
        "type": "documento",
        "project_id": project_ref[3:],
        "html": docs.markdown_to_safe_html(text),
    })
    return jsonify(document={
        "id": str(document["id"]),
        "title": document.get("title"),
        "editor_url": f"/workspace/docs/{document['id']}",
    }), 201


@bp.get("/runs/<uuid:run_id>/events")
def run_events(run_id):
    current = resolve()
    return jsonify(events=journal.events(str(run_id), current.client_id, current.user_id))


@bp.get("/runs/<uuid:run_id>/state")
def run_state(run_id):
    current = resolve()
    try:
        return jsonify(journal.state(str(run_id), current.client_id, current.user_id))
    except ValueError as exc:
        abort(404, description=str(exc))


@bp.post("/runs/<uuid:run_id>/steps/<uuid:step_id>/decision")
def run_step_decision(run_id, step_id):
    current = resolve()
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("approved"), bool):
        abort(400, description="Informe approved como verdadeiro ou falso.")
    try:
        step = journal.decide_step(str(run_id), str(step_id), current.client_id, current.user_id,
                                   data["approved"], data.get("note"))
        if data["approved"] and step.get("kind") == "action":
            try:
                receipt = action_executor.execute(step, current)
                step = journal.finish_action(str(run_id), str(step_id), current.client_id, current.user_id,
                                             receipt=receipt)
            except ToolError as exc:
                journal.finish_action(str(run_id), str(step_id), current.client_id, current.user_id,
                                      error_code=exc.code)
                abort(409, description=str(exc))
            except Exception:
                journal.finish_action(str(run_id), str(step_id), current.client_id, current.user_id,
                                      error_code="action_failed")
                raise
        return jsonify(step=step, state=journal.state(str(run_id), current.client_id, current.user_id))
    except ValueError as exc:
        abort(409, description=str(exc))


@bp.get("/observability/runs/<uuid:run_id>")
def observability_run(run_id):
    if session.get("user_type") not in {"admin", "superadmin"}:
        abort(403)
    current = resolve()
    try:
        return jsonify(observability.run_detail(current.client_id, str(run_id)))
    except ValueError as exc:
        abort(404, description=str(exc))


@bp.post("/runs/<uuid:run_id>/stop")
def stop_run(run_id):
    current = resolve()
    rows = repository.rows(
        """SELECT task_id, status, execution_mode FROM cadu_family_chat_runs
             WHERE id = %s AND user_id = %s AND client_id = %s AND runtime_version = 'v2'""",
        (str(run_id), current.user_id, current.client_id),
    )
    if not rows:
        abort(404)
    if rows[0]["status"] != "running":
        return jsonify(stopped=True)
    if not rows[0].get("task_id"):
        abort(409, description="A geração ainda está iniciando. Tente novamente.")
    from . import provider
    provider.stop(rows[0]["task_id"], "user-" + str(current.user_id),
                  rows[0].get("execution_mode") or "analysis")
    conn = repository.get_db()
    with conn.cursor() as cur:
        cur.execute("""UPDATE cadu_family_chat_runs SET status = 'cancelled', finished_at = NOW()
                       WHERE id = %s AND user_id = %s AND client_id = %s AND status = 'running'""",
                    (str(run_id), current.user_id, current.client_id))
    conn.commit()
    try:
        journal.record(str(run_id), "run.cancelled", {"user_id": current.user_id})
    except Exception:
        current_app.logger.exception("Falha ao registrar cancelamento do Turn %s", run_id)
    return jsonify(stopped=True)


@bp.post("/artifacts")
def artifact_create():
    data = request.get_json(silent=True) or {}
    current = resolve(conversation_id=data.get("conversation_id"),
                      surface=str(data.get("surface") or "conversations"))
    artifact = create_draft(current, str(data.get("type") or ""), data.get("content"),
                            title=data.get("title"), conversation_id=data.get("conversation_id"))
    return jsonify(artifact=artifact), 201


@bp.get("/artifacts/<uuid:artifact_id>")
def artifact_get(artifact_id):
    return jsonify(artifact=get_artifact(resolve(), str(artifact_id)))


@bp.get("/artifacts/<uuid:artifact_id>/versions")
def artifact_versions(artifact_id):
    return jsonify(versions=list_versions(resolve(), str(artifact_id)))


@bp.get("/artifacts/<uuid:artifact_id>/versions/<int:version>")
def artifact_version(artifact_id, version):
    return jsonify(version=get_version(resolve(), str(artifact_id), version))


@bp.patch("/artifacts/<uuid:artifact_id>")
def artifact_patch(artifact_id):
    data = request.get_json(silent=True) or {}
    artifact = patch_artifact(resolve(conversation_id=data.get("conversation_id")), str(artifact_id),
                              data.get("content"), expected_version=data.get("expected_version"),
                              title=data.get("title"), status=data.get("status"),
                              change_summary=data.get("change_summary"))
    return jsonify(artifact=artifact)
