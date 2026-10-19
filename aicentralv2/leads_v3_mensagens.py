"""Leads v3: mensagens personalizadas por pessoa e contexto de mercado da empresa (IA via OpenRouter).

A conexão é de topo e meio de funil: conteúdo útil, relação íntegra e transparente, em vários
canais. O fundo (proposta) é consequência. As mensagens usam o foco de conteúdo definido na
empresa, o contexto de mercado, o papel da pessoa e o histórico de interações.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

import requests

from .leads_v3_prospeccao import ProspeccaoError

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELO_MENSAGEM = os.getenv("LEADS_V3_MESSAGE_MODEL", os.getenv("CRM_V3_ACTIVITY_MODEL", "openai/gpt-4o"))
MODELO_CONTEXTO = os.getenv("LEADS_V3_CONTEXT_MODEL", "perplexity/sonar")

# Regras de cada canal (o LinkedIn limita a nota do convite a 300 caracteres).
CANAIS = {
    "email": "E-mail. Primeira linha 'Assunto: ...' (até 60 caracteres), depois o corpo em 3 a 6 linhas, sem anexos.",
    "whatsapp": "WhatsApp. Até 4 linhas curtas, tom humano, sem formatação de e-mail, no máximo 1 emoji ou nenhum.",
    "linkedin_conexao": "Nota de convite de conexão no LinkedIn. No máximo 280 caracteres, sem link e sem pitch de venda.",
    "linkedin": "Mensagem no LinkedIn para quem já é conexão. Até 5 linhas, conversacional.",
    "telefone": "Roteiro de ligação de até 2 minutos: abertura, motivo, pergunta aberta e pedido de próximo passo.",
}
ETAPAS = {
    "topo": "TOPO de funil: gerar interesse e relação. Ofereça um conteúdo útil (dado de audiência, tendência do setor, "
            "estudo, ideia de campanha) sem pedir reunião de cara. Nada de proposta ou preço.",
    "meio": "MEIO de funil: aprofundar. Traga um case, um diagnóstico ou uma pergunta sobre o desafio da marca e convide "
            "para uma conversa curta e específica. Ainda sem proposta comercial.",
}


def resolve_openrouter_key() -> str:
    try:
        from .services.integration_credentials import get_configuration

        config = get_configuration("openrouter", include_secrets=True)
        if config.get("status") != "disabled" and config.get("api_key"):
            return str(config["api_key"]).strip()
    except Exception:
        pass
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def chat(api_key, model, system, user, *, max_tokens=1500, temperature=0.6, post=requests.post):
    """Chamada simples ao OpenRouter. Devolve (texto, fontes citadas)."""
    if not api_key:
        raise ProspeccaoError("OpenRouter sem chave. Cadastre em Parâmetros › Integrações.")
    try:
        response = post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}", "HTTP-Referer": "https://centralcomm.media", "X-Title": "CentralX Leads v3"},
            json={"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=90,
        )
        response.raise_for_status()
        body = response.json()
        texto = body["choices"][0]["message"]["content"] or ""
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        raise ProspeccaoError("A IA não respondeu agora. Tente de novo em instantes.") from exc
    fontes = body.get("citations") or []
    if not fontes:  # alguns provedores mandam as fontes como anotações da mensagem
        for nota in (body["choices"][0]["message"].get("annotations") or []):
            url = (nota.get("url_citation") or {}).get("url")
            if url:
                fontes.append(url)
    return texto.strip(), [f for f in dict.fromkeys(fontes) if isinstance(f, str) and f.startswith("http")][:8]


def gerar_contexto_mercado(api_key, *, empresa, dominio=None, segmento=None, chat_fn=chat):
    """Notícias e movimentos recentes da empresa e do setor, com fontes (busca na web)."""
    system = ("Você é analista de inteligência de mercado de uma agência de mídia no Brasil. Pesquise na web e responda "
              "em português, em tópicos curtos, só com fatos verificáveis dos últimos 12 meses, citando as fontes. "
              "Se não achar algo, diga que não achou; não invente.")
    user = (f"Empresa: {empresa}" + (f" (site {dominio})" if dominio else "") + (f", setor {segmento}" if segmento else "") +
            ".\nTraga, em até 8 tópicos:\n"
            "1. Notícias e movimentos recentes (lançamentos, expansão, resultados, mudanças de liderança de marketing).\n"
            "2. Campanhas e ações de marketing/mídia recentes e onde aparecem.\n"
            "3. Desafios e tendências do setor no Brasil que afetam comunicação e mídia.\n"
            "4. Duas ideias de conteúdo de topo de funil que interessariam ao marketing desta empresa.")
    texto, fontes = chat_fn(api_key, MODELO_CONTEXTO, system, user, max_tokens=1800, temperature=0.2)
    return {"texto": texto, "fontes": fontes, "modelo": MODELO_CONTEXTO, "gerado_em": datetime.now().isoformat(timespec="minutes")}


def _resumo_foco(foco):
    foco = foco or {}
    if isinstance(foco, str):
        try:
            foco = json.loads(foco)
        except ValueError:
            foco = {}
    partes = [f"{rotulo}: {foco[chave]}" for chave, rotulo in
              (("topo", "Conteúdos de topo"), ("meio", "Conteúdos de meio"), ("tom", "Tom"), ("evitar", "Evitar")) if foco.get(chave)]
    return "\n".join(partes)


def montar_prompt_mensagem(*, canal, etapa, objetivo, pessoa, empresa, foco=None, contexto=None, historico=None, remetente=None):
    """Prompt da mensagem. Separado da chamada para dar para testar sem rede."""
    if canal not in CANAIS:
        raise ProspeccaoError("Canal inválido.")
    if etapa not in ETAPAS:
        raise ProspeccaoError("Etapa de funil inválida.")
    system = (
        "Você escreve mensagens de prospecção para executivos da CentralComm, hub de mídia digital no Brasil. "
        "Princípios: relação íntegra e transparente, multicanal, conteúdo útil antes de qualquer pedido. "
        "Escreva em português do Brasil, em primeira pessoa, como o próprio executivo. Personalize com fatos da empresa "
        "e do cargo da pessoa; nunca invente números, cases ou notícias que não estejam no contexto. "
        "Responda só com a mensagem pronta para enviar, sem comentários.\n\n"
        f"Canal: {CANAIS[canal]}\nEtapa: {ETAPAS[etapa]}"
    )
    linhas = [
        f"Objetivo deste toque: {objetivo or 'abrir conversa'}",
        f"Pessoa: {pessoa.get('nome')} — {pessoa.get('cargo') or 'cargo não informado'}"
        + (f" (área {pessoa['papel']})" if pessoa.get("papel") else ""),
        f"Empresa: {empresa.get('nome')}" + (f", setor {empresa['segmento']}" if empresa.get("segmento") else ""),
    ]
    if empresa.get("descricao"):
        linhas.append(f"Sobre a empresa: {empresa['descricao'][:600]}")
    if empresa.get("oportunidades_midia"):
        linhas.append(f"Oportunidades de mídia já mapeadas: {empresa['oportunidades_midia'][:500]}")
    if foco:
        linhas.append("Foco definido pelo executivo para esta empresa:\n" + foco)
    if contexto:
        linhas.append("Contexto de mercado recente (use só o que for relevante):\n" + contexto[:1800])
    if historico:
        linhas.append("Interações anteriores com a empresa (não repita o que já foi dito):\n" + "\n".join(f"- {h}" for h in historico[:6]))
    if remetente:
        linhas.append(f"Assine como {remetente}, CentralComm.")
    return system, "\n\n".join(linhas)


def gerar_mensagem(api_key, *, chat_fn=chat, **dados):
    system, user = montar_prompt_mensagem(**dados)
    texto, _ = chat_fn(api_key, MODELO_MENSAGEM, system, user, max_tokens=1200, temperature=0.7)
    assunto = None
    if dados["canal"] == "email":
        match = re.match(r"\s*assunto:\s*(.+)", texto, re.I)
        if match:
            assunto = match.group(1).strip()
            texto = texto[match.end():].strip()
    if dados["canal"] == "linkedin_conexao" and len(texto) > 300:
        texto = texto[:297].rsplit(" ", 1)[0] + "…"
    return {"assunto": assunto, "texto": texto}
