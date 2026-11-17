"""Comparação PI lido × cotação: sugestão da cotação certa e linhas-chave para a página de verificação.

A página mostra poucas linhas (12 a 15), duas colunas: o que o PI diz e o que a cotação diz. Cada linha tem um
status: ``igual``, ``proximo`` (dentro da tolerância de arredondamento), ``diferente``, ``so_pi``, ``so_cotacao``
ou ``sem_leitura``. Tudo aqui é puro: o banco entra só em ``repositorio.py``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from . import normalizar as n

TOLERANCIA_VALOR = Decimal("0.005")      # 0,5%: arredondamento de CPM, CPC e volume
TOLERANCIA_NOME = 0.82                   # semelhança mínima para considerar o mesmo nome de campanha


def _d(valor):
    try:
        return Decimal(str(valor)) if valor not in (None, "") else None
    except Exception:
        return None


def _data(valor):
    if isinstance(valor, date):
        return valor
    return n.data_br(valor)


def _fmt_data(valor) -> str:
    d = _data(valor)
    return d.strftime("%d/%m/%Y") if d else ""


# ---------- linhas de comparação ----------

def _linha(chave, rotulo, valor_pi, valor_cot, status, nota=""):
    return {"chave": chave, "rotulo": rotulo, "pi": valor_pi, "cotacao": valor_cot, "status": status, "nota": nota}


def _comparar_texto(chave, rotulo, pi, cot, minimo=TOLERANCIA_NOME):
    pi, cot = n.limpo(pi), n.limpo(cot)
    if not pi and not cot:
        return None
    if not pi:
        return _linha(chave, rotulo, "", cot, "so_cotacao")
    if not cot:
        return _linha(chave, rotulo, pi, "", "so_pi")
    razao = n.parecidos(pi, cot)
    if razao >= 0.97:
        return _linha(chave, rotulo, pi, cot, "igual")
    return _linha(chave, rotulo, pi, cot, "proximo" if razao >= minimo else "diferente",
                  f"semelhança de {int(razao * 100)}%" if razao >= minimo else "")


def _comparar_valor(chave, rotulo, pi, cot, formatador, tolerancia=TOLERANCIA_VALOR):
    a, b = _d(pi), _d(cot)
    if a is None and b is None:
        return None
    if a is None:
        return _linha(chave, rotulo, "", formatador(b), "so_cotacao")
    if b is None:
        return _linha(chave, rotulo, formatador(a), "", "so_pi")
    if a == b:
        return _linha(chave, rotulo, formatador(a), formatador(b), "igual")
    diferenca = abs(a - b)
    relativo = diferenca / abs(b) if b else Decimal("1")
    status = "proximo" if relativo <= tolerancia else "diferente"
    nota = f"diferença de {formatador(diferenca)} ({relativo * 100:.2f}%)".replace(".", ",")
    return _linha(chave, rotulo, formatador(a), formatador(b), status, nota)


def _conjunto(valores) -> list[str]:
    vistos, saida = set(), []
    for v in valores:
        t = n.limpo(v)
        if t and n.sem_acento(t).lower() not in vistos:
            vistos.add(n.sem_acento(t).lower())
            saida.append(t)
    return saida


def _comparar_conjunto(chave, rotulo, pi_valores, cot_valores):
    pi_l, cot_l = _conjunto(pi_valores), _conjunto(cot_valores)
    if not pi_l and not cot_l:
        return None
    if not pi_l or not cot_l:
        return _linha(chave, rotulo, ", ".join(pi_l), ", ".join(cot_l), "so_pi" if pi_l else "so_cotacao")
    chaves_pi = {n.sem_acento(x).lower() for x in pi_l}
    chaves_cot = {n.sem_acento(x).lower() for x in cot_l}
    cruzam = any(n.parecidos(a, b) >= 0.8 for a in chaves_pi for b in chaves_cot)
    if chaves_pi == chaves_cot:
        status = "igual"
    else:
        status = "proximo" if cruzam else "diferente"
    return _linha(chave, rotulo, ", ".join(pi_l), ", ".join(cot_l), status)


def totais_da_cotacao(cotacao: dict) -> dict:
    """Soma das linhas da cotação: bruto, líquido, volume e preço médio ponderado."""
    linhas = [l for l in (cotacao.get("linhas") or []) if not l.get("is_subtotal") and not l.get("is_header")]
    bruto = sum((_d(l.get("investimento_bruto") if l.get("investimento_bruto") is not None else l.get("valor_total")) or Decimal("0")) for l in linhas)
    liquido = sum((_d(l.get("investimento_liquido")) or Decimal("0")) for l in linhas)
    volume = sum((_d(l.get("volume_contratado")) or Decimal("0")) for l in linhas)
    precos = {str(_d(l.get("valor_unitario_negociado") if l.get("valor_unitario_negociado") is not None else l.get("valor_unitario"))) for l in linhas}
    precos.discard("None")
    return {"bruto": bruto or None, "liquido": liquido or None, "volume": volume or None,
            "preco": Decimal(next(iter(precos))) if len(precos) == 1 else None, "linhas": linhas}


def comparar(pi: dict, cotacao: dict | None) -> list[dict]:
    """Linhas-chave da página de verificação. Sem cotação, a coluna da cotação fica vazia (status ``sem_cotacao``)."""
    tot = pi.get("totais") or {}
    linhas_pi = pi.get("linhas") or []
    cot = cotacao or {}
    tc = totais_da_cotacao(cot) if cotacao else {"bruto": None, "liquido": None, "volume": None, "preco": None, "linhas": []}
    linhas_cot = tc["linhas"]

    def so_pi(chave, rotulo, valor):
        return _linha(chave, rotulo, valor, "", "sem_cotacao") if n.limpo(valor) else None

    saida = [
        _comparar_texto("campanha", "Campanha", pi.get("campanha") or (linhas_pi[0].get("campanha") if linhas_pi else ""), cot.get("nome_campanha")) if cotacao
        else so_pi("campanha", "Campanha", pi.get("campanha") or (linhas_pi[0].get("campanha") if linhas_pi else "")),
    ]
    ini_pi, fim_pi = pi.get("periodo_inicio"), pi.get("periodo_fim")
    if cotacao:
        for chave, rotulo, a, b in (("periodo_inicio", "Início", ini_pi, cot.get("periodo_inicio")),
                                    ("periodo_fim", "Fim", fim_pi, cot.get("periodo_fim"))):
            if not a and not b:
                continue
            ig = _data(a) == _data(b) and _data(a) is not None
            saida.append(_linha(chave, rotulo, _fmt_data(a), _fmt_data(b),
                                "igual" if ig else ("so_cotacao" if not a else ("so_pi" if not b else "diferente"))))
    else:
        saida += [so_pi("periodo_inicio", "Início", _fmt_data(ini_pi)), so_pi("periodo_fim", "Fim", _fmt_data(fim_pi))]

    plataformas_pi = [l.get("plataforma") or l.get("meio") for l in linhas_pi]
    formatos_pi = [l.get("formato") for l in linhas_pi]
    modelos_pi = [l.get("modelo_compra") for l in linhas_pi]
    pracas_pi = [l.get("praca") for l in linhas_pi]
    if cotacao:
        saida += [
            _comparar_conjunto("plataforma", "Plataforma", plataformas_pi, [l.get("plataforma") for l in linhas_cot] or [cot.get("plataforma_campanha")]),
            _comparar_conjunto("formato", "Formato", formatos_pi, [l.get("formatos") or l.get("formato") for l in linhas_cot]),
            _comparar_conjunto("modelo_compra", "Modelo de compra", modelos_pi, [l.get("objetivo_kpi") or l.get("formato_compra") for l in linhas_cot]),
            _comparar_conjunto("praca", "Praça", pracas_pi, [l.get("praca") for l in linhas_cot]),
            _comparar_valor("entrega", "Entrega contratada", sum((l.get("entrega") or 0) for l in linhas_pi) or None, tc["volume"], n.formatar_int),
            _comparar_valor("preco", "Preço unitário",
                            next(iter({l.get("preco_unitario") for l in linhas_pi if l.get("preco_unitario")}), None) if len({l.get("preco_unitario") for l in linhas_pi if l.get("preco_unitario")}) == 1 else None,
                            tc["preco"], n.formatar_brl, tolerancia=Decimal("0.01")),
            _comparar_valor("bruto", "Valor bruto", tot.get("bruto"), tc["bruto"] if tc["bruto"] is not None else cot.get("valor_total_proposta"), n.formatar_brl),
            _comparar_valor("liquido", "Valor líquido", tot.get("liquido"), tc["liquido"], n.formatar_brl),
        ]
    else:
        saida += [
            so_pi("plataforma", "Plataforma", ", ".join(_conjunto(plataformas_pi))),
            so_pi("formato", "Formato", ", ".join(_conjunto(formatos_pi))),
            so_pi("modelo_compra", "Modelo de compra", ", ".join(_conjunto(modelos_pi))),
            so_pi("praca", "Praça", ", ".join(_conjunto(pracas_pi))),
            so_pi("entrega", "Entrega contratada", n.formatar_int(sum((l.get("entrega") or 0) for l in linhas_pi)) if linhas_pi else ""),
            so_pi("bruto", "Valor bruto", n.formatar_brl(tot.get("bruto"))),
            so_pi("liquido", "Valor líquido", n.formatar_brl(tot.get("liquido"))),
        ]
    return [l for l in saida if l]


def resumo(linhas: list[dict]) -> dict:
    contagem = {"igual": 0, "proximo": 0, "diferente": 0, "so_pi": 0, "so_cotacao": 0, "sem_cotacao": 0}
    for l in linhas:
        contagem[l["status"]] = contagem.get(l["status"], 0) + 1
    comparaveis = sum(contagem[k] for k in ("igual", "proximo", "diferente", "so_pi", "so_cotacao"))
    return {**contagem, "comparaveis": comparaveis, "conferem": contagem["igual"] + contagem["proximo"]}


# ---------- sugestão da cotação ----------

def pontuar(pi: dict, cotacao: dict) -> float:
    """Pontuação de 0 a 1 de uma cotação para este PI: período, valor e nome. Aprovadas ganham um pequeno bônus."""
    pontos, pesos = 0.0, 0.0
    tot = _d((pi.get("totais") or {}).get("bruto"))
    valor = _d(cotacao.get("valor_total_proposta")) or _d(cotacao.get("budget_estimado"))
    if tot and valor:
        pesos += 0.4
        pontos += 0.4 * max(0.0, 1 - float(abs(tot - valor) / max(tot, valor)) * 4)
    ini_pi, fim_pi = _data(pi.get("periodo_inicio")), _data(pi.get("periodo_fim"))
    ini_c, fim_c = _data(cotacao.get("periodo_inicio")), _data(cotacao.get("periodo_fim"))
    if ini_pi and fim_pi and ini_c and fim_c:
        pesos += 0.35
        sobreposicao = (min(fim_pi, fim_c) - max(ini_pi, ini_c)).days + 1
        total = max((fim_pi - ini_pi).days + 1, (fim_c - ini_c).days + 1)
        pontos += 0.35 * max(0.0, min(1.0, sobreposicao / total))
    nome_pi = pi.get("campanha") or (pi.get("linhas") or [{}])[0].get("campanha")
    if nome_pi and cotacao.get("nome_campanha"):
        pesos += 0.25
        pontos += 0.25 * n.parecidos(nome_pi, cotacao["nome_campanha"])
    base = pontos / pesos if pesos else 0.0
    return round(min(1.0, base + (0.02 if str(cotacao.get("status", "")).lower().startswith("aprov") else 0.0)), 3)


def sugerir(pi: dict, cotacoes: list[dict], limite: int = 5) -> list[dict]:
    pontuadas = [{**c, "pontuacao": pontuar(pi, c)} for c in cotacoes]
    return sorted(pontuadas, key=lambda c: c["pontuacao"], reverse=True)[:limite]
