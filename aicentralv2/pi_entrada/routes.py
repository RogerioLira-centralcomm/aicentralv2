"""Entrada de PI automatizada (CentralX, Comercial) em ``/pi-entrada``.

Tela **nova**, ao lado da atual (``/cadu_pi/novo``, que não muda). O executivo arrasta o PDF, o sistema lê (texto do PDF
e, se preciso, OCR), confere as contas do documento, compara com a cotação escolhida e mostra o que falta no cadastro.
Nada vira PI sem a verificação humana desta página; o resultado é um rascunho no formato da tela atual.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, send_file, session, url_for

from ..auth import centralcomm_required, centralcomm_required_api
from . import cadastro, leitor, normalizar, rascunho, repositorio, servico, visao

logger = logging.getLogger(__name__)
bp = Blueprint("pi_entrada", __name__, url_prefix="/pi-entrada")

ROTULO_STATUS = {
    "recebido": ("Na fila", "cx-badge-muted"), "lendo": ("Lendo", "cx-badge-info"), "lido": ("Para verificar", "cx-badge-warning"),
    "aprovado": ("Aprovado", "cx-badge-success"), "rascunho": ("Rascunho pronto", "cx-badge-success"), "erro": ("Erro na leitura", "cx-badge-danger"),
}


def _usuario() -> int | None:
    return session.get("user_id")


def _erro(mensagem: str, codigo: int = 400):
    return jsonify({"ok": False, "erro": mensagem}), codigo


def travada(entrada: dict, minutos: int = 5) -> bool:
    """Presa em 'recebido' ou 'lendo' há mais que alguns minutos (o servidor reiniciou no meio da leitura)."""
    if entrada.get("status") not in ("recebido", "lendo"):
        return False
    quando = entrada.get("atualizado_em")
    if not isinstance(quando, datetime):
        return False
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - quando > timedelta(minutes=minutos)


def _entrada_ou_404(id_entrada: int) -> dict:
    entrada = repositorio.obter(id_entrada)
    if not entrada:
        abort(404)
    return entrada


@bp.app_context_processor
def _globais():
    return {"pi_entrada_status": ROTULO_STATUS}


@bp.app_template_filter("pi_brl")
def _filtro_brl(valor):
    return normalizar.formatar_brl(valor) or "—"


@bp.app_template_filter("pi_int")
def _filtro_int(valor):
    return normalizar.formatar_int(valor) or "—"


@bp.app_template_filter("pi_data")
def _filtro_data(valor):
    d = normalizar.data_br(valor)
    return d.strftime("%d/%m/%Y") if d else ""


# ---------- fila e envio ----------

@bp.route("/")
@centralcomm_required
def fila():
    minhas = request.args.get("minhas") == "1"
    entradas = repositorio.listar(100, id_executivo=_usuario() if minhas else None)
    for e in entradas:
        e["resumo"] = e.get("conferencias") or {}
    return render_template("pi_entrada/fila.html", entradas=entradas, minhas=minhas)


@bp.route("/upload", methods=["POST"])
@centralcomm_required_api
def upload():
    arquivos = request.files.getlist("arquivos")
    if not arquivos:
        return _erro("Escolha ao menos um PDF.")
    if len(arquivos) > servico.LIMITE_ARQUIVOS_POR_ENVIO:
        return _erro(f"Envie até {servico.LIMITE_ARQUIVOS_POR_ENVIO} PDFs por vez.")
    saida = []
    for arquivo in arquivos:
        nome = Path(arquivo.filename or "pi.pdf").name
        conteudo = arquivo.read(leitor.MAX_BYTES + 1)
        if not nome.lower().endswith(".pdf") or conteudo[:5] != b"%PDF-":
            saida.append({"nome": nome, "erro": "Só aceito arquivos PDF."})
            continue
        if len(conteudo) > leitor.MAX_BYTES:
            saida.append({"nome": nome, "erro": "O PDF passa de 20 MB."})
            continue
        import hashlib
        anterior = repositorio.entrada_por_sha(hashlib.sha256(conteudo).hexdigest())
        if anterior:
            saida.append({"nome": nome, "id": anterior["id"], "duplicado": True, "url": url_for("pi_entrada.verificar", id_entrada=anterior["id"])})
            continue
        id_entrada = repositorio.criar_entrada("centralx", id_usuario=_usuario(), id_executivo=_usuario())
        guardado = servico.guardar_arquivo(id_entrada, nome, conteudo)
        repositorio.registrar_arquivo(id_entrada, nome, guardado["sha256"], guardado["tamanho"], guardado["caminho"])
        servico.iniciar_em_segundo_plano(id_entrada)
        saida.append({"nome": nome, "id": id_entrada, "url": url_for("pi_entrada.verificar", id_entrada=id_entrada)})
    return jsonify({"ok": True, "entradas": saida})


@bp.route("/<int:id_entrada>/status")
@centralcomm_required_api
def status(id_entrada):
    entrada = repositorio.obter(id_entrada)
    if not entrada:
        return _erro("Entrada não encontrada.", 404)
    return jsonify({"ok": True, "status": entrada["status"], "erro": entrada.get("erro"), "pronto": entrada["status"] not in ("recebido", "lendo")})


@bp.route("/<int:id_entrada>/arquivo")
@centralcomm_required
def arquivo(id_entrada):
    _entrada_ou_404(id_entrada)
    registro = repositorio.arquivo_da_entrada(id_entrada)
    if not registro or not Path(registro["caminho"]).is_file():
        abort(404)
    resposta = send_file(registro["caminho"], mimetype="application/pdf", download_name=registro["nome_original"], conditional=True)
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["Cache-Control"] = "private, no-store"
    return resposta


@bp.route("/<int:id_entrada>/reler", methods=["POST"])
@centralcomm_required
def reler(id_entrada):
    entrada = _entrada_ou_404(id_entrada)
    if entrada["status"] in ("erro", "lido") or travada(entrada):
        repositorio.mudar_status(id_entrada, "recebido")
        servico.iniciar_em_segundo_plano(id_entrada)
    return redirect(url_for("pi_entrada.verificar", id_entrada=id_entrada))


# ---------- verificação ----------

def _visao(entrada: dict, cotacao_id=None) -> dict:
    pi = entrada.get("json_revisado") or {}
    ctx = cadastro.contexto(pi)
    cotacoes = cadastro.cotacoes_do_cliente(ctx.get("cliente_id"), ctx.get("agencia_id"))
    escolhida = cotacao_id if cotacao_id is not None else entrada.get("cotacao_id")
    cotacao = cadastro.cotacao_completa(escolhida) if escolhida else None
    v = visao.montar(entrada, ctx=ctx, cotacao=cotacao, cotacoes=cotacoes, ajustes=repositorio.ajustes(entrada["id"]))
    v["cotacao_sugerida"] = False
    if cotacao is None and v["cotacoes"] and v["cotacoes"][0]["pontuacao"] >= 0.8:
        sugerida = cadastro.cotacao_completa(v["cotacoes"][0]["id"])
        if sugerida:
            v = {**visao.montar(entrada, ctx=ctx, cotacao=sugerida, cotacoes=cotacoes, ajustes=repositorio.ajustes(entrada["id"])), "cotacao_sugerida": True}
    v["ctx"] = ctx
    return v


@bp.route("/<int:id_entrada>")
@centralcomm_required
def verificar(id_entrada):
    entrada = _entrada_ou_404(id_entrada)
    parada = travada(entrada)
    contexto = {"entrada": entrada, "travada": parada, "status_rotulo": ROTULO_STATUS.get(entrada["status"], (entrada["status"], "cx-badge-muted"))}
    if entrada["status"] in ("recebido", "lendo", "erro") or not entrada.get("json_revisado"):
        return render_template("pi_entrada/verificar.html", carregando=entrada["status"] in ("recebido", "lendo") and not parada, v=None, **contexto)
    if entrada.get("origem") == "hub":
        contexto["remetente"] = cadastro.contato_por_id(entrada.get("id_contato_envio"))
    return render_template("pi_entrada/verificar.html", carregando=False, v=_visao(entrada), **contexto)


@bp.route("/<int:id_entrada>/cotacao", methods=["POST"])
@centralcomm_required
def escolher_cotacao(id_entrada):
    _entrada_ou_404(id_entrada)
    valor = (request.form.get("cotacao_id") or "").strip()
    repositorio.definir_cotacao(id_entrada, int(valor) if valor.isdigit() else None)
    return redirect(url_for("pi_entrada.verificar", id_entrada=id_entrada))


@bp.route("/<int:id_entrada>/ajustes", methods=["POST"])
@centralcomm_required_api
def ajustes(id_entrada):
    entrada = repositorio.obter(id_entrada)
    if not entrada or not entrada.get("json_revisado"):
        return _erro("Entrada não encontrada ou ainda sem leitura.", 404)
    itens = (request.get_json(silent=True) or {}).get("itens") or []
    if not itens:
        return _erro("Nada para salvar.")
    pi, registros = entrada["json_revisado"], []
    try:
        for item in itens:
            campo, tipo = str(item.get("campo") or ""), str(item.get("tipo") or "ajuste")
            visao.validar_justificativa(campo, tipo, str(item.get("motivo") or ""), str(item.get("justificativa") or ""), str(item.get("referencia") or ""))
            antigo = novo = ""
            if tipo == "ajuste" and not campo.startswith(("cmp:", "conf:")):
                pi, antigo, novo = visao.definir_valor(pi, campo, item.get("valor"))
            else:
                antigo = novo = str(item.get("referencia") or "")
            registros.append({"campo": campo, "tipo": tipo, "valor_lido": "" if antigo is None else str(antigo),
                              "valor_final": "" if novo is None else str(novo), "motivo": item["motivo"], "justificativa": item["justificativa"].strip()})
    except visao.EdicaoInvalida as exc:
        return _erro(str(exc), 422)
    repositorio.salvar_revisado(id_entrada, pi)
    for r in registros:
        repositorio.registrar_ajuste(id_entrada, id_usuario=_usuario(), **r)
    return jsonify({"ok": True, "salvos": len(registros)})


@bp.route("/<int:id_entrada>/aprovar", methods=["POST"])
@centralcomm_required
def aprovar(id_entrada):
    entrada = _entrada_ou_404(id_entrada)
    if entrada["status"] not in ("lido", "aprovado", "rascunho"):
        flash("Esta entrada ainda não foi lida.", "error")
        return redirect(url_for("pi_entrada.verificar", id_entrada=id_entrada))
    v = _visao(entrada)
    if v["pendentes"]:
        flash(f"Faltam {len(v['pendentes'])} justificativa(s) antes de preparar a entrada.", "error")
        return redirect(url_for("pi_entrada.verificar", id_entrada=id_entrada))
    ctx = v["ctx"]
    montado = rascunho.montar(entrada["json_revisado"], cliente_id=ctx.get("cliente_id"), agencia_id=ctx.get("agencia_id"),
                              executivo_id=ctx.get("executivo_id") or entrada.get("id_executivo") or _usuario(),
                              cotacao=v["cotacao"], entrada_id=id_entrada)
    repositorio.aprovar(id_entrada, _usuario(), montado)
    return redirect(url_for("pi_entrada.ver_rascunho", id_entrada=id_entrada))


@bp.route("/<int:id_entrada>/rascunho")
@centralcomm_required
def ver_rascunho(id_entrada):
    entrada = _entrada_ou_404(id_entrada)
    if not entrada.get("rascunho"):
        return redirect(url_for("pi_entrada.verificar", id_entrada=id_entrada))
    return render_template("pi_entrada/rascunho.html", entrada=entrada, rascunho=entrada["rascunho"])
