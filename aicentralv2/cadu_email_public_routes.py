"""Descadastro público da sequência de e-mails do Cadu.

O link do e-mail leva a uma confirmação (GET não descadastra: leitores de e-mail
abrem links sozinhos). O POST descadastra e também atende o "um clique" do
cabeçalho List-Unsubscribe-Post (RFC 8058), sem sessão: o token assinado basta.
"""
from __future__ import annotations

import logging

from flask import Blueprint, abort, render_template

from .services.cadu_email_sequence import read_unsubscribe_token, set_opt_out

bp = Blueprint("cadu_email_public", __name__)
logger = logging.getLogger(__name__)


@bp.get("/workspace/email/descadastrar/<token>")
def unsubscribe_confirm(token):
    if read_unsubscribe_token(token) is None:
        abort(404)
    return render_template("emails/descadastro.html", token=token, done=False)


@bp.post("/workspace/email/descadastrar/<token>")
def unsubscribe_apply(token):
    contato_id = read_unsubscribe_token(token)
    if contato_id is None:
        abort(404)
    try:
        set_opt_out(contato_id, "link")
    except Exception:
        logger.exception("Descadastro não aplicado para o contato %s", contato_id)
        abort(503, description="Não foi possível concluir agora. Tente novamente em instantes.")
    return render_template("emails/descadastro.html", token=token, done=True)
