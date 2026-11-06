"""Admin interno das estratégias (Parâmetros > Estratégias de mídia)."""

from __future__ import annotations

from flask import abort, jsonify, render_template, request, session

from ..auth import admin_required, admin_required_api
from . import catalogo, estimativa, repositorio, visao


def _ok(data=None, status=200):
    return jsonify({"success": True, "data": data}), status


def _erro(msg, status=400):
    return jsonify({"success": False, "error": msg}), status


def _meta() -> dict:
    canais = visao.canais_catalogo()
    return {
        "canais": [{"slug": s, **c} for s, c in sorted(canais.items(), key=lambda kv: (kv[1].get("categoria") or "", kv[1]["nome"]))],
        "nos": [{"slug": s, **n} for s, n in catalogo.NOS_FLUXO.items()],
        "padrao": {s: {"formatos": f, "otimizacoes": o} for s, (f, o) in catalogo.PADRAO_CANAL.items()},
        "minimos": catalogo.MINIMO_CANAL, "objetivos": catalogo.OBJETIVOS, "papeis": list(catalogo.PAPEIS),
        "destinos": catalogo.DESTINOS, "fontes": list(catalogo.FONTES_KPI), "faixas": list(catalogo.FAIXAS),
    }


def _vazia() -> dict:
    return {"id": None, "slug": "", "nome": "", "objetivo": "consideracao", "resumo": "", "verba_minima": 10_000,
            "ativo": False, "ordem": 500, "descricao": "", "duracao": "30 dias", "publico": "", "cena": "", "como_escala": "",
            "canais": [], "fluxo": [{"titulo": "Alcance", "descricao": "", "nos": []}, {"titulo": "Conversão", "descricao": "", "nos": []}],
            "conversao": {"destino": "site", "precisa_link": False, "descricao": "", "eventos": []},
            "remarketing": {"usa": True, "publicos": [], "janela_dias": 30, "descricao": ""},
            "lista_clientes": {"usa": False, "usos": [], "requisito": ""},
            "criativos": [], "kpis": [], "otimizacoes": [],
            "efeitos": [{"fase": "Semanas 1 e 2", "texto": ""}, {"fase": "Semanas 3 e 4", "texto": ""}, {"fase": "Depois do 1º mês", "texto": ""}]}


def register_estrategias_admin_routes(bp):
    @bp.route("/estrategias")
    @admin_required
    def estrategias_lista():
        todas, do_banco = repositorio.listar(somente_ativas=False)
        canais = visao.canais_catalogo()
        linhas = []
        for e in todas:
            c = visao.cartao(e, canais)
            c.update({"ativo": e.get("ativo", True), "ordem": e.get("ordem"), "n_kpis": len(e.get("kpis") or []),
                      "n_pecas": sum(int(p.get("quantidade") or 1) for p in e.get("criativos") or []),
                      "n_imagens": len(visao.imagens(e["slug"])), "atualizado_em": e.get("atualizado_em")})
            linhas.append(c)
        return render_template("parametros/estrategias_lista.html", linhas=linhas, do_banco=do_banco,
                               objetivos=catalogo.OBJETIVOS, aviso_tabela=repositorio.TABELA_AUSENTE)

    @bp.route("/estrategias/nova")
    @bp.route("/estrategias/<int:estrategia_id>")
    @admin_required
    def estrategias_editar(estrategia_id=None):
        _, do_banco = repositorio.listar(somente_ativas=False)
        if estrategia_id:
            e = repositorio.obter(estrategia_id, somente_ativas=False)
            if not e:
                abort(404)
        else:
            base = request.args.get("de", type=int)
            e = repositorio.obter(base, somente_ativas=False) if base else None
            if e:
                e = dict(e, id=None, slug=e["slug"] + "-copia", nome=e["nome"] + " (cópia)", ativo=False)
            else:
                e = _vazia()
        e.pop("atualizado_em", None)
        return render_template("parametros/estrategias_form.html", estrategia=e, meta=_meta(), do_banco=do_banco,
                               imagens=visao.imagens(e["slug"]) if e.get("slug") else [],
                               aviso_tabela=repositorio.TABELA_AUSENTE)

    @bp.route("/api/estrategias", methods=["POST"])
    @bp.route("/api/estrategias/<int:estrategia_id>", methods=["PUT"])
    @admin_required_api
    def estrategias_salvar(estrategia_id=None):
        try:
            e = repositorio.normalizar(request.get_json(silent=True) or {}, visao.slugs_validos())
            novo_id = repositorio.salvar(e, estrategia_id, session.get("user_id"))
        except repositorio.EstrategiaInvalida as exc:
            return _erro(str(exc))
        except repositorio.TabelaAusente as exc:
            return _erro(str(exc), 409)
        return _ok({"id": novo_id}, 200 if estrategia_id else 201)

    @bp.route("/api/estrategias/<int:estrategia_id>/ativo", methods=["POST"])
    @admin_required_api
    def estrategias_ativo(estrategia_id):
        try:
            return _ok({"ativo": repositorio.alternar_ativo(estrategia_id, session.get("user_id"))})
        except repositorio.TabelaAusente as exc:
            return _erro(str(exc), 409)

    @bp.route("/api/estrategias/previa", methods=["POST"])
    @admin_required_api
    def estrategias_previa():
        """Divisão por faixa para o editor, sem gravar. Aceita a estratégia incompleta."""
        corpo = request.get_json(silent=True) or {}
        canais = []
        for c in corpo.get("canais") or []:
            try:
                canais.append({"slug": str(c.get("slug") or ""), "papel": str(c.get("papel") or ""),
                               "peso": max(0, min(100, int(float(c.get("peso") or 0)))),
                               "essencial": bool(c.get("essencial")),
                               "minimo": None if c.get("minimo") in (None, "") else max(0, int(float(c["minimo"])))})
            except (TypeError, ValueError):
                continue
        try:
            verba_minima = int(corpo.get("verba_minima") or catalogo.FAIXAS[0])
        except (TypeError, ValueError):
            verba_minima = catalogo.FAIXAS[0]
        nomes = visao.canais_catalogo()
        faixas = []
        for f in catalogo.tabela_faixas(canais, verba_minima):
            faixas.append({"verba": f["verba"], "rotulo": catalogo.brl_curto(f["verba"]), "disponivel": f["disponivel"],
                           "linhas": [{"slug": l["slug"], "valor": l["valor"], "pct": l["pct"]} for l in f["linhas"]],
                           "fora": f["fora"]})
        return _ok({"faixas": faixas, "escala": visao.escala_texto(canais, verba_minima, nomes)})

    @bp.route("/estrategias/benchmarks")
    @admin_required
    def estrategias_benchmarks():
        atual = estimativa.parametros()
        canais = visao.canais_catalogo()
        linhas = [{"slug": s, "nome": (canais.get(s) or {}).get("nome", s), "logo": (canais.get(s) or {}).get("logo", ""),
                   "valores": atual["benchmarks"][s], "padrao": list(estimativa.BENCHMARKS[s])}
                  for s in sorted(estimativa.BENCHMARKS, key=lambda s: (canais.get(s) or {}).get("nome", s))]
        conv = [{"chave": k, "rotulo": estimativa.ROTULO_CONVERSAO.get(k, k), "valores": atual["conversao"][k],
                 "padrao": list(estimativa.CONVERSAO[k])} for k in estimativa.CONVERSAO]
        return render_template("parametros/estrategias_benchmarks.html", linhas=linhas, conv=conv,
                               quantis=estimativa.QUANTIS, aviso_tabela=repositorio.TABELA_AUSENTE)

    @bp.route("/api/estrategias/parametros", methods=["PUT"])
    @admin_required_api
    def estrategias_parametros_salvar():
        try:
            dados = estimativa.validar_parametros(request.get_json(silent=True) or {})
            repositorio.salvar_parametros("benchmarks", dados["benchmarks"], session.get("user_id"))
            repositorio.salvar_parametros("conversao", dados["conversao"], session.get("user_id"))
        except ValueError as exc:
            return _erro(str(exc))
        except repositorio.TabelaAusente as exc:
            return _erro(str(exc), 409)
        estimativa.limpar_cache()
        return _ok({"ok": True})
