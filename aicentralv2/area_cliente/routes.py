"""Área do Cliente em ``clientes.centralcomm.media``.

O mesmo Flask atende todos os hosts e ``/clientes`` já é a lista interna do
CentralX. Por isso a área não registra regras globais: no host de clientes um
``before_request`` casa o caminho num mapa próprio e chama a view. Fora dele
nada muda. No host de clientes, tudo que não é da área, do login ou estático
devolve 404, então nenhuma rota interna fica alcançável por ali.
"""

from __future__ import annotations

import secrets
import time
from datetime import date
from urllib.parse import urlencode, urlparse

from flask import abort, current_app, redirect, render_template, request, session
from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing import Map, Rule

from . import acesso, briefing, dados, descobrir

ROTAS = Map([
    Rule("/", endpoint="inicio"),
    Rule("/briefing", endpoint="briefing", methods=["GET", "HEAD", "POST"]),
    Rule("/projetos", endpoint="projetos"),
    Rule("/projetos/<int:id_pi>", endpoint="projeto"),
    Rule("/campanhas", endpoint="campanhas"),
    Rule("/descobrir", endpoint="descobrir"),
    Rule("/descobrir/selecao", endpoint="descobrir_selecao", methods=["POST"]),
    Rule("/descobrir/<secao>", endpoint="descobrir_secao"),
    Rule("/descobrir/<secao>/<int:item_id>", endpoint="descobrir_item"),
    Rule("/planejamento", endpoint="planejamento_antigo"),
    Rule("/pis", endpoint="pis"),
    Rule("/pis/<int:id_pi>", endpoint="pi"),
    Rule("/midia", endpoint="midia_antigo"),
    Rule("/relatorios", endpoint="relatorios"),
    Rule("/arquivos", endpoint="arquivos_antigo"),
    Rule("/equipe", endpoint="equipe"),
    Rule("/sair", endpoint="sair"),
    Rule("/ver-como", endpoint="ver_como", methods=["POST"]),
    Rule("/ver-como/sair", endpoint="ver_como_sair", methods=["POST"]),
], strict_slashes=False)

# Rotas do app que continuam valendo no host de clientes: login e seus links
# (senha, cadastro, Google), estáticos. O resto dá 404.
PASSAGEM_EXATA = {"/login", "/logout", "/acesso-confirmado", "/favicon.ico",
                  "/forgot-password", "/signup", "/bem-vindo"}
PASSAGEM_PREFIXO = ("/static/", "/reset-password/", "/auth/")

# Jornada do cliente: Descobrir → Briefing → Projeto (PI fechado) → Campanhas.
NAV_PRINCIPAL = (
    ("inicio", "Início", "home"),
    ("descobrir", "Descobrir", "compass"),
    ("briefing", "Briefing", "send"),
    ("projetos", "Projetos", "folder"),
    ("campanhas", "Campanhas", "megaphone"),
    ("pis", "PIs", "file"),
    ("relatorios", "Relatórios", "chart"),
    ("equipe", "Equipe", "users"),
)

EM_PREPARACAO = {
    "relatorios": ("Relatórios", "chart", "Dashboards de entrega atualizados diariamente e as prestações de contas de cada projeto."),
    "equipe": ("Equipe", "users", "Quem da sua empresa tem acesso a esta área e o time Centralcomm que cuida da sua conta."),
}


def _host_clientes() -> str:
    return (urlparse(str(current_app.config.get("CLIENTES_URL") or "")).hostname or "").lower()


def is_clientes_request() -> bool:
    host = _host_clientes()
    return bool(host) and (request.host.split(":", 1)[0] or "").lower() == host


def area_url(endpoint: str, **values) -> str:
    return ROTAS.bind("clientes").build(endpoint, values)


def _cadu_links():
    from ..product_domains import product_url
    return (
        {"rotulo": "Studio", "icone": "sparkles", "url": product_url("studio", "/")},
        {"rotulo": "MediaSafe", "icone": "shield", "url": "", "em_breve": True},
        {"rotulo": "Flow", "icone": "flow", "url": product_url("connect", "/connect/app/flows")},
        {"rotulo": "Reports", "icone": "chart", "url": product_url("connect", "/connect/app")},
    )


_CACHE_VER_COMO = {"em": 0.0, "ano": None, "dados": []}


def _opcoes_ver_como() -> list[dict]:
    """Clientes e agências com PI validado no ano corrente (cache de 5 minutos)."""
    ano = date.today().year
    if _CACHE_VER_COMO["ano"] != ano or time.time() - _CACHE_VER_COMO["em"] > 300:
        _CACHE_VER_COMO.update(em=time.time(), ano=ano, dados=acesso.clientes_para_ver_como(ano))
    return _CACHE_VER_COMO["dados"]


def _render(template, usuario, ativo, **ctx):
    ativo = "descobrir" if ativo.startswith("descobrir") else ativo
    nav = [
        {"id": e, "rotulo": r, "icone": i, "url": area_url(e), "ativo": e == ativo}
        for e, r, i in NAV_PRINCIPAL
    ]
    resp = current_app.make_response(render_template(
        f"area_cliente/{template}",
        usuario=usuario, nav=nav, cadu=_cadu_links(), area_url=area_url,
        pagina_ativa=ativo, busca=request.args.get("q", "") if ativo == "projetos" else "",
        n_selecao=len(descobrir.selecao(session)), csrf_global=_csrf_token(),
        ver_como_opcoes=_opcoes_ver_como() if usuario.get("pode_ver_como") else [],
        ver_como_ano=date.today().year, **ctx,
    ))
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


def _exigir_acesso():
    """Usuário liberado, ou a resposta para quem não está (login ou aviso)."""
    if "user_id" not in session:
        destino = request.full_path if request.query_string else request.path
        return None, redirect(f"/login?{urlencode({'next': destino})}")
    usuario = acesso.contexto_usuario(session.get("user_id"))
    if not usuario:
        session.clear()
        return None, redirect(f"/login?{urlencode({'next': '/'})}")
    if usuario["liberado"] and session.get("area_cliente_ver_como"):
        alvo = acesso.aplicar_ver_como(usuario, session["area_cliente_ver_como"], date.today().year,
                                       _opcoes_ver_como() if usuario.get("pode_ver_como") else [])
        if alvo:
            return alvo, None
        session.pop("area_cliente_ver_como", None)
    if not usuario["liberado"]:
        resp = current_app.make_response((render_template(
            "area_cliente/sem_acesso.html", usuario=usuario, area_url=area_url,
        ), 403))
        resp.headers["Cache-Control"] = "no-store"
        return None, resp
    return usuario, None


def view_inicio(usuario):
    return _render("inicio.html", usuario, "inicio", resumo=dados.resumo_inicio(usuario["cliente_id"]))


def view_projetos(usuario):
    busca = request.args.get("q", "").strip()[:80]
    filtro = request.args.get("status", "todos")
    projetos = dados.listar_projetos(usuario["cliente_id"], busca)
    if filtro == "ativos":
        projetos = [p for p in projetos if p["ativo"]]
    elif filtro == "encerrados":
        projetos = [p for p in projetos if not p["ativo"]]
    return _render("projetos.html", usuario, "projetos", projetos=projetos, filtro=filtro, termo=busca)


def view_projeto(usuario, id_pi):
    projeto = dados.projeto_do_cliente(usuario["cliente_id"], id_pi)
    if projeto is None:
        abort(404)
    resumo = dados.resumo_projeto(usuario["cliente_id"], id_pi)
    return _render("projeto.html", usuario, "projetos", projeto=projeto, resumo=resumo)


def _csrf_token() -> str:
    token = session.get("area_cliente_csrf")
    if not token:
        token = session["area_cliente_csrf"] = secrets.token_urlsafe(24)
    return token


def _checar_csrf():
    enviado = (request.form.get("csrf") or "").encode()
    esperado = (session.get("area_cliente_csrf") or "").encode()
    if not esperado or not secrets.compare_digest(enviado, esperado):
        abort(400)


def view_ver_como(usuario):
    _checar_csrf()
    real = acesso.contexto_usuario(session.get("user_id"))
    alvo = acesso.aplicar_ver_como(real or {}, request.form.get("cliente_id"), date.today().year)
    if not alvo:
        abort(403)
    session["area_cliente_ver_como"] = alvo["cliente_id"]
    session.pop("area_cliente_descobrir", None)
    try:
        from ..audit import registrar_acao_admin
        registrar_acao_admin(user_id=real["user_id"], acao="VIEW_AS", modulo="area_cliente",
                             descricao=f"Abriu a Área do Cliente como {alvo['cliente_nome']}",
                             registro_id=alvo["cliente_id"], registro_tipo="cliente")
    except Exception:
        current_app.logger.warning("Auditoria do modo ver como indisponível.", exc_info=True)
    return redirect(area_url("inicio"), code=303)


def view_ver_como_sair():
    _checar_csrf()
    session.pop("area_cliente_ver_como", None)
    session.pop("area_cliente_descobrir", None)
    return redirect(area_url("inicio"), code=303)


def view_briefing(usuario):
    valores, erros = {}, {}
    if request.method == "POST" and usuario.get("ver_como"):
        # Modo de validação: nada é gravado em nome do cliente.
        _checar_csrf()
        erros = {"_ver_como": "Envio desativado enquanto você vê a área como outro cliente."}
    elif request.method == "POST":
        _checar_csrf()
        if request.form.get("remover_item"):
            secao, _, item_id = request.form["remover_item"].partition(":")
            descobrir.alternar(session, secao, item_id, "")
            return redirect(area_url("briefing"), code=303)
        valores, erros = briefing.validar(request.form)
        if not erros:
            valores["descobrir"] = descobrir.texto_selecao(descobrir.selecao(session))
            novo_id = briefing.enviar(usuario, valores)
            session.pop("area_cliente_descobrir", None)
            return redirect(f"{area_url('briefing')}?enviado={novo_id}", code=303)
    status = 422 if erros else 200
    resp = _render(
        "briefing.html", usuario, "briefing",
        canais=briefing.CANAIS, valores=valores, erros=erros, csrf=_csrf_token(),
        itens_descobrir=descobrir.selecao(session),
        enviados=briefing.listar(usuario["cliente_id"]),
        enviado_id=request.args.get("enviado", type=int),
    )
    resp.status_code = status
    return resp


def view_descobrir(usuario):
    return _render("descobrir.html", usuario, "descobrir", secoes=descobrir.resumo_secoes(),
                   itens=descobrir.selecao(session))


def view_descobrir_secao(usuario, secao):
    if secao not in descobrir.SECOES:
        abort(404)
    pagina = request.args.get("pagina", 1, type=int) or 1
    lista = descobrir.listar(secao, request.args.get("q", ""), request.args.get("categoria", ""), pagina)
    titulo, icone, texto = descobrir.SECOES[secao]
    return _render("descobrir_secao.html", usuario, "descobrir", secao=secao, titulo=titulo, icone=icone,
                   texto=texto, lista=lista, secoes=descobrir.SECOES, csrf=_csrf_token(),
                   marcados=descobrir.selecionados(session))


def view_descobrir_item(usuario, secao, item_id):
    item = descobrir.detalhe(secao, item_id)
    titulo, _icone, _texto = descobrir.SECOES[secao]
    return _render("descobrir_item.html", usuario, "descobrir", secao=secao, secao_titulo=titulo, item=item,
                   tipo=descobrir.TIPO_ROTULO[secao], csrf=_csrf_token(),
                   marcado=(secao, item_id) in descobrir.selecionados(session))


def view_descobrir_selecao():
    _checar_csrf()
    descobrir.alternar(session, request.form.get("secao", ""), request.form.get("id"), request.form.get("nome", ""))
    if request.headers.get("X-Requested-With") == "fetch":
        return current_app.response_class(status=204)
    destino = request.form.get("voltar") or area_url("descobrir")
    if not destino.startswith("/") or destino.startswith("//"):
        destino = area_url("descobrir")
    return redirect(destino, code=303)


def view_campanhas(usuario):
    filtro = request.args.get("status", "andamento")
    if filtro not in dados.GRUPOS_CAMPANHA:
        filtro = "andamento"
    ritmo = dados.ritmo_campanhas(usuario["cliente_id"])
    return _render("campanhas.html", usuario, "campanhas", ritmo=ritmo, filtro=filtro,
                   grupos_rotulo={k: v[0] for k, v in dados.GRUPOS_CAMPANHA.items()})


def view_pis(usuario):
    pis = dados.listar_pis(usuario["cliente_id"])
    return _render("pis.html", usuario, "pis", pis=pis, etapas=dados.ETAPAS_PI)


def view_pi(usuario, id_pi):
    pi = dados.pi_do_cliente(usuario["cliente_id"], id_pi)
    if pi is None:
        abort(404)
    campanhas = dados.campanhas_dos_pis([id_pi])
    return _render("pi.html", usuario, "pis", pi=pi, campanhas=campanhas)


def view_em_preparacao(usuario, endpoint):
    titulo, icone, texto = EM_PREPARACAO[endpoint]
    return _render("em_preparacao.html", usuario, endpoint, titulo=titulo, icone=icone, texto=texto)


def view_sair():
    session.clear()
    return redirect(f"/login?{urlencode({'next': '/'})}")


def despachar():
    """``before_request``: só age no host de clientes."""
    if not is_clientes_request():
        return None
    path = request.path
    if path in PASSAGEM_EXATA or path.startswith(PASSAGEM_PREFIXO):
        return None
    try:
        endpoint, args = ROTAS.bind_to_environ(request.environ).match()
    except (NotFound, MethodNotAllowed):
        abort(404)
    if request.method not in {"GET", "HEAD"} and endpoint not in {"briefing", "descobrir_selecao", "ver_como", "ver_como_sair"}:
        abort(405)
    if endpoint == "sair":
        return view_sair()
    if endpoint == "ver_como_sair":
        return view_ver_como_sair()
    usuario, bloqueio = _exigir_acesso()
    if bloqueio is not None:
        return bloqueio
    if endpoint == "inicio":
        return view_inicio(usuario)
    if endpoint == "ver_como":
        return view_ver_como(usuario)
    if endpoint == "briefing":
        return view_briefing(usuario)
    if endpoint == "planejamento_antigo":
        return redirect(area_url("descobrir"), code=301)
    if endpoint == "midia_antigo":
        return redirect(area_url("campanhas"), code=301)
    if endpoint == "arquivos_antigo":
        return redirect(area_url("pis"), code=301)
    if endpoint == "campanhas":
        return view_campanhas(usuario)
    if endpoint == "pis":
        return view_pis(usuario)
    if endpoint == "pi":
        return view_pi(usuario, **args)
    if endpoint == "descobrir":
        return view_descobrir(usuario)
    if endpoint == "descobrir_secao":
        return view_descobrir_secao(usuario, **args)
    if endpoint == "descobrir_item":
        return view_descobrir_item(usuario, **args)
    if endpoint == "descobrir_selecao":
        return view_descobrir_selecao()
    if endpoint == "projetos":
        return view_projetos(usuario)
    if endpoint == "projeto":
        return view_projeto(usuario, **args)
    return view_em_preparacao(usuario, endpoint)


def register(app) -> None:
    app.before_request(despachar)
