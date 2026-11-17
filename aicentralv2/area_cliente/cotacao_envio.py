"""Telas do briefing para cotação no hub: anexar, ver "o que entendi", ajustar e enviar ao executivo (retorno em até 24 h)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from flask import abort, current_app, jsonify, redirect, request

from . import briefing, cotacao

LIMITE_POR_HORA = 6


def _rotas():
    from . import routes
    return routes


def _do_usuario(usuario, uuid_rascunho) -> dict:
    rascunho = cotacao.obter(uuid_rascunho)
    if not rascunho or rascunho.get("id_cliente") != usuario["cliente_id"]:
        abort(404)
    return rascunho


def _valores_da_leitura(leitura: dict) -> dict:
    v = dict(leitura or {})
    v["pracas_texto"] = ", ".join(v.get("pracas") or [])
    return v


def view_cotacao(usuario):
    r = _rotas()
    if request.method == "GET":
        return r._render("cotacao_enviar.html", usuario, "briefing", csrf=r._csrf_token(),
                         limite=cotacao.MAX_ARQUIVOS, prazo_horas=cotacao.HORAS_PRAZO)
    r._checar_csrf()
    arquivos = [a for a in request.files.getlist("arquivos") if a and a.filename]
    if not arquivos:
        return jsonify(ok=False, erro="Escolha ao menos um arquivo."), 400
    if len(arquivos) > cotacao.MAX_ARQUIVOS:
        return jsonify(ok=False, erro=f"Envie até {cotacao.MAX_ARQUIVOS} arquivos por vez."), 400
    if cotacao.contar_recentes(usuario["cliente_id"], 60) >= LIMITE_POR_HORA:
        return jsonify(ok=False, erro="Muitos envios seguidos. Tente de novo em alguns minutos ou fale com o seu executivo."), 429
    lidos = []
    for a in arquivos:
        nome = a.filename
        conteudo = a.read(cotacao.MAX_BYTES + 1)
        try:
            tipo = cotacao.validar_arquivo(nome, conteudo)
        except cotacao.CotacaoErro as exc:
            return jsonify(ok=False, erro=str(exc)), 400
        lidos.append((nome, conteudo, tipo))
    rascunho = cotacao.criar_rascunho(usuario["cliente_id"], usuario["user_id"])
    guardados = [cotacao.guardar(rascunho["id"], n, c, t) for n, c, t in lidos]
    cotacao.definir_arquivos(rascunho["id"], guardados)
    cotacao.iniciar_em_segundo_plano(rascunho["id"], rascunho["uuid"])
    return jsonify(ok=True, entradas=[{"nome": f"{len(guardados)} arquivo(s)", "url": r.area_url("briefing_cotacao_rascunho", uuid=rascunho["uuid"])}])


def _render_rascunho(usuario, rascunho, *, valores=None, erros=None, status=200):
    r = _rotas()
    estado = cotacao.situacao(rascunho)
    leitura = rascunho.get("leitura") or {}
    resposta = r._render(
        "cotacao_lido.html", usuario, "briefing", rascunho=rascunho, estado=estado, leitura=leitura,
        v=valores if valores is not None else _valores_da_leitura(leitura), erros=erros or {}, csrf=r._csrf_token(),
        canais=briefing.CANAIS, status_url=r.area_url("briefing_cotacao_status", uuid=rascunho["uuid"]),
        enviar_url=r.area_url("briefing_cotacao_enviar", uuid=rascunho["uuid"]), prazo_horas=cotacao.HORAS_PRAZO,
        prazo=cotacao.prazo_texto(rascunho.get("prazo_resposta_em")), enviado=request.args.get("enviado") == "1",
        previsto=cotacao.prazo_texto(cotacao.prazo_resposta()), arquivos=rascunho.get("arquivos") or [])
    resposta.status_code = status
    return resposta


def view_cotacao_rascunho(usuario, uuid):
    return _render_rascunho(usuario, _do_usuario(usuario, uuid))


def view_cotacao_status(usuario, uuid):
    estado = cotacao.situacao(_do_usuario(usuario, uuid))
    resposta = jsonify(ok=True, estado=estado, pronto=estado != "lendo")
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


def view_cotacao_enviar(usuario, uuid):
    from . import emails
    r = _rotas()
    r._checar_csrf()
    rascunho = _do_usuario(usuario, uuid)
    destino = r.area_url("briefing_cotacao_rascunho", uuid=uuid)
    if cotacao.situacao(rascunho) not in ("pronto", "erro"):
        return redirect(destino, code=303)
    valores, erros = briefing.validar(request.form)
    if erros:
        return _render_rascunho(usuario, rascunho, valores={**valores, "pracas_texto": ", ".join(valores.get("pracas") or []),
                                                          "inicio": valores["inicio"].isoformat() if valores.get("inicio") else "",
                                                          "fim": valores["fim"].isoformat() if valores.get("fim") else ""}, erros=erros, status=422)
    arquivos = rascunho.get("arquivos") or []
    leitura = rascunho.get("leitura") or {}
    nomes = [a["nome"] for a in arquivos]
    extras = ["Arquivos anexados: " + ", ".join(nomes)] if nomes else []
    if leitura.get("resumo"):
        extras.append("Leitura automática dos arquivos: " + leitura["resumo"])
    if leitura.get("faltou"):
        extras.append("Não achei nos arquivos: " + "; ".join(leitura["faltou"]))
    valores["descobrir"] = ""
    valores["descricao"] = "\n\n".join(p for p in [valores.get("descricao"), *extras] if p)[:6000]
    prazo = cotacao.prazo_resposta()
    extra = {"modo": "cotacao", "prazo_resposta_em": prazo, "arquivos": [{k: a[k] for k in ("nome", "sha256", "tamanho", "caminho", "tipo")} for a in arquivos],
             "leitura_ia": {**leitura, "rascunho_uuid": rascunho["uuid"]}}
    anterior = cotacao.reservar(rascunho["id"])
    if not anterior:
        return redirect(destino, code=303)                         # outro envio (duplo clique, outra aba) já pegou este rascunho
    try:
        novo_id = briefing.enviar(usuario, valores, extra)
    except Exception:
        cotacao.mudar_status(rascunho["id"], anterior, rascunho.get("erro"))    # nada foi gravado: libera para tentar de novo
        raise
    cotacao.marcar_enviado(rascunho["id"], novo_id, prazo)
    valores["prazo_texto"], valores["anexos"] = cotacao.prazo_texto(prazo), nomes
    try:
        emails.briefing_novo(usuario, valores, novo_id)
        emails.briefing_recebido(usuario, valores)
    except Exception:
        current_app.logger.warning("E-mails do briefing de cotação %s não enviados.", novo_id, exc_info=True)
    return redirect(destino + "?enviado=1", code=303)
