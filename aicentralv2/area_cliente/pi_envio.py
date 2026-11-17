"""Enviar PI pelo hub de mídia: o cliente (ou a agência) arrasta o PDF, o hub lê, mostra o que entendeu e segue para o executivo.

É a ponta simples da Entrada de PI (``aicentralv2/pi_entrada``): a leitura é a mesma, mas o cliente só vê o resumo permitido
(``pi_entrada.hub``). Quem confere tudo e dá andamento, manualmente, é o executivo, na tela da equipe. Nenhuma entrada vira PI
por aqui. Plano: docs/plans/hub-de-midia-pi-briefing-onboarding.md (seções 3 e 3B).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import abort, current_app, jsonify, redirect, request

logger = logging.getLogger(__name__)
FUSO = ZoneInfo("America/Sao_Paulo")
LIMITE_ARQUIVOS = 5
LIMITE_POR_HORA = 10


def _rotas():
    from . import routes                                     # importação tardia: routes importa este módulo
    return routes


def _so_leitura(usuario) -> bool:
    """Equipe vendo "como cliente" não envia PI em nome dele."""
    return bool(usuario.get("ver_como"))


def _entrada_do_usuario(usuario, uuid_entrada) -> dict:
    from ..pi_entrada import repositorio
    entrada = repositorio.obter_por_uuid(uuid_entrada)
    if not entrada or entrada.get("origem") != "hub" or entrada.get("id_cliente_envio") != usuario["cliente_id"]:
        abort(404)
    return entrada


def _quando(valor) -> str:
    if not valor:
        return ""
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(FUSO).strftime("%d/%m/%Y às %H:%M")


def _whatsapp(usuario, numero_pi="") -> str:
    from . import emails
    motivo = f"Enviei o PI {numero_pi} pelo hub de mídia." if numero_pi else "Quero falar sobre um PI que enviei pelo hub de mídia."
    contato = emails._contato_executivo(usuario.get("executivo"), usuario.get("nome"), usuario.get("cliente_nome"), motivo)
    return (contato or {}).get("whatsapp") or ""


# ---------- enviar ----------

def view_pi_enviar(usuario):
    from ..pi_entrada import cadastro, leitor, repositorio, servico
    r = _rotas()
    if request.method == "GET":
        recentes = repositorio.enviadas_pelo_cliente(usuario["cliente_id"], 8)
        for item in recentes:
            item["quando"] = _quando(item.get("criado_em"))
        return r._render("pi_enviar.html", usuario, "pis", recentes=recentes, so_leitura=_so_leitura(usuario),
                         csrf=r._csrf_token(), limite=LIMITE_ARQUIVOS)

    r._checar_csrf()
    if _so_leitura(usuario):
        return jsonify(ok=False, erro="Você está vendo o hub como cliente: o envio fica desligado."), 403
    arquivos = request.files.getlist("arquivos")
    if not arquivos:
        return jsonify(ok=False, erro="Escolha o PDF do PI."), 400
    if len(arquivos) > LIMITE_ARQUIVOS:
        return jsonify(ok=False, erro=f"Envie até {LIMITE_ARQUIVOS} PDFs por vez."), 400
    if repositorio.contar_envios_recentes(usuario["cliente_id"], 60) + len(arquivos) > LIMITE_POR_HORA:
        return jsonify(ok=False, erro="Muitos envios seguidos. Tente de novo em alguns minutos ou fale com o seu executivo."), 429
    executivo_id = cadastro.executivo_da_conta(usuario["cliente_id"])
    saida = []
    for arquivo in arquivos:
        nome = Path(arquivo.filename or "pi.pdf").name
        conteudo = arquivo.read(leitor.MAX_BYTES + 1)
        if not nome.lower().endswith(".pdf") or conteudo[:5] != b"%PDF-":
            saida.append({"nome": nome, "erro": "Envie o PI em PDF."})
            continue
        if len(conteudo) > leitor.MAX_BYTES:
            saida.append({"nome": nome, "erro": "O PDF passa de 20 MB."})
            continue
        anterior = repositorio.entrada_por_sha(hashlib.sha256(conteudo).hexdigest())
        if anterior:
            existente = repositorio.obter(anterior["id"])
            if existente and existente.get("origem") == "hub" and existente.get("id_cliente_envio") == usuario["cliente_id"]:
                saida.append({"nome": nome, "url": r.area_url("pi_enviado", uuid=existente["uuid"]), "repetido": True})
                continue                                                   # o mesmo PDF já foi enviado por esta conta
        id_entrada = repositorio.criar_entrada("hub", id_cliente_envio=usuario["cliente_id"], id_contato_envio=usuario["user_id"],
                                               id_executivo=executivo_id)
        guardado = servico.guardar_arquivo(id_entrada, nome, conteudo)
        repositorio.registrar_arquivo(id_entrada, nome, guardado["sha256"], guardado["tamanho"], guardado["caminho"])
        servico.iniciar_em_segundo_plano(id_entrada)
        entrada = repositorio.obter(id_entrada)
        saida.append({"nome": nome, "url": r.area_url("pi_enviado", uuid=entrada["uuid"])})
    return jsonify(ok=True, entradas=saida)


# ---------- ver e enviar ao executivo ----------

def view_pi_enviado(usuario, uuid):
    from ..pi_entrada import hub
    r = _rotas()
    entrada = _entrada_do_usuario(usuario, uuid)
    estado = hub.situacao(entrada)
    resumo = hub.resumo_para_cliente(entrada["json_revisado"]) if estado in ("pronto", "enviado") and entrada.get("json_revisado") else None
    numero = (resumo or {}).get("numero_pi") or entrada.get("numero_pi") or ""
    return r._render("pi_enviado.html", usuario, "pis", entrada=entrada, estado=estado, resumo=resumo, numero_pi=numero,
                     whatsapp=_whatsapp(usuario, numero), enviado_quando=_quando(entrada.get("enviado_em")), csrf=r._csrf_token(),
                     so_leitura=_so_leitura(usuario), status_url=r.area_url("pi_enviado_status", uuid=uuid))


def view_pi_enviado_status(usuario, uuid):
    from ..pi_entrada import hub
    entrada = _entrada_do_usuario(usuario, uuid)
    estado = hub.situacao(entrada)
    resposta = jsonify(ok=True, estado=estado, pronto=estado != "lendo")
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


def view_pi_enviado_enviar(usuario, uuid):
    from ..pi_entrada import hub, repositorio
    from . import emails
    r = _rotas()
    r._checar_csrf()
    if _so_leitura(usuario):
        abort(403)
    entrada = _entrada_do_usuario(usuario, uuid)
    destino = r.area_url("pi_enviado", uuid=uuid)
    if hub.situacao(entrada) != "pronto":
        return redirect(destino, code=303)
    mensagem = (request.form.get("mensagem") or "").strip()[:1000]
    if not repositorio.marcar_enviado(entrada["id"], mensagem):
        return redirect(destino, code=303)
    resumo = hub.resumo_para_cliente(entrada["json_revisado"])
    try:
        emails.pi_recebido(usuario, resumo, entrada["id"], mensagem)
        emails.pi_enviado(usuario, resumo)
    except Exception:                                                      # o envio já valeu; e-mail que falha só vai para o log
        current_app.logger.warning("E-mails do PI enviado %s não saíram.", entrada["id"], exc_info=True)
    return redirect(destino + "?enviado=1", code=303)
