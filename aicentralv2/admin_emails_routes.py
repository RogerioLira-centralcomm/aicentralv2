"""Painel de e-mails do CentralX: eventos, histórico por usuário e ações em massa na sequência.

Somente admin interno da CentralComm. Ações passam por uma prévia com a contagem
(``/acao`` com ``dry_run``) antes de executar, e cada execução vai para a auditoria.
"""
from __future__ import annotations

import logging
import secrets

from flask import Blueprint, abort, jsonify, render_template, request, session

from .auth import admin_required, admin_required_api
from .services import cadu_email_admin as admin
from .services.cadu_email_sequence import SEQUENCE_STEPS, sequence_enabled

bp = Blueprint("admin_emails", __name__, url_prefix="/admin/emails")
logger = logging.getLogger(__name__)
MAX_BULK = 5000


def _csrf() -> str:
    token = session.get("admin_emails_csrf")
    if not token:
        token = session["admin_emails_csrf"] = secrets.token_urlsafe(24)
    return token


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@bp.get("/")
@admin_required
def page():
    tab = request.args.get("tab", "visao")
    if tab not in {"visao", "eventos", "sequencia"}:
        tab = "visao"
    context = {"tab": tab, "csrf": _csrf(), "steps": SEQUENCE_STEPS, "actions": admin.ACTIONS,
               "status_labels": admin.STATUS_LABELS, "sequence_labels": admin.SEQUENCE_STATUS_LABELS,
               "sequence_enabled": sequence_enabled(), "args": request.args}
    try:
        if tab == "visao":
            context["overview"] = admin.overview(_int(request.args.get("dias"), 7))
        elif tab == "eventos":
            context["events"] = admin.list_events(q=request.args.get("q", "").strip(), status=request.args.get("status", ""),
                                                  kind=request.args.get("tipo", ""), days=_int(request.args.get("dias"), 30),
                                                  page=_int(request.args.get("pagina"), 1))
        else:
            context["sequence"] = admin.list_sequence(q=request.args.get("q", "").strip(), status=request.args.get("status", ""),
                                                      step=request.args.get("passo", ""), page=_int(request.args.get("pagina"), 1))
    except Exception:
        logger.exception("Painel de e-mails: falha ao consultar")
        context["load_error"] = True
    return render_template("admin/emails.html", **context)


@bp.get("/usuario/<int:contato_id>")
@admin_required
def user(contato_id):
    history = admin.user_history(contato_id)
    if not history:
        abort(404)
    return render_template("admin/emails_usuario.html", h=history, csrf=_csrf(), steps=SEQUENCE_STEPS,
                           actions=admin.ACTIONS, status_labels=admin.STATUS_LABELS,
                           sequence_labels=admin.SEQUENCE_STATUS_LABELS)


@bp.post("/acao")
@admin_required_api
def action():
    payload = request.get_json(silent=True) or {}
    if not secrets.compare_digest(str(request.headers.get("X-CSRF-Token") or ""), session.get("admin_emails_csrf") or "-"):
        return jsonify({"ok": False, "error": "Sessão expirada. Atualize a página."}), 403
    name = str(payload.get("action") or "")
    if name not in admin.ACTIONS:
        return jsonify({"ok": False, "error": "Ação desconhecida."}), 400
    filters = payload.get("filters") if payload.get("scope") == "filter" else None
    targets = admin.resolve_targets(contato_ids=payload.get("ids") or [],
                                    filters=filters if isinstance(filters, dict) else None)
    if len(targets) > MAX_BULK:
        return jsonify({"ok": False, "error": f"Selecione no máximo {MAX_BULK} pessoas por vez."}), 400
    if payload.get("dry_run"):
        return jsonify({"ok": True, "count": len(targets), "label": admin.ACTIONS[name]})
    affected = admin.apply_action(name, targets)
    try:
        from .audit import registrar_acao_admin
        registrar_acao_admin(session.get("user_id"), "UPDATE", "emails",
                             descricao=f"{admin.ACTIONS[name]}: {affected} de {len(targets)} contato(s)",
                             dados_novos={"action": name, "contatos": targets[:200], "afetados": affected})
    except Exception:
        logger.warning("Painel de e-mails: ação sem registro de auditoria.", exc_info=True)
    return jsonify({"ok": True, "count": len(targets), "affected": affected})
