"""Protótipo visual CRM — dados fictícios com API mock em memória."""

from flask import Blueprint, jsonify, render_template, request

from .crm_test_data import store
from .crm_test_helpers import parse_texto_contatos

bp = Blueprint("crm_test", __name__, url_prefix="/teste-crm")


def _ok(data=None, **extra):
    body = {"success": True}
    if data is not None:
        body["data"] = data
    body.update(extra)
    return jsonify(body)


def _err(message, status=400):
    return jsonify({"success": False, "error": message}), status


@bp.route("/")
def teste_crm_mock():
    return render_template("teste_crm_mock.html")


@bp.route("/api/clientes")
def api_clientes():
    clientes = store.list_clientes()
    return _ok(clientes, clientes=clientes)


@bp.route("/api/clientes/<cliente_id>")
def api_cliente_detail(cliente_id):
    cliente = store.get_cliente(cliente_id)
    if not cliente:
        return _err("Cliente não encontrado", 404)
    return _ok(cliente, cliente=cliente)


@bp.route("/api/clientes", methods=["POST"])
def api_create_cliente():
    try:
        data = request.get_json(silent=True) or {}
        cliente = store.create_cliente(data)
        return _ok(cliente, cliente=cliente), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/clientes/<cliente_id>", methods=["PATCH"])
def api_update_cliente(cliente_id):
    try:
        cliente = store.update_cliente(cliente_id, request.get_json(silent=True) or {})
        if cliente is None:
            return _err("Cliente não encontrado", 404)
        return _ok(cliente, cliente=cliente)
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/clientes/<cliente_id>/contatos")
def api_contatos(cliente_id):
    contatos = store.list_contatos(cliente_id)
    if contatos is None:
        return _err("Cliente não encontrado", 404)
    return _ok(contatos, contatos=contatos)


@bp.route("/api/clientes/<cliente_id>/contatos", methods=["POST"])
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
def api_update_contato(contato_id):
    data = request.get_json(silent=True) or {}
    contato, cliente_id = store.update_contato(contato_id, data)
    if not contato:
        return _err("Contato não encontrado", 404)
    return _ok(contato, contato=contato, cliente_id=cliente_id)


@bp.route("/api/clientes/<cliente_id>/atividades")
def api_atividades(cliente_id):
    items = store.list_atividades(cliente_id)
    if items is None:
        return _err("Cliente não encontrado", 404)
    return _ok(items, atividades=items)


@bp.route("/api/clientes/<cliente_id>/atividades", methods=["POST"])
def api_create_atividade(cliente_id):
    try:
        data = request.get_json(silent=True) or {}
        ativ = store.create_atividade(cliente_id, data)
        if ativ is None:
            return _err("Cliente não encontrado", 404)
        return _ok(ativ, atividade=ativ), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/atividades/<atividade_id>", methods=["PATCH"])
def api_update_atividade(atividade_id):
    try:
        data = request.get_json(silent=True) or {}
        ativ, cliente_id = store.update_atividade(atividade_id, data)
        if not ativ:
            return _err("Atividade não encontrada", 404)
        return _ok(ativ, atividade=ativ, cliente_id=cliente_id)
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/atividades/<atividade_id>", methods=["DELETE"])
def api_delete_atividade(atividade_id):
    ok, cliente_id = store.delete_atividade(atividade_id)
    if not ok:
        return _err("Atividade não encontrada", 404)
    return _ok(cliente_id=cliente_id)


@bp.route("/api/clientes/<cliente_id>/objetivos")
def api_objetivos(cliente_id):
    items = store.list_objetivos(cliente_id)
    if items is None:
        return _err("Cliente não encontrado", 404)
    return _ok(items, objetivos=items)


@bp.route("/api/clientes/<cliente_id>/objetivos", methods=["POST"])
def api_create_objetivo(cliente_id):
    try:
        objetivo = store.create_objetivo(cliente_id, request.get_json(silent=True) or {})
        if objetivo is None:
            return _err("Cliente não encontrado", 404)
        return _ok(objetivo, objetivo=objetivo), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/objetivos/<objetivo_id>", methods=["PATCH"])
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
def api_delete_objetivo(objetivo_id):
    ok, cliente_id = store.delete_objetivo(objetivo_id)
    if not ok:
        return _err("Objetivo não encontrado", 404)
    return _ok(cliente_id=cliente_id)


@bp.route("/api/clientes/<cliente_id>/cotacoes")
def api_cotacoes(cliente_id):
    items = store.list_cotacoes(cliente_id)
    if items is None:
        return _err("Cliente não encontrado", 404)
    return _ok(items, cotacoes=items)


@bp.route("/api/clientes/<cliente_id>/cotacoes", methods=["POST"])
def api_create_cotacao(cliente_id):
    try:
        cotacao = store.create_cotacao(cliente_id, request.get_json(silent=True) or {})
        if cotacao is None:
            return _err("Cliente não encontrado", 404)
        return _ok(cotacao, cotacao=cotacao), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/cotacoes/<cotacao_id>", methods=["PATCH"])
def api_update_cotacao(cotacao_id):
    try:
        cotacao, cliente_id = store.update_cotacao(
            cotacao_id, request.get_json(silent=True) or {}
        )
        if cotacao is None:
            return _err("Cotação não encontrada", 404)
        return _ok(cotacao, cotacao=cotacao, cliente_id=cliente_id)
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/cotacoes/<cotacao_id>", methods=["DELETE"])
def api_delete_cotacao(cotacao_id):
    ok, cliente_id = store.delete_cotacao(cotacao_id)
    if not ok:
        return _err("Cotação não encontrada", 404)
    return _ok(cliente_id=cliente_id)


@bp.route("/api/clientes/<cliente_id>/notas")
def api_notas(cliente_id):
    notas = store.list_notas(cliente_id)
    if notas is None:
        return _err("Cliente não encontrado", 404)
    return _ok(notas, notas=notas)


@bp.route("/api/clientes/<cliente_id>/notas", methods=["POST"])
def api_create_nota(cliente_id):
    try:
        nota = store.create_nota(cliente_id, request.get_json(silent=True) or {})
        if nota is None:
            return _err("Cliente não encontrado", 404)
        return _ok(nota, nota=nota), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/notas/<nota_id>", methods=["PATCH"])
def api_update_nota(nota_id):
    try:
        nota, cliente_id = store.update_nota(nota_id, request.get_json(silent=True) or {})
        if nota is None:
            return _err("Nota não encontrada", 404)
        return _ok(nota, nota=nota, cliente_id=cliente_id)
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/notas/<nota_id>", methods=["DELETE"])
def api_delete_nota(nota_id):
    ok, cliente_id = store.delete_nota(nota_id)
    if not ok:
        return _err("Nota não encontrada", 404)
    return _ok(cliente_id=cliente_id)


@bp.route("/api/contatos/parse-texto", methods=["POST"])
def api_parse_texto():
    data = request.get_json(silent=True) or {}
    texto = data.get("texto") or ""
    contatos = parse_texto_contatos(texto)
    return _ok(contatos, contatos=contatos, message="" if contatos else "Nenhum contato reconhecido no texto.")


@bp.route("/api/clientes/<cliente_id>/contatos/importar", methods=["POST"])
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
