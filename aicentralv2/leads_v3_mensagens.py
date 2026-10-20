"""Leads v3: mensagens personalizadas por pessoa e dossiê de ganchos da empresa (IA via OpenRouter).

A conexão é de topo e meio de funil: conteúdo útil, relação íntegra e transparente, em vários
canais. O fundo (proposta) é consequência. Cada mensagem parte de um gancho (fato verificável,
com fonte e data, que interessa a quem cuida de mídia, marketing e comunicação na empresa-alvo)
e é escrita como o próprio executivo escreveria, sem cara de IA nem de e-mail de marketing.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

import requests

from .leads_v3_prospeccao import ProspeccaoError

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELO_MENSAGEM = os.getenv("LEADS_V3_MESSAGE_MODEL", "anthropic/claude-sonnet-5")
MODELO_CONTEXTO = os.getenv("LEADS_V3_CONTEXT_MODEL", "perplexity/sonar-pro")

# Regras de cada canal (o LinkedIn limita a nota do convite a 300 caracteres).
CANAIS = {
    "email": "E-mail. Primeira linha 'Assunto: ...' em minúsculas, de 2 a 6 palavras, como um colega escreveria "
             "(ex.: 'dado de ctv no varejo'), sem nome da CentralComm e sem clickbait. Depois o corpo, de 50 a 90 palavras.",
    "whatsapp": "WhatsApp. No máximo 3 linhas curtas (até 40 palavras), tom de conversa, no máximo 1 emoji ou nenhum.",
    "linkedin_conexao": "Nota de convite de conexão no LinkedIn. No máximo 280 caracteres, sem link e sem pitch.",
    "linkedin": "Mensagem no LinkedIn para quem já é conexão. Até 60 palavras, conversacional.",
    "telefone": "Roteiro de ligação de até 2 minutos: abertura com o gancho, uma pergunta aberta e o pedido de próximo passo.",
}
ETAPAS = {
    "topo": "TOPO de funil: puxar conversa com um fato que interessa à pessoa. Dê sua leitura do fato e termine com uma "
            "pergunta de opinião. Não peça reunião, não apresente serviços, não mande link de agenda, sem proposta ou preço.",
    "meio": "MEIO de funil: aprofundar. Ligue o gancho a um desafio provável da marca, ofereça algo concreto (um diagnóstico "
            "rápido, um material, um case só se estiver no contexto) e proponha 15 minutos sobre esse ponto específico. "
            "Ainda sem proposta comercial.",
}
TIPOS_GANCHO = ("empresa", "campanha", "concorrente", "setor", "lideranca", "tendencia")
DISPOSITIVOS = {"nenhum": "", "iphone": "Enviado do meu iPhone", "galaxy": "Enviado do meu Galaxy"}

# Marcas de texto de IA e de e-mail de prospecção genérico. Se aparecerem, a mensagem é reescrita uma vez.
FRASES_PROIBIDAS = (
    r"incr[ií]ve(?:l|is)", r"inovador(?:a|es|as)?", r"admir[aá]ve(?:l|is)", r"espero que (?:esteja|você esteja|estejam) bem",
    r"estou ansios[oa]", r"insights? valios[oa]s?", r"gostaria de me apresentar", r"sinergia", r"alavanc\w+",
    r"potencializ\w+", r"parceria estrat[ée]gica", r"no cen[aá]rio atual", r"cada vez mais", r"solu[çc][õo]es",
    r"agregar valor", r"de forma (?:eficaz|eficiente)", r"no mundo (?:atual|de hoje)", r"tudo bem\?",
)
_PROIBIDAS_RE = re.compile(r"(?<!\w)(" + "|".join(FRASES_PROIBIDAS) + r")(?!\w)", re.I)
# Despedidas que o modelo escreve mesmo pedindo para não assinar; a assinatura é do executivo.
_DESPEDIDA_RE = re.compile(r"\n+\s*(?:um abra[çc]o|abra[çc]os?|abs|att|atenciosamente|grande abra[çc]o|at[ée] mais)"
                           r"[\s,.!]*(?:\n+[^\n]{0,60})?\s*$", re.I)


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
            timeout=120,
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
    return texto.strip(), [f for f in dict.fromkeys(fontes) if isinstance(f, str) and f.startswith("http")][:12]


def _json_da_resposta(texto):
    """Extrai o objeto JSON de uma resposta (com ou sem cercas de código). None se não houver."""
    limpo = re.sub(r"```(?:json)?", "", texto or "")
    inicio, fim = limpo.find("{"), limpo.rfind("}")
    if inicio < 0 or fim <= inicio:
        return None
    try:
        valor = json.loads(limpo[inicio:fim + 1])
    except ValueError:
        return None
    return valor if isinstance(valor, dict) else None


# ─────────────────────────────────────────────────────
# Dossiê de ganchos
# ─────────────────────────────────────────────────────
def _texto(valor, limite):
    return str(valor or "").strip()[:limite] or None


def normalizar_gancho(bruto, fontes=()):
    """Valida um gancho vindo da IA (ou do executivo). Sem fato ou sem fonte http, devolve None."""
    if not isinstance(bruto, dict):
        return None
    fato = _texto(bruto.get("fato"), 600)
    url = str(bruto.get("fonte_url") or "").strip()
    ref = re.fullmatch(r"\[?(\d{1,2})\]?", url)
    if ref and fontes:  # o Sonar às vezes cita pelo índice da lista de fontes
        indice = int(ref.group(1)) - 1
        url = fontes[indice] if 0 <= indice < len(fontes) else ""
    if not fato or not url.startswith("http"):
        return None
    tipo = str(bruto.get("tipo") or "").strip().lower()
    etapa = str(bruto.get("etapa") or "").strip().lower()
    return {
        "fato": fato,
        "numero": _texto(bruto.get("numero"), 120),
        "angulo": _texto(bruto.get("angulo"), 400),
        "fonte_url": url[:1000],
        "fonte_nome": _texto(bruto.get("fonte_nome"), 120),
        "data_fato": _texto(bruto.get("data"), 20),
        "tipo": tipo if tipo in TIPOS_GANCHO else "setor",
        "etapa": etapa if etapa in ETAPAS else "topo",
    }


def gerar_dossie(api_key, *, empresa, dominio=None, segmento=None, descricao=None, papeis=(), chat_fn=chat):
    """Pesquisa na web e devolve um resumo e ganchos verificáveis (fato, número, fonte, data, ângulo)."""
    publico = ", ".join(sorted({p for p in papeis if p})) or "marketing, mídia e comunicação"
    system = (
        "Você é analista de inteligência de mercado de uma agência de mídia no Brasil. Pesquise na web e monte pautas "
        "para executivos de mídia puxarem conversa com quem cuida de marketing, mídia e comunicação numa empresa. "
        "Só fatos verificáveis dos últimos 12 meses, cada um com a URL da fonte. Prefira fatos com número (investimento, "
        "audiência, crescimento, participação). Se não achar algo, não invente: traga menos ganchos. "
        "Responda só com JSON válido, sem texto antes ou depois."
    )
    user = (
        f"Empresa-alvo: {empresa}" + (f" (site {dominio})" if dominio else "") + (f", setor {segmento}" if segmento else "") + ".\n"
        + (f"Sobre a empresa: {descricao[:500]}\n" if descricao else "")
        + f"Quem vai ler as mensagens: {publico}.\n\n"
        "Traga de 6 a 8 ganchos variados, pelo menos 4 de topo de funil, entre estes tipos:\n"
        "- empresa: lançamento, expansão, resultado, nova unidade ou produto da própria empresa;\n"
        "- campanha: campanha ou ação de marketing recente da empresa e onde veiculou;\n"
        "- concorrente: movimento de mídia ou marketing de um concorrente direto;\n"
        "- setor: dado de mercado do setor no Brasil (Kantar IBOPE, Cenp-Meios, IAB Brasil, Comscore, Nielsen, associações);\n"
        "- lideranca: mudança de liderança de marketing, mídia ou comunicação;\n"
        "- tendencia: tendência de mídia aplicada ao setor (CTV, retail media, DOOH, programática, creators, busca com IA).\n\n"
        'Formato: {"resumo": "3 a 5 linhas sobre o momento da empresa", "ganchos": [{"tipo": "...", '
        '"etapa": "topo|meio", "fato": "o fato em uma ou duas frases", "numero": "o número principal ou null", '
        '"angulo": "a pergunta ou leitura que um executivo de mídia faria a partir do fato", '
        '"fonte_nome": "veículo ou instituto", "fonte_url": "https://...", "data": "AAAA-MM"}]}'
    )
    texto, fontes = chat_fn(api_key, MODELO_CONTEXTO, system, user, max_tokens=3000, temperature=0.2)
    dados = _json_da_resposta(texto) or {}
    ganchos, vistos = [], set()
    for bruto in dados.get("ganchos") or []:
        gancho = normalizar_gancho(bruto, fontes)
        chave = gancho and gancho["fato"].lower()[:80]
        if gancho and chave not in vistos:
            vistos.add(chave)
            ganchos.append(gancho)
    resumo = _texto(dados.get("resumo"), 1500) or ("" if dados else texto[:1500])
    return {
        "contexto": {"texto": resumo, "fontes": fontes, "modelo": MODELO_CONTEXTO,
                     "gerado_em": datetime.now().isoformat(timespec="minutes")},
        "ganchos": ganchos,
    }


def sugerir_foco(api_key, *, empresa, segmento=None, descricao=None, papeis=(), ganchos=(), chat_fn=chat):
    """Foco de conteúdo (topo, meio, tom, evitar) a partir dos ganchos e de quem vai ler. Não grava nada."""
    linhas = "\n".join(f"- [{g.get('etapa')}/{g.get('tipo')}] {g.get('fato')}" + (f" Ângulo: {g['angulo']}" if g.get("angulo") else "")
                       for g in list(ganchos)[:10])
    system = ("Você é estrategista de uma agência de mídia no Brasil e orienta executivos na prospecção. "
              "Responda só com JSON válido.")
    user = (
        f"Empresa: {empresa}" + (f", setor {segmento}" if segmento else "") + ".\n"
        + (f"Sobre a empresa: {descricao[:500]}\n" if descricao else "")
        + f"Pessoas a conectar: {', '.join(sorted({p for p in papeis if p})) or 'marketing e mídia'}.\n"
        + (f"Ganchos pesquisados:\n{linhas}\n" if linhas else "Ainda não há ganchos pesquisados.\n")
        + "\nDefina o foco de conteúdo da prospecção, em frases curtas e específicas desta empresa (nada genérico):\n"
        '{"topo": "2 ou 3 temas que geram interesse sem pedir nada", "meio": "2 temas para aprofundar e justificar uma conversa", '
        '"tom": "como falar com essas pessoas", "evitar": "o que não citar ou não fazer"}'
    )
    texto, _ = chat_fn(api_key, MODELO_MENSAGEM, system, user, max_tokens=700, temperature=0.4)
    dados = _json_da_resposta(texto)
    if not dados:
        raise ProspeccaoError("A IA não devolveu um foco válido. Tente de novo.")
    return {k: str(dados.get(k) or "").strip()[:1000] for k in ("topo", "meio", "tom", "evitar")}


# ─────────────────────────────────────────────────────
# Mensagem
# ─────────────────────────────────────────────────────
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


def _descrever_gancho(gancho):
    partes = [f"Fato: {gancho['fato']}"]
    if gancho.get("numero"):
        partes.append(f"Número: {gancho['numero']}")
    fonte = gancho.get("fonte_nome") or gancho.get("fonte_url")
    if fonte:
        partes.append(f"Fonte: {fonte}" + (f" ({gancho['data_fato']})" if gancho.get("data_fato") else ""))
    if gancho.get("angulo"):
        partes.append(f"Ângulo sugerido: {gancho['angulo']}")
    return "\n".join(partes)


def montar_prompt_mensagem(*, canal, etapa, objetivo, pessoa, empresa, foco=None, contexto=None, historico=None,
                           remetente=None, gancho=None, ja_usados=None):
    """Prompt da mensagem. Separado da chamada para dar para testar sem rede."""
    if canal not in CANAIS:
        raise ProspeccaoError("Canal inválido.")
    if etapa not in ETAPAS:
        raise ProspeccaoError("Etapa de funil inválida.")
    quem = remetente or "o executivo"
    system = (
        f"Você escreve como {quem}, executivo de mídia da CentralComm (hub de mídia digital no Brasil), uma mensagem "
        "que ele mesmo mandaria. Tem que parecer escrita por uma pessoa ocupada e curiosa, não por marketing nem por IA.\n"
        "Regras de escrita:\n"
        "- Português do Brasil, profissional e coloquial; trate por você e pelo primeiro nome.\n"
        "- Frases curtas, parágrafos de uma ou duas frases. Comece pelo assunto: 'Oi, Ana' ou 'Ana,' e já o fato.\n"
        "- Use um único fato do gancho, com o número se houver, e diga de onde veio de forma natural "
        "('saiu no Meio & Mensagem que...', 'o Kantar mostrou...'). Nunca invente número, case, cliente ou notícia.\n"
        "- Dê sua leitura do fato para a mídia ou o marketing da empresa em uma frase, com opinião própria.\n"
        "- Termine com uma única pergunta curta e fácil de responder.\n"
        "- Proibido: elogio genérico (incrível, inovador, admirável), 'espero que esteja bem', 'tudo bem?', 'estou ansioso', "
        "'insights valiosos', 'gostaria de me apresentar', sinergia, alavancar, potencializar, soluções, parceria estratégica, "
        "'no cenário atual', 'cada vez mais', listas, negrito, travessões, emoji (exceto WhatsApp, no máximo um).\n"
        "- Sobre a CentralComm, no máximo meia frase de quem você é, e só se ajudar.\n"
        "- Não assine nem escreva despedida: a assinatura entra depois.\n"
        "Responda só com a mensagem pronta para enviar, sem comentários.\n\n"
        f"Canal: {CANAIS[canal]}\nEtapa: {ETAPAS[etapa]}"
    )
    linhas = [
        f"Objetivo deste toque: {objetivo or 'abrir conversa'}",
        f"Pessoa: {pessoa.get('nome')} — {pessoa.get('cargo') or 'cargo não informado'}"
        + (f" (área {pessoa['papel']})" if pessoa.get("papel") else ""),
        f"Empresa: {empresa.get('nome')}" + (f", setor {empresa['segmento']}" if empresa.get("segmento") else ""),
    ]
    if gancho:
        linhas.append("Gancho desta mensagem (use este fato):\n" + _descrever_gancho(gancho))
    if empresa.get("descricao"):
        linhas.append(f"Sobre a empresa: {empresa['descricao'][:600]}")
    if empresa.get("oportunidades_midia"):
        linhas.append(f"Oportunidades de mídia já mapeadas: {empresa['oportunidades_midia'][:500]}")
    if foco:
        linhas.append("Foco definido pelo executivo para esta empresa:\n" + foco)
    if contexto and not gancho:
        linhas.append("Contexto de mercado recente (use só um fato, e só se for relevante):\n" + contexto[:1800])
    if ja_usados:
        linhas.append("Fatos já usados com esta pessoa (não repita):\n" + "\n".join(f"- {f}" for f in ja_usados[:6]))
    if historico:
        linhas.append("Interações anteriores com a empresa (não repita o que já foi dito):\n" + "\n".join(f"- {h}" for h in historico[:6]))
    return system, "\n\n".join(linhas)


def frases_proibidas(texto):
    """Trechos de tom de IA encontrados no texto (sem repetição, na ordem em que aparecem)."""
    return list(dict.fromkeys(m.group(0).lower() for m in _PROIBIDAS_RE.finditer(texto or "")))


def assinar(texto, canal, *, remetente=None, assinatura=None, dispositivo="nenhum"):
    """Tira a despedida que o modelo escreveu e põe a do executivo (e o 'Enviado do meu…', se ele quiser)."""
    corpo = _DESPEDIDA_RE.sub("", texto or "").rstrip()
    if canal != "email":
        return corpo
    primeiro = (remetente or "").split(" ")[0]
    fecho = (assinatura or "").strip() or (f"Abs,\n{primeiro}" if primeiro else "Abs,")
    rodape = DISPOSITIVOS.get(dispositivo or "nenhum", "")
    return f"{corpo}\n\n{fecho}" + (f"\n\n{rodape}" if rodape else "")


def _separar(texto, canal):
    assunto = None
    if canal == "email":
        match = re.match(r"\s*assunto:\s*(.+)", texto, re.I)
        if match:
            assunto = match.group(1).strip()
            texto = texto[match.end():].strip()
    return assunto, texto


def gerar_mensagem(api_key, *, chat_fn=chat, assinatura=None, dispositivo="nenhum", **dados):
    system, user = montar_prompt_mensagem(**dados)
    canal = dados["canal"]
    texto, _ = chat_fn(api_key, MODELO_MENSAGEM, system, user, max_tokens=1200, temperature=0.7)
    assunto, texto = _separar(texto, canal)
    alertas = frases_proibidas(f"{assunto or ''}\n{texto}")
    if alertas:  # uma reescrita só; se sobrar algo, a tela avisa
        pedido = (f"{user}\n\nVersão anterior:\n" + (f"Assunto: {assunto}\n\n" if assunto else "") + texto +
                  f"\n\nReescreva sem estes trechos, mantendo o fato e a pergunta: {', '.join(alertas)}.")
        novo, _ = chat_fn(api_key, MODELO_MENSAGEM, system, pedido, max_tokens=1200, temperature=0.6)
        assunto, texto = _separar(novo, canal)
        alertas = frases_proibidas(f"{assunto or ''}\n{texto}")
    if canal == "linkedin_conexao" and len(texto) > 300:
        texto = texto[:297].rsplit(" ", 1)[0] + "…"
    texto = assinar(texto, canal, remetente=dados.get("remetente"), assinatura=assinatura, dispositivo=dispositivo)
    return {"assunto": assunto, "texto": texto, "alertas": alertas}
