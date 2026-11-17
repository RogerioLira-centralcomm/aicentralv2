"""Telas do briefing para cotação no hub: anexar, ver "o que entendi", ajustar e enviar ao executivo (retorno em até 24 h)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from flask import abort, current_app, jsonify, redirect, request

from . import briefing, cotacao, demo

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
    if demo.ativo(usuario["cliente_id"]):
        return _demo_upload(arquivos, r.area_url("briefing_cotacao_rascunho", uuid="__UUID__"), None)
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


def _demo_upload(arquivos, modelo_url, dados_modelo):
    """Demonstração: confere só o tipo do arquivo e simula a leitura na sessão (nada vai ao banco, ao disco ou ao modelo)."""
    nomes = []
    for a in arquivos:
        nome = a.filename.rsplit("/", 1)[-1]
        if "." + nome.rsplit(".", 1)[-1].lower() not in cotacao.TIPOS:
            return jsonify(ok=False, erro="Envie PDF, imagem (PNG, JPG) ou planilha (XLSX, CSV)."), 400
        nomes.append(nome)
    novo = demo.novo_envio("cotacao", nomes)
    r = _rotas()
    if dados_modelo:
        return jsonify(ok=True, uuid=novo, dados_url=r.area_url("briefing_anexo_dados", uuid=novo), nomes=nomes)
    return jsonify(ok=True, entradas=[{"nome": f"{len(nomes)} arquivo(s)", "url": modelo_url.replace("__UUID__", novo)}])


def _demo_rascunho(usuario, uuid):
    """Rascunho de demonstração no mesmo formato do banco (para reaproveitar as telas)."""
    reg = demo.envio("cotacao", uuid)
    if not reg:
        abort(404)
    status = "enviado" if reg.get("enviado_em") else ("lendo" if demo.lendo(reg) else "lido")
    return {"id": 0, "uuid": uuid, "id_cliente": usuario["cliente_id"], "status": status, "arquivos": [{"nome": n} for n in reg["nomes"]],
            "leitura": None if status == "lendo" else demo.LEITURA_COTACAO, "erro": None,
            "atualizado_em": demo.quando(reg["em"]), "prazo_resposta_em": cotacao.prazo_resposta(demo.quando(reg["enviado_em"])) if reg.get("enviado_em") else None}


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
    if demo.ativo(usuario["cliente_id"]) and str(uuid).startswith("demo-"):
        return _render_rascunho(usuario, _demo_rascunho(usuario, uuid))
    return _render_rascunho(usuario, _do_usuario(usuario, uuid))


def view_cotacao_status(usuario, uuid):
    if demo.ativo(usuario["cliente_id"]) and str(uuid).startswith("demo-"):
        estado = cotacao.situacao(_demo_rascunho(usuario, uuid))
    else:
        estado = cotacao.situacao(_do_usuario(usuario, uuid))
    resposta = jsonify(ok=True, estado=estado, pronto=estado != "lendo")
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


def view_cotacao_enviar(usuario, uuid):
    from . import emails
    r = _rotas()
    r._checar_csrf()
    simulado = demo.ativo(usuario["cliente_id"]) and str(uuid).startswith("demo-")
    rascunho = _demo_rascunho(usuario, uuid) if simulado else _do_usuario(usuario, uuid)
    destino = r.area_url("briefing_cotacao_rascunho", uuid=uuid)
    if cotacao.situacao(rascunho) not in ("pronto", "erro"):
        return redirect(destino, code=303)
    valores, erros = briefing.validar(request.form)
    if erros:
        return _render_rascunho(usuario, rascunho, valores={**valores, "pracas_texto": ", ".join(valores.get("pracas") or []),
                                                          "inicio": valores["inicio"].isoformat() if valores.get("inicio") else "",
                                                          "fim": valores["fim"].isoformat() if valores.get("fim") else ""}, erros=erros, status=422)
    if simulado:
        # Demonstração: o briefing "vai" só na sessão; nenhuma linha no banco e nenhum e-mail.
        demo.registrar_briefing(valores)
        demo.marcar_enviado("cotacao", uuid)
        return redirect(destino + "?enviado=1", code=303)
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


# ---------- anexo opcional do briefing de planejamento ----------
# O arquivo só ajuda a preencher: o briefing continua sendo escrito no formulário. Usa o mesmo rascunho e a mesma leitura da cotação.

def rascunho_anexo(usuario, uuid_rascunho):
    """Rascunho de anexo deste cliente, ou None."""
    if not uuid_rascunho:
        return None
    r = cotacao.obter(str(uuid_rascunho)[:40])
    return r if r and r.get("id_cliente") == usuario["cliente_id"] and r.get("status") != "enviado" else None


def view_anexo(usuario):
    r = _rotas()
    r._checar_csrf()
    arquivos = [a for a in request.files.getlist("arquivos") if a and a.filename]
    if not arquivos:
        return jsonify(ok=False, erro="Escolha ao menos um arquivo."), 400
    if len(arquivos) > cotacao.MAX_ARQUIVOS:
        return jsonify(ok=False, erro=f"Envie até {cotacao.MAX_ARQUIVOS} arquivos por vez."), 400
    if demo.ativo(usuario["cliente_id"]):
        return _demo_upload(arquivos, "", True)
    if cotacao.contar_recentes(usuario["cliente_id"], 60) >= LIMITE_POR_HORA:
        return jsonify(ok=False, erro="Muitos envios seguidos. Tente de novo em alguns minutos."), 429
    lidos = []
    for a in arquivos:
        conteudo = a.read(cotacao.MAX_BYTES + 1)
        try:
            lidos.append((a.filename, conteudo, cotacao.validar_arquivo(a.filename, conteudo)))
        except cotacao.CotacaoErro as exc:
            return jsonify(ok=False, erro=str(exc)), 400
    rascunho = cotacao.criar_rascunho(usuario["cliente_id"], usuario["user_id"])
    guardados = [cotacao.guardar(rascunho["id"], n, c, t) for n, c, t in lidos]
    cotacao.definir_arquivos(rascunho["id"], guardados)
    cotacao.iniciar_em_segundo_plano(rascunho["id"], rascunho["uuid"])
    return jsonify(ok=True, uuid=rascunho["uuid"], dados_url=r.area_url("briefing_anexo_dados", uuid=rascunho["uuid"]),
                   nomes=[g["nome"] for g in guardados])


def view_anexo_dados(usuario, uuid):
    rascunho = _demo_rascunho(usuario, uuid) if demo.ativo(usuario["cliente_id"]) and str(uuid).startswith("demo-") else _do_usuario(usuario, uuid)
    estado = cotacao.situacao(rascunho)
    resposta = jsonify(ok=True, estado=estado, pronto=estado != "lendo", leitura=rascunho.get("leitura") or {},
                       erro=rascunho.get("erro") or "", nomes=[a["nome"] for a in rascunho.get("arquivos") or []])
    resposta.headers["Cache-Control"] = "no-store"
    return resposta
