"""Monta o que a página de verificação mostra (e valida o que ela envia). Sem Flask: testável sem banco.

A página compara o PI lido com a cotação escolhida, lista as conferências e as oportunidades de cadastro e diz o que
ainda exige justificativa antes de seguir. Toda divergência (``diferente`` na comparação, ``erro`` nas conferências)
precisa de um ajuste ou de um aceite com motivo e texto: nada segue "no escuro".
"""

from __future__ import annotations

import copy
import re

from . import conferencias, cotacao as cmp, normalizar as n, oportunidades as oport

MOTIVOS = (
    ("erro_de_leitura", "Erro de leitura (a leitura trocou o valor)"),
    ("erro_do_pi", "Erro no próprio PI"),
    ("combinado_com_cliente", "Combinado com o cliente ou a agência"),
    ("diferente_da_cotacao", "Diferente da cotação aprovada, e está certo"),
    ("arredondamento", "Arredondamento"),
    ("outro", "Outro motivo"),
)
MOTIVOS_VALIDOS = {m[0] for m in MOTIVOS}

_DINHEIRO = {"totais.bruto", "totais.comissao", "totais.liquido"}
_DATAS = {"data_emissao", "periodo_inicio", "periodo_fim"}
_TEXTOS = {"numero_pi", "campanha", "projeto", "plano", "planilha", "produto"}
_PARTES = {"nome", "razao_social", "cnpj", "endereco", "cep", "municipio", "uf", "inscricao_estadual", "inscricao_municipal", "telefone", "email", "contato"}
_LINHA = {"praca", "plataforma", "meio", "formato", "modelo_compra", "preco_unitario", "entrega", "valor_bruto", "target", "estrategia", "objetivo"}
_LINHA_RE = re.compile(r"^linhas\.(\d+)\.([a-z_]+)$")


class EdicaoInvalida(ValueError):
    """Campo desconhecido ou valor que não dá para entender (a mensagem vai para o usuário)."""


def _tipo_do_campo(caminho: str):
    if caminho in _DINHEIRO:
        return "dinheiro"
    if caminho == "totais.comissao_perc":
        return "percentual"
    if caminho in _DATAS:
        return "data"
    if caminho in _TEXTOS:
        return "texto"
    partes = caminho.split(".")
    if len(partes) == 2 and partes[0] in ("cliente", "agencia", "veiculo") and partes[1] in _PARTES:
        return "texto"
    achou = _LINHA_RE.match(caminho)
    if achou and achou.group(2) in _LINHA:
        return {"preco_unitario": "dinheiro", "valor_bruto": "dinheiro", "entrega": "inteiro"}.get(achou.group(2), "texto")
    return None


def ler_valor(pi: dict, caminho: str):
    atual = pi
    for parte in caminho.split("."):
        if isinstance(atual, list):
            atual = atual[int(parte) - 1] if parte.isdigit() and 0 < int(parte) <= len(atual) else None
        elif isinstance(atual, dict):
            atual = atual.get(parte)
        else:
            return None
    return atual


def definir_valor(pi: dict, caminho: str, bruto):
    """Aplica uma edição no PI (cópia profunda). Devolve (pi_novo, valor_antigo, valor_novo). Levanta EdicaoInvalida."""
    tipo = _tipo_do_campo(caminho)
    if tipo is None:
        raise EdicaoInvalida(f"Campo não editável: {caminho}")
    texto = n.limpo(bruto)
    if tipo == "dinheiro":
        v = n.dinheiro(texto) if texto else None
        if texto and v is None:
            raise EdicaoInvalida("Valor em reais inválido.")
        novo = str(v) if v is not None else ""
    elif tipo == "percentual":
        v = n.percentual(texto) if texto else None
        if texto and v is None:
            raise EdicaoInvalida("Percentual inválido.")
        novo = str(v) if v is not None else ""
    elif tipo == "inteiro":
        v = n.inteiro_br(texto) if texto else None
        if texto and v is None:
            raise EdicaoInvalida("Número inválido.")
        novo = v
    elif tipo == "data":
        d = n.data_br(texto) if texto else None
        if texto and d is None:
            raise EdicaoInvalida("Data inválida.")
        novo = d.isoformat() if d else ""
    else:
        novo = n.cnpj_formatado(texto) if caminho.endswith(".cnpj") else texto
    copia = copy.deepcopy(pi)
    antigo = ler_valor(copia, caminho)
    partes = caminho.split(".")
    alvo = copia
    for parte in partes[:-1]:
        if isinstance(alvo, list):
            indice = int(parte) - 1
            if not 0 <= indice < len(alvo):
                raise EdicaoInvalida("Linha inexistente.")
            alvo = alvo[indice]
        else:
            alvo = alvo.setdefault(parte, {})
    if isinstance(alvo, list):
        raise EdicaoInvalida("Caminho inválido.")
    alvo[partes[-1]] = novo
    return copia, antigo, novo


def montar(entrada: dict, *, ctx: dict, cotacao: dict | None, cotacoes: list[dict], ajustes: list[dict]) -> dict:
    """Tudo que o template precisa. ``ctx`` é ``cadastro.contexto``; ``cotacao`` a escolhida; ``ajustes`` o último de cada campo."""
    pi = entrada.get("json_revisado") or {}
    extraido = entrada.get("json_extraido") or {}
    bruto = extraido.get("bruto") or {}
    conf_ctx = {"cliente_id": ctx.get("cliente_id"), "agencia_id": ctx.get("agencia_id"), "pi_existente": ctx.get("pi_existente"),
                "texto_divergente": bruto.get("texto_divergente") or [], "texto_conferido": bool(bruto.get("texto_conferido"))}
    itens = conferencias.conferir(pi, conf_ctx)
    comparacao = cmp.comparar(pi, cotacao)
    ops = oport.oportunidades(pi, ctx.get("cliente"), ctx.get("agencia"), ctx.get("emails"), ctx.get("observacoes"))
    por_campo = {a["campo"]: a for a in ajustes}

    exigem = []
    for linha in comparacao:
        if linha["status"] == "diferente":
            exigem.append({"campo": f"cmp:{linha['chave']}", "titulo": linha["rotulo"], "detalhe": f"PI {linha['pi']} × cotação {linha['cotacao']}"})
    for item in itens:
        if item["status"] == "erro":
            exigem.append({"campo": f"conf:{item['id']}", "titulo": item["titulo"], "detalhe": item["detalhe"]})
    for e in exigem:
        a = por_campo.get(e["campo"])
        e["justificado"] = bool(a and n.limpo(a.get("justificativa")) and a.get("motivo") in MOTIVOS_VALIDOS
                                # o aceite vale para os números que foram aceitos: se mudaram, justifica de novo
                                and (a.get("tipo") != "aceite" or n.limpo(a.get("valor_lido")) == n.limpo(e["detalhe"])))
        e["ajuste"] = a
    pendentes = [e for e in exigem if not e["justificado"]]
    return {
        "pi": pi, "cotacao": cotacao, "comparacao": comparacao, "comparacao_resumo": cmp.resumo(comparacao),
        "conferencias": itens, "conferencias_resumo": conferencias.resumo(itens), "oportunidades": ops, "oportunidades_resumo": oport.resumo(ops),
        "cotacoes": cmp.sugerir(pi, cotacoes) if cotacoes else [], "exigem": exigem, "pendentes": pendentes,
        "pode_preparar": entrada.get("status") in ("lido", "aprovado", "rascunho") and not pendentes,
        "ajustes": por_campo, "motivos": MOTIVOS, "contexto": {"cliente": ctx.get("cliente"), "agencia": ctx.get("agencia")},
    }


def validar_justificativa(campo: str, tipo: str, motivo: str, texto: str, referencia: str = "") -> None:
    if tipo not in ("ajuste", "aceite"):
        raise EdicaoInvalida("Tipo de registro inválido.")
    if tipo == "aceite" and not n.limpo(referencia):
        raise EdicaoInvalida("Faltou a referência do que está sendo aceito.")
    if motivo not in MOTIVOS_VALIDOS:
        raise EdicaoInvalida("Escolha o motivo.")
    if len(n.limpo(texto)) < 5:
        raise EdicaoInvalida("Escreva a justificativa (pelo menos uma frase curta).")
    if not (campo.startswith(("cmp:", "conf:")) or _tipo_do_campo(campo)):
        raise EdicaoInvalida(f"Campo desconhecido: {campo}")
