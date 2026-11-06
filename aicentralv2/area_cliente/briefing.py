"""Briefing enviado pelo cliente para a Centralcomm montar o planejamento.

Grava em ``cadu_briefings`` como ``pendente`` e ``enviado_para_centralcomm``,
com o executivo da conta como responsável de vendas. A equipe recebe na tela
de Briefings do CentralX e segue o fluxo atual (iniciar cotação, devolver).

O wizard da Área do Cliente coleta campos estruturados (tipo de objetivo, KPI,
público, praças, materiais, mensuração) e o texto que vai para
``briefing_original`` sai em seções fixas, com a nota de qualidade e as
pendências, para o comercial saber o que perguntar. Análise em
``docs/area-cliente-briefing-wizard.md``.

Regra da casa: nada de custo, margem, fee ou valor de PI. O histórico só lê
campos de texto (praça, segmentação, objetivo, plataforma, período).
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
import uuid
from datetime import date, timedelta

CANAIS = (
    ("tv_ctv", "TV e CTV"),
    ("programatica", "Digital e programática"),
    ("social", "Redes sociais"),
    ("busca", "Busca"),
    ("audio", "Áudio e rádio"),
    ("ooh", "OOH e DOOH"),
    ("influencia", "Influenciadores"),
    ("sugestao", "Quero sugestão da Centralcomm"),
)
_CANAIS_ROTULO = dict(CANAIS)

# Tipo de objetivo -> (rótulo, KPIs possíveis, é conversão?)
OBJETIVOS = (
    ("marca", "Tornar a marca conhecida", ("Alcance", "Frequência", "Lembrança de marca", "Impressões"), False),
    ("video", "Fazer o vídeo ser visto", ("Visualizações completas", "Alcance", "Custo por view"), False),
    ("trafego", "Levar pessoas ao site", ("Cliques", "Sessões no site", "CTR"), True),
    ("leads", "Gerar contatos (leads)", ("Leads", "Custo por lead", "Cadastros qualificados"), True),
    ("vendas", "Vender pelo site ou app", ("Vendas", "Custo por venda", "ROAS"), True),
    ("app", "Instalações de app", ("Instalações", "Custo por instalação", "Usuários ativos"), True),
    ("loja", "Levar pessoas à loja", ("Visitas à loja", "Alcance local", "Rotas e ligações"), False),
    ("lancamento", "Lançamento ou data especial", ("Alcance", "Lembrança de marca", "Vendas"), False),
)
_OBJ = {o[0]: o for o in OBJETIVOS}

ABRANGENCIAS = (
    ("nacional", "Brasil todo"),
    ("regioes", "Regiões"),
    ("estados", "Estados"),
    ("cidades", "Cidades"),
    ("raio", "Perto das minhas lojas"),
)
_ABR = dict(ABRANGENCIAS)

IDADES = ("13-17", "18-24", "25-34", "35-44", "45-54", "55+")
GENEROS = (("todos", "Todos"), ("mulheres", "Mulheres"), ("homens", "Homens"))
CLASSES = ("A", "B", "C", "D/E")
MATERIAIS = (
    ("prontas", "Tenho as peças prontas"),
    ("adaptar", "Tenho peças, mas precisam de adaptação"),
    ("produzir", "Preciso de produção"),
    ("indefinido", "Ainda não sei"),
)
_MAT = dict(MATERIAIS)
MENSURACAO = ("Pixel da Meta", "Google Analytics 4", "Tag do Google Ads", "CRM", "Não tenho")
VERBAS = ("Até R$ 20 mil", "R$ 20 a 50 mil", "R$ 50 a 150 mil", "R$ 150 a 500 mil", "Acima de R$ 500 mil", "Quero uma recomendação")

STATUS_CLIENTE = {
    "rascunho": ("Rascunho", "gray"),
    "pendente": ("Enviado · em análise", "brand"),
    "aceito": ("Em planejamento", "success"),
    "rejeitado": ("Devolvido para ajustes", "warning"),
}

LIMITES = {
    "titulo": 160, "objetivo": 2000, "publico": 1000, "verba": 120, "descricao": 6000,
    "kpi": 80, "kpi_meta": 160, "publico_b2b": 400, "raio_detalhe": 1000, "datas_chave": 400,
    "materiais_detalhe": 600, "site": 300, "concorrentes": 600, "origem": 40,
}
MAX_PRACAS = 60


def _db():
    from .. import db
    return db


def _data(valor):
    try:
        return date.fromisoformat((valor or "").strip()) if valor else None
    except ValueError:
        return None


def _escolhas(form, campo, validos) -> list[str]:
    vistos = []
    for v in form.getlist(campo):
        if v in validos and v not in vistos:
            vistos.append(v)
    return vistos


def validar(form) -> tuple[dict, dict]:
    """Normaliza o formulário. Devolve (dados, erros por campo)."""
    dados = {chave: (form.get(chave) or "").strip()[:limite] for chave, limite in LIMITES.items()}
    dados["canais"] = _escolhas(form, "canais", _CANAIS_ROTULO)
    dados["inicio"] = _data(form.get("inicio"))
    dados["fim"] = _data(form.get("fim"))
    tipo = form.get("objetivo_tipo") or ""
    dados["objetivo_tipo"] = tipo if tipo in _OBJ else ""
    abr = form.get("abrangencia") or ""
    dados["abrangencia"] = abr if abr in _ABR else ""
    dados["idades"] = _escolhas(form, "idades", IDADES)
    gen = form.get("genero") or ""
    dados["genero"] = gen if gen in dict(GENEROS) else ""
    dados["classes"] = _escolhas(form, "classes", CLASSES)
    dados["b2b"] = form.get("b2b") == "1"
    mat = form.get("materiais") or ""
    dados["materiais"] = mat if mat in _MAT else ""
    dados["mensuracao"] = _escolhas(form, "mensuracao", MENSURACAO)
    pracas = []
    for bruto in form.getlist("pracas"):
        # Sem JS o campo de busca chega como texto livre: "BH, Contagem; Betim".
        for p in re.split(r"[;,\n]+", bruto or ""):
            p = re.sub(r"\s+", " ", p).strip()[:80]
            if p and p.lower() not in {x.lower() for x in pracas}:
                pracas.append(p)
    dados["pracas"] = pracas[:MAX_PRACAS]
    if dados["abrangencia"] == "nacional":
        dados["pracas"] = []

    erros = {}
    if len(dados["titulo"]) < 3:
        erros["titulo"] = "Dê um nome para a campanha ou ação."
    if len(dados["objetivo"]) < 10:
        erros["objetivo"] = "Conte em uma ou duas frases o que você quer alcançar."
    if dados["inicio"] and dados["fim"] and dados["fim"] < dados["inicio"]:
        erros["fim"] = "O fim precisa ser depois do início."
    return dados, erros


# ---------- Qualidade ----------

def qualidade(d: dict, hoje: date | None = None) -> dict:
    """Nota de 0 a 100 e pendências. As mesmas regras rodam no navegador (area_cliente_briefing.js)."""
    hoje = hoje or date.today()
    conversao = bool(_OBJ.get(d.get("objetivo_tipo"), (0, 0, 0, False))[3])
    checagens = [
        ("objetivo", bool(d.get("objetivo_tipo") and d.get("kpi")), "Escolher o tipo de objetivo e o KPI principal."),
        ("publico", bool(d.get("idades") or d.get("classes") or d.get("genero") in ("mulheres", "homens")
                         or d.get("b2b") or len(d.get("publico") or "") >= 20), "Descrever o público com pelo menos um recorte."),
        ("pracas", bool(d.get("abrangencia") == "nacional" or d.get("pracas")
                        or (d.get("abrangencia") == "raio" and d.get("raio_detalhe"))), "Definir as praças."),
        ("periodo", bool(d.get("inicio") and d.get("fim")), "Informar início e fim."),
        ("verba", bool(d.get("verba")), "Informar a verba ou uma faixa."),
        ("canais", bool(d.get("canais")), "Escolher canais ou pedir sugestão."),
        ("materiais", bool(d.get("materiais")), "Dizer como estão as peças."),
    ]
    if conversao:
        checagens.append(("mensuracao", bool(d.get("site") and d.get("mensuracao")),
                          "Informar o site e como a conversão é medida."))
    feitos = sum(1 for _, ok, _ in checagens if ok)
    pendencias = [msg for _, ok, msg in checagens if not ok]
    avisos = []
    ini, fim = d.get("inicio"), d.get("fim")
    if ini and ini < hoje + timedelta(days=7):
        avisos.append("Início em menos de 7 dias: prazo curto para planejar e subir as campanhas.")
    if ini and fim and (fim - ini).days < 7:
        avisos.append("Período menor que 7 dias: pouco tempo para otimizar.")
    if conversao and "Não tenho" in (d.get("mensuracao") or []):
        avisos.append("Objetivo de conversão sem mensuração instalada.")
    return {"nota": round(100 * feitos / len(checagens)), "pendencias": pendencias, "avisos": avisos}


# ---------- Texto para o comercial ----------

def _fmt(dt):
    return dt.strftime("%d/%m/%Y") if dt else "a definir"


def resumo(d: dict) -> list[tuple[str, str]]:
    """Seções (rótulo, texto) usadas no texto do briefing e no e-mail ao comercial."""
    obj = _OBJ.get(d.get("objetivo_tipo"))
    linhas_obj = []
    if obj:
        linhas_obj.append(f"Tipo: {obj[1]}")
    if d.get("kpi"):
        linhas_obj.append(f"KPI principal: {d['kpi']}" + (f" (meta: {d['kpi_meta']})" if d.get("kpi_meta") else ""))
    linhas_obj.append(d.get("objetivo") or "")

    pub = []
    if d.get("publico"):
        pub.append(d["publico"])
    recortes = []
    if d.get("genero") and d["genero"] != "todos":
        recortes.append(dict(GENEROS)[d["genero"]])
    if d.get("idades"):
        recortes.append("idades " + ", ".join(d["idades"]))
    if d.get("classes"):
        recortes.append("classes " + ", ".join(d["classes"]))
    if recortes:
        pub.append("Recorte: " + "; ".join(recortes))
    if d.get("b2b"):
        pub.append("B2B" + (f": {d['publico_b2b']}" if d.get("publico_b2b") else ""))

    pracas = []
    if d.get("abrangencia"):
        pracas.append(f"Abrangência: {_ABR[d['abrangencia']]}")
    if d.get("pracas"):
        pracas.append("; ".join(d["pracas"]))
    if d.get("abrangencia") == "raio" and d.get("raio_detalhe"):
        pracas.append(f"Lojas e raio: {d['raio_detalhe']}")

    periodo = []
    if d.get("inicio") or d.get("fim"):
        periodo.append(f"{_fmt(d.get('inicio'))} a {_fmt(d.get('fim'))}")
    if d.get("datas_chave"):
        periodo.append(f"Datas-chave: {d['datas_chave']}")

    mat = []
    if d.get("materiais"):
        mat.append(_MAT[d["materiais"]])
    if d.get("materiais_detalhe"):
        mat.append(d["materiais_detalhe"])
    if d.get("site"):
        mat.append(f"Site/destino: {d['site']}")
    if d.get("mensuracao"):
        mat.append("Mensuração: " + ", ".join(d["mensuracao"]))

    secoes = [
        ("Objetivo", "\n".join(x for x in linhas_obj if x)),
        ("Público", "\n".join(pub)),
        ("Praças", "\n".join(pracas)),
        ("Período", "\n".join(periodo)),
        ("Verba prevista", d.get("verba") or ""),
        ("Canais de interesse", ", ".join(_CANAIS_ROTULO[c] for c in d.get("canais") or [])),
        ("Materiais e mensuração", "\n".join(mat)),
        ("Concorrentes e referências", d.get("concorrentes") or ""),
        ("Mais detalhes", d.get("descricao") or ""),
    ]
    return [(r, t) for r, t in secoes if t]


def _texto_briefing(d: dict) -> str:
    blocos = [f"## {rotulo}\n{texto}" for rotulo, texto in resumo(d)]
    if d.get("descobrir"):
        blocos.append(f"## Do Descobrir\n{d['descobrir']}")
    if d.get("origem_rotulo"):
        blocos.append(f"## Origem\nReaproveitou dados de: {d['origem_rotulo']}")
    q = d.get("qualidade") or qualidade(d)
    linhas_q = [f"Nota do briefing: {q['nota']}/100"]
    linhas_q += [f"- Falta: {p}" for p in q["pendencias"]]
    linhas_q += [f"- Atenção: {a}" for a in q["avisos"]]
    blocos.append("## Qualidade\n" + "\n".join(linhas_q))
    return "\n\n".join(blocos)


def enviar(usuario: dict, d: dict) -> int:
    """Cria o briefing do cliente da sessão. Devolve o id."""
    d.setdefault("qualidade", qualidade(d))
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT cli.nome_fantasia, cli.vendas_central_comm, vend.nome_completo AS exec_nome,
                       vend.email AS exec_email
                  FROM tbl_cliente cli
                  LEFT JOIN tbl_contato_cliente vend ON vend.id_contato_cliente = cli.vendas_central_comm
                 WHERE cli.id_cliente = %s
                """,
                (usuario["cliente_id"],),
            )
            cli = cursor.fetchone() or {}
            cursor.execute(
                """
                INSERT INTO cadu_briefings (
                    uuid, id_cliente, id_contato_cliente, cliente, titulo, status, progresso,
                    briefing_original, objetivo, budget, prazo, canais, responsavel,
                    responsavel_centralcomm, id_responsavel_vendas, email_destinatario,
                    enviado_para_centralcomm, data_envio, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, 'pendente', 0,
                    %s, %s, %s, %s, %s::jsonb, %s,
                    %s, %s, %s,
                    TRUE, NOW(), NOW(), NOW()
                )
                RETURNING id
                """,
                (
                    str(uuid.uuid4()), usuario["cliente_id"], usuario["user_id"], cli.get("nome_fantasia"),
                    d["titulo"], _texto_briefing(d), d["objetivo"], d["verba"] or None, d["inicio"],
                    _json([_CANAIS_ROTULO[c] for c in d["canais"]]), usuario["nome"],
                    cli.get("exec_nome"), cli.get("vendas_central_comm"), cli.get("exec_email"),
                ),
            )
            novo_id = cursor.fetchone()["id"]
        conn.commit()
        return int(novo_id)
    except Exception:
        conn.rollback()
        raise


def _json(valor):
    return json.dumps(valor, ensure_ascii=False)


def listar(cliente_id) -> list[dict]:
    """Briefings que o cliente (ou a Centralcomm por ele) enviou, mais recentes primeiro."""
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT b.id, b.titulo, b.status, b.objetivo, b.data_envio, b.created_at,
                       autor.nome_completo AS autor_nome
                  FROM cadu_briefings b
                  LEFT JOIN tbl_contato_cliente autor ON autor.id_contato_cliente = b.id_contato_cliente
                 WHERE b.id_cliente = %s AND b.deleted_at IS NULL
                   AND COALESCE(b.enviado_para_centralcomm, FALSE)
                 ORDER BY COALESCE(b.data_envio, b.created_at) DESC
                 LIMIT 50
                """,
                (cliente_id,),
            )
            rows = cursor.fetchall()
    except Exception:
        conn.rollback()
        raise
    saida = []
    for r in rows:
        rotulo, tom = STATUS_CLIENTE.get(r["status"], ("Enviado", "brand"))
        quando = r["data_envio"] or r["created_at"]
        saida.append({
            "id": r["id"], "titulo": r["titulo"] or "Briefing", "objetivo": r["objetivo"] or "",
            "status": rotulo, "tom": tom, "autor": r["autor_nome"] or "",
            "em": quando.strftime("%d/%m/%Y") if quando else "",
        })
    return saida


# ---------- Histórico para reaproveitar ----------

# Modelo de compra das campanhas -> tipo de objetivo do wizard.
_MODELO_OBJETIVO = {"CPM": "marca", "CPV": "video", "CPCV": "video", "CPC": "trafego", "CPL": "leads",
                    "CPA": "vendas", "CPE": "marca", "FLAT": "marca"}
_KPI_MODELO = {"CPM": "Alcance", "CPV": "Visualizações completas", "CPCV": "Visualizações completas",
               "CPC": "Cliques", "CPL": "Leads", "CPA": "Vendas"}


def _canal_da_plataforma(nome: str) -> str | None:
    n = _sem_acento(nome)
    if any(k in n for k in ("meta", "tik tok", "tiktok", "linkedin", "pinterest", "twitter", "x ads")):
        return "social"
    if any(k in n for k in ("google ads", "microsoft")):
        return "busca"
    if any(k in n for k in ("spotify", "deezer", "radio")):
        return "audio"
    if any(k in n for k in ("netflix", "globoplay", "disney", "hbo", "paramount", "prime", "you tube", "youtube")):
        return "tv_ctv"
    if any(k in n for k in ("dv360", "amazon dsp", "programatica", "logan", "serasa", "cadastro positivo", "uber")):
        return "programatica"
    return None


def _limpa_segmentacao(texto: str) -> str:
    t = re.sub(r"^\s*AS\s*[|\-:]\s*", "", texto or "", flags=re.I)
    return re.sub(r"\s+", " ", t).strip()[:400]


def _quebra_pracas(texto: str) -> list[str]:
    if not texto or _sem_acento(texto) in {"a definir", "", "-"}:
        return []
    partes = (re.sub(r"\s+", " ", p.rsplit(":", 1)[-1]).strip(" .*") for p in re.split(r"[\n;,]+", texto))
    return [p for p in partes if p and _sem_acento(p) not in {"nacional", "brasil", "a definir"}][:20]


def historico(cliente_id, limite: int = 8) -> list[dict]:
    """PIs e briefings anteriores do cliente, com o que dá para reaproveitar."""
    from .dados import SUB_STATUS_CANCELADO, _fetch

    pis = _fetch(
        """
        SELECT pi.id_pi, pi.titulo_pi, pi.codigo_pi_cc, pi.periodo_inicio, pi.periodo_fim,
               cot.objetivo_campanha
          FROM cadu_pi pi
          LEFT JOIN cadu_cotacoes cot ON cot.id = pi.cotacao_id
         WHERE (pi.id_cliente = %s OR pi.id_agencia = %s)
           AND COALESCE(pi.id_sub_status_pi, 0) <> %s
         ORDER BY COALESCE(pi.periodo_inicio, pi.created_at::date) DESC NULLS LAST, pi.id_pi DESC
         LIMIT %s
        """,
        (cliente_id, cliente_id, SUB_STATUS_CANCELADO, limite),
    )
    ids = [r["id_pi"] for r in pis]
    camps, linhas = [], []
    if ids:
        camps = _fetch(
            """
            SELECT c.id_pi, plt.descricao AS plataforma, obj.descricao AS modelo
              FROM cadu_pi_campanha c
              LEFT JOIN cadu_pi_camp_plataforma plt ON plt.id_plataforma = c.id_plataforma
              LEFT JOIN cadu_pi_camp_objetivos obj ON obj.id_objetivos_campanha = c.id_objetivos_campanha
             WHERE c.id_pi = ANY(%s)
            """,
            (ids,),
        )
        linhas = _fetch(
            """
            SELECT DISTINCT pi.id_pi, l.praca, l.segmentacao
              FROM cadu_pi pi
              JOIN cadu_cotacao_linhas l ON l.cotacao_id = pi.cotacao_id
             WHERE pi.id_pi = ANY(%s) AND COALESCE(l.is_deleted, FALSE) = FALSE
               AND COALESCE(l.is_header, FALSE) = FALSE AND COALESCE(l.is_subtotal, FALSE) = FALSE
            """,
            (ids,),
        )
    saida = []
    for r in pis:
        das = [c for c in camps if c["id_pi"] == r["id_pi"]]
        plataformas = sorted({c["plataforma"] for c in das if c["plataforma"] and "teste" not in c["plataforma"].lower()})
        modelos = [c["modelo"] for c in das if c["modelo"]]
        modelo = max(set(modelos), key=modelos.count) if modelos else None
        pracas, publicos = [], []
        for ln in (x for x in linhas if x["id_pi"] == r["id_pi"]):
            for p in _quebra_pracas(ln["praca"]):
                if p.lower() not in {x.lower() for x in pracas}:
                    pracas.append(p)
            seg = _limpa_segmentacao(ln["segmentacao"])
            if seg and seg not in publicos:
                publicos.append(seg)
        dias = (r["periodo_fim"] - r["periodo_inicio"]).days if r["periodo_inicio"] and r["periodo_fim"] else None
        objetivo = (r["objetivo_campanha"] or "").strip()
        if objetivo.lower() in {"none", "objetivo de teste"}:
            objetivo = ""
        canais = sorted({c for c in (_canal_da_plataforma(p) for p in plataformas) if c})
        titulo = (r["titulo_pi"] or "").strip() or (f"PI {r['codigo_pi_cc']}" if r["codigo_pi_cc"] else f"PI {r['id_pi']}")
        saida.append({
            "id": f"pi:{r['id_pi']}", "fonte": "PI", "titulo": titulo,
            "quando": r["periodo_inicio"].strftime("%m/%Y") if r["periodo_inicio"] else "",
            "objetivo": objetivo, "objetivo_tipo": _MODELO_OBJETIVO.get(modelo or "", ""),
            "kpi": _KPI_MODELO.get(modelo or "", ""), "plataformas": plataformas, "canais": canais,
            "pracas": pracas[:20], "publico": " | ".join(publicos[:2])[:900], "dias": dias,
        })

    briefs = _fetch(
        """
        SELECT id, titulo, objetivo, briefing_original, COALESCE(data_envio, created_at) AS em
          FROM cadu_briefings
         WHERE id_cliente = %s AND deleted_at IS NULL AND COALESCE(enviado_para_centralcomm, FALSE)
         ORDER BY COALESCE(data_envio, created_at) DESC
         LIMIT 4
        """,
        (cliente_id,),
    )
    for b in briefs:
        texto = b["briefing_original"] or ""
        publico = _secao(texto, "Público") or _linha(texto, "Público e praças")
        pracas_txt = _secao(texto, "Praças")
        linhas_pr = [ln for ln in pracas_txt.split("\n") if ln and not ln.startswith(("Abrangência:", "Lojas e raio:"))]
        pracas = [p for p in re.split(r";\s*", linhas_pr[0]) if p] if linhas_pr else []
        saida.append({
            "id": f"briefing:{b['id']}", "fonte": "Briefing", "titulo": b["titulo"] or "Briefing",
            "quando": b["em"].strftime("%m/%Y") if b["em"] else "", "objetivo": (b["objetivo"] or "")[:600],
            "objetivo_tipo": "", "kpi": "", "plataformas": [], "canais": [], "pracas": pracas[:20],
            "publico": publico[:900], "dias": None,
        })
    return [h for h in saida if h["objetivo"] or h["pracas"] or h["publico"] or h["plataformas"]]


def _secao(texto: str, nome: str) -> str:
    m = re.search(rf"^## {re.escape(nome)}\n(.*?)(?=\n\n## |\Z)", texto, flags=re.S | re.M)
    return m.group(1).strip() if m else ""


def _linha(texto: str, rotulo: str) -> str:
    m = re.search(rf"^{re.escape(rotulo)}:\s*(.+)$", texto, flags=re.M)
    return m.group(1).strip() if m else ""


# ---------- Praças: base local + IA ----------

UFS = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
    "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}
REGIOES = ("Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul")
# Capitais e cidades com mais de ~250 mil habitantes (IBGE, Censo 2022), para responder sem esperar a IA.
CIDADES = (
    "São Paulo-SP Guarulhos-SP Campinas-SP São Bernardo do Campo-SP Santo André-SP Osasco-SP Ribeirão Preto-SP "
    "Sorocaba-SP São José dos Campos-SP Mauá-SP São José do Rio Preto-SP Mogi das Cruzes-SP Santos-SP Diadema-SP "
    "Jundiaí-SP Piracicaba-SP Carapicuíba-SP Bauru-SP Itaquaquecetuba-SP Franca-SP São Vicente-SP Praia Grande-SP "
    "Guarujá-SP Taubaté-SP Limeira-SP Suzano-SP Taboão da Serra-SP Barueri-SP Sumaré-SP Indaiatuba-SP "
    "Rio de Janeiro-RJ São Gonçalo-RJ Duque de Caxias-RJ Nova Iguaçu-RJ Niterói-RJ Campos dos Goytacazes-RJ "
    "Belford Roxo-RJ São João de Meriti-RJ Petrópolis-RJ Volta Redonda-RJ Macaé-RJ Magé-RJ "
    "Belo Horizonte-MG Uberlândia-MG Contagem-MG Juiz de Fora-MG Betim-MG Montes Claros-MG Uberaba-MG "
    "Ribeirão das Neves-MG Governador Valadares-MG Ipatinga-MG Sete Lagoas-MG Divinópolis-MG Santa Luzia-MG "
    "Nova Lima-MG Poços de Caldas-MG "
    "Vitória-ES Vila Velha-ES Serra-ES Cariacica-ES "
    "Curitiba-PR Londrina-PR Maringá-PR Ponta Grossa-PR Cascavel-PR São José dos Pinhais-PR Foz do Iguaçu-PR "
    "Porto Alegre-RS Caxias do Sul-RS Canoas-RS Pelotas-RS Santa Maria-RS Gravataí-RS Novo Hamburgo-RS "
    "Florianópolis-SC Joinville-SC Blumenau-SC São José-SC Itajaí-SC Chapecó-SC Balneário Camboriú-SC "
    "Brasília-DF Goiânia-GO Aparecida de Goiânia-GO Anápolis-GO Campo Grande-MS Dourados-MS Cuiabá-MT "
    "Várzea Grande-MT Rondonópolis-MT "
    "Salvador-BA Feira de Santana-BA Vitória da Conquista-BA Camaçari-BA Juazeiro-BA Lauro de Freitas-BA "
    "Fortaleza-CE Caucaia-CE Juazeiro do Norte-CE Maracanaú-CE Sobral-CE "
    "Recife-PE Jaboatão dos Guararapes-PE Olinda-PE Caruaru-PE Petrolina-PE Paulista-PE "
    "São Luís-MA Imperatriz-MA Teresina-PI Natal-RN Mossoró-RN Parnamirim-RN João Pessoa-PB Campina Grande-PB "
    "Maceió-AL Arapiraca-AL Aracaju-SE "
    "Manaus-AM Belém-PA Ananindeua-PA Santarém-PA Marabá-PA Porto Velho-RO Macapá-AP Rio Branco-AC Boa Vista-RR "
    "Palmas-TO Araguaína-TO"
)


def base_pracas() -> list[dict]:
    """Lista curta para o autocompletar local (sem rede)."""
    itens = [{"nome": "Brasil (nacional)", "tipo": "pais"}]
    itens += [{"nome": f"Região {r}", "tipo": "regiao"} for r in REGIOES]
    itens += [{"nome": f"{nome} (estado)", "uf": uf, "tipo": "estado"} for uf, nome in UFS.items()]
    for token in re.findall(r"([^\s][^-]*?)-([A-Z]{2})(?=\s|$)", CIDADES):
        nome, uf = token[0].strip(), token[1]
        itens.append({"nome": f"{nome} - {uf}", "uf": uf, "tipo": "cidade"})
    return itens


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn").strip()


_CACHE_IA: dict[str, tuple[float, dict]] = {}
_PROMPT_PRACAS = (
    "Você normaliza praças de mídia no Brasil para um briefing de campanha. Recebe o texto livre que o cliente "
    "digitou e as praças que ele já escolheu. Responda só JSON no formato "
    '{"pracas":[{"nome":"Belo Horizonte - MG","tipo":"cidade"}],'
    '"sugestoes":[{"nome":"Contagem - MG","tipo":"cidade","motivo":"Região metropolitana de BH"}],'
    '"observacao":""}. '
    "Regras: cidades no formato 'Cidade - UF' com acentos corretos; estados como 'Nome do estado (estado)'; "
    "regiões do país como 'Região Sudeste'; regiões metropolitanas como 'RM de Cidade - UF'; o país como "
    "'Brasil (nacional)'. tipo é cidade, estado, regiao, rm ou pais. Expanda siglas e apelidos (BH, Sampa, "
    "POA, Floripa, ABC, Grande SP). Não invente cidades; se um trecho não for um lugar, ignore e explique em "
    "observacao. Em sugestoes, traga até 6 praças próximas ou complementares às escolhidas (região "
    "metropolitana, cidades polo vizinhas), sem repetir as que já estão em pracas ou nas escolhidas, cada uma "
    "com um motivo curto."
)


def pracas_ia(texto: str, escolhidas: list[str]) -> dict:
    """Normaliza o texto em praças e sugere vizinhas. Cache de 1 hora por entrada."""
    from ..services.openrouter_service import OpenRouterError, chat_completion

    texto = (texto or "").strip()[:600]
    escolhidas = [e[:80] for e in escolhidas or []][:MAX_PRACAS]
    chave = _sem_acento(texto) + "|" + "|".join(sorted(_sem_acento(e) for e in escolhidas))
    agora = time.time()
    if chave in _CACHE_IA and agora - _CACHE_IA[chave][0] < 3600:
        return _CACHE_IA[chave][1]
    mensagens = [
        {"role": "system", "content": _PROMPT_PRACAS},
        {"role": "user", "content": json.dumps({"texto": texto, "escolhidas": escolhidas}, ensure_ascii=False)},
    ]
    try:
        resp = chat_completion(mensagens, max_tokens=None, temperature=0.1, timeout=40,
                               response_format={"type": "json_object"})
    except OpenRouterError as exc:
        raise RuntimeError(str(exc) or "A IA não respondeu.") from exc
    conteudo = (resp.get("message") or {}).get("content") or ""
    if isinstance(conteudo, list):
        conteudo = "".join(p.get("text", "") for p in conteudo if isinstance(p, dict))
    m = re.search(r"\{.*\}", conteudo, flags=re.S)
    try:
        bruto = json.loads(m.group(0)) if m else {}
    except ValueError:
        bruto = {}
    tipos = {"cidade", "estado", "regiao", "rm", "pais"}

    def _itens(lista, com_motivo=False):
        saida, vistos = [], {_sem_acento(e) for e in escolhidas} if com_motivo else set()
        for it in lista if isinstance(lista, list) else []:
            if not isinstance(it, dict):
                continue
            nome = re.sub(r"\s+", " ", str(it.get("nome") or "")).strip()[:80]
            if not nome or _sem_acento(nome) in vistos:
                continue
            vistos.add(_sem_acento(nome))
            item = {"nome": nome, "tipo": it.get("tipo") if it.get("tipo") in tipos else "cidade"}
            if com_motivo:
                item["motivo"] = str(it.get("motivo") or "")[:120]
            saida.append(item)
        return saida

    pracas = _itens(bruto.get("pracas"))[:30]
    ja = {_sem_acento(p["nome"]) for p in pracas}
    sugestoes = [s for s in _itens(bruto.get("sugestoes"), com_motivo=True) if _sem_acento(s["nome"]) not in ja][:6]
    resultado = {"pracas": pracas, "sugestoes": sugestoes, "observacao": str(bruto.get("observacao") or "")[:200]}
    if len(_CACHE_IA) > 500:
        _CACHE_IA.clear()
    _CACHE_IA[chave] = (agora, resultado)
    return resultado
