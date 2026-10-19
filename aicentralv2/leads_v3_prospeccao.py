"""Leads v3: descoberta de pessoas e Golden Circle.

Fluxo (docs/leads-v3-plano.md): listar contatos → entender os contatos da empresa →
separar empresas → cadências. A descoberta é em cascata:

1. Apollo, busca de pessoas (não consome créditos; nomes vêm parcialmente ocultos).
2. Busca própria na web: perfis públicos do LinkedIn indexados, via Firecrawl search.
3. Revelar e-mail só de quem o executivo aprova (Apollo people/match, consome crédito).

Nada vira contato sem aprovação: tudo entra antes em cadu_lead_contato_candidatos.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from urllib.parse import urlparse

import requests

APOLLO_BASE = "https://api.apollo.io/api/v1"
BRASILAPI_CNPJ = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
TIMEOUT = 25

# Foco da prospecção: quem compra ou influencia mídia.
APOLLO_TITLES = [
    "marketing", "mídia", "midia", "media", "comunicação", "comunicacao", "brand", "marca",
    "publicidade", "criação", "criacao", "creative", "growth", "CMO",
]
APOLLO_SENIORITIES = ["owner", "founder", "c_suite", "partner", "vp", "head", "director", "manager"]
PAPEIS_FOCO = {"marketing", "midia", "criacao", "diretoria"}
FREE_EMAIL_DOMAINS = {"gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "yahoo.com.br", "bol.com.br",
                      "uol.com.br", "terra.com.br", "icloud.com", "live.com"}


class ProspeccaoError(RuntimeError):
    """Erro mostrado ao usuário (texto já em português)."""


# ─────────────────────────────────────────────────────
# Normalização e classificação de cargo
# ─────────────────────────────────────────────────────
def sem_acento(texto) -> str:
    base = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in base if not unicodedata.combining(c)).lower().strip()


def _tem(texto, termos) -> bool:
    """Termo no início de palavra; siglas curtas (coo, vp, cmo) também precisam terminar a palavra."""
    return any(re.search(rf"(?<![a-z]){t}{'(?![a-z])' if len(t) <= 4 else ''}", texto) for t in termos)


# Ordem importa: o primeiro papel que casar vence (CMO → marketing, não diretoria).
_PAPEIS = (
    ("midia", ("midia", "(?<!social )media", "paid", "performance marketing", "marketing de performance", "programat", "trading")),
    ("criacao", ("criacao", "criativ", "creative", "design", "art director", "diretor de arte", "redator", "copywriter")),
    ("marketing", ("marketing", "mkt", "cmo", "brand", "marca", "comunicacao", "communication", "publicidade",
                   "propaganda", "growth", "conteudo", "content", "social media", "relacoes publicas", "digital")),
    ("compras", ("compras", "procurement", "suprimentos", "purchasing", "sourcing")),
    ("comercial", ("comercial", "sales", "vendas", "business development", "novos negocios")),
    ("diretoria", ("ceo", "presidente", "president", "founder", "fundador", "socio", "partner", "diretor geral",
                   "general manager", "country manager", "coo", "cfo")),
)
_SENIORIDADES = (
    ("c_level", ("chief", "ceo", "cmo", "cfo", "coo", "cto", "presidente", "president", "founder", "fundador",
                 "vp", "vice president", "vice-president", "vice presidente", "socio")),
    ("diretor", ("diretor", "diretora", "director", "head")),
    ("gerente", ("gerente", "manager")),
    ("coordenador", ("coordenador", "coordenadora", "coordinator", "supervisor", "supervisora")),
    ("analista", ("analista", "analyst", "assistente", "assistant", "especialista", "specialist", "estagiari", "intern")),
)


def classificar_cargo(cargo) -> tuple[str, str]:
    """Devolve (papel, senioridade) a partir do cargo, por regras simples e previsíveis."""
    texto = sem_acento(cargo)
    papel = next((p for p, termos in _PAPEIS if _tem(texto, termos)), "outro")
    senioridade = next((s for s, termos in _SENIORIDADES if _tem(texto, termos)), "outro")
    return papel, senioridade


def normalizar_dominio(valor) -> str:
    texto = str(valor or "").strip().lower()
    if not texto:
        return ""
    if "@" in texto and "/" not in texto:
        texto = texto.split("@", 1)[1]
    if "://" not in texto:
        texto = "http://" + texto
    host = (urlparse(texto).hostname or "").strip(".")
    return host[4:] if host.startswith("www.") else host


def trimestre_atual(hoje: date | None = None) -> str:
    hoje = hoje or date.today()
    return f"{hoje.year}-Q{(hoje.month - 1) // 3 + 1}"


def digitos(valor) -> str:
    return re.sub(r"\D", "", str(valor or ""))


# ─────────────────────────────────────────────────────
# Apollo
# ─────────────────────────────────────────────────────
def _apollo_post(path, api_key, payload):
    if not api_key:
        raise ProspeccaoError("Apollo sem chave. Cadastre em Parâmetros › Integrações ou no .env (APOLLO_API_KEY).")
    try:
        response = requests.post(
            f"{APOLLO_BASE}/{path}",
            headers={"X-Api-Key": api_key, "Content-Type": "application/json", "Cache-Control": "no-cache"},
            json=payload, timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ProspeccaoError("Não foi possível falar com o Apollo agora.") from exc
    if response.status_code in (401, 403):
        raise ProspeccaoError("O Apollo recusou a chave ou o plano não libera esta função.")
    if response.status_code == 429:
        raise ProspeccaoError("Limite de chamadas do Apollo atingido. Tente de novo em alguns minutos.")
    if response.status_code == 422 and "credit" in response.text.lower():
        raise ProspeccaoError("Sem créditos no Apollo para revelar este contato.")
    if not response.ok:
        raise ProspeccaoError(f"O Apollo respondeu com erro ({response.status_code}).")
    try:
        return response.json()
    except ValueError as exc:
        raise ProspeccaoError("Resposta inválida do Apollo.") from exc


def apollo_buscar_pessoas(api_key, dominio, *, por_pagina=25):
    """Busca de pessoas por domínio da empresa. Não consome créditos; sobrenome vem oculto."""
    body = _apollo_post("mixed_people/api_search", api_key, {
        "q_organization_domains_list": [dominio],
        "person_titles": APOLLO_TITLES,
        "person_seniorities": APOLLO_SENIORITIES,
        "page": 1,
        "per_page": por_pagina,
    })
    candidatos = []
    for p in body.get("people") or []:
        cargo = p.get("title") or ""
        papel, senioridade = classificar_cargo(cargo)
        sobrenome = p.get("last_name") or p.get("last_name_obfuscated") or ""
        candidatos.append({
            "provedor": "apollo",
            "provedor_ref": p.get("id"),
            "nome": f"{p.get('first_name') or ''} {sobrenome}".strip() or "Sem nome",
            "cargo": cargo,
            "papel_sugerido": papel,
            "senioridade_sugerida": senioridade,
            "linkedin_url": p.get("linkedin_url"),
            "payload": {"has_email": p.get("has_email"), "has_direct_phone": p.get("has_direct_phone"),
                        "organization": (p.get("organization") or {}).get("name")},
        })
    return candidatos, body.get("total_entries")


_EMAIL_STATUS = {"verified": "valido", "likely to engage": "valido", "guessed": "arriscado",
                 "extrapolated": "arriscado", "unavailable": "invalido", "bounced": "invalido"}


def apollo_revelar(api_key, *, apollo_id=None, linkedin_url=None, nome=None, dominio=None):
    """people/match: devolve nome completo, e-mail e LinkedIn. Consome crédito do plano Apollo."""
    payload = {"reveal_personal_emails": False}
    if apollo_id:
        payload["id"] = apollo_id
    elif linkedin_url:
        payload["linkedin_url"] = linkedin_url
    elif nome and dominio:
        partes = nome.split()
        payload.update({"first_name": partes[0], "last_name": " ".join(partes[1:]), "domain": dominio})
    else:
        raise ProspeccaoError("Faltam dados para o Apollo achar esta pessoa (LinkedIn ou nome + domínio).")
    pessoa = (_apollo_post("people/match", api_key, payload) or {}).get("person")
    if not pessoa:
        raise ProspeccaoError("O Apollo não encontrou esta pessoa.")
    email = pessoa.get("email")
    if email and "email_not_unlocked" in email:
        email = None
    return {
        "nome": pessoa.get("name"),
        "cargo": pessoa.get("title"),
        "email": email,
        "email_status": _EMAIL_STATUS.get(str(pessoa.get("email_status") or "").lower(), "nao_verificado") if email else None,
        "linkedin_url": pessoa.get("linkedin_url"),
        "apollo_id": pessoa.get("id"),
    }


# ─────────────────────────────────────────────────────
# Busca própria: perfis públicos do LinkedIn via Firecrawl search
# ─────────────────────────────────────────────────────
def _firecrawl_search_endpoint():
    from .crm_v3_web_scout import _firecrawl_url

    return _firecrawl_url().rsplit("/scrape", 1)[0] + "/search"


def _parse_titulo_linkedin(titulo):
    """'Ana Lima - Gerente de Mídia - Gerdau | LinkedIn' → ('Ana Lima', 'Gerente de Mídia')."""
    texto = re.sub(r"\s*[|–-]\s*LinkedIn\s*$", "", str(titulo or ""), flags=re.I).strip()
    partes = [p.strip() for p in re.split(r"\s+[-–|]\s+", texto) if p.strip()]
    if not partes:
        return "", ""
    return partes[0], (partes[1] if len(partes) >= 2 else "")


def web_buscar_pessoas(api_key, empresa, *, limite=20):
    """Perfis públicos do LinkedIn que citam a empresa e um cargo de marketing/mídia/criação."""
    if not api_key:
        raise ProspeccaoError("Firecrawl sem chave. Cadastre em Parâmetros › Integrações.")
    nome = str(empresa or "").strip()
    if not nome:
        raise ProspeccaoError("O lead não tem nome de empresa para buscar.")
    # br.linkedin.com: só perfis do Brasil (o país da busca não filtra o LinkedIn de outras regiões).
    query = (f'site:br.linkedin.com/in "{nome}" '
             '(marketing OR mídia OR media OR comunicação OR brand OR criação OR publicidade)')
    try:
        response = requests.post(
            _firecrawl_search_endpoint(),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"query": query, "limit": limite, "country": "BR", "ignoreInvalidURLs": True},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ProspeccaoError("A busca na web falhou agora. Tente de novo em instantes.") from exc
    data = body.get("data") or {}
    resultados = data.get("web") if isinstance(data, dict) else data
    empresa_norm = sem_acento(nome)
    candidatos, vistos = [], set()
    for item in resultados or []:
        url = str(item.get("url") or "")
        match = re.search(r"linkedin\.com/in/([^/?#]+)", url)
        if not match:
            continue
        slug = match.group(1).lower()
        titulo = item.get("title") or ""
        descricao = item.get("description") or ""
        pessoa, cargo = _parse_titulo_linkedin(titulo)
        # Evita homônimos: a empresa precisa aparecer fora do nome da pessoa (há quem tenha
        # o sobrenome da empresa e trabalhe em outro lugar).
        fora_do_nome = sem_acento(f"{titulo} {descricao}").replace(sem_acento(pessoa), " ", 1)
        if empresa_norm not in fora_do_nome or slug in vistos:
            continue
        if not pessoa or sem_acento(cargo) == empresa_norm:
            cargo = ""
        papel, senioridade = classificar_cargo(f"{cargo} {descricao[:160]}")
        if papel not in PAPEIS_FOCO and senioridade != "c_level":
            continue
        vistos.add(slug)
        candidatos.append({
            "provedor": "pesquisa_web",
            "provedor_ref": slug,
            "nome": pessoa,
            "cargo": cargo or None,
            "papel_sugerido": papel,
            "senioridade_sugerida": senioridade,
            "linkedin_url": f"https://www.linkedin.com/in/{slug}",
            "payload": {"titulo": titulo[:300], "resumo": descricao[:500]},
        })
    return candidatos


# ─────────────────────────────────────────────────────
# Golden Circle: validação automática
# ─────────────────────────────────────────────────────
def consultar_cnpj(cnpj):
    """Dados públicos da Receita via BrasilAPI. Devolve None se não achar ou o serviço falhar."""
    try:
        response = requests.get(BRASILAPI_CNPJ.format(cnpj=cnpj), timeout=TIMEOUT)
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    return {
        "razao_social": data.get("razao_social"),
        "nome_fantasia": data.get("nome_fantasia"),
        "situacao": str(data.get("descricao_situacao_cadastral") or "").upper(),
        "porte": data.get("porte") or data.get("descricao_porte"),
        "cnae": data.get("cnae_fiscal_descricao"),
        "uf": data.get("uf"),
        "municipio": data.get("municipio"),
        "email": data.get("email"),
    }


def validar_conta(cursor, *, nome, dominio, cnpj, id_executivo, trimestre, consultar=consultar_cnpj):
    """Checagens automáticas antes de uma empresa entrar no Golden Circle (não grava nada).

    Bloqueia: nome vazio, trimestre inválido, CNPJ malformado ou inativo, conta repetida no
    mesmo Golden Circle. Avisa: já é cliente (vira expansão), já está no Golden Circle de outro
    executivo, CNPJ não consultado.
    """
    nome = str(nome or "").strip()
    dominio = normalizar_dominio(dominio)
    cnpj = digitos(cnpj)
    bloqueios, avisos = [], []
    dados = {"nome": nome, "dominio": dominio or None, "cnpj": cnpj or None, "objetivo": "captacao",
             "id_lead": None, "id_cliente": None}

    if not nome:
        bloqueios.append("Informe o nome da empresa.")
    if not re.fullmatch(r"\d{4}-Q[1-4]", str(trimestre or "")):
        bloqueios.append("Trimestre inválido.")
    if not id_executivo:
        bloqueios.append("Escolha o executivo dono do Golden Circle.")

    if cnpj:
        if len(cnpj) != 14:
            bloqueios.append("CNPJ precisa ter 14 dígitos.")
        else:
            receita = consultar(cnpj)
            if receita is None:
                avisos.append("Não consegui consultar o CNPJ agora; a conta entra sem os dados da Receita.")
            else:
                dados["receita"] = receita
                if receita["situacao"] and receita["situacao"] != "ATIVA":
                    bloqueios.append(f"CNPJ com situação {receita['situacao'].lower()} na Receita.")
                email_dom = normalizar_dominio(receita.get("email"))
                if not dominio and email_dom and email_dom not in FREE_EMAIL_DOMAINS:
                    dominio = dados["dominio"] = email_dom
    else:
        avisos.append("Sem CNPJ: a situação na Receita não foi conferida.")
    if not dominio:
        avisos.append("Sem domínio do site: a busca no Apollo fica indisponível até preencher.")

    if not nome:
        return {"ok": False, "bloqueios": bloqueios, "avisos": avisos, "dados": dados}

    # Já existe como lead? (CNPJ, domínio ou mesmo nome de empresa)
    cursor.execute(
        """
        SELECT id, empresa, status FROM cadu_leads
         WHERE (%(cnpj)s <> '' AND regexp_replace(COALESCE(cnpj, ''), '\\D', '', 'g') = %(cnpj)s)
            OR (%(dominio)s <> '' AND lower(dominio) = %(dominio)s)
            OR lower(trim(empresa)) = lower(%(nome)s)
         ORDER BY (status IN ('nao_qualificado', 'fechado_perdido')), updated_at DESC
         LIMIT 1
        """,
        {"cnpj": cnpj, "dominio": dominio, "nome": nome},
    )
    lead = cursor.fetchone()
    if lead:
        dados["id_lead"] = lead["id"]
        dados["lead_status"] = lead["status"]

    # Já é cliente da carteira? Então o alvo é expansão.
    cursor.execute(
        """
        SELECT id_cliente, nome_fantasia FROM tbl_cliente
         WHERE (%(cnpj)s <> '' AND regexp_replace(COALESCE(cnpj, ''), '\\D', '', 'g') = %(cnpj)s)
            OR lower(trim(nome_fantasia)) = lower(%(nome)s)
            OR lower(trim(razao_social)) = lower(%(nome)s)
         LIMIT 1
        """,
        {"cnpj": cnpj, "nome": nome},
    )
    cliente = cursor.fetchone()
    if cliente:
        dados.update(id_cliente=cliente["id_cliente"], objetivo="expansao")
        avisos.append(f"Já é cliente ({cliente['nome_fantasia']}): entra como expansão.")

    cursor.execute(
        """
        SELECT id, id_executivo FROM cadu_golden_circle
         WHERE trimestre = %(trimestre)s
           AND (lower(nome_conta) = lower(%(nome)s) OR (%(id_lead)s::int IS NOT NULL AND id_lead = %(id_lead)s::int))
        """,
        {"trimestre": trimestre, "nome": nome, "id_lead": dados["id_lead"]},
    )
    for row in cursor.fetchall():
        if row["id_executivo"] == id_executivo:
            bloqueios.append("Esta empresa já está no Golden Circle deste executivo no trimestre.")
        else:
            avisos.append("Esta empresa também está no Golden Circle de outro executivo neste trimestre.")

    return {"ok": not bloqueios, "bloqueios": bloqueios, "avisos": avisos, "dados": dados}


def criar_conta(cursor, validacao, *, id_executivo, trimestre, usuario_id):
    """Grava a conta validada: cria o lead se ainda não existir e liga ao Golden Circle."""
    dados = validacao["dados"]
    receita = dados.get("receita") or {}
    id_lead = dados.get("id_lead")
    if id_lead:
        cursor.execute(
            """
            UPDATE cadu_leads
               SET cnpj = COALESCE(cnpj, %s), dominio = COALESCE(dominio, %s),
                   url_site = COALESCE(url_site, %s), prioridade_conta = 'A', updated_at = CURRENT_TIMESTAMP
             WHERE id = %s
            """,
            [dados.get("cnpj"), dados.get("dominio"), dados.get("dominio"), id_lead],
        )
    else:
        cursor.execute(
            """
            INSERT INTO cadu_leads (nome, email, empresa, origem, fonte, status, potencial, tipo_lead,
                                    id_executivo, atribuido_em, url_site, cnpj, dominio, prioridade_conta, segmento)
            VALUES (%s, '', %s, 'golden_circle', 'manual', 'inbox', 'alto', 'cliente',
                    %s, CURRENT_TIMESTAMP, %s, %s, %s, 'A', %s)
            RETURNING id
            """,
            [dados["nome"], dados["nome"], id_executivo, dados.get("dominio"), dados.get("cnpj"),
             dados.get("dominio"), receita.get("cnae")],
        )
        id_lead = cursor.fetchone()["id"]
    cursor.execute(
        """
        INSERT INTO cadu_golden_circle (id_executivo, trimestre, nome_conta, id_lead, id_cliente, objetivo, criado_por)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        [id_executivo, trimestre, dados["nome"], id_lead, dados.get("id_cliente"), dados["objetivo"], usuario_id],
    )
    return {"id": cursor.fetchone()["id"], "id_lead": id_lead}
