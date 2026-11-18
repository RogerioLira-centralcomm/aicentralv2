"""Organizador de praças do briefing, sem IA: nomes corrigidos, um formato só e nada repetido.

Base: os 5.571 municípios do IBGE (``static/data/municipios_br.json``, API de localidades), os estados, as regiões do país,
apelidos comuns (BH, Sampa, Grande SP) e recortes ("interior de SP", "MG exceto BH"). O que não é reconhecido continua no
briefing, marcado "a conferir": nada trava o envio; a equipe entende nas etapas seguintes.

Formatos de saída (os mesmos da IA e do autocompletar):
  cidade  "Belo Horizonte - MG"            estado  "Minas Gerais (estado)"      regiao  "Região Sudeste"
  rm      "RM de Belo Horizonte - MG"      pais    "Brasil (nacional)"
  recorte "Minas Gerais (estado) exceto Belo Horizonte - MG"                    livre   o texto como veio
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

UFS = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
    "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}
CAPITAIS = {
    "AC": "Rio Branco", "AL": "Maceió", "AP": "Macapá", "AM": "Manaus", "BA": "Salvador", "CE": "Fortaleza", "DF": "Brasília",
    "ES": "Vitória", "GO": "Goiânia", "MA": "São Luís", "MT": "Cuiabá", "MS": "Campo Grande", "MG": "Belo Horizonte",
    "PA": "Belém", "PB": "João Pessoa", "PR": "Curitiba", "PE": "Recife", "PI": "Teresina", "RJ": "Rio de Janeiro",
    "RN": "Natal", "RS": "Porto Alegre", "RO": "Porto Velho", "RR": "Boa Vista", "SC": "Florianópolis", "SP": "São Paulo",
    "SE": "Aracaju", "TO": "Palmas",
}
REGIOES = ("Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul")
# Apelidos -> forma completa (chave já sem acento e em minúsculas).
APELIDOS = {
    "bh": "Belo Horizonte - MG", "beaga": "Belo Horizonte - MG", "sampa": "São Paulo - SP", "poa": "Porto Alegre - RS",
    "floripa": "Florianópolis - SC", "bsb": "Brasília - DF", "cwb": "Curitiba - PR", "ssa": "Salvador - BA", "rec": "Recife - PE",
    "rio": "Rio de Janeiro - RJ", "jf": "Juiz de Fora - MG", "bc": "Balneário Camboriú - SC", "vix": "Vitória - ES",
    "grande bh": "RM de Belo Horizonte - MG", "grande sp": "RM de São Paulo - SP", "grande sao paulo": "RM de São Paulo - SP",
    "grande rio": "RM de Rio de Janeiro - RJ", "grande poa": "RM de Porto Alegre - RS", "grande porto alegre": "RM de Porto Alegre - RS",
    "grande recife": "RM de Recife - PE", "grande curitiba": "RM de Curitiba - PR", "grande vitoria": "RM de Vitória - ES",
    "abc": "ABC Paulista - SP", "abc paulista": "ABC Paulista - SP", "triangulo mineiro": "Triângulo Mineiro - MG",
}
_EXCECAO = re.compile(r"^(?P<base>.+?)\s*[-–(,]?\s*\b(?:exceto|excluindo|excluido|excluída|excluida|menos|sem|fora|exclui|tirando)\b\s*(?P<exc>.+?)\)?\s*$", re.I)


def sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip()


@lru_cache(maxsize=1)
def _base() -> tuple[dict, dict]:
    """(cidade sem acento -> ["Nome - UF", ...], "nome|uf" sem acento -> "Nome - UF")."""
    caminho = Path(__file__).resolve().parent.parent / "static" / "data" / "municipios_br.json"
    por_nome: dict[str, list[str]] = {}
    por_nome_uf: dict[str, str] = {}
    for item in json.loads(caminho.read_text(encoding="utf-8")):
        nome, uf = item.rsplit(" - ", 1)
        chave = sem_acento(nome)
        por_nome.setdefault(chave, []).append(item)
        por_nome_uf[f"{chave}|{uf}"] = item
    return por_nome, por_nome_uf


_ESTADOS = {sem_acento(n): uf for uf, n in UFS.items()}


def _item(nome, tipo, ok=True, obs=""):
    return {"nome": nome, "tipo": tipo, "ok": ok, "obs": obs}


def _estado(texto: str) -> str | None:
    """UF de "MG", "Minas Gerais", "estado de Minas Gerais", "Minas Gerais (estado)"."""
    k = sem_acento(texto)
    k = re.sub(r"^(o |a )?estado (de |do |da )?", "", k)
    k = re.sub(r"\s*\(estado\)$", "", k).strip(" .")
    if k.upper() in UFS and len(k) == 2:
        return k.upper()
    return _ESTADOS.get(k)


def _cidade(texto: str) -> dict | None:
    por_nome, por_nome_uf = _base()
    t = re.sub(r"\s+", " ", texto).strip(" .*")
    m = re.match(r"^(?P<nome>.+?)\s*(?:[-–/,]|\()\s*(?P<uf>[A-Za-z]{2})\)?$", t) or re.match(r"^(?P<nome>.+?)\s+(?P<uf>[A-Za-z]{2})$", t)
    if m and m.group("uf").upper() in UFS:
        achada = por_nome_uf.get(f"{sem_acento(m.group('nome'))}|{m.group('uf').upper()}")
        if achada:
            return _item(achada, "cidade")
    opcoes = por_nome.get(sem_acento(t)) or []
    if len(opcoes) == 1:
        return _item(opcoes[0], "cidade")
    if len(opcoes) > 1:
        capital = [o for o in opcoes if CAPITAIS.get(o.rsplit(" - ", 1)[1]) == o.rsplit(" - ", 1)[0]]
        if capital:
            return _item(capital[0], "cidade")
        ufs = ", ".join(o.rsplit(" - ", 1)[1] for o in opcoes[:6])
        return _item(t, "livre", False, f"Há {t} em mais de um estado ({ufs}). Informe a UF.")
    return None


def normalizar(texto: str) -> dict:
    """Uma praça escrita de qualquer jeito -> {nome, tipo, ok, obs}. Nunca levanta erro."""
    t = re.sub(r"\s+", " ", str(texto or "")).strip(" .*;,-")
    if not t:
        return _item("", "livre", False)
    k = sem_acento(t)
    if k in {"brasil", "nacional", "brasil (nacional)", "brasil todo", "todo o brasil"}:
        return _item("Brasil (nacional)", "pais")
    if k in APELIDOS:
        nome = APELIDOS[k]
        nome_c, _, uf_c = nome.rpartition(" - ")
        cidade = f"{sem_acento(nome_c)}|{uf_c}" in _base()[1]
        return _item(nome, "rm" if nome.startswith("RM de") else ("cidade" if cidade else "recorte"))

    exata = _cidade(t)                    # nome de município vence as palavras de exceção ("Juiz de Fora - MG", "Sem-Peixe - MG")
    if exata and exata["ok"] and re.search(r"[-–/(]|\b[A-Za-z]{2}$", t):
        return exata

    m = _EXCECAO.match(t)
    if m:
        base = normalizar(m.group("base"))
        fora = [normalizar(p) for p in re.split(r"\s*(?:,| e |/)\s*", m.group("exc")) if p.strip()]
        nomes = [f["nome"] for f in fora if f["nome"]]
        return _item(f"{base['nome']} exceto {' e '.join(nomes)}", "recorte", base["ok"] and all(f["ok"] for f in fora),
                     base["obs"] or next((f["obs"] for f in fora if f["obs"]), ""))

    m = re.match(r"^interior (?:de |do |da )?(.+)$", k)
    if m and _estado(m.group(1)):
        uf = _estado(m.group(1))
        return _item(f"{UFS[uf]} (estado) exceto {CAPITAIS[uf]} - {uf}", "recorte")

    m = re.match(r"^(?:rm|regiao metropolitana|grande)(?: de| do| da)? (.+)$", k) or re.match(r"^(.+?) e regiao$", k)
    if m:
        c = normalizar(m.group(1))                                       # "Campinas e região", "BH e região", "Grande Recife"
        if c["tipo"] == "cidade":
            return _item(f"RM de {c['nome']}", "rm")
        if c["tipo"] == "rm":
            return c

    m = re.match(r"^capitais(?: do| da| de)?(?: regiao)? (norte|nordeste|centro[- ]oeste|sudeste|sul)$", k)
    if m:
        nome = next(r for r in REGIOES if sem_acento(r).replace("-", " ") == m.group(1).replace("-", " "))
        return _item(f"Capitais da Região {nome}", "recorte")
    if k in {"capitais", "todas as capitais", "capitais do brasil"}:
        return _item("Capitais do Brasil", "recorte")

    m = re.match(r"^(?:regiao )?(norte|nordeste|centro[- ]oeste|sudeste|sul)$", k)
    if m:
        nome = next(r for r in REGIOES if sem_acento(r).replace("-", " ") == m.group(1).replace("-", " "))
        return _item(f"Região {nome}", "regiao")

    uf = _estado(t)
    if uf:
        return _item(f"{UFS[uf]} (estado)", "estado")
    c = _cidade(t)
    if c:
        return c
    return _item(t, "livre", False, "Não reconhecemos como praça. A equipe confere com você.")


def dividir(texto: str) -> list[str]:
    """Separa um texto livre em praças: vírgula, ponto e vírgula, quebra de linha e " e " quando os dois lados são praças."""
    partes = []
    for bloco in re.split(r"[;,\n]+", str(texto or "")):
        bloco = bloco.strip()
        if not bloco:
            continue
        if partes and re.match(r"^(?:exceto|excluindo|menos|sem|fora|tirando)\b", bloco, re.I):
            partes[-1] = f"{partes[-1]} {bloco}"                         # "MG, exceto BH": a exceção é da praça anterior
            continue
        lados = re.split(r"\s+(?:e|\+|&)\s+", bloco)
        if len(lados) > 1 and not re.search(r"\b(exceto|excluindo|menos|sem|fora)\b", bloco, re.I) \
                and all(normalizar(l)["ok"] for l in lados):
            partes += lados
        else:
            partes.append(bloco)
    return partes


def organizar(itens: list[str]) -> list[dict]:
    """Normaliza e tira repetidas (a mesma praça escrita de dois jeitos vira uma só), na ordem em que vieram."""
    saida, vistos = [], set()
    for bruto in itens or []:
        for parte in dividir(bruto):
            p = normalizar(parte)
            chave = sem_acento(p["nome"])
            if p["nome"] and chave not in vistos:
                vistos.add(chave)
                saida.append(p)
    return saida
