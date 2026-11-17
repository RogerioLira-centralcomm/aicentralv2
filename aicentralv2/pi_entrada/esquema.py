"""Esquema de extração do PI, prompt e normalização da resposta do modelo.

A leitura é por **significado**, não por posição: cada agência desenha o PI de um jeito (rótulos como
"PI Nº" e "PIT Nº", "Contato" e "Responsável"). O modelo devolve JSON; aqui ele vira um dicionário
tipado e estável, que o resto da Entrada de PI usa (conferências, comparação com a cotação, rascunho).
"""

from __future__ import annotations

import json
import re
from decimal import Decimal

from . import normalizar as n

PROMPT_VERSAO = "pi-2026-11-17.1"

PROMPT_SISTEMA = """Você lê Pedidos de Inserção (PI) de agências de publicidade do Brasil. O veículo é a Centralcomm \
(CENTRALCOMM-PUBLICIDADE ONLINE LTDA). Responda SOMENTE com um objeto JSON, sem texto antes ou depois.

Regras:
- Leia por significado. Os rótulos mudam de uma agência para outra ("PI Nº", "PIT Nº", "Contato", "Responsável").
- Copie os valores exatamente como estão escritos (dinheiro como "R$ 10.000,00", datas como "28/10/2026"). Não calcule, não corrija, não complete.
- Campo que não existe no documento: null. Nunca invente.
- O cabeçalho (agência, cliente, veículo) repete em toda página: use uma vez. Ignore o calendário de dias (D S T Q Q S S) e as colunas vazias.
- O conteúdo de uma campanha continua de uma página para a outra ("veja página seguinte"): junte tudo antes de listar.
- Cada campo escalar vem como {"valor": ..., "confianca": 0 a 1, "pagina": número da página}. Listas de linhas usam valores simples e "pagina".
- "agencia" é quem emitiu o PI (o logotipo no topo). "cliente" é o anunciante. "veiculo" é a Centralcomm.
- "linhas" tem uma entrada por segmentação ou item de mídia, com praça, público, preço unitário, entrega contratada e valor bruto.
- "pagamento.regras" é uma lista de frases curtas (uma regra por item) tiradas das páginas de observações e faturamento.
- "valor_extenso" é o valor escrito por extenso que aparece ao lado do valor total, se houver.
"""

ESQUEMA_EXEMPLO = {
    "documento": {
        "numero_pi": {"valor": "86761", "confianca": 0.99, "pagina": 1},
        "data_emissao": {"valor": "28/10/2026", "confianca": 0.99, "pagina": 1},
        "periodo": {"valor": "NOVEMBRO/2026", "confianca": 0.95, "pagina": 1},
        "projeto": {"valor": None, "confianca": 0, "pagina": None},
        "plano": {"valor": None, "confianca": 0, "pagina": None},
        "planilha": {"valor": None, "confianca": 0, "pagina": None},
        "produto": {"valor": None, "confianca": 0, "pagina": None},
        "campanha": {"valor": None, "confianca": 0, "pagina": None},
        "valor_extenso": {"valor": None, "confianca": 0, "pagina": None},
    },
    "agencia": {"nome": {}, "razao_social": {}, "cnpj": {}, "endereco": {}, "cep": {}, "municipio": {}, "uf": {},
                "inscricao_estadual": {}, "inscricao_municipal": {}, "telefone": {}, "email": {}, "contato": {}},
    "cliente": {"nome": {}, "razao_social": {}, "cnpj": {}, "endereco": {}, "cep": {}, "municipio": {}, "uf": {},
                "inscricao_estadual": {}, "inscricao_municipal": {}, "telefone": {}, "email": {}, "contato": {}},
    "veiculo": {"nome": {}, "razao_social": {}, "cnpj": {}},
    "linhas": [{
        "campanha": "", "meio": "", "plataforma": "", "estrategia": "", "objetivo": "", "formato": "",
        "modelo_compra": "CPM ou CPC ou outro", "praca": "", "target": "", "detalhe": "",
        "preco_unitario": "R$ 61,20", "entrega": "163.399", "unidade": "impressões ou cliques",
        "valor_bruto": "R$ 10.000,00", "periodo": "01/11 a 30/11", "pagina": 1,
    }],
    "totais": {"bruto": {}, "comissao": {}, "comissao_perc": {}, "liquido": {}},
    "pagamento": {
        "prazo": {}, "local_entrega_nf": {}, "local_cobranca": {}, "centro_custos": {}, "help_desk": {},
        "responsavel_cliente": {}, "emails_faturamento": [], "regras": [], "documentos_exigidos": [], "retencoes": {},
    },
    "observacoes": "",
}


def montar_prompt_usuario(texto_paginas: str) -> str:
    return (
        "Extraia o PI abaixo no formato JSON a seguir (mantenha exatamente estas chaves):\n"
        + json.dumps(ESQUEMA_EXEMPLO, ensure_ascii=False)
        + "\n\nTEXTO DO PI (páginas separadas por '=== PÁGINA n ==='):\n"
        + texto_paginas
    )


def extrair_json(texto: str) -> dict:
    """Pega o objeto JSON da resposta mesmo com cerca de código ou texto em volta."""
    bruto = str(texto or "").strip()
    bruto = re.sub(r"^```(?:json)?\s*|\s*```$", "", bruto, flags=re.I).strip()
    try:
        dado = json.loads(bruto)
    except ValueError:
        inicio, fim = bruto.find("{"), bruto.rfind("}")
        if inicio < 0 or fim <= inicio:
            raise ValueError("A resposta do modelo não trouxe JSON.")
        dado = json.loads(bruto[inicio:fim + 1])
    if not isinstance(dado, dict):
        raise ValueError("A resposta do modelo não é um objeto JSON.")
    return dado


# ---------- normalização ----------

def _folha(no):
    """({"valor", "confianca", "pagina"} ou valor simples) -> (valor, confiança, página)."""
    if isinstance(no, dict) and ("valor" in no or "confianca" in no):
        conf = n.decimal_br(no.get("confianca"))
        pag = n.inteiro_br(no.get("pagina"))
        return no.get("valor"), (float(conf) if conf is not None else None), pag
    if isinstance(no, dict):
        return None, None, None
    return no, None, None


def _texto(no) -> str:
    return n.limpo(_folha(no)[0])


def _iso(d) -> str:
    return d.isoformat() if d else ""


def _money(valor) -> str:
    v = n.dinheiro(valor)
    return str(v) if v is not None else ""


def normalizar_extracao(bruto: dict) -> dict:
    """JSON do modelo -> PI normalizado (valores como texto seguro para JSONB)."""
    bruto = bruto if isinstance(bruto, dict) else {}
    confianca: dict[str, float] = {}
    paginas: dict[str, int] = {}

    def pegar(grupo: str, campo: str, no, converter=n.limpo):
        valor, conf, pag = _folha(no)
        chave = f"{grupo}.{campo}" if grupo else campo
        if conf is not None:
            confianca[chave] = conf
        if pag is not None:
            paginas[chave] = pag
        return converter(valor)

    doc = bruto.get("documento") or {}
    periodo_texto = pegar("", "periodo_texto", doc.get("periodo"))
    emissao = n.data_br(pegar("", "data_emissao", doc.get("data_emissao")))
    mes = n.mes_ano(periodo_texto)
    extenso_texto = pegar("", "valor_extenso", doc.get("valor_extenso"))
    pi = {
        "numero_pi": pegar("", "numero_pi", doc.get("numero_pi")),
        "data_emissao": _iso(emissao),
        "periodo_texto": periodo_texto,
        "mes_ref": f"{mes[0]:04d}-{mes[1]:02d}" if mes else "",
        "projeto": pegar("", "projeto", doc.get("projeto")),
        "plano": pegar("", "plano", doc.get("plano")),
        "planilha": pegar("", "planilha", doc.get("planilha")),
        "produto": pegar("", "produto", doc.get("produto")),
        "campanha": pegar("", "campanha", doc.get("campanha")),
        "valor_extenso": extenso_texto,
    }
    ext = n.extenso_para_decimal(extenso_texto) if extenso_texto else None
    pi["valor_extenso_num"] = str(ext) if ext is not None else ""

    for grupo in ("agencia", "cliente", "veiculo"):
        no = bruto.get(grupo) or {}
        parte = {campo: pegar(grupo, campo, no.get(campo))
                 for campo in ("nome", "razao_social", "endereco", "municipio", "inscricao_estadual", "inscricao_municipal",
                               "telefone", "email", "contato")}
        parte["cnpj"] = pegar(grupo, "cnpj", no.get("cnpj"), lambda v: n.cnpj_formatado(v) if n.cnpj_digitos(v) else "")
        parte["cep"] = pegar(grupo, "cep", no.get("cep"), lambda v: (f"{n.cnpj_digitos(v)[:5]}-{n.cnpj_digitos(v)[5:8]}" if len(n.cnpj_digitos(v)) == 8 else n.limpo(v)))
        parte["uf"] = pegar(grupo, "uf", no.get("uf"), lambda v: n.limpo(v).upper()[:2])
        pi[grupo] = parte

    tot = bruto.get("totais") or {}
    pi["totais"] = {
        "bruto": pegar("totais", "bruto", tot.get("bruto"), _money),
        "comissao": pegar("totais", "comissao", tot.get("comissao"), _money),
        "comissao_perc": pegar("totais", "comissao_perc", tot.get("comissao_perc"),
                               lambda v: str(n.percentual(v)) if n.percentual(v) is not None else ""),
        "liquido": pegar("totais", "liquido", tot.get("liquido"), _money),
    }

    pag = bruto.get("pagamento") or {}
    pi["pagamento"] = {
        campo: pegar("pagamento", campo, pag.get(campo))
        for campo in ("prazo", "local_entrega_nf", "local_cobranca", "centro_custos", "help_desk", "responsavel_cliente", "retencoes")
    }
    for lista in ("emails_faturamento", "regras", "documentos_exigidos"):
        itens = pag.get(lista) or []
        pi["pagamento"][lista] = [n.limpo(_folha(i)[0]) for i in (itens if isinstance(itens, list) else [itens]) if n.limpo(_folha(i)[0])]

    linhas = []
    for item in bruto.get("linhas") or []:
        if not isinstance(item, dict):
            continue
        ini, fim = n.periodo_do_texto(item.get("periodo"), int(pi["mes_ref"][:4]) if pi["mes_ref"] else None)
        linha = {
            "campanha": n.limpo(item.get("campanha")), "meio": n.limpo(item.get("meio")),
            "plataforma": n.limpo(item.get("plataforma")), "estrategia": n.limpo(item.get("estrategia")),
            "objetivo": n.limpo(item.get("objetivo")), "formato": n.limpo(item.get("formato")),
            "modelo_compra": n.limpo(item.get("modelo_compra")).upper(),
            "praca": n.limpo(item.get("praca")), "target": n.limpo(item.get("target")), "detalhe": n.limpo(item.get("detalhe")),
            "preco_unitario": _money(item.get("preco_unitario")),
            "entrega": n.inteiro_br(item.get("entrega")),
            "unidade": n.limpo(item.get("unidade")).lower(),
            "valor_bruto": _money(item.get("valor_bruto")),
            "periodo_inicio": _iso(ini), "periodo_fim": _iso(fim),
            "pagina": n.inteiro_br(item.get("pagina")),
        }
        if any(linha[k] for k in ("praca", "target", "valor_bruto", "entrega", "plataforma")):
            linhas.append(linha)
    pi["linhas"] = linhas

    # Período do PI: o texto do cabeçalho dá o mês; as datas exatas vêm das linhas.
    inicios = sorted(l["periodo_inicio"] for l in linhas if l["periodo_inicio"])
    fins = sorted(l["periodo_fim"] for l in linhas if l["periodo_fim"])
    pi["periodo_inicio"] = inicios[0] if inicios else ""
    pi["periodo_fim"] = fins[-1] if fins else ""
    pi["observacoes"] = n.limpo(bruto.get("observacoes"))
    valores = list(confianca.values())
    pi["confianca"] = confianca
    pi["paginas"] = paginas
    pi["confianca_geral"] = round(sum(valores) / len(valores), 3) if valores else 0.0
    return pi


def decimal_de(texto) -> Decimal | None:
    """Valor normalizado (texto "10000.00") -> Decimal; vazio -> None."""
    try:
        return Decimal(texto) if texto not in (None, "") else None
    except Exception:
        return None
