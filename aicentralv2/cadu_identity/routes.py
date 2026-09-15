"""Identity hub and one-time database ticket exchange for PHP/Flask SSO."""

from __future__ import annotations

import hashlib
import secrets
from urllib.parse import urlencode

from flask import Blueprint, current_app, flash, redirect, request, session, url_for

from .. import db
from ..auth import login_required, persist_login_session
from ..product_domains import product_url, safe_product_target
from .google_oidc import GoogleLoginError, authorization_url as google_authorization_url, exchange_code


def _google_realm(target: str) -> str:
    from urllib.parse import urlparse
    centralx_host = (urlparse(product_url("centralx")).hostname or "").lower()
    return "centralx" if (urlparse(target).hostname or "").lower() == centralx_host else "cadu"


bp = Blueprint("cadu_identity", __name__, url_prefix="/auth")


def _start_flask_session(user: dict, auth_method: str = "sso_ticket") -> None:
    client_id = user.get("pk_id_tbl_cliente")
    client = db.obter_cliente_por_id(client_id) if client_id else None
    session.clear()
    persist_login_session()
    session.update(
        user_id=user["id_contato_cliente"],
        user_name=user.get("nome_completo") or "",
        user_email=user.get("email") or "",
        cliente_id=client_id,
        user_type=user.get("user_type") or "client",
        is_finance_admin=bool(user.get("is_finance_admin")),
        is_centralcomm=bool(client and str(client.get("nome_fantasia") or "").upper() == "CENTRALCOMM"),
        auth_method=auth_method,
    )


def _resolve_google_user(identity: dict) -> dict:
    """Resolve an existing internal CentralX account."""
    email = identity["email"]
    found = db.obter_contato_por_email(email)

    if identity["realm"] != "centralx":
        raise GoogleLoginError("O cadastro Google do Cadu é concluído pelo aplicativo Cadu.")
    if not email.endswith("@centralcomm.media"):
        raise GoogleLoginError("O CentralX aceita somente contas Google @centralcomm.media.")
    user = db.obter_contato_por_id(found["id_contato_cliente"]) if found else None
    if not user or not user.get("status") or not user.get("cliente_status"):
        raise GoogleLoginError("Esta conta Google não possui acesso ativo ao CentralX.")
    return user


@bp.get("")
@bp.get("/")
def index():
    if session.get("user_id"):
        if session.get("is_centralcomm"):
            return redirect(product_url("centralx"), code=302)
        # Cadu permanece em PHP; entre nele pela troca de ticket para criar
        # também a sessão PHP, em vez de cair numa página sem PHPSESSID.
        return redirect(
            url_for("cadu_identity.issue_cadu_ticket", next=product_url("cadu")),
            code=302,
        )
    return redirect(url_for("login", next=product_url("cadu")), code=302)


@bp.get("/google")
def google_login():
    try:
        target = safe_product_target(
            request.args.get("next"), product_url("centralx")
        )
        if _google_realm(target) == "cadu":
            login_url = str(
                current_app.config.get("CADU_GOOGLE_LOGIN_URL")
                or product_url("cadu", "/google-login.php")
            )
            separator = "&" if "?" in login_url else "?"
            # `return_to` já viaja no contrato para a futura troca de URLs. O
            # PHP atual usa v3/nav e continua responsável pelo provisionamento.
            query = urlencode({"v3": "1", "nav": "/v3", "return_to": target})
            return redirect(f"{login_url}{separator}{query}", code=302)
        session["google_auth_next"] = target
        return redirect(google_authorization_url("centralx"), code=302)
    except GoogleLoginError as exc:
        flash(str(exc), "error")
        return redirect(url_for("login"), code=302)


@bp.get("/google/callback")
def google_callback():
    target = safe_product_target(session.pop("google_auth_next", ""), product_url("centralx"))
    if request.args.get("error"):
        session.pop("google_auth_state", None)
        session.pop("google_auth_nonce", None)
        session.pop("google_auth_pkce", None)
        session.pop("google_auth_realm", None)
        flash("O login com Google foi cancelado.", "warning")
        return redirect(url_for("login", next=target), code=302)
    try:
        identity = exchange_code(request.args.get("code") or "", request.args.get("state") or "")
        user = _resolve_google_user(identity)
        _start_flask_session(user, auth_method="google")
        session["google_identity_sub"] = identity["sub"]
        return redirect(target, code=303)
    except GoogleLoginError as exc:
        current_app.logger.warning("Login Google recusado: %s", exc)
        flash(str(exc), "error")
        return redirect(url_for("login", next=target), code=302)


@bp.get("/sso/consume")
def consume_sso():
    """Consume a short-lived token created by PHP or another trusted app."""
    ticket = str(request.args.get("ticket") or "").strip()
    if len(ticket) < 43 or len(ticket) > 128:
        flash("O acesso compartilhado é inválido ou já expirou.", "error")
        return redirect(url_for("login"), code=302)

    token_hash = hashlib.sha256(ticket.encode("utf-8")).hexdigest()
    conn = db.get_db()
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, user_id, target_url
              FROM cadu_sso_tickets
             WHERE token_hash = %s
               AND consumed_at IS NULL
               AND expires_at > NOW()
             FOR UPDATE
            """,
            (token_hash,),
        )
        row = cursor.fetchone()
        if not row:
            flash("O acesso compartilhado é inválido ou já expirou.", "error")
            return redirect(url_for("login"), code=302)
        user = db.obter_contato_por_id(row["user_id"])
        if not user or not user.get("status"):
            flash("Esta conta não está disponível.", "error")
            return redirect(url_for("login"), code=302)
        cursor.execute(
            "UPDATE cadu_sso_tickets SET consumed_at = NOW() WHERE id = %s AND consumed_at IS NULL",
            (row["id"],),
        )
    conn.commit()
    _start_flask_session(user)
    response = redirect(safe_product_target(row.get("target_url"), product_url("centralx")), code=303)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@bp.get("/sso/to-cadu")
@login_required
def issue_cadu_ticket():
    """Create a one-time ticket for the PHP application to consume."""
    consume_url = str(current_app.config.get("CADU_SSO_CONSUME_URL") or "").strip()
    if not consume_url:
        flash("A entrada integrada do Cadu ainda não foi configurada.", "warning")
        return redirect(product_url("cadu"), code=302)

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    target = safe_product_target(request.args.get("next"), product_url("cadu"))
    conn = db.get_db()
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO cadu_sso_tickets
                (token_hash, user_id, source_app, target_url, expires_at)
            VALUES (%s, %s, 'python', %s, NOW() + INTERVAL '90 seconds')
            """,
            (token_hash, session["user_id"], target),
        )
    conn.commit()
    separator = "&" if "?" in consume_url else "?"
    response = redirect(f"{consume_url}{separator}{urlencode({'ticket': raw_token})}", code=303)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
