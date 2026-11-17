"""Normalizadores da Entrada de PI: dinheiro, datas, CNPJ, porcentagens e valor por extenso.

Tudo aqui é puro (sem banco, sem rede) e tolerante: devolve ``None`` quando não entende o texto,
nunca levanta exceção por causa de um PDF mal lido.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

CENTAVO = Decimal("0.01")

_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}


def sem_acento(texto) -> str:
    base = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in base if not unicodedata.combining(c))


def limpo(texto) -> str:
    """Texto sem espaços repetidos; ``None`` e "None" viram vazio."""
    valor = re.sub(r"\s+", " ", str(texto if texto is not None else "")).strip()
    return "" if valor.lower() in ("none", "null", "nan") else valor


# ---------- dinheiro e números ----------

def decimal_br(valor) -> Decimal | None:
    """"R$ 10.000,00", "59.393,20", "8,16", 1250 ou "1.250" viram Decimal. Sem número: None."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    texto = limpo(valor).lower().replace("r$", "").replace(" ", "")
    texto = re.sub(r"[^\d.,\-]", "", texto)
    if not re.search(r"\d", texto):
        return None
    negativo = texto.startswith("-")
    texto = texto.replace("-", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):
        texto = texto.replace(".", "")          # "1.250" é mil duzentos e cinquenta
    try:
        numero = Decimal(texto)
    except InvalidOperation:
        return None
    return -numero if negativo else numero


def dinheiro(valor) -> Decimal | None:
    numero = decimal_br(valor)
    return numero.quantize(CENTAVO) if numero is not None else None


def inteiro_br(valor) -> int | None:
    """"1.566.580" e "163.399 impressões" viram inteiro."""
    numero = decimal_br(valor)
    return int(numero) if numero is not None else None


def percentual(valor) -> Decimal | None:
    """"20%", "20,5" e 20 viram 20, 20.5 e 20: sempre em pontos percentuais, sem adivinhar escala."""
    return decimal_br(str(valor).replace("%", "")) if valor is not None else None


def formatar_brl(valor) -> str:
    numero = decimal_br(valor)
    if numero is None:
        return ""
    texto = f"{numero.quantize(CENTAVO):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def formatar_int(valor) -> str:
    numero = inteiro_br(valor)
    return "" if numero is None else f"{numero:,}".replace(",", ".")


# ---------- datas ----------

def data_br(valor) -> date | None:
    """"28/10/2026", "2026-10-28" e "28-10-26" viram date."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = limpo(valor)
    if not texto:
        return None
    achado = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", texto)
    if achado:
        ano, mes, dia = (int(g) for g in achado.groups())
    else:
        achado = re.search(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})", texto)
        if not achado:
            return None
        dia, mes, ano = (int(g) for g in achado.groups())
        if ano < 100:
            ano += 2000
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def mes_ano(valor) -> tuple[int, int] | None:
    """"NOVEMBRO/2026", "11/2026" e "Agosto/2026" viram (ano, mês)."""
    texto = sem_acento(limpo(valor)).lower()
    achado = re.search(r"([a-z]{3,9})\W+(\d{4})", texto)
    if achado and achado.group(1) in _MESES:
        return int(achado.group(2)), _MESES[achado.group(1)]
    achado = re.search(r"(\d{1,2})\s*[/\-]\s*(\d{4})", texto)
    if achado and 1 <= int(achado.group(1)) <= 12:
        return int(achado.group(2)), int(achado.group(1))
    return None


def periodo_do_texto(texto, ano_padrao: int | None = None) -> tuple[date | None, date | None]:
    """"26/10 A 26/11/2026" ou "01/11 a 30/11" viram (início, fim); o ano que falta vem do fim ou do padrão."""
    achados = re.findall(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", limpo(texto))
    if len(achados) < 2:
        return None, None
    (d1, m1, a1), (d2, m2, a2) = achados[0], achados[-1]
    ano_fim = int(a2) if a2 else (ano_padrao or date.today().year)
    if ano_fim < 100:
        ano_fim += 2000
    ano_ini = int(a1) if a1 else (ano_fim - 1 if int(m1) > int(m2) else ano_fim)
    if ano_ini < 100:
        ano_ini += 2000
    try:
        return date(ano_ini, int(m1), int(d1)), date(ano_fim, int(m2), int(d2))
    except ValueError:
        return None, None


# ---------- CNPJ e códigos ----------

def cnpj_digitos(valor) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def cnpj_valido(valor) -> bool:
    d = cnpj_digitos(valor)
    if len(d) != 14 or len(set(d)) == 1:
        return False

    def digito(base, pesos):
        resto = sum(int(n) * p for n, p in zip(base, pesos)) % 11
        return "0" if resto < 2 else str(11 - resto)

    d1 = digito(d[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = digito(d[:12] + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return d[12:] == d1 + d2


def cnpj_formatado(valor) -> str:
    d = cnpj_digitos(valor)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else limpo(valor)


def chave_numero_pi(valor) -> str:
    """"036826" e "36826" são o mesmo PI: compara sem zeros à esquerda e sem pontuação."""
    texto = re.sub(r"[^0-9A-Za-z]", "", limpo(valor)).upper()
    return texto.lstrip("0") or texto


# ---------- valor por extenso ----------

_UNIDADES = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
    "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14,
    "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19,
}
_DEZENAS = {"vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70, "oitenta": 80, "noventa": 90}
_CENTENAS = {"cem": 100, "cento": 100, "duzentos": 200, "trezentos": 300, "quatrocentos": 400, "quinhentos": 500,
             "seiscentos": 600, "setecentos": 700, "oitocentos": 800, "novecentos": 900}
_VALORES = {**_UNIDADES, **_DEZENAS, **_CENTENAS}


def _palavras_para_inteiro(tokens: list[str]) -> int | None:
    total = atual = 0
    entendeu = False
    for token in tokens:
        if token in _VALORES:
            atual += _VALORES[token]
            entendeu = True
        elif token == "mil":
            total += (atual or 1) * 1000
            atual = 0
            entendeu = True
        elif token in ("milhao", "milhoes"):
            total += (atual or 1) * 1_000_000
            atual = 0
            entendeu = True
        elif token in ("e", "de"):
            continue
        else:
            return None
    return total + atual if entendeu else None


def extenso_para_decimal(texto) -> Decimal | None:
    """"quarenta e dois mil reais" -> 42000. Entende reais e centavos; devolve None se não for número por extenso."""
    bruto = sem_acento(limpo(texto)).lower()
    bruto = re.sub(r"[^a-z\s]", " ", bruto)
    tokens = [t for t in bruto.split() if t]
    if not tokens:
        return None
    reais_tokens, centavos_tokens, em_centavos = [], [], False
    for token in tokens:
        if token in ("real", "reais"):
            em_centavos = True
            continue
        if token in ("centavo", "centavos"):
            continue
        (centavos_tokens if em_centavos else reais_tokens).append(token)
    if not em_centavos:
        reais_tokens, centavos_tokens = tokens, []
    reais = _palavras_para_inteiro(reais_tokens) if reais_tokens else 0
    centavos = _palavras_para_inteiro(centavos_tokens) if centavos_tokens else 0
    if reais is None or centavos is None or (not reais_tokens and not centavos_tokens):
        return None
    return Decimal(reais) + Decimal(centavos) / 100


def extenso_no_texto(texto) -> Decimal | None:
    """Acha "[quarenta e dois mil reais]" ou "(cinco mil reais)" dentro de uma linha de valor."""
    for trecho in re.findall(r"[\[(]([^\])]{3,120})[\])]", str(texto or "")):
        valor = extenso_para_decimal(trecho)
        if valor is not None:
            return valor
    return None


def parecidos(a, b) -> float:
    """Semelhança de 0 a 1 entre dois textos, sem acento nem caixa."""
    from difflib import SequenceMatcher

    x, y = sem_acento(limpo(a)).lower(), sem_acento(limpo(b)).lower()
    if not x or not y:
        return 0.0
    return SequenceMatcher(None, x, y).ratio()
