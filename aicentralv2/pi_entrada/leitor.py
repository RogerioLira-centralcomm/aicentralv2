"""Leitura do PDF do PI: camada de texto primeiro, OCR do OpenRouter quando o PDF é imagem.

Estratégia (decidida a partir dos PIs de amostra, que são PDFs digitais com assinatura manuscrita):
1. PyMuPDF extrai o texto de cada página. Se há texto suficiente, só o texto vai ao modelo (barato e exato).
2. Se o PDF é escaneado (quase sem texto), o arquivo inteiro vai ao OpenRouter com o plugin ``file-parser``
   em modo ``mistral-ocr``, o mesmo caminho que o Agente CentralX usa para anexos.
3. A resposta é JSON no esquema de ``esquema.py``; depois ``conferir_contra_texto`` confirma, no texto
   bruto, os números e códigos que o modelo devolveu (segunda checagem local e gratuita).
"""

from __future__ import annotations

import base64
import logging
import os
import re
import time
from dataclasses import dataclass, field

from . import esquema
from . import normalizar as n

logger = logging.getLogger(__name__)

MODELO_PADRAO = "google/gemini-2.5-flash"
MIN_CARACTERES_POR_PAGINA = 200
MAX_PAGINAS = 30
MAX_BYTES = 20 * 1024 * 1024


class LeituraErro(RuntimeError):
    """Falha de leitura que o usuário pode entender (arquivo inválido, grande demais, modelo fora do ar)."""


@dataclass
class Leitura:
    pi: dict
    bruto: dict
    metodo: str                      # "texto" ou "ocr"
    modelo: str
    paginas: int
    tokens_entrada: int = 0
    tokens_saida: int = 0
    duracao_ms: int = 0
    texto: str = ""                  # texto limpo enviado ao modelo (vazio no OCR)
    avisos: list[str] = field(default_factory=list)


def modelo_configurado() -> str:
    return os.getenv("PI_ENTRADA_MODELO", "").strip() or MODELO_PADRAO


# ---------- PDF ----------

def paginas_do_pdf(conteudo: bytes) -> list[str]:
    """Texto de cada página. Levanta LeituraErro se não for um PDF legível."""
    if not conteudo or conteudo[:5] != b"%PDF-":
        raise LeituraErro("O arquivo não é um PDF.")
    if len(conteudo) > MAX_BYTES:
        raise LeituraErro("O PDF passa de 20 MB.")
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:                                              # pragma: no cover
        raise LeituraErro("A leitura de PDF não está instalada neste ambiente.") from exc
    try:
        with fitz.open(stream=conteudo, filetype="pdf") as doc:
            if doc.needs_pass:
                raise LeituraErro("O PDF tem senha.")
            if doc.page_count > MAX_PAGINAS:
                raise LeituraErro(f"O PDF tem {doc.page_count} páginas; o limite é {MAX_PAGINAS}.")
            return [pagina.get_text("text") or "" for pagina in doc]
    except LeituraErro:
        raise
    except Exception as exc:
        raise LeituraErro("Não consegui abrir o PDF.") from exc


def limpar_paginas(paginas: list[str]) -> list[str]:
    """Tira o calendário de dias e o cabeçalho que se repete em toda página (mantém a primeira)."""
    linhas = [[l.strip() for l in p.splitlines() if l.strip()] for p in paginas]
    repetidas: set[str] = set()
    if len(linhas) >= 2:
        comuns = set(linhas[0])
        for outra in linhas[1:]:
            comuns &= set(outra)
        repetidas = {l for l in comuns if len(l) > 3}
    saida = []
    for i, ls in enumerate(linhas):
        mantidas = []
        for l in ls:
            if re.fullmatch(r"\d{1,2}|[DSTQ]|TOT|INS|P|E|Ç|A", l):
                continue                                                      # calendário e colunas vazias
            if i > 0 and l in repetidas:
                continue                                                      # cabeçalho repetido
            mantidas.append(l)
        saida.append("\n".join(mantidas))
    return saida


def tem_texto_suficiente(paginas: list[str]) -> bool:
    return bool(paginas) and sum(len(p.strip()) for p in paginas) / len(paginas) >= MIN_CARACTERES_POR_PAGINA


def texto_para_modelo(paginas: list[str]) -> str:
    return "\n\n".join(f"=== PÁGINA {i} ===\n{p}" for i, p in enumerate(paginas, 1))


# ---------- modelo ----------

def _chamar_padrao(*args, **kwargs):
    from ..services.openrouter_service import chat_completion
    return chat_completion(*args, **kwargs)


def _texto_da_resposta(resposta: dict) -> str:
    mensagem = (resposta or {}).get("message") or {}
    conteudo = mensagem.get("content")
    if isinstance(conteudo, list):
        conteudo = "\n".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in conteudo)
    return str(conteudo or "")


def ler(conteudo: bytes, nome: str = "pi.pdf", *, modelo: str | None = None, chamar=None) -> Leitura:
    """PDF -> Leitura (PI normalizado). ``chamar`` troca o cliente do modelo (testes)."""
    chamar = chamar or _chamar_padrao
    modelo = modelo or modelo_configurado()
    inicio = time.monotonic()
    brutas = paginas_do_pdf(conteudo)
    limpas = limpar_paginas(brutas)
    avisos: list[str] = []

    if tem_texto_suficiente(limpas):
        metodo, plugins = "texto", None
        usuario = [{"type": "text", "text": esquema.montar_prompt_usuario(texto_para_modelo(limpas))}]
        texto = texto_para_modelo(limpas)
    else:
        metodo, texto = "ocr", ""
        plugins = [{"id": "file-parser", "pdf": {"engine": "mistral-ocr"}}]
        dados = "data:application/pdf;base64," + base64.b64encode(conteudo).decode("ascii")
        usuario = [
            {"type": "text", "text": esquema.montar_prompt_usuario("(o PDF está anexado; use o texto que o OCR extrair)")},
            {"type": "file", "file": {"filename": nome, "file_data": dados}},
        ]
        avisos.append("PDF sem camada de texto: leitura por OCR.")

    mensagens = [{"role": "system", "content": esquema.PROMPT_SISTEMA}, {"role": "user", "content": usuario}]
    tokens_in = tokens_out = 0
    bruto = None
    ultimo_erro = None
    for tentativa in range(2):
        try:
            resposta = chamar(mensagens, plugins=plugins, model=modelo, timeout=170, max_tokens=12000,
                              temperature=0, response_format={"type": "json_object"})
        except Exception as exc:
            logger.warning("Leitura do PI falhou no modelo: %s", exc)
            raise LeituraErro("O modelo de leitura não respondeu. Tente de novo em instantes.") from exc
        uso = (resposta or {}).get("usage") or {}
        tokens_in += int(uso.get("prompt_tokens") or 0)
        tokens_out += int(uso.get("completion_tokens") or 0)
        try:
            bruto = esquema.extrair_json(_texto_da_resposta(resposta))
            break
        except ValueError as exc:
            ultimo_erro = exc
            mensagens = mensagens + [{"role": "user", "content": "Responda de novo, somente com o objeto JSON válido."}]
    if bruto is None:
        raise LeituraErro("O modelo não devolveu um JSON válido.") from ultimo_erro

    pi = esquema.normalizar_extracao(bruto)
    if not pi["numero_pi"] and not pi["linhas"]:
        raise LeituraErro("Não encontrei um PI neste arquivo.")
    return Leitura(pi=pi, bruto=bruto, metodo=metodo, modelo=(resposta or {}).get("model") or modelo,
                   paginas=len(brutas), tokens_entrada=tokens_in, tokens_saida=tokens_out,
                   duracao_ms=int((time.monotonic() - inicio) * 1000), texto=texto, avisos=avisos)


# ---------- segunda checagem local: o que o modelo devolveu existe no texto? ----------

_NUMERO_NO_TEXTO = re.compile(r"\d[\d.,]*\d|\d")


def numeros_do_texto(texto: str) -> set:
    achados = set()
    for trecho in _NUMERO_NO_TEXTO.findall(texto or ""):
        v = n.decimal_br(trecho)
        if v is not None:
            achados.add(v.normalize())
    return achados


def conferir_contra_texto(pi: dict, texto: str) -> list[dict]:
    """Campos-chave que o modelo devolveu mas não aparecem no texto do PDF. Sem texto, não confere."""
    if not (texto or "").strip():
        return []
    numeros = numeros_do_texto(texto)
    plano = re.sub(r"\W+", "", n.sem_acento(texto)).lower()
    achados = []

    def numero_sumiu(campo, rotulo, valor):
        v = n.decimal_br(valor)
        if v is not None and v.normalize() not in numeros:
            achados.append({"campo": campo, "rotulo": rotulo, "valor": str(valor), "motivo": "valor não aparece no texto do PDF"})

    if pi.get("numero_pi") and re.sub(r"\W+", "", n.sem_acento(pi["numero_pi"])).lower() not in plano:
        achados.append({"campo": "numero_pi", "rotulo": "Nº do PI", "valor": pi["numero_pi"], "motivo": "texto não aparece no PDF"})
    for grupo, rotulo in (("cliente", "CNPJ do cliente"), ("agencia", "CNPJ da agência")):
        cnpj = n.cnpj_digitos((pi.get(grupo) or {}).get("cnpj"))
        if cnpj and cnpj not in re.sub(r"\D", "", texto):
            achados.append({"campo": f"{grupo}.cnpj", "rotulo": rotulo, "valor": cnpj, "motivo": "CNPJ não aparece no texto do PDF"})
    for campo, rotulo in (("bruto", "Total bruto"), ("comissao", "Comissão"), ("liquido", "Líquido")):
        numero_sumiu(f"totais.{campo}", rotulo, (pi.get("totais") or {}).get(campo))
    for i, linha in enumerate(pi.get("linhas") or [], 1):
        numero_sumiu(f"linhas.{i}.valor_bruto", f"Linha {i}: valor bruto", linha.get("valor_bruto"))
        numero_sumiu(f"linhas.{i}.preco_unitario", f"Linha {i}: preço unitário", linha.get("preco_unitario"))
        if linha.get("entrega"):
            numero_sumiu(f"linhas.{i}.entrega", f"Linha {i}: entrega", linha.get("entrega"))
    return achados
