"""Protótipo visual CRM — dados fictícios com API mock em memória."""

from flask import Blueprint, jsonify, render_template, request

from .crm_test_data import store

bp = Blueprint("crm_test", __name__, url_prefix="/teste-crm")


@bp.route("/")
def teste_crm_mock():
    return render_template("teste_crm_mock.html")


@bp.route("/api/clientes")
def api_clientes():
    return jsonify({"clientes": store.list_clientes()})


@bp.route("/api/clientes/<cliente_id>")
def api_cliente_detail(cliente_id):
    cliente = store.get_cliente(cliente_id)
    if not cliente:
        return jsonify({"error": "Cliente não encontrado"}), 404
    return jsonify({"cliente": cliente})


@bp.route("/api/clientes", methods=["POST"])
def api_create_cliente():
    try:
        data = request.get_json(silent=True) or {}
        cliente = store.create_cliente(data)
        return jsonify({"cliente": cliente}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/clientes/<cliente_id>/contatos")
def api_contatos(cliente_id):
    contatos = store.list_contatos(cliente_id)
    if contatos is None:
        return jsonify({"error": "Cliente não encontrado"}), 404
    return jsonify({"contatos": contatos})


@bp.route("/api/clientes/<cliente_id>/contatos", methods=["POST"])
def api_create_contato(cliente_id):
    try:
        data = request.get_json(silent=True) or {}
        contato = store.create_contato(cliente_id, data)
        if contato is None:
            return jsonify({"error": "Cliente não encontrado"}), 404
        return jsonify({"contato": contato}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/contatos/<contato_id>", methods=["PATCH"])
def api_update_contato(contato_id):
    data = request.get_json(silent=True) or {}
    contato, cliente_id = store.update_contato(contato_id, data)
    if not contato:
        return jsonify({"error": "Contato não encontrado"}), 404
    return jsonify({"contato": contato, "cliente_id": cliente_id})
