"""CRM v3 — rotas de API e página.

Fase 3 (auth): todas as rotas exigem sessão. A página `/crm-v3/` usa
`@login_required` (redireciona para /login); os endpoints `/crm-v3/api/*` usam
`@login_required_api` (retornam 401 JSON) para permitir chamadas fetch.
"""

from flask import Blueprint, g, jsonify, render_template, request, session, url_for

from .auth import admin_required_api, login_required, login_required_api
from .crm_v3_helpers import parse_texto_contatos
from .crm_v3_repository import StoreUnavailable, get_store, store_diagnostic


class _LazyStore:
    """Proxy que resolve o store por request (via Flask `g`).

    Motivos para não segurar `store = get_store()` no import:
    - Se o smoke test falhar durante o boot do worker (banco ainda
      subindo, alguma coluna faltando), o processo travaria em erro
      até restart. Com o proxy, cada request reavalia — a recuperação
      é automática assim que o banco volta.
    - Debug fica mais transparente: o diagnostic é preenchido no request
      atual e reflete o que o usuário está vendo agora.

    Se `get_store()` lançar `StoreUnavailable`, o proxy propaga a
    exceção para o handler que traduz em 503 (nunca mais mascara com
    mock em produção).
    """

    def __getattr__(self, name):
        try:
            if not hasattr(g, "_crm_v3_store"):
                g._crm_v3_store = get_store()
            return getattr(g._crm_v3_store, name)
        except StoreUnavailable:
            # Propaga direto para o @bp.errorhandler(StoreUnavailable) —
            # antes o `except RuntimeError` abaixo capturava por acidente
            # (StoreUnavailable herda de RuntimeError) e tentava resolver
            # o store de novo, gerando confusão nos logs.
            raise
        except RuntimeError:
            # `flask.g` só existe dentro de contexto de request.
            return getattr(get_store(), name)


store = _LazyStore()


def _store_unavailable_response(exc: StoreUnavailable):
    """Traduz `StoreUnavailable` em 503 JSON com o motivo.

    Formato compatível com `_err(...)` mas HTTP 503 (Service Unavailable):
    o frontend detecta e mostra banner "Banco indisponível" em vez de
    renderizar clientes fictícios.
    """
    diag = store_diagnostic()
    return jsonify({
        "success": False,
        "error": "Banco indisponível. O CRM v3 e o CRM legado usam a mesma base — verifique o Postgres.",
        "reason": diag.get("reason"),
        "db_error": diag.get("db_error") or str(exc),
        "store_unavailable": True,
    }), 503

bp = Blueprint("crm_v3", __name__, url_prefix="/crm-v3")


@bp.errorhandler(StoreUnavailable)
def _handle_store_unavailable(exc):
    """Handler central: qualquer rota do CRM v3 que falhar ao acessar
    o banco cai aqui. Para APIs devolvemos 503 JSON; para a página
    HTML renderizamos o `crm_v3.html` com o banner de erro visível
    (o template já trata `store_mode='unavailable'`).
    """
    if request.path.startswith("/crm-v3/api/"):
        return _store_unavailable_response(exc)
    # Página HTML: render sem executivos e com banner de erro.
    diag = store_diagnostic()
    return render_template(
        "crm_v3.html",
        executivos=[],
        usuario_atual=_executivo_from_session(),
        store_mode="unavailable",
        store_diag=diag,
    ), 503


@bp.errorhandler(Exception)
def _handle_any_exception(exc):
    """Handler defensivo (set/2026): converte qualquer erro do CRM v3
    em um 500 informativo E grava o traceback no log da aplicação.

    Antes um 500 do repository podia sumir silenciosamente porque o
    Flask, em produção, esconde tracebacks. Agora todo 500 do CRM v3:
      - vira uma entrada `ERROR` completa em `logs/aicentral.log`
      - retorna JSON com `error_type` (para clientes API)
      - continua renderizando a página com banner de erro (para HTML)

    HTTPExceptions (401, 403, 404) são deixadas passar para o handler
    padrão do Flask — não queremos transformar auth-required em 500.
    """
    from werkzeug.exceptions import HTTPException
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, StoreUnavailable):
        return _handle_store_unavailable(exc)

    import logging
    import traceback as _tb
    tb_str = _tb.format_exc()
    logging.getLogger("aicentral.crm_v3").error(
        "[crm_v3] 500 em %s %s: %s\n%s",
        request.method, request.path, exc, tb_str,
    )
    # Também escreve no stderr — durante `python3 run.py` em dev o
    # traceback aparece direto no terminal do Flask.
    import sys as _sys
    print(f"[crm_v3] 500 em {request.method} {request.path}: {exc}", file=_sys.stderr)
    print(tb_str, file=_sys.stderr)

    is_admin = session.get("user_type") in ("admin", "superadmin")
    if request.path.startswith("/crm-v3/api/"):
        payload = {
            "success": False,
            "error": "Erro interno no CRM v3. Verifique os logs.",
            "error_type": type(exc).__name__,
        }
        if is_admin:
            # Para admin, incluímos a mensagem exata e a última linha do
            # traceback para diagnosticar sem abrir o log do gunicorn.
            payload["error_message"] = str(exc)[:500]
            payload["traceback_tail"] = "\n".join(tb_str.splitlines()[-8:])
        return jsonify(payload), 500

    # Página HTML: renderiza com banner de erro. Reaproveita o mesmo
    # template usado quando o banco está indisponível.
    diag = store_diagnostic()
    diag = dict(diag)
    diag["db_error"] = f"{type(exc).__name__}: {str(exc)[:240]}"
    return render_template(
        "crm_v3.html",
        executivos=[],
        usuario_atual=_executivo_from_session(),
        store_mode="unavailable",
        store_diag=diag,
    ), 500


def _executivo_from_session():
    """Retorna dict {'id', 'nome'} do usuário logado, ou defaults do mock.

    Usado como executivo/responsável padrão em criação de atividade/objetivo/nota.
    """
    return {
        "id": session.get("user_id"),
        "nome": session.get("user_name") or session.get("user_email") or "Executivo",
    }


def _can_access_crm_v3():
    """Regra mínima de acesso: precisa ter sessão. Restringir por is_centralcomm
    ou tipo de usuário é feito na camada de repositório (Fase 3).
    """
    return "user_id" in session


def _ok(data=None, **extra):
    body = {"success": True}
    if data is not None:
        body["data"] = data
    body.update(extra)
    return jsonify(body)


def _err(message, status=400):
    return jsonify({"success": False, "error": message}), status


@bp.route("/")
@login_required
def crm_v3():
    # Executivos reais para o combo do topo. Ver docs/crm-v3-api.md.
    # Falha em silêncio (lista vazia) se o Postgres não estiver acessível —
    # o template ainda renderiza e o usuário só vê "Executivo: todos".
    executivos = []
    try:
        from . import db as _db  # import lazy para permitir ambientes sem libpq
        executivos = _db.obter_vendedores_centralcomm() or []
    except Exception:  # noqa: BLE001 — best effort para não quebrar a página
        executivos = []
    # Usuário logado é o executivo "default" do combo. O JS usa esse valor
    # para pré-selecionar a base de clientes dele quando não há preferência
    # anterior no localStorage.
    usuario_atual = _executivo_from_session()
    # Força o proxy a resolver o store agora, para preencher o
    # diagnostic (mode/reason) já disponível no primeiro render.
    try:
        store.list_clientes  # noqa: B018 — acessa lazy pra disparar smoke test
    except Exception:  # noqa: BLE001
        pass
    diag = store_diagnostic()
    return render_template(
        "crm_v3.html",
        executivos=executivos,
        usuario_atual=usuario_atual,
        store_mode=diag.get("mode") or "unknown",
        store_diag=diag,
    )


@bp.route("/api/_debug/store")
@admin_required_api
def api_debug_store():
    """Retorna o diagnóstico atual do store do CRM v3.

    Uso: abrir /crm-v3/api/_debug/store logado como admin para saber se
    o CRM está servindo dados do banco real ou do mock, e por quê.
    A intenção é dar ao time comercial/operações uma resposta imediata
    quando aparecem "clientes fictícios" na tela em vez de investigar
    logs do gunicorn.
    """
    # Força uma resolução fresca (não pega o cache do request atual).
    fresh = get_store()
    diag = store_diagnostic()
    sample = []
    try:
        clientes = fresh.list_clientes() or []
        sample = [
            {
                "id": c.get("id"),
                "nome": c.get("nome"),
                "responsavel": c.get("responsavel"),
            }
            for c in clientes[:3]
        ]
    except Exception as e:  # noqa: BLE001
        diag["list_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    return _ok(diag, sample=sample, total_sample=len(sample))


@bp.route("/api/clientes")
@login_required_api
def api_clientes():
    clientes = store.list_clientes()
    return _ok(clientes, clientes=clientes)


@bp.route("/api/lookups")
@login_required_api
def api_lookups():
    """Agregador dos combos "de dominio" usados pelos drawers/modais.

    Consolidação de set/2026: antes cada combo estava hardcoded no
    template (tipos, UF, executivos "Luisa Santana", etc.). Agora um
    único GET traz tudo em uma resposta cacheável no cliente.

    Response:
      { tipos_cliente, estados, setores, cargos, executivos,
        plataformas, classificacoes }
    """
    data = store.list_lookups()
    # Achata tudo no root do body (`body.tipos_cliente`, etc). O JS
    # lê direto sem indireção — vale para todos os drawers/modais.
    return _ok(**data)


@bp.route("/api/agencias")
@login_required_api
def api_agencias():
    """Lista TODAS as agências reais da base (não paginado).

    Usada pelo drawer 'Editar cliente' → seção "Vínculos com agência"
    para popular o <select>. Antes o frontend derivava a lista de
    state.clientes (paginado), o que fazia aparecer só 2-3 agências
    mesmo quando a base tinha dezenas.
    """
    agencias = store.list_agencias()
    return _ok(agencias, agencias=agencias)


@bp.route("/api/clientes/<cliente_id>")
@login_required_api
def api_cliente_detail(cliente_id):
    cliente = store.get_cliente(cliente_id)
    if not cliente:
        return _err("Cliente não encontrado", 404)
    return _ok(cliente, cliente=cliente)


@bp.route("/api/agencia/<agencia_id>/clientes")
@login_required_api
def api_agencia_clientes(agencia_id):
    """Lista clientes finais vinculados a uma agência (paridade com /crm)."""
    cliente = store.get_cliente(agencia_id)
    if not cliente:
        return _err("Agência não encontrada", 404)
    if not cliente.get("is_agencia"):
        return _err("Cliente informado não é agência", 400)
    filhos_ids = cliente.get("clientes_finais_ids") or []
    filhos = [store.get_cliente(fid) for fid in filhos_ids]
    filhos = [f for f in filhos if f]
    return _ok(filhos, clientes=filhos, total=len(filhos))


@bp.route("/api/clientes", methods=["POST"])
@login_required_api
def api_create_cliente():
    try:
        data = request.get_json(silent=True) or {}
        cliente = store.create_cliente(data)
        return _ok(cliente, cliente=cliente), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/clientes/<cliente_id>", methods=["PATCH"])
@login_required_api
def api_update_cliente(cliente_id):
    try:
        cliente = store.update_cliente(cliente_id, request.get_json(silent=True) or {})
        if cliente is None:
            return _err("Cliente não encontrado", 404)
        return _ok(cliente, cliente=cliente)
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/clientes/<cliente_id>/contatos")
@login_required_api
def api_contatos(cliente_id):
    contatos = store.list_contatos(cliente_id)
    if contatos is None:
        return _err("Cliente não encontrado", 404)
    return _ok(contatos, contatos=contatos)


@bp.route("/api/clientes/<cliente_id>/contatos", methods=["POST"])
@login_required_api
def api_create_contato(cliente_id):
    try:
        data = request.get_json(silent=True) or {}
        contato = store.create_contato(cliente_id, data)
        if contato is None:
            return _err("Cliente não encontrado", 404)
        return _ok(contato, contato=contato), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/contatos/<contato_id>", methods=["PATCH"])
@login_required_api
def api_update_contato(contato_id):
    data = request.get_json(silent=True) or {}
    contato, cliente_id = store.update_contato(contato_id, data)
    if not contato:
        return _err("Contato não encontrado", 404)
    return _ok(contato, contato=contato, cliente_id=cliente_id)


@bp.route("/api/clientes/<cliente_id>/atividades")
@login_required_api
def api_atividades(cliente_id):
    items = store.list_atividades(cliente_id)
    if items is None:
        return _err("Cliente não encontrado", 404)
    return _ok(items, atividades=items)


@bp.route("/api/clientes/<cliente_id>/atividades", methods=["POST"])
@login_required_api
def api_create_atividade(cliente_id):
    try:
        data = request.get_json(silent=True) or {}
        ativ = store.create_atividade(cliente_id, data)
        if ativ is None:
            return _err("Cliente não encontrado", 404)
        return _ok(ativ, atividade=ativ), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/atividades/<atividade_id>", methods=["PATCH"])
@login_required_api
def api_update_atividade(atividade_id):
    try:
        data = request.get_json(silent=True) or {}
        ativ, cliente_id = store.update_atividade(atividade_id, data)
        if not ativ:
            return _err("Atividade não encontrada", 404)
        return _ok(ativ, atividade=ativ, cliente_id=cliente_id)
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/atividades/<atividade_id>", methods=["DELETE"])
@login_required_api
def api_delete_atividade(atividade_id):
    ok, cliente_id = store.delete_atividade(atividade_id)
    if not ok:
        return _err("Atividade não encontrada", 404)
    return _ok(cliente_id=cliente_id)


@bp.route("/api/clientes/<cliente_id>/objetivos")
@login_required_api
def api_objetivos(cliente_id):
    items = store.list_objetivos(cliente_id)
    if items is None:
        return _err("Cliente não encontrado", 404)
    return _ok(items, objetivos=items)


@bp.route("/api/clientes/<cliente_id>/objetivos", methods=["POST"])
@login_required_api
def api_create_objetivo(cliente_id):
    try:
        objetivo = store.create_objetivo(cliente_id, request.get_json(silent=True) or {})
        if objetivo is None:
            return _err("Cliente não encontrado", 404)
        return _ok(objetivo, objetivo=objetivo), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/objetivos/<objetivo_id>", methods=["PATCH"])
@login_required_api
def api_update_objetivo(objetivo_id):
    try:
        objetivo, cliente_id = store.update_objetivo(
            objetivo_id, request.get_json(silent=True) or {}
        )
        if objetivo is None:
            return _err("Objetivo não encontrado", 404)
        return _ok(objetivo, objetivo=objetivo, cliente_id=cliente_id)
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/objetivos/<objetivo_id>", methods=["DELETE"])
@login_required_api
def api_delete_objetivo(objetivo_id):
    ok, cliente_id = store.delete_objetivo(objetivo_id)
    if not ok:
        return _err("Objetivo não encontrado", 404)
    return _ok(cliente_id=cliente_id)


@bp.route("/api/clientes/<cliente_id>/cotacoes")
@login_required_api
def api_cotacoes(cliente_id):
    items = store.list_cotacoes(cliente_id)
    if items is None:
        return _err("Cliente não encontrado", 404)
    return _ok(items, cotacoes=items)


@bp.route("/api/clientes/<cliente_id>/cotacoes", methods=["POST"])
@login_required_api
def api_create_cotacao(cliente_id):
    """Cria o cabeçalho da cotação (Caminho A).

    Após criar, devolvemos `redirect_url` apontando para a tela dedicada
    de montagem (`/cotacoes/<id>/detalhes`), onde o usuário completa
    audiência, produtos, valores e comissões. O CRM v3 usa esse campo
    para abrir a próxima etapa em nova aba quando o usuário escolhe
    "Salvar e montar cotação".
    """
    try:
        cotacao = store.create_cotacao(cliente_id, request.get_json(silent=True) or {})
        if cotacao is None:
            return _err("Cliente não encontrado", 404)
        redirect_url = None
        cot_id = cotacao.get("id") if isinstance(cotacao, dict) else None
        if cot_id:
            try:
                # Rota do módulo legado — mantém a URL estável independente
                # de refactors internos do CRM v3.
                redirect_url = url_for(
                    "cotacoes.cotacao_detalhes", cotacao_id=cot_id
                )
            except Exception:  # noqa: BLE001 — rota ausente em testes/dev sem blueprint
                redirect_url = f"/cotacoes/{cot_id}/detalhes"
            cotacao["detalhes_url"] = redirect_url
        payload = {"cotacao": cotacao}
        if redirect_url:
            payload["redirect_url"] = redirect_url
        return _ok(cotacao, **payload), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/cotacoes/<cotacao_id>", methods=["PATCH"])
@login_required_api
def api_update_cotacao(cotacao_id):
    try:
        cotacao, cliente_id = store.update_cotacao(
            cotacao_id, request.get_json(silent=True) or {}
        )
        if cotacao is None:
            return _err("Cotação não encontrada", 404)
        return _ok(cotacao, cotacao=cotacao, cliente_id=cliente_id)
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/cotacoes/<cotacao_id>", methods=["DELETE"])
@login_required_api
def api_delete_cotacao(cotacao_id):
    ok, cliente_id = store.delete_cotacao(cotacao_id)
    if not ok:
        return _err("Cotação não encontrada", 404)
    return _ok(cliente_id=cliente_id)


@bp.route("/api/clientes/<cliente_id>/notas")
@login_required_api
def api_notas(cliente_id):
    notas = store.list_notas(cliente_id)
    if notas is None:
        return _err("Cliente não encontrado", 404)
    return _ok(notas, notas=notas)


@bp.route("/api/clientes/<cliente_id>/notas", methods=["POST"])
@login_required_api
def api_create_nota(cliente_id):
    try:
        nota = store.create_nota(cliente_id, request.get_json(silent=True) or {})
        if nota is None:
            return _err("Cliente não encontrado", 404)
        return _ok(nota, nota=nota), 201
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/notas/<nota_id>", methods=["PATCH"])
@login_required_api
def api_update_nota(nota_id):
    try:
        nota, cliente_id = store.update_nota(nota_id, request.get_json(silent=True) or {})
        if nota is None:
            return _err("Nota não encontrada", 404)
        return _ok(nota, nota=nota, cliente_id=cliente_id)
    except ValueError as e:
        return _err(str(e))


@bp.route("/api/notas/<nota_id>", methods=["DELETE"])
@login_required_api
def api_delete_nota(nota_id):
    ok, cliente_id = store.delete_nota(nota_id)
    if not ok:
        return _err("Nota não encontrada", 404)
    return _ok(cliente_id=cliente_id)


@bp.route("/api/contatos/parse-texto", methods=["POST"])
@login_required_api
def api_parse_texto():
    data = request.get_json(silent=True) or {}
    texto = data.get("texto") or ""
    contatos = parse_texto_contatos(texto)
    return _ok(contatos, contatos=contatos, message="" if contatos else "Nenhum contato reconhecido no texto.")


@bp.route("/api/clientes/<cliente_id>/contatos/importar", methods=["POST"])
@login_required_api
def api_import_contatos(cliente_id):
    try:
        data = request.get_json(silent=True) or {}
        rows = data.get("contatos") or []
        if not rows:
            return _err("Nenhum contato para importar")
        created = store.import_contatos(cliente_id, rows)
        if created is None:
            return _err("Cliente não encontrado", 404)
        return _ok(created, importados=len(created), contatos=created)
    except ValueError as e:
        return _err(str(e))


# =============================================================================
# IA — Fase 3
# -----------------------------------------------------------------------------
# Rotas /crm-v3/api/ia/* usam OpenRouter (Gemini) via `_call_openrouter` do
# módulo real `crm.ia_routes`. Se `OPENROUTER_API_KEY` estiver ausente ou a
# chamada falhar por qualquer motivo, caímos em fallback determinístico para
# preservar a experiência (útil em dev/testes offline). Nada de mock silencioso:
# quando o fallback é usado, a resposta traz `source: 'fallback'`.
# =============================================================================

import os
from datetime import date, timedelta


def _openrouter_available() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def _call_openrouter(system_prompt: str, user_content: str, max_tokens: int = 1000, temperature: float = 0.7):
    """Wrapper defensivo em torno de `crm.ia_routes._call_openrouter`.

    Retorna a string de resposta ou levanta a exceção original. Evita duplicar
    a lógica HTTP: reaproveitamos o mesmo cliente OpenRouter do CRM oficial.
    """
    from .crm.ia_routes import _call_openrouter as _real_call  # type: ignore
    return _real_call(system_prompt, user_content, max_tokens=max_tokens, temperature=temperature)


@bp.route("/api/ia/melhorar-texto", methods=["POST"])
@login_required_api
def api_ia_melhorar_texto():
    data = request.get_json(silent=True) or {}
    texto = (data.get("descricao") or data.get("texto") or "").strip()
    if not texto:
        return _err("Envie um texto para melhorar", 400)

    if _openrouter_available():
        system_prompt = (
            "Você é um assistente comercial. Receba o texto do executivo de vendas "
            "sobre uma interação com cliente e:\n"
            "1. Corrija erros de português\n"
            "2. Amplie brevemente mantendo o sentido original\n"
            "3. Mantenha tom profissional e objetivo\n"
            "4. Não invente informações que não estão no texto original\n"
            "Retorne apenas o texto melhorado, sem explicações."
        )
        try:
            resultado = _call_openrouter(system_prompt, texto)
            return _ok({"texto": resultado, "texto_melhorado": resultado, "source": "openrouter"})
        except Exception:  # pragma: no cover — cai no fallback
            pass

    # Fallback determinístico: normaliza pontuação e adiciona call-to-action
    aprimorado = texto.rstrip(".") + "."
    aprimorado = aprimorado[:1].upper() + aprimorado[1:]
    if "próximos passos" not in aprimorado.lower():
        aprimorado += "\n\nPróximos passos: alinhar cronograma, confirmar orçamento e agendar retorno."
    return _ok({"texto": aprimorado, "texto_melhorado": aprimorado, "source": "fallback"})


@bp.route("/api/ia/sugerir-atividade", methods=["POST"])
@login_required_api
def api_ia_sugerir_atividade():
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id") or ""
    cliente = store.get_cliente(cliente_id) if cliente_id else None

    if _openrouter_available() and cliente:
        try:
            import json as json_mod
            contatos = store.list_contatos(cliente_id) or []
            contatos_str = ", ".join(
                f"{c.get('nome') or ''} ({c.get('cargo') or 'sem cargo'})" for c in contatos[:5]
            ) if contatos else "Nenhum contato"
            atividades = store.list_atividades(cliente_id) or []
            ultimas_str = "\n".join(
                f"- [{a.get('status')}] {a.get('titulo') or a.get('descricao')}" for a in atividades[:5]
            ) if atividades else "Sem atividades recentes"
            contexto = (
                f"Cliente: {cliente.get('nome')}\n"
                f"Classificação: {cliente.get('classificacao_cliente') or 'Prospecção'}\n"
                f"Contatos: {contatos_str}\n"
                f"Últimas atividades:\n{ultimas_str}"
            )
            system_prompt = (
                "Você é um assistente comercial da CENTRALCOMM (mídia digital).\n"
                "Com base no contexto do cliente, sugira UMA atividade de acompanhamento.\n"
                "Responda APENAS em JSON com: {\"tipo\": \"...\", \"titulo\": \"...\", \"descricao\": \"...\", \"prioridade\": \"Alta|Média|Baixa\"}\n"
                "Tipos válidos: ligacao, almoco, reuniao, projeto, planejamento, cadu, atividade\n"
                "Seja breve e prático."
            )
            resp = _call_openrouter(system_prompt, contexto, max_tokens=300, temperature=0.7).strip()
            if resp.startswith("```"):
                resp = resp.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            sugestao = json_mod.loads(resp)
            hoje = date.today()
            delta = {"Prospecção": 1, "Ativo": 3, "Geladeira": 14}.get(
                cliente.get("classificacao_cliente") or "Prospecção", 2
            )
            sugestao.setdefault("data_sugerida", (hoje + timedelta(days=delta)).isoformat())
            sugestao["source"] = "openrouter"
            return _ok(sugestao)
        except Exception:  # pragma: no cover
            pass

    # Fallback determinístico
    classificacao = (cliente or {}).get("classificacao_cliente") or "Prospecção"
    responsavel = (cliente or {}).get("responsavel") or "Executivo"
    hoje = date.today()
    delta = {"Prospecção": 1, "Ativo": 3, "Geladeira": 14}.get(classificacao, 2)
    sugestao = {
        "titulo": "Alinhamento comercial com " + ((cliente or {}).get("nome") or "cliente"),
        "descricao": (
            f"Retomar contato com o cliente ({classificacao}). "
            f"Confirmar cadência de acompanhamento e próximos entregáveis. "
            f"Responsável sugerido: {responsavel}."
        ),
        "tipo": "ligacao" if classificacao != "Ativo" else "reuniao",
        "prioridade": "Alta" if classificacao == "Prospecção" else "Média",
        "data_sugerida": (hoje + timedelta(days=delta)).isoformat(),
        "source": "fallback",
    }
    return _ok(sugestao)


@bp.route("/api/ia/touchpoints", methods=["POST"])
@login_required_api
def api_ia_touchpoints():
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id") or ""
    cliente = store.get_cliente(cliente_id) if cliente_id else None

    if _openrouter_available() and cliente:
        try:
            import json as json_mod
            nome_cliente = cliente.get("nome") or "cliente"
            classificacao = cliente.get("classificacao_cliente") or "Prospecção"
            contexto = (
                f"Cliente: {nome_cliente}\n"
                f"Classificação: {classificacao}\n"
                f"Responsável: {cliente.get('responsavel') or 'Executivo'}\n"
            )
            system_prompt = (
                "Você é um estrategista de cadência comercial (estilo Pipedrive/Outreach).\n"
                "Gere uma sequência de 4 touchpoints com dias (D+1, D+3, D+7, D+14 para prospecção; "
                "D+7, D+14, D+30 para clientes ativos; D+14, D+45, D+90 para geladeira).\n"
                "Ajuste a cadência conforme a classificação do cliente.\n"
                "Responda APENAS em JSON: {\"touchpoints\":[{\"titulo\":\"...\",\"descricao\":\"...\",\"tipo\":\"email|whatsapp|ligacao|reuniao\",\"prioridade\":\"Alta|Média|Baixa\",\"dias\":N}]}"
            )
            resp = _call_openrouter(system_prompt, contexto, max_tokens=800, temperature=0.6).strip()
            if resp.startswith("```"):
                resp = resp.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            parsed = json_mod.loads(resp)
            hoje = date.today()
            for tp in parsed.get("touchpoints", []):
                dias = int(tp.pop("dias", 1) or 1)
                tp["data_sugerida"] = (hoje + timedelta(days=dias)).isoformat()
                tp.setdefault("hora", "09:00")
            parsed["classificacao"] = classificacao
            parsed["source"] = "openrouter"
            return _ok(**parsed)
        except Exception:  # pragma: no cover
            pass

    classificacao = (cliente or {}).get("classificacao_cliente") or "Prospecção"
    cadencia = {
        "Prospecção": [1, 3, 7, 14],
        "Ativo": [7, 14, 30],
        "Geladeira": [14, 45, 90],
    }.get(classificacao, [1, 3, 7, 14])
    tipos = ["email", "whatsapp", "ligacao", "reuniao"]
    hoje = date.today()
    nome_cliente = (cliente or {}).get("nome") or "cliente"
    touchpoints = []
    for idx, dias in enumerate(cadencia):
        touchpoints.append(
            {
                "titulo": f"Touchpoint #{idx + 1} — {nome_cliente}",
                "descricao": f"D+{dias}: manter cliente aquecido e mover para próximo estágio.",
                "tipo": tipos[idx % len(tipos)],
                "prioridade": "Média",
                "data_sugerida": (hoje + timedelta(days=dias)).isoformat(),
                "hora": "09:00",
            }
        )
    return _ok({"touchpoints": touchpoints, "classificacao": classificacao, "source": "fallback"})


@bp.route("/api/ia/gerar-comunicacao", methods=["POST"])
@login_required_api
def api_ia_gerar_comunicacao():
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id") or ""
    cliente = store.get_cliente(cliente_id) if cliente_id else None
    tipo = (data.get("tipo") or "email").strip().lower()
    tamanho = (data.get("tamanho") or "medio").strip().lower()
    objetivo = (data.get("objetivo") or "").strip()

    contatos = store.list_contatos(cliente_id) or [] if cliente_id else []
    contato_principal = next((c for c in contatos if c.get("principal")), (contatos[0] if contatos else {}))

    if _openrouter_available() and cliente and objetivo:
        try:
            nome_contato = (contato_principal or {}).get("nome") or "responsável"
            cargo_contato = (contato_principal or {}).get("cargo") or "sem cargo definido"
            responsavel = (session.get("user_name") or cliente.get("responsavel") or "Equipe CentralComm").strip()
            system_prompt = (
                "Você é um redator comercial da CENTRALCOMM, empresa de operação de mídia digital.\n\n"
                f"Gere uma mensagem {tipo} de tamanho {tamanho} para o contato "
                f"{nome_contato} ({cargo_contato}) do cliente {cliente.get('nome')}.\n\n"
                f"Objetivo: {objetivo}\n"
                "Se for WhatsApp: tom direto, pessoal, sem formalidades excessivas. Máximo 3 parágrafos curtos.\n"
                "Se for Email: inclua assunto, saudação, corpo e despedida. Tom profissional mas acessível.\n"
                "Não use emojis excessivos. Seja natural.\n"
                f"Assine como: {responsavel}"
            )
            resultado = _call_openrouter(system_prompt, objetivo, max_tokens=1500)
            # Tentamos separar assunto e corpo se for email
            assunto = None
            mensagem = resultado
            if tipo == "email":
                for line in resultado.splitlines():
                    if line.lower().startswith("assunto:"):
                        assunto = line.split(":", 1)[1].strip()
                        mensagem = resultado.replace(line, "", 1).strip()
                        break
                if not assunto:
                    assunto = f"Follow-up comercial — {cliente.get('nome')}"
            return _ok({
                "assunto": assunto,
                "mensagem": mensagem,
                "tipo": tipo,
                "contato": contato_principal,
                "source": "openrouter",
            })
        except Exception:  # pragma: no cover
            pass

    # Fallback determinístico
    contatos_fb = contatos
    contato_principal = next((c for c in contatos if c.get("principal")), (contatos[0] if contatos else {}))
    nome_cliente = (cliente or {}).get("nome") or "cliente"
    responsavel = (cliente or {}).get("responsavel") or "Executivo CentralX"
    nome_contato = contato_principal.get("nome") if contato_principal else "responsável"
    assunto = f"Follow-up comercial — {nome_cliente}"
    mensagem = (
        f"Olá {nome_contato},\n\n"
        f"Aqui é {responsavel}, da CentralX. Passando para retomar nosso alinhamento "
        f"sobre a agenda comercial da {nome_cliente}. Preparei um resumo dos próximos "
        "passos e gostaria de propor uma rápida reunião para alinharmos prioridades.\n\n"
        "Posso reservar 30 minutos na sua agenda esta semana?\n\n"
        "Abraço,\n"
        f"{responsavel}\nCentralX"
    )
    return _ok({"assunto": assunto, "mensagem": mensagem, "contato": contato_principal, "source": "fallback"})


@bp.route("/api/ia/sugerir-objetivos", methods=["POST"])
@login_required_api
def api_ia_sugerir_objetivos():
    """Sugere 3-5 objetivos comerciais para o próximo mês.

    Paridade com /crm/api/ia/sugerir-objetivos. Cai em fallback determinístico
    se OPENROUTER_API_KEY não estiver definida.
    """
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id") or ""
    cliente = store.get_cliente(cliente_id) if cliente_id else None
    if not cliente:
        return _err("Cliente não encontrado", 404)

    if _openrouter_available():
        try:
            contatos = store.list_contatos(cliente_id) or []
            atividades = store.list_atividades(cliente_id) or []
            contatos_str = ", ".join(
                f"{c.get('nome')} ({c.get('cargo') or 'sem cargo'})" for c in contatos[:10]
            ) if contatos else "Nenhum contato cadastrado"
            atividades_str = "\n".join(
                f"- [{a.get('status')}] {a.get('descricao')}" for a in atividades[:5]
            ) if atividades else "Sem atividades pendentes"
            contexto = (
                f"Cliente: {cliente.get('nome')}\n"
                f"Classificação: {cliente.get('classificacao_cliente') or 'Prospecção'}\n"
                f"Contatos: {contatos_str}\n"
                f"Atividades pendentes:\n{atividades_str}"
            )
            system_prompt = (
                "Você é um consultor comercial da CENTRALCOMM. Sugira 3-5 objetivos "
                "comerciais práticos para o próximo mês, focados em retomar contatos, "
                "apresentar novos produtos e ampliar volume de cotações. Retorne apenas "
                "a lista de objetivos, um por linha, sem numeração."
            )
            resultado = _call_openrouter(system_prompt, contexto)
            objetivos = [o.strip("-• ").strip() for o in resultado.splitlines() if o.strip()]
            return _ok({"objetivos": objetivos, "source": "openrouter"})
        except Exception:  # pragma: no cover
            pass

    # Fallback
    nome = cliente.get("nome") or "cliente"
    objetivos = [
        f"Retomar contato com decisor principal de {nome} nesta semana",
        f"Apresentar portfólio de mídia programática para {nome}",
        f"Levar case de performance similar ao segmento de {nome}",
        f"Agendar reunião de planejamento comercial trimestral com {nome}",
    ]
    return _ok({"objetivos": objetivos, "source": "fallback"})


@bp.route("/api/ia/extrair-contatos", methods=["POST"])
@login_required_api
def api_ia_extrair_contatos():
    """Extrai contatos estruturados de texto livre (paridade com crm/ia_routes)."""
    data = request.get_json(silent=True) or {}
    texto = (data.get("texto") or "").strip()
    if not texto:
        return _err("Texto obrigatório", 400)

    if _openrouter_available():
        try:
            import json as json_mod
            system_prompt = (
                "Você é um extrator de dados de contatos profissionais. "
                "Retorne APENAS um array JSON válido com objetos "
                "{\"nome\":\"...\",\"email\":\"...\",\"telefone\":\"...\",\"telefone2\":\"...\"}. "
                "Nome e email são obrigatórios."
            )
            resp = _call_openrouter(system_prompt, texto, max_tokens=2000, temperature=0.1).strip()
            if resp.startswith("```"):
                resp = resp.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            contatos = json_mod.loads(resp)
            if not isinstance(contatos, list):
                raise ValueError("Resposta da IA não é um array JSON")
            limpos = []
            for c in contatos:
                nome = (c.get("nome") or "").strip()
                email = (c.get("email") or "").strip().lower()
                if nome and email and "@" in email:
                    limpos.append({
                        "nome": nome,
                        "email": email,
                        "telefone": (c.get("telefone") or "").strip(),
                        "telefone2": (c.get("telefone2") or "").strip(),
                    })
            return _ok({"contatos": limpos, "source": "openrouter"})
        except Exception:  # pragma: no cover
            pass

    # Fallback: usa o parser determinístico local
    contatos = parse_texto_contatos(texto)
    return _ok({"contatos": contatos, "source": "fallback"})
