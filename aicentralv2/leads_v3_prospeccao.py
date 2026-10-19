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
        # O cargo manda; o resumo do perfil só entra quando o cargo não diz a área.
        papel, senioridade = classificar_cargo(cargo)
        if papel == "outro" or senioridade == "outro":
            papel_r, senioridade_r = classificar_cargo(f"{cargo} {descricao[:160]}")
            papel = papel if papel != "outro" else papel_r
            senioridade = senioridade if senioridade != "outro" else senioridade_r
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
                   url_site = COALESCE(url_site, %s), prioridade_conta = 'A',
                   -- Lead sem dono passa a ser do executivo; o de outro executivo não é tomado.
                   id_executivo = COALESCE(id_executivo, %s),
                   atribuido_em = CASE WHEN id_executivo IS NULL THEN CURRENT_TIMESTAMP ELSE atribuido_em END,
                   -- Conta-alvo volta para a fila mesmo que o lead tenha sido descartado antes.
                   status = CASE WHEN status IN ('nao_qualificado', 'fechado_perdido') THEN 'inbox' ELSE status END,
                   updated_at = CURRENT_TIMESTAMP
             WHERE id = %s
            """,
            [dados.get("cnpj"), dados.get("dominio"), dados.get("dominio"), id_executivo, id_lead],
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


# ─────────────────────────────────────────────────────
# E-mail sem Apollo: padrão da empresa + Firecrawl + MX
# ─────────────────────────────────────────────────────
# Ordem da cascata em achar_email(): contatos já conhecidos do mesmo domínio → e-mails do
# domínio achados na web/no site (Firecrawl) → confere MX. O Apollo fica como último recurso,
# acionado pelo usuário. O resultado é um palpite (email_status = "arriscado"), nunca "valido".
PARTICULAS = {"de", "da", "do", "das", "dos", "e", "di", "du", "van", "von"}
GENERICOS = {
    "contato", "contatos", "comercial", "imprensa", "sac", "rh", "vendas", "marketing", "atendimento",
    "financeiro", "ouvidoria", "privacidade", "dpo", "lgpd", "suporte", "noreply", "no-reply", "info",
    "hello", "ola", "oi", "faleconosco", "fale", "comunicacao", "juridico", "compras", "parcerias",
    "trabalheconosco", "carreiras", "vagas", "admin", "webmaster", "press", "contact", "sales", "support",
}
# Padrões em ordem de frequência no Brasil corporativo.
PADROES = ("nome.sobrenome", "nome", "nsobrenome", "nomesobrenome", "nome_sobrenome", "n.sobrenome",
           "nome-sobrenome", "sobrenome.nome", "nomes")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Só telefone formatado (DDD com parênteses ou separadores): sequências soltas de dígitos costumam
# ser carimbos de data ou IDs no código da página.
_TEL_RE = re.compile(r"(?:\+55[\s.-]?)?\(?[1-9]\d\)?[\s.-]9?\d{4}[\s.-]\d{4}(?!\d)")


def _partes_nome(nome):
    tokens = [re.sub(r"[^a-z]", "", t) for t in sem_acento(nome).replace("*", " ").split()]
    tokens = [t for t in tokens if t and t not in PARTICULAS]
    if len(tokens) < 1:
        return None, None
    return tokens[0], (tokens[-1] if len(tokens) > 1 else "")


def gerar_local(nome, padrao):
    primeiro, ultimo = _partes_nome(nome)
    if not primeiro or (padrao != "nome" and not ultimo):
        return None
    if padrao == "nome":
        return primeiro
    return {
        "nome.sobrenome": f"{primeiro}.{ultimo}", "nsobrenome": f"{primeiro[0]}{ultimo}",
        "nomesobrenome": f"{primeiro}{ultimo}", "nome_sobrenome": f"{primeiro}_{ultimo}",
        "n.sobrenome": f"{primeiro[0]}.{ultimo}", "nome-sobrenome": f"{primeiro}-{ultimo}",
        "sobrenome.nome": f"{ultimo}.{primeiro}", "nomes": f"{primeiro}{ultimo[0]}",
    }.get(padrao)  # aqui `ultimo` já existe (checado acima)


def inferir_padrao_por_exemplos(exemplos):
    """exemplos: [(nome, email)] do mesmo domínio. Devolve (padrão, quantos exemplos casaram)."""
    votos = {}
    for nome, email in exemplos:
        local = str(email or "").split("@")[0].lower()
        for padrao in PADROES:
            if gerar_local(nome, padrao) == local:
                votos[padrao] = votos.get(padrao, 0) + 1
                break
    if not votos:
        return None, 0
    padrao = max(votos, key=lambda p: (votos[p], -PADROES.index(p)))
    return padrao, votos[padrao]


def inferir_padrao_por_estrutura(emails):
    """Sem nomes, só pela forma dos e-mails pessoais (ex.: 'joao.silva@' → nome.sobrenome)."""
    votos = {}
    for email in emails:
        local = email.split("@")[0].lower()
        if local in GENERICOS or any(ch.isdigit() for ch in local):
            continue
        if re.fullmatch(r"[a-z]{2,}\.[a-z]{2,}", local):
            padrao = "nome.sobrenome"
        elif re.fullmatch(r"[a-z]\.[a-z]{2,}", local):
            padrao = "n.sobrenome"
        elif re.fullmatch(r"[a-z]{2,}_[a-z]{2,}", local):
            padrao = "nome_sobrenome"
        elif re.fullmatch(r"[a-z]{2,}-[a-z]{2,}", local):
            padrao = "nome-sobrenome"
        else:
            continue  # "joaosilva" ou "joao" é ambíguo sem o nome da pessoa
        votos[padrao] = votos.get(padrao, 0) + 1
    if not votos:
        return None, 0
    padrao = max(votos, key=votos.get)
    return padrao, votos[padrao]


def _coletar_contatos(texto, dominio):
    emails = {e.lower().rstrip(".") for e in _EMAIL_RE.findall(texto or "")}
    do_dominio = sorted(e for e in emails if e.endswith("@" + dominio) or e.endswith("." + dominio))
    telefones = sorted({re.sub(r"\s+", " ", t).strip() for t in _TEL_RE.findall(texto or "") if len(digitos(t)) >= 10})
    return do_dominio, telefones[:5]


def firecrawl_contatos_do_dominio(api_key, dominio, *, scrape=None, search=None):
    """E-mails e telefones públicos do domínio: busca na web + página inicial e de contato do site."""
    emails, telefones = set(), set()
    if api_key and search is not False:
        try:
            response = (search or requests.post)(
                _firecrawl_search_endpoint(),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"query": f'"@{dominio}"', "limit": 10, "country": "BR", "ignoreInvalidURLs": True},
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            data = (response.json() or {}).get("data") or {}
            for item in (data.get("web") if isinstance(data, dict) else data) or []:
                achados, tels = _coletar_contatos(f"{item.get('title', '')} {item.get('description', '')}", dominio)
                emails.update(achados)
                telefones.update(tels)
        except (requests.RequestException, ValueError):
            pass
    if scrape is None:
        from .crm_v3_web_scout import _firecrawl_scrape as scrape
    for caminho in ("", "/contato", "/fale-conosco"):
        try:
            pagina = scrape(f"https://{dominio}{caminho}", formats=["markdown"], timeout_s=30, only_main_content=False)
        except Exception:
            continue
        achados, tels = _coletar_contatos((pagina or {}).get("markdown") or "", dominio)
        emails.update(achados)
        telefones.update(tels)
        if emails:
            break  # já dá para inferir o padrão; não gasta mais créditos
    return sorted(emails), sorted(telefones)[:5]


def dominio_recebe_email(dominio):
    """MX via DNS sobre HTTPS (Google), sem dependência nova. None = não deu para conferir."""
    try:
        response = requests.get("https://dns.google/resolve", params={"name": dominio, "type": "MX"}, timeout=10)
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError):
        return None
    return bool(body.get("Status") == 0 and any(a.get("type") == 15 for a in body.get("Answer") or []))


def achar_email(nome, dominio, exemplos, *, firecrawl_key=None, coletar=firecrawl_contatos_do_dominio, mx=dominio_recebe_email):
    """Cascata sem Apollo. Devolve dict com email (ou None), método, padrão, confiança e telefones da empresa."""
    resultado = {"email": None, "metodo": None, "padrao": None, "exemplos": 0, "telefones_empresa": [], "mx": None}
    if not dominio:
        resultado["motivo"] = "A empresa não tem domínio cadastrado."
        return resultado
    padrao, n = inferir_padrao_por_exemplos(exemplos)
    metodo = "padrao_contatos" if padrao else None
    if not padrao and firecrawl_key:
        emails, telefones = coletar(firecrawl_key, dominio)
        resultado["telefones_empresa"] = telefones
        padrao, n = inferir_padrao_por_estrutura(emails)  # sem nomes: só a forma dos e-mails ajuda
        metodo = "padrao_site" if padrao else None
    resultado["mx"] = mx(dominio)
    if resultado["mx"] is False:
        resultado["motivo"] = f"O domínio {dominio} não recebe e-mail (sem MX)."
        return resultado
    if not padrao:
        resultado["motivo"] = "Não achei o padrão de e-mail da empresa. Use o Apollo como último recurso."
        return resultado
    local = gerar_local(nome, padrao)
    if not local:
        resultado["motivo"] = "O nome da pessoa está incompleto para montar o e-mail (falta sobrenome)."
        return resultado
    resultado.update(email=f"{local}@{dominio}", metodo=metodo, padrao=padrao, exemplos=n)
    return resultado
