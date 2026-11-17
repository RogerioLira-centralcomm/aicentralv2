"""Oportunidades de cadastro: o que o PI traz e o cadastro do CentralX não tem, ou tem diferente.

Cada PI que chega é uma chance de deixar o cadastro mais completo. Esta primeira versão só **sinaliza**:
cada oportunidade aponta o cadastro certo para o executivo atualizar. Nada é escrito em ``tbl_cliente``.
Tudo aqui é puro; as linhas do cadastro entram já lidas (ver ``repositorio.cliente_por_cnpj``).
"""

from __future__ import annotations

import re

from . import normalizar as n

# (campo no PI, coluna no cadastro, rótulo, como comparar)
CAMPOS = (
    ("razao_social", "razao_social", "Razão social", "nome"),
    ("endereco", "endereco", "Endereço", "endereco"),
    ("cep", "cep", "CEP", "digitos"),
    ("municipio", "cidade", "Município", "texto"),
    ("uf", "estado", "UF", "texto"),
    ("inscricao_estadual", "inscricao_estadual", "Inscrição estadual", "inscricao"),
    ("inscricao_municipal", "inscricao_municipal", "Inscrição municipal", "inscricao"),
    ("telefone", "telefone", "Telefone", "preencher"),
    ("email", "email", "E-mail", "preencher"),
)

_RUIDO = re.compile(r"\b(S\.?\s?A\.?|LTDA\.?|EIRELI|ME|EPP|CIA|COMPANHIA)\b", re.I)


def _normal(texto) -> str:
    base = n.sem_acento(n.limpo(texto)).upper()
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", _RUIDO.sub(" ", base)).split())


def _endereco_cadastro(linha: dict) -> str:
    if n.limpo(linha.get("endereco")):
        return n.limpo(linha["endereco"])
    return " ".join(n.limpo(linha.get(k)) for k in ("logradouro", "numero", "complemento", "bairro") if n.limpo(linha.get(k)))


def _igual(modo: str, pi_valor: str, cad_valor: str) -> bool:
    if modo == "digitos":
        return n.cnpj_digitos(pi_valor) == n.cnpj_digitos(cad_valor)
    if modo == "inscricao":
        a, b = _normal(pi_valor), _normal(cad_valor)
        da, db = n.cnpj_digitos(pi_valor), n.cnpj_digitos(cad_valor)
        return a == b or (bool(da) and da == db) or (a.startswith("ISEN") and b.startswith("ISEN"))
    if modo == "nome":
        a, b = _normal(pi_valor), _normal(cad_valor)
        # O PI costuma truncar a razão social ("... ECONOMIA E CREDIT"): prefixo conta como igual.
        return a == b or (len(a) >= 12 and (b.startswith(a) or a.startswith(b))) or n.parecidos(a, b) >= 0.92
    if modo == "endereco":
        return n.parecidos(_normal(pi_valor), _normal(cad_valor)) >= 0.72
    return _normal(pi_valor) == _normal(cad_valor)


def _novo(entidade: str, parte: dict) -> dict:
    rotulos = {"razao_social": "Razão social", "cnpj": "CNPJ", "endereco": "Endereço", "cep": "CEP", "municipio": "Município",
               "uf": "UF", "inscricao_estadual": "Inscrição estadual", "inscricao_municipal": "Inscrição municipal"}
    dados = [{"campo": c, "rotulo": r, "valor_pi": n.limpo(parte.get(c))} for c, r in rotulos.items() if n.limpo(parte.get(c))]
    nome = n.limpo(parte.get("razao_social") or parte.get("nome"))
    return {"tipo": "novo", "entidade": entidade, "campo": "cadastro", "rotulo": f"{'Cliente' if entidade == 'cliente' else 'Agência'} não cadastrado(a)",
            "valor_pi": nome, "valor_cadastro": "", "dados": dados,
            "sugestao": f"Cadastrar {nome or 'o ' + entidade} com os dados do PI."}


def oportunidades(pi: dict, cliente: dict | None, agencia: dict | None, contatos_emails: dict | None = None,
                  observacoes: dict | None = None) -> list[dict]:
    """Lista de oportunidades. ``cliente``/``agencia`` são linhas de ``tbl_cliente`` (ou None se não achou o CNPJ);
    ``contatos_emails`` = {"cliente": {...e-mails...}, "agencia": {...}}; ``observacoes`` = texto comercial de cada um."""
    saida: list[dict] = []
    contatos_emails = contatos_emails or {}
    observacoes = observacoes or {}
    for entidade, linha in (("cliente", cliente), ("agencia", agencia)):
        parte = pi.get(entidade) or {}
        tem_dado = any(n.limpo(parte.get(k)) for k in ("cnpj", "razao_social", "nome"))
        if not tem_dado:
            continue
        if linha is None:
            saida.append(_novo(entidade, parte))
            continue
        for campo_pi, coluna, rotulo, modo in CAMPOS:
            valor_pi = n.limpo(parte.get(campo_pi))
            if not valor_pi:
                continue
            valor_cad = _endereco_cadastro(linha) if campo_pi == "endereco" else n.limpo(linha.get(coluna))
            base = {"entidade": entidade, "campo": campo_pi, "rotulo": rotulo, "valor_pi": valor_pi, "valor_cadastro": valor_cad,
                    "id_cliente": linha.get("id_cliente")}
            if not valor_cad:
                saida.append({**base, "tipo": "preencher", "sugestao": f"{rotulo} está vazio no cadastro; o PI traz {valor_pi}."})
            elif modo != "preencher" and not _igual(modo, valor_pi, valor_cad):
                saida.append({**base, "tipo": "revisar", "sugestao": f"{rotulo} difere do cadastro: revisar e, se o PI estiver certo, atualizar."})
        # contatos: e-mails de faturamento citados no PI que o cadastro não tem
        conhecidos = {e.lower() for e in contatos_emails.get(entidade, set())}
        if entidade == "cliente":
            for email in (pi.get("pagamento") or {}).get("emails_faturamento") or []:
                if email.lower() not in conhecidos:
                    saida.append({"tipo": "contato", "entidade": entidade, "campo": "contato", "rotulo": "Contato de faturamento",
                                  "valor_pi": email, "valor_cadastro": "", "id_cliente": linha.get("id_cliente"),
                                  "sugestao": "E-mail de faturamento do PI que não está nos contatos do cliente."})
    # regras de faturamento da conta: guardar na ficha para as próximas entradas
    pag = pi.get("pagamento") or {}
    regras = [x for x in (pag.get("prazo"), pag.get("centro_custos"), pag.get("retencoes")) if n.limpo(x)] + list(pag.get("regras") or [])
    if regras and cliente is not None:
        ficha = (observacoes.get("cliente") or "").lower()
        faltando = [r for r in regras[:3] if n.limpo(r).lower()[:40] not in ficha]
        if faltando:
            saida.append({"tipo": "regras", "entidade": "cliente", "campo": "regras", "rotulo": "Regras de faturamento do PI",
                          "valor_pi": "; ".join(n.limpo(r) for r in faltando[:3]), "valor_cadastro": "", "id_cliente": cliente.get("id_cliente"),
                          "sugestao": "Guardar prazo, retenções e centro de custos na ficha do cliente para as próximas entradas."})
    ordem = {"novo": 0, "revisar": 1, "preencher": 2, "contato": 3, "regras": 4}
    return sorted(saida, key=lambda o: (ordem.get(o["tipo"], 9), o["entidade"] != "cliente"))


def resumo(itens: list[dict]) -> dict:
    contagem = {"novo": 0, "revisar": 0, "preencher": 0, "contato": 0, "regras": 0}
    for i in itens:
        contagem[i["tipo"]] = contagem.get(i["tipo"], 0) + 1
    return {**contagem, "total": len(itens)}
