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
YEAR = {"type": "integer", "minimum": 2000, "maximum": 2100}

TOOLS = {
    tool.name: tool for tool in (
        Tool(
            "buscar_cliente",
            "Busca clientes e agências por nome, razão social, fantasia ou documento. Use em vez de pedir ID ao usuário.",
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
            "listar_atividades",
            "Lista ou resume atividades do responsável logado ou de um cliente. Sem prazo, devolve só o resumo (hoje / esta semana / atrasadas). Use prazo para listar.",
            commercial.listar_atividades,
            {
                "cliente_id": ID,
                "limit": LIMIT,
                "status": STATUS,
                "prazo": {"type": "string", "enum": ["hoje", "semana", "atrasadas"]},
            },
            (),
        ),
        Tool(
            "consultar_atividade", "Consulta uma atividade específica por ID e abre o contexto.",
            commercial.consultar_atividade, {"atividade_id": ID}, ("atividade_id",),
        ),
        Tool(
            "listar_cotacoes", "Lista cotações de um cliente.",
            commercial.listar_cotacoes,
            {"cliente_id": ID, "limit": LIMIT, "status": STATUS}, ("cliente_id",),
        ),
        Tool(
            "buscar_cotacao",
            "Busca cotações por número, título da campanha ou nome do cliente/agência. Use em vez de pedir o ID.",
            commercial.buscar_cotacao,
            {"query": {"type": "string", "minLength": 2, "maxLength": 120}, "limit": LIMIT},
            ("query",),
        ),
        Tool(
            "consultar_cotacao", "Consulta uma cotação específica por ID.",
            commercial.consultar_cotacao, {"cotacao_id": ID}, ("cotacao_id",),
        ),
        Tool(
            "listar_canais_plataformas",
            "Lista ou busca canais e plataformas disponíveis no catálogo CADU, com quantidade de audiências.",
            commercial.listar_canais_plataformas,
            {
                "query": {"type": "string", "minLength": 2, "maxLength": 120},
                "limit": LIMIT,
            },
            (),
        ),
        Tool(
            "buscar_audiencias",
            "Busca audiências ativas do CADU por nome, slug ou perfil.",
            commercial.buscar_audiencias,
            {
                "query": {"type": "string", "minLength": 2, "maxLength": 120},
                "plataforma_id": ID,
                "limit": LIMIT,
            },
            ("query",),
        ),
        Tool(
            "listar_formatos",
            "Lista ou busca formatos, tipos de compra e tipos de peça já utilizados nas cotações.",
            commercial.listar_formatos,
            {
                "query": {"type": "string", "minLength": 2, "maxLength": 120},
                "limit": LIMIT,
            },
            (),
        ),
        Tool(
            "buscar_pi",
            "Busca um PI por número, código ou título. Se o usuário informar um número (ex.: 36826), busque esse PI direto. Não faça resumo global antes.",
            commercial.buscar_pi,
            {"query": {"type": "string", "minLength": 2, "maxLength": 120}, "limit": LIMIT, "status": STATUS, "ano": YEAR},
            ("query",),
        ),
        Tool(
            "consultar_pi", "Consulta um PI específico por ID.",
            commercial.consultar_pi, {"pi_id": ID}, ("pi_id",),
        ),
        Tool(
            "listar_pis_cliente",
            "Resumo ou lista de PIs de um cliente/agência. Sem status, devolve o resumo do ano (padrão ano corrente) por status. Não liste dezenas de finalizados.",
            commercial.listar_pis_cliente,
            {"cliente_id": ID, "limit": LIMIT, "status": STATUS, "ano": YEAR},
            ("cliente_id",),
        ),
        Tool(
            "buscar_campanha",
            "Busca campanhas por ID ou nome. Para listagens por status no ano, use status e ano. Não liste centenas de campanhas finalizadas.",
            commercial.buscar_campanha,
            {
                "query": {"type": "string", "minLength": 2, "maxLength": 120},
                "limit": LIMIT,
                "status": STATUS,
                "ano": YEAR,
                "risco": {"type": "boolean"},
            },
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
            "Resumo de PIs e campanhas por status. Sem período, use o ano corrente. escopo=pis ou campanhas devolve só o resumo daquele conjunto, sem listar registros. Não totalize a base inteira.",
            commercial.resumir_operacao,
            {
                "ano": YEAR,
                "cliente_id": ID,
                "escopo": {"type": "string", "enum": ["operacao", "pis", "campanhas"]},
            },
            (),
        ),
        Tool(
            "listar_objetivos",
            "Lista objetivos comerciais de um cliente, incluindo prazo e se já foi conquistado.",
            commercial.listar_objetivos,
            {"cliente_id": ID, "limit": LIMIT}, ("cliente_id",),
        ),
        Tool(
            "listar_notas_fiscais",
            "Lista notas fiscais de um PI ou de um cliente/agência, com status de emissão e pagamento.",
            commercial.listar_notas_fiscais,
            {"pi_id": ID, "cliente_id": ID, "limit": LIMIT},
            (),
        ),
        Tool(
            "listar_reembolsos",
            "Lista reembolsos e despesas do financeiro. Sem acesso global, mostra só os do usuário.",
            commercial.listar_reembolsos,
            {"limit": LIMIT, "status": STATUS},
            (),
        ),
        Tool(
            "resumir_financeiro",
            "Resume reembolsos do usuário e o volume de notas fiscais por status de pagamento.",
            commercial.resumir_financeiro, {}, (),
        ),
        Tool(
            "preparar_atualizacao_operacao_campanha",
            "Prepara ajuste de objetivo, resultado (atingido) ou mídia realizada de uma campanha. Não altera valor bruto, comissões nem DRE. Não salva até o usuário confirmar. Use após ler print da plataforma ou quando o usuário informar os números.",
            commercial.preparar_atualizacao_operacao_campanha,
            {
                "campanha_id": ID,
                "obj_contratados": {"type": "string", "minLength": 1, "maxLength": 40},
                "totalizador_atingido": {"type": "string", "minLength": 1, "maxLength": 40},
                "totalizador_gasto": {"type": "string", "minLength": 1, "maxLength": 40},
            },
            ("campanha_id",),
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
            if isinstance(value, bool):
                raise ToolValidationError(f"{field} deve ser texto.")
            if isinstance(value, (int, float)):
                value = str(value)
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
