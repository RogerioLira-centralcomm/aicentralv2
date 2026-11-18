"""Briefing para cotação: o cliente anexa PDF, imagem ou planilha, o hub lê, mostra "o que entendi" e envia ao executivo.

A leitura segue o caminho da Entrada de PI (OpenRouter, texto do PDF primeiro e OCR só quando o PDF é imagem), mas aqui o
alvo são os campos do briefing. O rascunho vive em ``hub_briefing_cotacao``; só o envio cria a linha em ``cadu_briefings``
(modo ``cotacao``, com ``prazo_resposta_em``), então nenhum rascunho aparece nas listas da equipe.
Plano: docs/plans/hub-de-midia-pi-briefing-onboarding.md, seção 4.2.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import logging
import os
import threading
import uuid as uuidlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import current_app

from ..pi_entrada import esquema, leitor

logger = logging.getLogger(__name__)
FUSO = ZoneInfo("America/Sao_Paulo")
MAX_ARQUIVOS = 5
MAX_BYTES = 20 * 1024 * 1024
HORAS_PRAZO = 24
ABERTURA, FECHAMENTO = 9, 18          # horário útil da equipe: seg a sex, 9h às 18h (decisão D4, a confirmar)
TIPOS = {".pdf": "pdf", ".png": "imagem", ".jpg": "imagem", ".jpeg": "imagem", ".webp": "imagem",
         ".xlsx": "planilha", ".csv": "planilha"}
MIME_IMAGEM = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}

PROMPT = (
    "Você lê materiais que um cliente de mídia anexou para pedir uma cotação (briefing, mídia kit, planilha de mídia, PI antigo). "
    "Extraia só o que está escrito nos arquivos e devolva SOMENTE um objeto JSON com estas chaves: "
    "anunciante (nome do cliente ou da marca que vai anunciar, como aparece no material, ou null), "
    "titulo (nome da campanha ou ação, string), objetivo (o que a campanha precisa alcançar, 1 a 3 frases), publico (string), "
    "pracas (lista de cidades, estados ou regiões), inicio e fim (AAAA-MM-DD ou null), verba (texto como no material, ou null; "
    "nunca invente), canais (lista com valores de: tv_ctv, programatica, social, busca, audio, ooh, influencia), "
    "formatos (lista de formatos citados), pecas (texto curto sobre o estado do material criativo, ou null), "
    "resumo (2 frases do que o material pede) e faltou (lista curta, em português, do que não está nos arquivos e a equipe "
    "precisará perguntar: praças, período, verba, público, objetivo). Use null ou lista vazia para o que não aparece. "
    "Verba é só o que o cliente declara que pretende investir. Se um arquivo for PI, proposta ou cotação antiga, NUNCA use os valores dele como verba "
    "(nem preços, margens ou totais): use null. Quando houver mais de uma campanha nos arquivos, descreva a mais recente ou a que o material pede."
)


class CotacaoErro(RuntimeError):
    """Falha que o cliente pode entender."""


# ---------- prazo ----------

def prazo_resposta(inicio: datetime | None = None) -> datetime:
    """24 horas corridas a partir do envio; se o fim cair fora do horário útil (seg a sex, 9h às 18h), vai para o próximo
    horário útil. Assim o cliente nunca recebe um prazo que vence no domingo à noite."""
    agora = (inicio or datetime.now(timezone.utc)).astimezone(FUSO)
    fim = agora + timedelta(hours=HORAS_PRAZO)
    if fim.weekday() >= 5 or fim.hour < ABERTURA or fim.hour >= FECHAMENTO:
        if fim.weekday() < 5 and fim.hour < ABERTURA:
            fim = fim.replace(hour=ABERTURA, minute=0, second=0, microsecond=0)
        else:
            fim = (fim + timedelta(days=1)).replace(hour=ABERTURA, minute=0, second=0, microsecond=0)
            while fim.weekday() >= 5:
                fim += timedelta(days=1)
    return fim.astimezone(timezone.utc)


def prazo_texto(prazo: datetime | None) -> str:
    if not prazo:
        return ""
    local = prazo.astimezone(FUSO)
    return f"{local:%d/%m} às {local:%H:%M}"


# ---------- arquivos ----------

def pasta_privada() -> Path:
    base = current_app.config.get("HUB_BRIEFING_DIR") or os.path.join(current_app.instance_path, "hub_briefing")
    pasta = Path(base)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def validar_arquivo(nome: str, conteudo: bytes) -> str:
    """Devolve o tipo (pdf, imagem, planilha) ou levanta CotacaoErro."""
    ext = Path(nome or "").suffix.lower()
    tipo = TIPOS.get(ext)
    if not tipo:
        raise CotacaoErro("Envie PDF, imagem (PNG, JPG) ou planilha (XLSX, CSV).")
    if not conteudo:
        raise CotacaoErro("O arquivo está vazio.")
    if len(conteudo) > MAX_BYTES:
        raise CotacaoErro("O arquivo passa de 20 MB.")
    assinaturas = {"pdf": (b"%PDF-",), "imagem": (b"\x89PNG", b"\xff\xd8\xff", b"RIFF"), "planilha": ()}[tipo]
    if assinaturas and not conteudo.startswith(assinaturas):
        raise CotacaoErro(f"{Path(nome).name} não parece ser um arquivo {tipo} válido.")
    if ext == ".xlsx" and not conteudo.startswith(b"PK"):
        raise CotacaoErro("A planilha XLSX está corrompida.")
    return tipo


def guardar(id_rascunho: int, nome: str, conteudo: bytes, tipo: str) -> dict:
    sha = hashlib.sha256(conteudo).hexdigest()
    destino = pasta_privada() / str(id_rascunho)
    destino.mkdir(parents=True, exist_ok=True)
    ext = Path(nome).suffix.lower()
    caminho = destino / f"{sha[:16]}{ext}"
    caminho.write_bytes(conteudo)
    return {"nome": Path(nome).name[:160], "sha256": sha, "tamanho": len(conteudo), "caminho": str(caminho), "tipo": tipo}


def _texto_planilha(conteudo: bytes, ext: str) -> str:
    if ext == ".csv":
        texto = conteudo.decode("utf-8-sig", errors="replace")
        return "\n".join(" | ".join(l) for l in list(csv.reader(io.StringIO(texto)))[:300])
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    partes = []
    for aba in wb.worksheets[:4]:
        linhas = []
        for i, linha in enumerate(aba.iter_rows(values_only=True)):
            if i >= 300:
                break
            if any(c is not None for c in linha):
                linhas.append(" | ".join("" if c is None else str(c) for c in linha))
        partes.append(f"--- aba {aba.title} ---\n" + "\n".join(linhas))
    return "\n".join(partes)


def _conteudo_para_modelo(arquivos: list[dict]) -> tuple[list[dict], list | None, list[str]]:
    """Blocos de mensagem (texto, imagem, PDF para OCR), os plugins necessários e os avisos."""
    blocos, avisos, plugins = [], [], None
    for a in arquivos:
        caminho = Path(a["caminho"])
        dados = caminho.read_bytes()
        ext = caminho.suffix.lower()
        if a["tipo"] == "pdf":
            paginas = leitor.limpar_paginas(leitor.paginas_do_pdf(dados))
            if leitor.tem_texto_suficiente(paginas):
                blocos.append({"type": "text", "text": f"### Arquivo: {a['nome']}\n{leitor.texto_para_modelo(paginas)[:60000]}"})
            else:
                plugins = [{"id": "file-parser", "pdf": {"engine": "mistral-ocr"}}]
                blocos.append({"type": "file", "file": {"filename": a["nome"], "file_data": "data:application/pdf;base64," + base64.b64encode(dados).decode("ascii")}})
                avisos.append(f"{a['nome']}: PDF sem camada de texto, lido por OCR.")
        elif a["tipo"] == "imagem":
            blocos.append({"type": "text", "text": f"### Arquivo (imagem): {a['nome']}"})
            blocos.append({"type": "image_url", "image_url": {"url": f"data:{MIME_IMAGEM.get(ext, 'image/png')};base64," + base64.b64encode(dados).decode("ascii")}})
        else:
            blocos.append({"type": "text", "text": f"### Arquivo (planilha): {a['nome']}\n{_texto_planilha(dados, ext)[:60000]}"})
    return blocos, plugins, avisos


def _normalizar(bruto: dict) -> dict:
    """Mantém só o que o formulário aceita; o que o modelo inventar fora do esquema não passa."""
    from . import briefing

    def txt(v, limite):
        return " ".join(str(v or "").split())[:limite]

    def lista(v, limite, quantos):
        saida = []
        for item in v if isinstance(v, list) else []:
            t = txt(item, limite)
            if t and t.lower() not in {x.lower() for x in saida}:
                saida.append(t)
        return saida[:quantos]

    def data(v):
        return briefing._data(str(v or "")).isoformat() if briefing._data(str(v or "")) else ""

    canais = [c for c in lista(bruto.get("canais"), 30, 8) if c in dict(briefing.CANAIS)]
    return {
        "anunciante": txt(bruto.get("anunciante"), 160), "titulo": txt(bruto.get("titulo"), 160), "objetivo": txt(bruto.get("objetivo"), 2000), "publico": txt(bruto.get("publico"), 1000),
        "pracas": lista(bruto.get("pracas"), 80, briefing.MAX_PRACAS), "inicio": data(bruto.get("inicio")), "fim": data(bruto.get("fim")),
        "verba": txt(bruto.get("verba"), 120), "canais": canais, "formatos": lista(bruto.get("formatos"), 80, 10),
        "pecas": txt(bruto.get("pecas"), 300), "resumo": txt(bruto.get("resumo"), 600), "faltou": lista(bruto.get("faltou"), 120, 8),
    }


def ler(arquivos: list[dict], *, chamar=None, modelo: str | None = None) -> dict:
    """Arquivos guardados -> {leitura, avisos, modelo, tokens_entrada, tokens_saida}."""
    chamar = chamar or leitor._chamar_padrao
    modelo = modelo or leitor.modelo_configurado()
    blocos, plugins, avisos = _conteudo_para_modelo(arquivos)
    if not blocos:
        raise CotacaoErro("Não há arquivo para ler.")
    mensagens = [{"role": "system", "content": PROMPT}, {"role": "user", "content": [{"type": "text", "text": "Materiais do cliente:"}, *blocos]}]
    tokens_in = tokens_out = 0
    bruto = None
    for _ in range(2):
        try:
            resposta = chamar(mensagens, plugins=plugins, model=modelo, timeout=170, max_tokens=4000, temperature=0,
                              response_format={"type": "json_object"})
        except Exception as exc:
            logger.warning("Leitura do briefing de cotação falhou no modelo: %s", exc)
            raise CotacaoErro("O modelo de leitura não respondeu agora.") from exc
        uso = (resposta or {}).get("usage") or {}
        tokens_in += int(uso.get("prompt_tokens") or 0)
        tokens_out += int(uso.get("completion_tokens") or 0)
        try:
            bruto = esquema.extrair_json(leitor._texto_da_resposta(resposta))
            break
        except ValueError:
            mensagens = mensagens + [{"role": "user", "content": "Responda de novo, somente com o objeto JSON válido."}]
    if bruto is None:
        raise CotacaoErro("O modelo não devolveu uma leitura válida.")
    return {"leitura": _normalizar(bruto), "avisos": avisos, "modelo": (resposta or {}).get("model") or modelo,
            "tokens_entrada": tokens_in, "tokens_saida": tokens_out}


# ---------- banco ----------

def _db():
    from .. import db
    return db


def _executar(sql, params=(), *, uma=False, nenhuma=False, commit=False):
    conn = _db().get_db()
    try:
        with conn.cursor() as c:
            c.execute(sql, params)
            resultado = None if nenhuma else (c.fetchone() if uma else c.fetchall())
        if commit:
            conn.commit()
        return resultado
    except Exception:
        conn.rollback()
        raise


def criar_rascunho(id_cliente: int, id_contato: int | None) -> dict:
    novo = str(uuidlib.uuid4())
    row = _executar("INSERT INTO hub_briefing_cotacao (uuid, id_cliente, id_contato) VALUES (%s, %s, %s) RETURNING id", (novo, id_cliente, id_contato), uma=True, commit=True)
    return {"id": row["id"], "uuid": novo}


def definir_arquivos(id_rascunho: int, arquivos: list[dict]) -> None:
    _executar("UPDATE hub_briefing_cotacao SET arquivos = %s::jsonb, atualizado_em = NOW() WHERE id = %s", (json.dumps(arquivos, ensure_ascii=False), id_rascunho), nenhuma=True, commit=True)


def obter(uuid_rascunho: str) -> dict | None:
    row = _executar("SELECT * FROM hub_briefing_cotacao WHERE uuid = %s", (str(uuid_rascunho),), uma=True)
    return dict(row) if row else None


def mudar_status(id_rascunho: int, status: str, erro: str | None = None) -> None:
    _executar("UPDATE hub_briefing_cotacao SET status = %s, erro = %s, atualizado_em = NOW() WHERE id = %s", (status, erro, id_rascunho), nenhuma=True, commit=True)


def salvar_leitura(id_rascunho: int, resultado: dict) -> None:
    leitura = {**resultado["leitura"], "avisos": resultado["avisos"]}
    _executar("""UPDATE hub_briefing_cotacao SET status = 'lido', erro = NULL, leitura = %s::jsonb, modelo = %s, tokens_entrada = %s,
                        tokens_saida = %s, atualizado_em = NOW() WHERE id = %s""",
              (json.dumps(leitura, ensure_ascii=False), resultado["modelo"], resultado["tokens_entrada"], resultado["tokens_saida"], id_rascunho), nenhuma=True, commit=True)


def reservar(id_rascunho: int) -> str | None:
    """Trava o rascunho para um único envio (duplo clique ou duas abas). Devolve o status anterior, ou None se outro envio já pegou."""
    row = _executar("""UPDATE hub_briefing_cotacao h SET status = 'enviando', atualizado_em = NOW()
                         FROM (SELECT id, status FROM hub_briefing_cotacao WHERE id = %s AND status IN ('lido', 'erro') FOR UPDATE) a
                        WHERE h.id = a.id RETURNING a.status AS anterior""", (id_rascunho,), uma=True, commit=True)
    return row["anterior"] if row else None


def marcar_enviado(id_rascunho: int, briefing_id: int, prazo) -> bool:
    row = _executar("""UPDATE hub_briefing_cotacao SET status = 'enviado', briefing_id = %s, prazo_resposta_em = %s, atualizado_em = NOW()
                        WHERE id = %s AND status = 'enviando' RETURNING id""", (briefing_id, prazo, id_rascunho), uma=True, commit=True)
    return bool(row)


def contar_recentes(id_cliente: int, minutos: int = 60) -> int:
    row = _executar("SELECT COUNT(*) AS n FROM hub_briefing_cotacao WHERE id_cliente = %s AND criado_em > NOW() - (%s || ' minutes')::interval", (id_cliente, str(int(minutos))), uma=True)
    return int(row["n"])


def situacao(rascunho: dict) -> str:
    """lendo, erro, pronto ou enviado. Leitura presa há mais de 5 minutos conta como erro."""
    if rascunho.get("status") in ("enviado", "enviando"):
        return "enviado"
    if rascunho.get("status") in ("recebido", "lendo"):
        quando = rascunho.get("atualizado_em")
        if isinstance(quando, datetime):
            quando = quando if quando.tzinfo else quando.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - quando > timedelta(minutes=5):
                return "erro"
        return "lendo"
    return "erro" if rascunho.get("status") == "erro" else "pronto"


# ---------- segundo plano ----------

def processar(id_rascunho: int, uuid_rascunho: str, *, chamar=None) -> None:
    try:
        rascunho = obter(uuid_rascunho)
        mudar_status(id_rascunho, "lendo")
        resultado = ler(rascunho["arquivos"], chamar=chamar)
        salvar_leitura(id_rascunho, resultado)
    except (CotacaoErro, leitor.LeituraErro) as exc:                                # mensagens escritas para o cliente (PDF com senha, grande demais…)
        mudar_status(id_rascunho, "erro", str(exc))
    except Exception:
        logger.exception("Leitura do briefing de cotação %s falhou", id_rascunho)
        mudar_status(id_rascunho, "erro", "Não consegui ler os arquivos. Você pode enviar do mesmo jeito: a equipe vê os anexos.")


def iniciar_em_segundo_plano(id_rascunho: int, uuid_rascunho: str) -> None:
    app = current_app._get_current_object()

    def tarefa():
        with app.app_context():
            processar(id_rascunho, uuid_rascunho)
    threading.Thread(target=tarefa, name=f"cotacao-{id_rascunho}", daemon=True).start()
