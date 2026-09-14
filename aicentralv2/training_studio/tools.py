"""Tools do Agente Imersão."""

import json
import re

from .prompts import (
    CLASSIFY_ATTACHMENT_SYSTEM,
    EDIT_INSTRUCTIONS,
    FORMAT_SESSION_SYSTEM,
    SLIDE_SYSTEM,
    style_prompt,
    wrap_untrusted,
)


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "editar_texto",
            "description": "Reescreve, expande, resume, ajusta tom ou continua um trecho.",
            "parameters": {
                "type": "object",
                "properties": {
                    "acao": {"type": "string", "enum": list(EDIT_INSTRUCTIONS)},
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
            "description": "Pesquisa na internet via OpenAI web_search. Só use se busca_web estiver ligada.",
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
            "description": "Gera uma ilustração no guia de estilo do treinamento.",
            "parameters": {
                "type": "object",
                "properties": {"prompt": {"type": "string"}},
                "required": ["prompt"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "formatar_para_sessao",
            "description": "Formata pesquisa, URL ou anexo em HTML de sessão (h2/h3/p).",
            "parameters": {
                "type": "object",
                "properties": {
                    "texto": {"type": "string"},
                    "bloco": {"type": "string"},
                },
                "required": ["texto"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aplicar_na_sessao",
            "description": "Devolve HTML para gravar no editor da sessão atual.",
            "parameters": {
                "type": "object",
                "properties": {
                    "html": {"type": "string"},
                    "modo": {"type": "string", "enum": ["anexar", "substituir"]},
                },
                "required": ["html"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "criar_sessao",
            "description": "Cria uma sessão extra na grade do treinamento.",
            "parameters": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "horario_inicio": {"type": "string"},
                    "horario_fim": {"type": "string"},
                    "apos_slug": {"type": "string"},
                    "html": {"type": "string"},
                },
                "required": ["titulo"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gerar_slide",
            "description": "Gera uma página de palco 16:9 a partir do trecho ou da página em foco.",
            "parameters": {
                "type": "object",
                "properties": {
                    "layout": {
                        "type": "string",
                        "enum": ["title", "statement", "split", "metrics"],
                    },
                    "instrucao": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reorganizar_slide",
            "description": "Reorganiza o palco em foco sem mudar o sentido.",
            "parameters": {
                "type": "object",
                "properties": {
                    "layout": {
                        "type": "string",
                        "enum": ["title", "statement", "split", "metrics"],
                    },
                    "instrucao": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "organizar_anexo",
            "description": "Classifica um anexo na sessão e no bloco certos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "texto": {"type": "string"},
                    "filename": {"type": "string"},
                },
                "required": ["texto"],
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
        kind = item.get("kind") or ""
        label = item.get("titulo") or item.get("url") or "fonte"
        prefix = f"[{kind}] " if kind else ""
        parts.append(f"- {prefix}{label}: {item.get('resumo')}")
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
    result["apply"] = False
    return result


def research_market(providers, query, selection="", buscar_web=False):
    if not buscar_web:
        raise ValueError("Ligue Buscar na internet para pesquisar.")
    query = (query or selection or "").strip()
    if not query:
        raise ValueError("Informe o que pesquisar ou selecione um trecho.")
    result = providers.research.search(query, context=selection)
    result["tool_used"] = "pesquisa"
    result["kind"] = "pesquisa"
    result["apply"] = False
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


def format_for_session(providers, texto, bloco="", document=""):
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Não há conteúdo para formatar.")
    messages = [
        {"role": "system", "content": FORMAT_SESSION_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Bloco sugerido: {bloco or 'dado'}\n\n"
                f"{wrap_untrusted('material', texto[:10000])}\n\n"
                f"Documento atual:\n{wrap_untrusted('documento', (document or '')[:4000])}"
            ),
        },
    ]
    result = providers.text.complete(messages, max_tokens=1800, temperature=0.3)
    result["tool_used"] = "formatacao"
    result["kind"] = "texto"
    result["apply"] = False
    return result


def compose_slide(providers, texto, page_html="", layout="", instrucao="", acao="gerar"):
    texto = (texto or "").strip() or _plain_page(page_html)
    if not texto:
        raise ValueError("Abra uma página ou selecione um trecho para o palco.")
    verb = (
        "Gere um palco novo a partir deste material."
        if acao == "gerar"
        else "Reorganize este palco. Preserve o sentido. Uma ideia só."
    )
    messages = [
        {"role": "system", "content": SLIDE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"{verb}\n"
                f"Layout sugerido: {layout or 'escolha o menor que caiba'}.\n"
                f"Instrução: {instrucao or '(nenhuma)'}\n\n"
                f"{wrap_untrusted('pagina', (page_html or '')[:8000])}\n\n"
                f"{wrap_untrusted('trecho', (texto or '')[:6000])}"
            ),
        },
    ]
    result = providers.text.complete(messages, max_tokens=1200, temperature=0.25)
    html = _as_slide_html(result.get("content") or "", layout)
    result["content"] = html
    result["html"] = html
    result["tool_used"] = "slide"
    result["kind"] = "slide"
    result["apply"] = True
    result["modo"] = "pagina"
    return result


def _plain_page(html):
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _as_slide_html(raw, layout=""):
    html = str(raw or "").strip()
    if html.startswith("```"):
        html = re.sub(r"^```(?:html)?\s*|\s*```$", "", html, flags=re.I).strip()
    if "ts-page" in html:
        if 'data-surface=' not in html:
            html = html.replace("<article", '<article data-surface="slide"', 1)
        return html
    layout = layout or "statement"
    art = (
        '<figure class="ts-page-art" data-slot="ilustracao"></figure>'
        if layout == "split"
        else ""
    )
    return (
        f'<article class="ts-page" data-layout="{layout}" data-surface="slide">'
        f'<div class="ts-page-copy">{html}</div>{art}</article>'
    )


def apply_to_session(html, modo="anexar"):
    html = (html or "").strip()
    if not html:
        raise ValueError("Não há HTML para aplicar.")
    return {
        "content": html,
        "html": html,
        "modo": modo if modo in {"anexar", "substituir"} else "anexar",
        "apply": True,
        "tool_used": "aplicacao",
        "kind": "texto",
        "model": None,
        "usage": {},
        "cost_usd": 0,
    }


def classify_attachment(providers, texto, filename=""):
    messages = [
        {"role": "system", "content": CLASSIFY_ATTACHMENT_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Arquivo: {filename or 'anexo'}\n\n"
                f"{wrap_untrusted('anexo', (texto or '')[:12000])}"
            ),
        },
    ]
    result = providers.text.complete(messages, max_tokens=1200, temperature=0.2)
    result["tool_used"] = "anexo"
    result["kind"] = "resumo_url"
    result["apply"] = False
    result["classificacao"] = parse_classification(result.get("content"))
    return result


def parse_classification(text):
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    bloco = str(data.get("bloco") or "dado")
    if bloco not in {"tese", "dado", "case", "formato", "nota_instrutor", "dinamica"}:
        bloco = "dado"
    html = str(data.get("html") or "").strip()
    return {
        "sessao_slug": str(data.get("sessao_slug") or "").strip(),
        "bloco": bloco,
        "titulo": str(data.get("titulo") or "").strip(),
        "html": html,
        "resumo": str(data.get("resumo") or raw)[:2000],
    }
