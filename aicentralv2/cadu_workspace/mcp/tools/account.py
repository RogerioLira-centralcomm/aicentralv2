"""Tenant-scoped account, team and credit tools for both MCP transports."""

import re

from werkzeug.exceptions import HTTPException

from .... import db
from ....cadu_family import repository
from ....cadu_skills.repository import credit_position
from ....db import get_db
from ...agent_v2.contracts import RequestContext
from ...credit_purchase_service import list_packages, request_extra
from ....product_domains import product_url
from .. import operations
from ..registry import ToolInputError, register_tool


def _admin(context: RequestContext) -> dict:
    actor = repository.actor(context.user_id) or {}
    if int(actor.get("organization_id") or 0) != context.client_id or repository.account_role(actor) != "admin":
        raise ToolInputError("Somente administradores podem realizar esta ação na conta.")
    return actor


@register_tool(name="account.get", capability="workspace", effect="read",
               description="Consulta os dados da pessoa atual e da agência sem expor cobrança ou segredos.",
               exposures=("internal", "customer_agent"))
def get_account(context: RequestContext, arguments: dict) -> dict:
    actor = repository.actor(context.user_id) or {}
    if int(actor.get("organization_id") or 0) != context.client_id:
        raise ToolInputError("Conta indisponível.")
    with get_db().cursor() as cursor:
        cursor.execute("SELECT nome_fantasia,razao_social,cnpj,cep,logradouro,numero,complemento,bairro,cidade FROM tbl_cliente WHERE id_cliente=%s",
                       (context.client_id,))
        agency = cursor.fetchone() or {}
    return {"profile":{"id":context.user_id, "name":actor.get("name"), "email":actor.get("email"),
                       "phone":actor.get("phone"), "role":repository.account_role(actor)},
            "agency":dict(agency)}


@register_tool(name="account.update_profile", capability="workspace", effect="write",
               description="Atualiza apenas nome e telefone da pessoa autenticada após confirmação explícita.",
               exposures=("internal", "customer_agent"),
               input_schema={"type":"object", "required":["request_id", "confirmed"], "properties":{
                   "request_id":{"type":"string", "minLength":36, "maxLength":36},
                   "confirmed":{"type":"boolean", "enum":[True]},
                   "name":{"type":"string", "minLength":2, "maxLength":160},
                   "phone":{"type":"string", "maxLength":40},
               }, "additionalProperties":False})
def update_profile(context: RequestContext, arguments: dict) -> dict:
    if not any(key in arguments for key in ("name", "phone")):
        raise ToolInputError("Informe nome ou telefone para atualizar.")
    actor = repository.actor(context.user_id) or {}
    if int(actor.get("organization_id") or 0) != context.client_id:
        raise ToolInputError("Conta indisponível.")
    values = {key: arguments[key] for key in ("name", "phone") if key in arguments}
    if "name" in values:
        values["name"] = " ".join(values["name"].split())
        if len(values["name"]) < 2:
            raise ToolInputError("Informe um nome válido.")

    def change():
        columns = {"name":"nome_completo", "phone":"telefone"}
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"UPDATE tbl_contato_cliente SET {', '.join(columns[key] + '=%s' for key in values)}, "
                               "data_modificacao=NOW() WHERE id_contato_cliente=%s AND pk_id_tbl_cliente=%s RETURNING id_contato_cliente",
                               (*values.values(), context.user_id, context.client_id))
                if not cursor.fetchone():
                    raise ToolInputError("Conta indisponível.")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return {"updated_fields":sorted(values), "profile":{"id":context.user_id, **values}}

    return operations.execute(arguments["request_id"], context, "account.update_profile", values, change)


@register_tool(name="account.update_agency", capability="workspace", effect="write",
               description="Atualiza nome e endereço da agência após confirmação de um administrador.",
               exposures=("internal", "customer_agent"),
               input_schema={"type":"object", "required":["request_id", "confirmed"], "properties":{
                   "request_id":{"type":"string", "minLength":36, "maxLength":36},
                   "confirmed":{"type":"boolean", "enum":[True]},
                   "trade_name":{"type":"string", "minLength":2, "maxLength":160},
                   "legal_name":{"type":"string", "maxLength":180},
                   "document":{"type":"string", "maxLength":18},
                   "postal_code":{"type":"string", "maxLength":9},
                   "street":{"type":"string", "maxLength":180},
                   "number":{"type":"string", "maxLength":40},
                   "complement":{"type":"string", "maxLength":180},
                   "district":{"type":"string", "maxLength":180},
                   "city":{"type":"string", "maxLength":180},
                   "state":{"type":"string", "maxLength":2},
               }, "additionalProperties":False})
def update_agency(context: RequestContext, arguments: dict) -> dict:
    _admin(context)
    columns = {"trade_name":"nome_fantasia", "legal_name":"razao_social", "document":"cnpj", "postal_code":"cep",
               "street":"logradouro", "number":"numero", "complement":"complemento",
               "district":"bairro", "city":"cidade"}
    values = {key:" ".join(str(arguments[key]).split()) for key in columns if key in arguments}
    state = str(arguments.get("state") or "").strip().upper() if "state" in arguments else None
    if not values and state is None:
        raise ToolInputError("Informe ao menos um dado da agência.")
    if "trade_name" in values and len(values["trade_name"]) < 2:
        raise ToolInputError("Informe um nome válido para a agência.")
    if "postal_code" in values:
        values["postal_code"] = re.sub(r"\D", "", values["postal_code"])
        if values["postal_code"] and len(values["postal_code"]) != 8:
            raise ToolInputError("Informe um CEP com oito dígitos.")
    if "document" in values:
        values["document"] = re.sub(r"\D", "", values["document"])
        if values["document"] and len(values["document"]) not in {11, 14}:
            raise ToolInputError("Informe um CPF ou CNPJ válido.")
    if state is not None and state and not re.fullmatch(r"[A-Z]{2}", state):
        raise ToolInputError("Informe a sigla de um estado válida.")

    def change():
        connection = get_db()
        try:
            with connection.cursor() as cursor:
                state_id = None
                if state:
                    cursor.execute("SELECT id_estado FROM tbl_estado WHERE UPPER(sigla)=%s LIMIT 1", (state,))
                    row = cursor.fetchone()
                    if not row:
                        raise ToolInputError("Selecione um estado válido.")
                    state_id = row["id_estado"]
                assignments = [columns[key] + '=%s' for key in values]
                parameters = list(values.values())
                if state is not None:
                    assignments.append("pk_id_aux_estado=%s")
                    parameters.append(state_id)
                cursor.execute(f"UPDATE tbl_cliente SET {', '.join(assignments)}, "
                               "data_modificacao=NOW() WHERE id_cliente=%s RETURNING id_cliente",
                               (*parameters, context.client_id))
                if not cursor.fetchone():
                    raise ToolInputError("Agência indisponível.")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return {"updated_fields":sorted([*values, *(["state"] if state is not None else [])]),
                "agency":{**values, **({"state":state} if state is not None else {})}}

    return operations.execute(arguments["request_id"], context, "account.update_agency",
                              {**values, **({"state":state} if state is not None else {})}, change)


@register_tool(name="account.list_team", capability="workspace", effect="read",
               description="Lista pessoas e convites da equipe da agência atual.", exposures=("internal", "customer_agent"))
def list_team(context: RequestContext, arguments: dict) -> dict:
    _admin(context)
    people = db.obter_contatos_por_cliente(context.client_id)
    invites = db.obter_invites_cliente(context.client_id)
    return {"people":[{"id":item.get("id_contato_cliente"), "name":item.get("nome_completo"),
                       "email":item.get("email"), "active":bool(item.get("status"))} for item in people],
            "invites":[{"id":item.get("id"), "email":item.get("email"), "status":item.get("status")}
                       for item in invites]}


@register_tool(name="account.invite_team_member", capability="workspace", effect="write",
               description="Envia convite de equipe a um e-mail após confirmação explícita de um administrador.",
               exposures=("internal", "customer_agent"),
               input_schema={"type":"object", "required":["request_id", "confirmed", "email", "role"], "properties":{
                   "request_id":{"type":"string", "minLength":36, "maxLength":36},
                   "confirmed":{"type":"boolean", "enum":[True]},
                   "email":{"type":"string", "minLength":5, "maxLength":254},
                   "role":{"type":"string", "enum":["member", "admin"]},
               }, "additionalProperties":False})
def invite_team_member(context: RequestContext, arguments: dict) -> dict:
    actor = _admin(context)
    email = str(arguments["email"]).strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ToolInputError("Informe um e-mail válido.")
    role = arguments["role"]

    def invite():
        from ....email_service import send_invite_email
        if db.verificar_convite_pendente(email, context.client_id):
            raise ToolInputError("Já existe um convite pendente para este e-mail.")
        invite_id = db.criar_invite(context.client_id, context.user_id, email, role)
        value = db.obter_invite_por_id(invite_id)
        company = (db.obter_cliente_por_id(context.client_id) or {}).get("nome_fantasia") or "sua empresa"
        sent = send_invite_email(email, value["invite_token"], company, actor.get("name") or "Equipe",
                                 value["expires_at"], role_label="Administrador" if role == "admin" else "Membro")
        if not sent.get("success"):
            db.cancelar_invite(invite_id)
            raise ToolInputError("O convite não pôde ser enviado; nenhum convite ficou ativo.")
        return {"invite_id":invite_id, "email":email, "role":role, "status":"sent",
                "requested_by":actor.get("name")}

    return operations.execute(arguments["request_id"], context, "account.invite_team_member",
                              {"email":email, "role":role}, invite)


@register_tool(name="credits.get_balance", capability="workspace", effect="read",
               description="Consulta saldo, consumo mensal e créditos disponíveis da conta atual.",
               exposures=("internal", "customer_agent"))
def get_credit_balance(context: RequestContext, arguments: dict) -> dict:
    return credit_position(context.client_id)


@register_tool(name="credits.list_packages", capability="workspace", effect="read",
               description="Lista pacotes extras de créditos com preço e quantidade definidos pelo servidor.",
               exposures=("internal", "customer_agent"))
def get_credit_packages(context: RequestContext, arguments: dict) -> dict:
    return {"packages":list_packages()}


@register_tool(name="credits.purchase_package", capability="workspace", effect="write",
               description="Prepara a compra de créditos e devolve um link para o administrador confirmar no Cadu. Nenhum crédito é liberado antes dessa confirmação.",
               exposures=("internal", "customer_agent"),
               input_schema={"type":"object", "required":["request_id", "package_name", "billing_mode"], "properties":{
                   "request_id":{"type":"string", "minLength":36, "maxLength":36},
                   "package_name":{"type":"string", "minLength":3, "maxLength":80},
                   "billing_mode":{"type":"string", "enum":["prepaid", "postpaid"]},
                   "note":{"type":"string", "maxLength":2000},
               }, "additionalProperties":False})
def purchase_credit_package(context: RequestContext, arguments: dict) -> dict:
    _admin(context)
    payload = {key:arguments[key] for key in ("package_name", "billing_mode", "note") if key in arguments}
    try:
        result = operations.execute(arguments["request_id"], context, "credits.purchase_package", payload,
                                    lambda: request_extra(context, arguments["package_name"],
                                                          arguments["billing_mode"], arguments.get("note", "")))
        return {**result, "confirmation_url": product_url(
            "workspace", f"/workspace/app/integracoes/agents/compras/{result['request_id']}")}
    except HTTPException as exc:
        raise ToolInputError(str(exc.description)) from exc
