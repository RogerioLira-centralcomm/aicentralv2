"""Allowlist, contratos e validação estrita das tools do agente."""

from dataclasses import dataclass

from . import commercial


class ToolValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    handler: object
    properties: dict
    required: tuple
    capability: str = "commercial.read.assigned"
    operation_type: str = "read"
    confirmation_required: bool = False

    def openrouter_definition(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.properties,
                    "required": list(self.required),
                    "additionalProperties": False,
                },
            },
        }


ID = {"type": "string", "minLength": 1, "maxLength": 80}
LIMIT = {"type": "integer", "minimum": 1, "maximum": 20}
STATUS = {"type": "string", "minLength": 1, "maxLength": 50}

TOOLS = {
    tool.name: tool for tool in (
        Tool(
            "buscar_cliente", "Busca clientes por nome, razão social ou documento.",
            commercial.buscar_cliente,
            {"query": {"type": "string", "minLength": 2, "maxLength": 120}, "limit": LIMIT},
            ("query",),
        ),
        Tool(
            "consultar_cliente", "Consulta o resumo de um cliente por ID.",
            commercial.consultar_cliente, {"cliente_id": ID}, ("cliente_id",),
        ),
        Tool(
            "listar_contatos", "Lista contatos de um cliente.",
            commercial.listar_contatos, {"cliente_id": ID, "limit": LIMIT}, ("cliente_id",),
        ),
        Tool(
            "buscar_contato", "Busca contatos por nome, e-mail ou telefone.",
            commercial.buscar_contato,
            {"query": {"type": "string", "minLength": 2, "maxLength": 120}, "limit": LIMIT},
            ("query",),
        ),
        Tool(
            "consultar_contato", "Consulta um contato específico por ID.",
            commercial.consultar_contato, {"contato_id": ID}, ("contato_id",),
        ),
        Tool(
            "listar_atividades", "Lista atividades comerciais de um cliente.",
            commercial.listar_atividades,
            {"cliente_id": ID, "limit": LIMIT, "status": STATUS}, ("cliente_id",),
        ),
        Tool(
            "listar_cotacoes", "Lista cotações de um cliente.",
            commercial.listar_cotacoes,
            {"cliente_id": ID, "limit": LIMIT, "status": STATUS}, ("cliente_id",),
        ),
        Tool(
            "consultar_cotacao", "Consulta uma cotação específica por ID.",
            commercial.consultar_cotacao, {"cotacao_id": ID}, ("cotacao_id",),
        ),
        Tool(
            "buscar_pi", "Busca PIs por ID, código ou título.",
            commercial.buscar_pi,
            {"query": {"type": "string", "minLength": 2, "maxLength": 120}, "limit": LIMIT},
            ("query",),
        ),
        Tool(
            "consultar_pi", "Consulta um PI específico por ID.",
            commercial.consultar_pi, {"pi_id": ID}, ("pi_id",),
        ),
        Tool(
            "listar_pis_cliente", "Lista os PIs vinculados a um cliente.",
            commercial.listar_pis_cliente,
            {"cliente_id": ID, "limit": LIMIT}, ("cliente_id",),
        ),
        Tool(
            "buscar_campanha", "Busca campanhas operacionais por ID ou nome.",
            commercial.buscar_campanha,
            {"query": {"type": "string", "minLength": 2, "maxLength": 120}, "limit": LIMIT},
            ("query",),
        ),
        Tool(
            "consultar_campanha", "Consulta uma campanha operacional específica por ID.",
            commercial.consultar_campanha, {"campanha_id": ID}, ("campanha_id",),
        ),
        Tool(
            "listar_campanhas_pi",
            "Lista as campanhas vinculadas a um PI, incluindo plataforma, responsável, objetivo, entrega, gasto e orçamento.",
            commercial.listar_campanhas_pi,
            {"pi_id": ID, "limit": LIMIT}, ("pi_id",),
        ),
        Tool(
            "consultar_operacao_pi",
            "Consulta o estado operacional completo de um PI: resumo, SLA, saúde, timeline, checklist e recomendações.",
            commercial.consultar_operacao_pi, {"pi_id": ID}, ("pi_id",),
        ),
        Tool(
            "resumir_operacao",
            "Consulta números consolidados da operação: PIs e valores por status, campanhas por status e plataforma, objetivos, entrega, gasto e orçamento.",
            commercial.resumir_operacao, {}, (),
        ),
        Tool(
            "preparar_alteracao_contato",
            "Prepara criação ou atualização de contato para revisão humana; não salva dados.",
            commercial.preparar_alteracao_contato,
            {
                "operation": {
                    "type": "string",
                    "enum": ["create_contact", "update_contact"],
                },
                "nome": {"type": "string", "minLength": 1, "maxLength": 200},
                "cliente_id": ID,
                "contato_id": ID,
                "email": {"type": "string", "minLength": 1, "maxLength": 320},
                "telefone": {"type": "string", "minLength": 1, "maxLength": 50},
                "telefone_secundario": {"type": "string", "minLength": 1, "maxLength": 50},
            },
            ("operation", "nome"),
        ),
    )
}


def openrouter_tools():
    return [tool.openrouter_definition() for tool in TOOLS.values()]


def get_tool(name):
    tool = TOOLS.get(name)
    if not tool:
        raise ToolValidationError("Ferramenta não permitida.")
    return tool


def validate_arguments(tool, arguments):
    if not isinstance(arguments, dict):
        raise ToolValidationError("Argumentos devem ser um objeto.")
    extras = set(arguments) - set(tool.properties)
    if extras:
        raise ToolValidationError("Argumentos não reconhecidos.")
    missing = [field for field in tool.required if field not in arguments]
    if missing:
        raise ToolValidationError(f"Argumento obrigatório ausente: {missing[0]}.")

    clean = {}
    for field, value in arguments.items():
        schema = tool.properties[field]
        expected = schema["type"]
        if expected == "string":
            if not isinstance(value, str):
                raise ToolValidationError(f"{field} deve ser texto.")
            value = value.strip()
            if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 10000):
                raise ToolValidationError(f"{field} possui tamanho inválido.")
        elif expected == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ToolValidationError(f"{field} deve ser inteiro.")
            if value < schema.get("minimum", value) or value > schema.get("maximum", value):
                raise ToolValidationError(f"{field} está fora do limite.")
        if "enum" in schema and value not in schema["enum"]:
            raise ToolValidationError(f"{field} possui valor inválido.")
        clean[field] = value
    return clean
