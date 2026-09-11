"""Rotas da tela de fechamento e do workspace financeiro do PI."""

import logging

from flask import Blueprint, flash, jsonify, make_response, redirect, render_template, request, session, url_for

from .auth import login_required, login_required_api
from .pi_documento_service import (
    DocumentoIndisponivelError,
    PiDocumentoService,
    STATUS_NF_PARA_FINANCEIRO,
    status_financeiro_por_notas,
)
from .pi_fechamento_service import HandoffBloqueadoError, PiFechamentoService
from .pi_operacao_repository import PiNaoEncontradoError


logger = logging.getLogger(__name__)
bp = Blueprint("pi_financeiro", __name__)


def _iso_date(value):
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    return text[:10] if text else ""


def _br_date(iso):
    if not iso or len(str(iso)) < 10:
        return "—"
    year, month, day = str(iso)[:10].split("-")
    return f"{day}/{month}/{year}"


def serializar_nota_fiscal(nota):
    row = dict(nota or {})
    for campo in (
        "data_emissao",
        "data_pagamento_previsto",
        "data_pagamento_realizado",
        "created_at",
        "updated_at",
    ):
        iso = _iso_date(row.get(campo))
        row[campo] = iso
        row[f"{campo}_br"] = _br_date(iso) if iso else "—"
    row["tem_pdf"] = bool(row.get("nf_arquivo_path"))
    if row.get("status") is not None:
        try:
            row["status"] = int(row["status"])
        except (TypeError, ValueError):
            pass
    return row


def _service():
    return PiFechamentoService()


def _erro_json(error, status):
    if isinstance(error, HandoffBloqueadoError):
        return jsonify({
            "success": False,
            "message": "PI com pendências de fechamento.",
            "pendencias": error.pendencias,
        }), status
    return jsonify({"success": False, "message": str(error)}), status


@bp.route("/cadu_pi/<int:id_pi>/fechamento")
@login_required
def fechamento(id_pi):
    from . import db

    pi = db.obter_cadu_pi_por_id(id_pi)
    if not pi:
        flash("PI não encontrado.", "error")
        return redirect(url_for("cadu_pi_lista", id_sub_status_pi=3))
    if str(pi.get("id_sub_status_pi")) not in {"3", "4"}:
        flash("Este PI ainda não está em fechamento.", "error")
        return redirect(url_for("cadu_pi_editar", id_pi=id_pi))
    if str(pi.get("id_sub_status_pi")) == "4":
        return redirect(url_for("pi_financeiro.workspace", id_pi=id_pi))
    preview = _service().preview(id_pi)
    doc_service = PiDocumentoService()
    documentos = doc_service.listar(preview)
    documentos_resumo = doc_service.resumo_sidebar(preview, modo="fechamento")
    return render_template(
        "cadu_pi_fechamento.html",
        pi=pi,
        preview=preview,
        documentos=documentos,
        documentos_resumo=documentos_resumo,
        modo="fechamento",
        somente_leitura=False,
        operacao_modo="pi",
    )


@bp.route("/cadu_pi/<int:id_pi>/financeiro")
@login_required
def workspace(id_pi):
    from . import db

    pi = db.obter_cadu_pi_por_id(id_pi)
    if not pi:
        flash("PI não encontrado.", "error")
        return redirect(url_for("cadu_pi_lista", id_sub_status_pi=4, origem="operacao"))
    resultado = _service().resultado(id_pi)
    documentos = PiDocumentoService().listar(resultado)
    try:
        notas = [serializar_nota_fiscal(item) for item in (db.obter_notas_fiscais_por_pi(id_pi) or [])]
        statuses_nf = list(db.obter_nota_fiscal_status() or [])
    except Exception:
        logger.exception("Erro ao carregar notas fiscais do PI %s", id_pi)
        notas = []
        statuses_nf = []
    resultado["notas_fiscais"] = notas
    doc_service = PiDocumentoService()
    comunicacoes_cliente = doc_service.listar_cliente(resultado, notas)
    documentos_resumo = doc_service.resumo_sidebar(resultado, modo="financeiro", notas=notas)
    id_status_pago = next(
        (item.get("id") for item in statuses_nf if str(item.get("descricao") or "") == "Pagamento Realizado"),
        None,
    )
    return render_template(
        "cadu_pi_financeiro.html",
        pi=pi,
        preview=resultado,
        documentos=documentos,
        comunicacoes_cliente=comunicacoes_cliente,
        documentos_resumo=documentos_resumo,
        notas_fiscais=notas,
        statuses_nf=statuses_nf,
        id_status_pagamento_realizado=id_status_pago,
        modo="financeiro",
        somente_leitura=False,
        operacao_modo="pi",
    )


@bp.get("/api/cadu_pi/<int:id_pi>/documentos/resumo")
@login_required_api
def api_documentos_resumo(id_pi):
    from . import db

    pi = db.obter_cadu_pi_por_id(id_pi)
    if not pi:
        return _erro_json("PI não encontrado", 404)
    substatus = str(pi.get("id_sub_status_pi") or "")
    doc_service = PiDocumentoService()
    if substatus == "3":
        snapshot = _service().preview(id_pi)
        modo = "fechamento"
        notas = []
    elif substatus in {"4", "5"}:
        snapshot = _service().resultado(id_pi)
        modo = "financeiro"
        try:
            notas = [
                serializar_nota_fiscal(item)
                for item in (db.obter_notas_fiscais_por_pi(id_pi) or [])
            ]
        except Exception:
            logger.exception("Erro ao carregar notas para resumo do PI %s", id_pi)
            notas = []
        snapshot["notas_fiscais"] = notas
    else:
        return jsonify({"success": True, "data": {"modo": "operacao", "documentos": [], "fiscal": None}})
    return jsonify({
        "success": True,
        "data": doc_service.resumo_sidebar(snapshot, modo=modo, notas=notas),
    })


@bp.get("/api/cadu_pi/<int:id_pi>/resultado-fechamento/preview")
@login_required_api
def api_preview(id_pi):
    try:
        return jsonify({"success": True, "data": _service().preview(id_pi)})
    except PiNaoEncontradoError:
        return _erro_json("PI não encontrado", 404)
    except Exception:
        logger.exception("Erro no preview de fechamento do PI %s", id_pi)
        return _erro_json("Erro ao montar preview de fechamento.", 500)


@bp.route("/cadu_pi/<int:id_pi>/financeiro/documento/<tipo>.pdf")
@login_required
def documento_pdf(id_pi, tipo):
    try:
        pdf, filename = PiDocumentoService().gerar(
            id_pi,
            tipo,
            variante=request.args.get("variante") or "agencia",
            id_campanha=request.args.get("id_campanha") or None,
            mensagem=request.args.get("mensagem") or None,
        )
    except DocumentoIndisponivelError as exc:
        flash(str(exc), "error")
        return redirect(url_for("pi_financeiro.workspace", id_pi=id_pi))
    except PiNaoEncontradoError:
        flash("PI não encontrado.", "error")
        return redirect(url_for("cadu_pi_lista", id_sub_status_pi=4, origem="operacao"))
    except Exception:
        logger.exception("Erro ao gerar PDF %s do PI %s", tipo, id_pi)
        flash("Não foi possível gerar o documento.", "error")
        return redirect(url_for("pi_financeiro.workspace", id_pi=id_pi))

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@bp.get("/api/cadu_pi/<int:id_pi>/resultado-fechamento")
@login_required_api
def api_resultado(id_pi):
    try:
        return jsonify({"success": True, "data": _service().resultado(id_pi)})
    except PiNaoEncontradoError:
        return _erro_json("PI não encontrado", 404)
    except Exception:
        logger.exception("Erro ao ler resultado de fechamento do PI %s", id_pi)
        return _erro_json("Erro ao ler resultado de fechamento.", 500)


@bp.put("/api/cadu_pi/<int:id_pi>/provisionamentos")
@login_required_api
def api_salvar_provisionamentos(id_pi):
    try:
        snapshot = _service().salvar_provisionamentos(
            id_pi,
            session.get("user_id"),
            request.get_json(silent=True) or {},
        )
        return jsonify({"success": True, "data": snapshot})
    except PiNaoEncontradoError:
        return _erro_json("PI não encontrado", 404)
    except Exception:
        logger.exception("Erro ao salvar provisionamentos do PI %s", id_pi)
        return _erro_json("Não foi possível salvar os provisionamentos.", 500)


@bp.post("/api/cadu_pi/<int:id_pi>/documentos/<tipo>/enviar-assinatura")
@login_required_api
def api_enviar_assinatura(id_pi, tipo):
    body = request.get_json(silent=True) or {}
    try:
        data = PiDocumentoService().enviar_para_assinatura(
            id_pi,
            tipo,
            mensagem=body.get("mensagem"),
            variante=body.get("variante") or "agencia",
            autor_id=session.get("user_id"),
        )
        return jsonify({"success": True, "data": data})
    except DocumentoIndisponivelError as exc:
        return _erro_json(exc, 400)
    except PiNaoEncontradoError:
        return _erro_json("PI não encontrado", 404)
    except Exception:
        logger.exception("Erro ao enviar documento %s do PI %s", tipo, id_pi)
        return _erro_json("Não foi possível enviar o documento para assinatura.", 500)


@bp.put("/api/cadu_pi/<int:id_pi>/financeiro/notas/<int:id_nota>/pagamento")
@login_required_api
def api_atualizar_pagamento(id_pi, id_nota):
    from . import db

    body = request.get_json(silent=True) or {}
    nota = db.obter_nota_fiscal_por_id(id_nota)
    if not nota or int(nota.get("id_pi") or 0) != int(id_pi):
        return _erro_json("Nota fiscal não encontrada neste PI.", 404)
    try:
        status = int(body.get("status"))
    except (TypeError, ValueError):
        return _erro_json("Status de pagamento inválido.", 400)

    statuses = {item.get("id"): item for item in (db.obter_nota_fiscal_status() or [])}
    status_row = statuses.get(status)
    if not status_row:
        return _erro_json("Status de pagamento inválido.", 400)

    descricao = str(status_row.get("descricao") or "")
    data_previsto = body.get("data_pagamento_previsto") or None
    data_realizado = body.get("data_pagamento_realizado") or None
    if descricao == "Pagamento Realizado" and not (data_realizado and str(data_realizado).strip()):
        return _erro_json("Informe a data do pagamento realizado.", 400)

    db.atualizar_nota_fiscal(
        id_nota,
        {
            "status": status,
            "data_pagamento_previsto": data_previsto,
            "data_pagamento_realizado": data_realizado,
        },
    )
    notas = [serializar_nota_fiscal(item) for item in (db.obter_notas_fiscais_por_pi(id_pi) or [])]
    codigo = status_financeiro_por_notas(notas) or STATUS_NF_PARA_FINANCEIRO.get(descricao.lower())
    if codigo:
        try:
            _service().repository.upsert_status(id_pi, codigo, session.get("user_id"))
        except Exception:
            logger.exception("Não atualizou o status financeiro do PI %s após o pagamento.", id_pi)
    atualizada = next((item for item in notas if item.get("id") == id_nota), serializar_nota_fiscal({
        **nota,
        "status": status,
        "status_descricao": descricao,
        "data_pagamento_previsto": data_previsto,
        "data_pagamento_realizado": data_realizado,
    }))
    return jsonify({
        "success": True,
        "data": {
            "nota": atualizada,
            "status_financeiro": codigo,
        },
    })


@bp.post("/api/cadu_pi/<int:id_pi>/financeiro/comunicacoes/<tipo>/enviar")
@login_required_api
def api_enviar_comunicacao_cliente(id_pi, tipo):
    body = request.get_json(silent=True) or {}
    try:
        data = PiDocumentoService().enviar_ao_cliente(
            id_pi,
            tipo,
            mensagem=body.get("mensagem"),
            autor_id=session.get("user_id"),
            pedir_assinatura=bool(body.get("pedir_assinatura")),
        )
        return jsonify({"success": True, "data": data})
    except DocumentoIndisponivelError as exc:
        return _erro_json(exc, 400)
    except PiNaoEncontradoError:
        return _erro_json("PI não encontrado", 404)
    except Exception:
        logger.exception("Erro ao enviar comunicação %s do PI %s ao cliente", tipo, id_pi)
        return _erro_json("Não foi possível enviar o e-mail ao cliente.", 500)
