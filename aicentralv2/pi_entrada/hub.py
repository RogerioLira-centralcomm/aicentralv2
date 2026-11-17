"""O que o hub de mídia mostra do PI ao cliente ou à agência que o enviou: uma leitura **simples**.

O cliente vê o suficiente para confirmar que o hub entendeu o documento (qual PI, de quem, quando, em quais
plataformas e praças) e segue para o executivo, que confere tudo no CentralX. Nada de comissão, líquido,
CNPJ, endereço, contatos, centro de custos ou regras de faturamento: esses dados só existem na visão completa.
Vale uma lista **permitida**: o que não está aqui não sai, mesmo que o modelo passe a ler mais campos.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import normalizar as n

MAX_PLATAFORMAS = 6
MAX_PRACAS = 6
MAX_LINHAS = 8


def _unicos(valores, limite):
    vistos, saida = set(), []
    for v in valores:
        t = n.limpo(v)
        chave = n.sem_acento(t).lower()
        if t and chave not in vistos:
            vistos.add(chave)
            saida.append(t)
    return saida[:limite], max(0, len({n.sem_acento(n.limpo(v)).lower() for v in valores if n.limpo(v)}) - limite)


def resumo_para_cliente(pi: dict) -> dict:
    """Resumo permitido ao cliente. ``total_bruto`` só aparece se o próprio documento traz o valor."""
    pi = pi or {}
    linhas = pi.get("linhas") or []
    plataformas, mais_plat = _unicos([l.get("plataforma") or l.get("meio") for l in linhas], MAX_PLATAFORMAS)
    pracas, mais_pracas = _unicos([l.get("praca") for l in linhas], MAX_PRACAS)
    formatos, _ = _unicos([l.get("formato") for l in linhas], 4)
    bruto = n.dinheiro((pi.get("totais") or {}).get("bruto"))
    cliente, agencia = pi.get("cliente") or {}, pi.get("agencia") or {}
    return {
        "numero_pi": n.limpo(pi.get("numero_pi")),
        "cliente": n.limpo(cliente.get("razao_social") or cliente.get("nome")),
        "agencia": n.limpo(agencia.get("razao_social") or agencia.get("nome")),
        "campanha": n.limpo(pi.get("campanha")) or n.limpo((linhas[0] if linhas else {}).get("campanha")),
        "produto": n.limpo(pi.get("produto")),
        "periodo": n.limpo(pi.get("periodo_texto")),
        "total_bruto": n.formatar_brl(bruto) if bruto is not None else "",
        "plataformas": plataformas, "plataformas_mais": mais_plat,
        "pracas": pracas, "pracas_mais": mais_pracas,
        "formatos": formatos,
        "n_linhas": len(linhas),
        "linhas": [{"plataforma": n.limpo(l.get("plataforma") or l.get("meio")), "praca": n.limpo(l.get("praca")),
                    "formato": n.limpo(l.get("formato"))} for l in linhas[:MAX_LINHAS]],
        "linhas_mais": max(0, len(linhas) - MAX_LINHAS),
    }


CAMPOS_PERMITIDOS = frozenset(resumo_para_cliente({}).keys())


def linha_pre_pi(entrada: dict) -> dict:
    """Pré-PI como linha da lista de PIs do hub (etapa "Pré-aprovação"), só com o que o resumo permitido mostra."""
    r = resumo_para_cliente(entrada.get("json_revisado") or {})
    return {"uuid": entrada.get("uuid"), "pi": r["numero_pi"] or entrada.get("numero_pi") or "—", "titulo": r["campanha"] or entrada.get("titulo") or "",
            "agencia": r["agencia"], "plataformas": r["plataformas"], "periodo": r["periodo"], "bruto": r["total_bruto"],
            "origem": entrada.get("origem") or "hub", "status": entrada.get("status")}


def situacao(entrada: dict) -> str:
    """Estado que o cliente enxerga: lendo, erro, pronto (lido, ainda não enviado), enviado ou em_verificacao (cadastrado pela equipe)."""
    if (entrada.get("origem") or "hub") != "hub":
        return "em_verificacao"
    if entrada.get("enviado_em"):
        return "enviado"
    status = entrada.get("status")
    if status in ("recebido", "lendo"):
        quando = entrada.get("atualizado_em")
        if isinstance(quando, datetime):
            if quando.tzinfo is None:
                quando = quando.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - quando > timedelta(minutes=5):
                return "erro"                      # o servidor reiniciou no meio da leitura: não fica "lendo" para sempre
        return "lendo"
    if status == "erro":
        return "erro"
    return "pronto"
