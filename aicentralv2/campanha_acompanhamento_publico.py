"""Monta o objeto CAMPANHA da página pública de acompanhamento (template operacional)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from urllib.parse import urlparse, urlunparse

from .campanha_pi_metrics import parse_volume_float
from .pi_operacao_service import PiOperacaoService


_LOOKER_HOSTS = ("lookerstudio.google.com", "datastudio.google.com")


_CONTA_GOOGLE = re.compile(r"^/u/\d+(?=/)")


def _sem_conta_google(path):
    """Remove o prefixo de conta (/u/0/) que o Google põe no link copiado do navegador."""
    return _CONTA_GOOGLE.sub("", path or "")


def normalizar_url_embed_looker_studio(url):
    """Converte link de visualização do Looker Studio para URL de incorporação."""
    text = (url or "").strip()
    if not text:
        return ""

    parsed = urlparse(text if "://" in text else f"https://{text}")
    host = (parsed.netloc or "").lower().removeprefix("www.")
    if host not in _LOOKER_HOSTS:
        return text

    path = _sem_conta_google(parsed.path)
    if path.startswith("/embed/reporting/"):
        return urlunparse(("https", host, path, parsed.params, parsed.query, parsed.fragment))
    if path.startswith("/reporting/"):
        path = "/embed" + path
    elif not path.startswith("/embed/reporting/"):
        return text

    normalized = urlunparse(
        (
            "https",
            host,
            path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
    return normalized


def normalizar_url_visualizacao_looker_studio(url):
    """Link para abrir o relatório no Looker (não depende de incorporação ativa)."""
    text = (url or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = f"https://{text}"

    parsed = urlparse(text)
    host = (parsed.netloc or "").lower().removeprefix("www.")
    if host not in _LOOKER_HOSTS:
        return text

    path = _sem_conta_google(parsed.path)
    if path.startswith("/embed/reporting/"):
        path = path.replace("/embed/reporting/", "/reporting/", 1)
    elif not path.startswith("/reporting/"):
        return text

    return urlunparse(
        (
            "https",
            host,
            path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    return None


def _iso(value):
    parsed = _as_date(value)
    return parsed.isoformat() if parsed else ""


def _fmt_periodo_br(inicio, fim):
    ini = _as_date(inicio)
    f = _as_date(fim)
    if not ini and not f:
        return "—"
    fmt = lambda d: d.strftime("%d/%m/%Y")
    if ini and f:
        return f"{fmt(ini)} a {fmt(f)}"
    if ini:
        return f"A partir de {fmt(ini)}"
    return f"Até {fmt(f)}"


def _shift(base, days):
    parsed = _as_date(base)
    if not parsed:
        return None
    return parsed + timedelta(days=days)


def _timeline_map(timeline):
    mapped = {}
    for item in timeline or []:
        etapa = item.get("etapa")
        if not etapa:
            continue
        mapped[etapa] = item
    return mapped


def _realizado_etapa(timeline_by_etapa, *etapas):
    for etapa in etapas:
        row = timeline_by_etapa.get(etapa) or {}
        if not row.get("concluida"):
            continue
        when = row.get("concluida_em")
        if when:
            return _iso(when)
        return date.today().isoformat()
    return ""


def _volume_label(value):
    if value is None or str(value).strip() == "":
        return "—"
    parsed = parse_volume_float(value)
    if parsed is None:
        return str(value).strip()
    if parsed == int(parsed):
        return f"{int(parsed):,}".replace(",", ".")
    return f"{parsed:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _contato_cc(nome, papel, email):
    if not (nome or email):
        return None
    return {
        "nome": nome or "Centralcomm",
        "papel": papel or "Operações",
        "email": email or "",
    }


def _so_digitos(value):
    return re.sub(r"\D", "", str(value or ""))


def _whatsapp(telefone):
    digitos = _so_digitos(telefone)
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    return f"https://wa.me/{digitos}" if len(digitos) >= 12 else ""


def _pessoa_interna(contato, nome, papel):
    contato = contato or {}
    nome = nome or contato.get("nome_completo")
    if not nome:
        return None
    telefone = contato.get("telefone") or ""
    return {
        "nome": nome,
        "papel": papel,
        "email": contato.get("email") or "",
        "telefone": telefone,
        "whatsapp": _whatsapp(telefone),
        "foto_url": contato.get("foto_url") or "",
    }


def _pct(atingido, meta):
    if not meta or meta <= 0:
        return None
    return round(atingido / meta * 100)


def _resultado_campanha(row, atual_id, hoje=None):
    """Painel de entrega de uma campanha: objetivo, meta, atingido. Nunca expõe custo."""
    from .campanha_pi_metrics import calcular_periodo_progresso

    meta = parse_volume_float(row.get("obj_contratados"))
    atingido = parse_volume_float(row.get("totalizador_atingido"))
    periodo = calcular_periodo_progresso(row.get("periodo_inicio"), row.get("periodo_fim"), hoje=hoje)
    pct = _pct(atingido, meta)
    tempo = periodo.get("periodo_pct_elapsed")
    ritmo = ""
    if pct is not None and tempo:
        ritmo = "adiantado" if pct >= tempo + 5 else "no_ritmo" if pct >= tempo - 10 else "atencao"
    link_raw = (row.get("link_dash") or "").strip()
    incorporar = row.get("link_dash_incorporar")
    incorporar = True if incorporar is None else bool(incorporar)
    return {
        "id": int(row.get("id_campanha") or 0),
        "nome": row.get("nome_campanha") or "Campanha",
        "plataforma": row.get("plataforma_nome") or "",
        "objetivo": row.get("objetivo_nome") or "—",
        "status": row.get("status_nome") or row.get("status_descricao") or "",
        "periodo": {"inicio": _iso(row.get("periodo_inicio")), "fim": _iso(row.get("periodo_fim"))},
        "meta": meta if meta > 0 else None,
        "meta_label": _volume_label(row.get("obj_contratados")),
        "atingido": atingido,
        "atingido_label": _volume_label(row.get("totalizador_atingido")) if atingido else "0",
        "pct": pct,
        "tempo_pct": tempo,
        "dias_restantes": periodo.get("periodo_dias_restantes"),
        "ritmo": ritmo,
        "dash_embed": normalizar_url_embed_looker_studio(link_raw) if incorporar and link_raw else "",
        "dash_abrir": normalizar_url_visualizacao_looker_studio(link_raw) if link_raw else "",
        "atual": int(row.get("id_campanha") or 0) == int(atual_id),
    }


def montar_payload_acompanhamento_campanha(id_campanha, *, service=None, linhas_campanhas=None):
    """Retorna dict usado pelas páginas públicas da campanha."""
    from . import db

    campanha_row = db.obter_campanha_pi_por_id(id_campanha)
    if not campanha_row:
        raise LookupError("Campanha não encontrada.")

    id_pi = campanha_row["id_pi"]
    operacao = (service or PiOperacaoService()).estado_campanha(id_pi, id_campanha)
    pi = operacao.get("pi") or {}
    campanha = operacao.get("campanha") or dict(campanha_row)
    if not campanha.get("link_dash") and campanha_row.get("link_dash"):
        campanha["link_dash"] = campanha_row["link_dash"]
    link_raw = (campanha.get("link_dash") or campanha_row.get("link_dash") or "").strip()
    link_dash_view = normalizar_url_visualizacao_looker_studio(link_raw)
    incorporar = campanha.get("link_dash_incorporar")
    if incorporar is None:
        incorporar = campanha_row.get("link_dash_incorporar", True)
    incorporar = bool(incorporar)
    link_dash_embed = (
        normalizar_url_embed_looker_studio(link_raw) if incorporar and link_raw else ""
    )
    campanhas_pi = operacao.get("campanhas_relacionadas") or []
    timeline = _timeline_map(operacao.get("timeline"))

    inicio = campanha.get("periodo_inicio") or pi.get("periodo_inicio")
    fim = campanha.get("periodo_fim") or pi.get("periodo_fim")

    codigo_pi = pi.get("codigo_pi_cc") or pi.get("codigo_pi_ag") or ""
    pi_label = codigo_pi or f"PI #{id_pi}"

    cotacao = None
    if pi.get("cotacao_id"):
        cotacao = db.obter_cotacao_por_id(pi["cotacao_id"])

    pracas = []
    if cotacao and cotacao.get("praca"):
        pracas.append(str(cotacao["praca"]).strip())

    combinados_pi = [
        {"rotulo": "Período", "valor": _fmt_periodo_br(inicio, fim)},
        {
            "rotulo": "Praças",
            "valor": ", ".join(pracas) if pracas else "Conforme PI",
        },
        {
            "rotulo": "Prazo dos materiais",
            "valor": "5 dias úteis antes do início",
        },
        {
            "rotulo": "Aprovação de criativos",
            "valor": "Até 2 dias úteis após o envio",
        },
        {
            "rotulo": "Acompanhamento",
            "valor": "Dashboard de entregas, atualização diária",
        },
        {
            "rotulo": "Canal oficial",
            "valor": "E-mail do grupo da campanha",
        },
    ]

    combinados_campanhas = []
    for item in campanhas_pi:
        full = next(
            (
                c
                for c in operacao.get("campanhas") or []
                if int(c.get("id_campanha") or 0) == int(item.get("id_campanha") or 0)
            ),
            None,
        )
        if not full and int(item.get("id_campanha") or 0) != int(id_campanha):
            all_camps = db.obter_campanhas_pi({"id_pi": id_pi}) or []
            full = next(
                (
                    c
                    for c in all_camps
                    if int(c.get("id_campanha") or 0) == int(item.get("id_campanha") or 0)
                ),
                None,
            )
        nome = item.get("nome") or (full or {}).get("nome_campanha") or "Campanha"
        plataforma = item.get("plataforma") or (full or {}).get("plataforma_nome") or ""
        titulo = nome if not plataforma else f"{nome} · {plataforma}"
        combinados_campanhas.append(
            {
                "nome": titulo,
                "itens": [
                    {
                        "rotulo": "Objetivo",
                        "valor": (full or {}).get("objetivo_nome") or "—",
                    },
                    {
                        "rotulo": "KPI",
                        "valor": (full or {}).get("objetivo_nome") or "Conforme PI",
                    },
                    {
                        "rotulo": "Volume contratado",
                        "valor": _volume_label((full or {}).get("obj_contratados")),
                    },
                    {
                        "rotulo": "Formato",
                        "valor": plataforma or "—",
                    },
                ],
            }
        )

    marcos = [
        {
            "id": "pi",
            "titulo": "PI aprovado",
            "previsto": _iso(_shift(inicio, -14) or pi.get("periodo_inicio")),
            "realizado": _realizado_etapa(timeline, "dados_validados"),
            "responsavel": "cliente",
            "nota": "Combinados extraídos do PI",
        },
        {
            "id": "materiais",
            "titulo": "Recebimento dos materiais",
            "previsto": _iso(_shift(inicio, -10)),
            "realizado": _realizado_etapa(timeline, "materiais_recebidos"),
            "responsavel": "cliente",
            "nota": "Criativos e URLs",
        },
        {
            "id": "setup",
            "titulo": "Planejamento e setup",
            "previsto": _iso(_shift(inicio, -7)),
            "realizado": _realizado_etapa(timeline, "campanhas_configuradas"),
            "responsavel": "cc",
            "nota": "Configuração nas plataformas",
        },
        {
            "id": "dashboard",
            "titulo": "Dashboard de entregas publicado",
            "previsto": _iso(_shift(inicio, -3)),
            "realizado": _iso(campanha.get("updated_at"))
            if link_dash_embed
            else "",
            "responsavel": "cc",
            "nota": "Acompanhamento diário",
        },
        {
            "id": "no_ar",
            "titulo": "Campanhas no ar",
            "previsto": _iso(inicio),
            "realizado": _realizado_etapa(timeline, "campanha_iniciada"),
            "responsavel": "cc",
            "nota": "Em operação",
        },
        {
            "id": "fim",
            "titulo": "Fim do período de veiculação",
            "previsto": _iso(fim),
            "realizado": _realizado_etapa(timeline, "fechamento_comunicado")
            if _as_date(fim) and _as_date(fim) <= date.today()
            else "",
            "responsavel": "cc",
            "nota": "Encerramento das campanhas",
        },
        {
            "id": "prestacao",
            "titulo": "Prestação de contas",
            "previsto": _iso(_shift(fim, 10)),
            "realizado": _realizado_etapa(timeline, "fechamento_comunicado"),
            "responsavel": "cc",
            "nota": "Resultados e entregas",
        },
        {
            "id": "faturamento",
            "titulo": "Faturamento",
            "previsto": _iso(_shift(fim, 15)),
            "realizado": _realizado_etapa(timeline, "enviado_financeiro"),
            "responsavel": "cc",
            "nota": "Emissão da nota fiscal",
        },
    ]

    resp_comercial = None
    if pi.get("id_resp_comercial"):
        resp_comercial = db.obter_contato_por_id(pi["id_resp_comercial"])
    resp_operacao = None
    if campanha.get("id_responsavel_operacao"):
        resp_operacao = db.obter_contato_por_id(campanha["id_responsavel_operacao"])

    centralcomm = []
    cc_vendas = _contato_cc(
        pi.get("responsavel_comercial_nome")
        or (resp_comercial or {}).get("nome_completo"),
        "Atendimento",
        (resp_comercial or {}).get("email"),
    )
    if cc_vendas:
        centralcomm.append(cc_vendas)
    resp_op = (
        campanha.get("responsavel_operacao_nome")
        or (resp_operacao or {}).get("nome_completo")
        or operacao.get("resumo", {}).get("executivo_vendas")
    )
    cc_ops = _contato_cc(resp_op, "Operações", (resp_operacao or {}).get("email"))
    if cc_ops:
        centralcomm.append(cc_ops)
    if not centralcomm:
        centralcomm.append(
            {"nome": "Centralcomm", "papel": "Operações", "email": "operacao@centralcomm.media"}
        )

    clientes = []
    for dest in operacao.get("destinatarios") or []:
        email = (dest.get("email") or "").strip()
        if not email:
            continue
        papel = dest.get("papel") or "cliente_final"
        label = {
            "agencia": "Agência",
            "parceiro": "Parceiro",
            "cliente_final": "Cliente",
        }.get(papel, "Cliente")
        clientes.append(
            {
                "nome": dest.get("nome_completo") or label,
                "papel": label,
                "email": email,
            }
        )

    documentos = []
    drive_docs = [
        ("PI assinado / pasta principal", pi.get("googled_pi_princ")),
        ("Plano de mídia / peças", pi.get("googled_pi_pecas")),
        ("Documentos assinados", pi.get("googled_pi_arq_ass")),
    ]
    for titulo, url in drive_docs:
        if not url:
            continue
        documentos.append(
            {
                "titulo": titulo,
                "url": url,
                "data": _iso(pi.get("updated_at") or campanha.get("updated_at")),
            }
        )

    relatorios = []
    if pi.get("googled_pi_financ"):
        relatorios.append(
            {
                "titulo": "Relatório de prestação de contas",
                "url": pi.get("googled_pi_financ"),
                "data": _iso(_shift(fim, 10)),
                "marco": "prestacao",
            }
        )

    if linhas_campanhas is None:
        linhas_campanhas = db.obter_campanhas_pi({"id_pi": id_pi}) or []
    linhas = list(linhas_campanhas) or [{**campanha_row, **campanha}]
    if not any(int(r.get("id_campanha") or 0) == int(id_campanha) for r in linhas):
        linhas.insert(0, {**campanha_row, **campanha})
    resultados = [_resultado_campanha(r, id_campanha) for r in linhas]
    resultados.sort(key=lambda r: (not r["atual"], r["id"]))

    executivo = _pessoa_interna(
        resp_comercial,
        pi.get("responsavel_comercial_nome"),
        "Executivo(a) de atendimento",
    )
    operacao_pessoa = _pessoa_interna(resp_operacao, resp_op, "Operações")
    if not executivo:
        executivo, operacao_pessoa = operacao_pessoa, None

    atualizado = operacao.get("resumo", {}).get("ultima_atualizacao") or campanha.get(
        "updated_at"
    ) or pi.get("updated_at")
    if isinstance(atualizado, datetime):
        atualizado = atualizado.date()

    return {
        "demo": False,
        "cliente": pi.get("cliente_nome") or campanha.get("cliente_nome") or "Cliente",
        "campanha": campanha.get("nome_campanha") or "Campanha",
        "pi": pi_label,
        "periodo": {"inicio": _iso(inicio), "fim": _iso(fim)},
        "atualizado_em": _iso(atualizado) or date.today().isoformat(),
        "marcos": marcos,
        "resultados": resultados,
        "executivo": executivo,
        "operacao": operacao_pessoa,
        "modulos": {
            "dashboard": {
                "aparece_apos": "dashboard",
                "titulo": "Dashboard de entregas",
                "descricao": "Atualizado diariamente pela operação Centralcomm.",
                "url_embed": link_dash_embed,
                "url_abrir": link_dash_view or link_raw,
                "incorporar_ativo": incorporar,
            },
            "relatorios": {
                "aparece_apos": "prestacao",
                "titulo": "Prestação de contas",
                "itens": relatorios,
            },
            "combinados": {
                "aparece_apos": "pi",
                "titulo": "Combinados",
                "pi": combinados_pi,
                "campanhas": combinados_campanhas,
            },
            "contatos": {
                "aparece_apos": "pi",
                "titulo": "Contatos",
                "centralcomm": centralcomm,
                "cliente": clientes,
            },
            "documentos": {
                "aparece_apos": "pi",
                "titulo": "Documentos",
                "itens": documentos,
            },
            "assistente": {
                "ativo": False,
                "aparece_apos": "no_ar",
                "titulo": "Pergunte sobre a campanha",
                "descricao": "Assistente com acesso aos dados da campanha. Em breve.",
            },
        },
    }


# Fases simuladas na prévia da operação (?fases=1&fase=N)
DEMO_FASES = (
    {"rotulo": "Dados atuais"},
    {"rotulo": "1 · PI aprovado", "concluidos": 1},
    {"rotulo": "2 · Dashboard", "concluidos": 4},
    {"rotulo": "3 · No ar", "concluidos": 5},
    {"rotulo": "4 · Prestação de contas", "concluidos": 7},
    {"rotulo": "5 · Faturado", "concluidos": 8},
)


def simular_fase(payload, indice):
    """Copia do payload com os N primeiros marcos concluídos (só para a prévia)."""
    import copy

    try:
        fase = DEMO_FASES[int(indice)]
    except (TypeError, ValueError, IndexError):
        return payload
    if "concluidos" not in fase:
        return payload
    out = copy.deepcopy(payload)
    for i, marco in enumerate(out["marcos"]):
        marco["realizado"] = (marco["realizado"] or marco["previsto"]) if i < fase["concluidos"] else ""
    return out


def contexto_pagina(payload, hoje=None):
    """Estado derivado (marco atual, progresso, liberação das páginas)."""
    hoje = hoje or date.today()
    marcos = payload["marcos"]
    feitos = {m["id"] for m in marcos if m["realizado"]}
    atual_idx = next((i for i, m in enumerate(marcos) if not m["realizado"]), -1)
    for i, m in enumerate(marcos):
        prev = _as_date(m["previsto"])
        m["atrasado"] = bool(not m["realizado"] and prev and prev < hoje)
        m["estado"] = "done" if m["realizado"] else "current" if i == atual_idx else "todo"
    modulos = payload["modulos"]

    def liberado(chave):
        mod = modulos.get(chave) or {}
        return mod.get("aparece_apos") in feitos

    tem_dash = any(r["dash_embed"] or r["dash_abrir"] for r in payload.get("resultados") or [])
    titulo = {m["id"]: m["titulo"] for m in marcos}
    paginas = [
        {"id": "geral", "rotulo": "Visão geral", "ok": True},
        {"id": "resultados", "rotulo": "Resultados", "ok": liberado("combinados")},
        {"id": "dashboard", "rotulo": "Dashboard", "ok": tem_dash or liberado("dashboard")},
        {"id": "combinados", "rotulo": "Combinados", "ok": liberado("combinados")},
        {"id": "documentos", "rotulo": "Documentos", "ok": True},
        {"id": "contato", "rotulo": "Fale com a gente", "ok": True},
    ]
    bloqueio = {"resultados": titulo.get("pi"), "combinados": titulo.get("pi"), "dashboard": titulo.get("dashboard")}
    for p in paginas:
        p["bloqueio"] = bloqueio.get(p["id"], "")
    atual = marcos[atual_idx] if atual_idx >= 0 else None
    return {
        "feitos": feitos,
        "atual": atual,
        "proximos": marcos[atual_idx:atual_idx + 3] if atual_idx >= 0 else [],
        "pct": round(len(feitos) / len(marcos) * 100) if marcos else 0,
        "n_feitos": len(feitos),
        "n_marcos": len(marcos),
        "paginas": paginas,
        "relatorios_liberados": [
            r for r in modulos["relatorios"]["itens"] if not r.get("marco") or r["marco"] in feitos
        ],
    }


def _slug_palavras(value, limite=44):
    import unicodedata

    raw = unicodedata.normalize("NFKD", str(value or "").lower())
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    out = ""
    for palavra in (w for w in re.split(r"[^a-z0-9]+", raw) if w):
        candidato = f"{out}-{palavra}" if out else palavra
        if len(candidato) > limite:
            break
        out = candidato
    return out


def token_amigavel(cliente, campanha):
    """Link como o do Smart Planner: ``cliente-nome-da-campanha-k7m2qx``."""
    import secrets

    alfabeto = "abcdefghijkmnpqrstuvwxyz23456789"
    base = _slug_palavras(f"{cliente or ''} {campanha or ''}") or "campanha"
    return f"{base}-{''.join(secrets.choice(alfabeto) for _ in range(6))}"
