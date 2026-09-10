"""Tools exclusivas do Agente Imersão."""

from .prompts import EDIT_INSTRUCTIONS, style_prompt, wrap_untrusted


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "editar_texto",
            "description": "Reescreve, expande, resume, ajusta tom ou continua um trecho do documento.",
            "parameters": {
                "type": "object",
                "properties": {
                    "acao": {
                        "type": "string",
                        "enum": list(EDIT_INSTRUCTIONS),
                    },
                    "instrucao": {"type": "string"},
                },
                "required": ["acao"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pesquisar_mercado",
            "description": "Pesquisa dados atuais de mercado via Perplexity.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gerar_imagem",
            "description": "Gera uma imagem no guia de estilo do treinamento.",
            "parameters": {
                "type": "object",
                "properties": {"prompt": {"type": "string"}},
                "required": ["prompt"],
                "additionalProperties": False,
            },
        },
    },
]


def fontes_block(fontes):
    if not fontes:
        return ""
    parts = []
    for item in fontes:
        parts.append(f"- {item.get('titulo') or item.get('url')}: {item.get('resumo')}")
    return wrap_untrusted("fontes da sessão", "\n".join(parts))


def edit_text(providers, acao, selection, document, fontes=None, instrucao=""):
    if acao not in EDIT_INSTRUCTIONS:
        raise ValueError("Ação de edição inválida.")
    if not (selection or "").strip() and acao != "continuar":
        raise ValueError("Selecione um trecho no editor.")
    messages = [
        {
            "role": "system",
            "content": (
                f"{EDIT_INSTRUCTIONS[acao]} Devolva somente o texto resultante, "
                "sem aspas e sem explicação."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Instrução extra: {instrucao or '(nenhuma)'}\n\n"
                f"Trecho selecionado:\n{selection or '(vazio)'}\n\n"
                f"Documento:\n{wrap_untrusted('documento', (document or '')[:8000])}\n\n"
                f"{fontes_block(fontes)}"
            ),
        },
    ]
    result = providers.text.complete(messages)
    result["tool_used"] = "edicao"
    result["kind"] = "texto"
    result["acao"] = acao
    return result


def research_market(providers, query, selection=""):
    query = (query or selection or "").strip()
    if not query:
        raise ValueError("Informe o que pesquisar ou selecione um trecho.")
    result = providers.research.search(query, context=selection)
    result["tool_used"] = "pesquisa"
    result["kind"] = "pesquisa"
    return result


def generate_image(providers, prompt, guia_estilo, selection=""):
    base = (prompt or selection or "").strip()
    if not base:
        raise ValueError("Descreva a imagem ou selecione um trecho.")
    full_prompt = f"{base}\n\n{style_prompt(guia_estilo)}"
    result = providers.image.generate(full_prompt)
    result["prompt"] = full_prompt
    result["tool_used"] = "imagem"
    result["kind"] = "imagem"
    return result
