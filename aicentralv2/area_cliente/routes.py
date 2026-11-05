"""Área do Cliente em ``clientes.centralcomm.media``.

O mesmo Flask atende todos os hosts e ``/clientes`` já é a lista interna do
CentralX. Por isso a área não registra regras globais: no host de clientes um
``before_request`` casa o caminho num mapa próprio e chama a view. Fora dele
nada muda. No host de clientes, tudo que não é da área, do login ou estático
devolve 404, então nenhuma rota interna fica alcançável por ali.
"""

from __future__ import annotations

import secrets
from urllib.parse import urlencode, urlparse

from flask import abort, current_app, redirect, render_template, request, session
from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing import Map, Rule

from . import acesso, briefing, dados

ROTAS = Map([
    Rule("/", endpoint="inicio"),
    Rule("/briefing", endpoint="briefing", methods=["GET", "HEAD", "POST"]),
    Rule("/projetos", endpoint="projetos"),
    Rule("/projetos/<int:id_pi>", endpoint="projeto"),
    Rule("/campanhas", endpoint="campanhas"),
    Rule("/planejamento", endpoint="planejamento"),
    Rule("/midia", endpoint="midia"),
    Rule("/relatorios", endpoint="relatorios"),
    Rule("/arquivos", endpoint="arquivos"),
    Rule("/equipe", endpoint="equipe"),
    Rule("/sair", endpoint="sair"),
], strict_slashes=False)

# Rotas do app que continuam valendo no host de clientes: login e seus links
# (senha, cadastro, Google), estáticos. O resto dá 404.
PASSAGEM_EXATA = {"/login", "/logout", "/acesso-confirmado", "/favicon.ico",
                  "/forgot-password", "/signup", "/bem-vindo"}
PASSAGEM_PREFIXO = ("/static/", "/reset-password/", "/auth/")

# Jornada do cliente: Briefing → Planejamento → Projeto (PI fechado) → Campanhas.
NAV_PRINCIPAL = (
    ("inicio", "Início", "home"),
    ("briefing", "Briefing", "send"),
    ("planejamento", "Planejamento", "compass"),
    ("projetos", "Projetos", "folder"),
    ("campanhas", "Campanhas", "megaphone"),
    ("midia", "Mídia e Veiculação", "broadcast"),
    ("relatorios", "Relatórios", "chart"),
    ("arquivos", "Arquivos", "file"),
    ("equipe", "Equipe", "users"),
)

EM_PREPARACAO = {
    "campanhas": ("Campanhas", "megaphone", "Todas as campanhas dos seus projetos em um só lugar, com meta, entregue e ritmo de cada uma, sem valores de custo."),
    "planejamento": ("Planejamento", "compass", "Depois do seu briefing, a Centralcomm monta o plano de mídia e ele aparece aqui para você revisar e aprovar. Em breve, um guia com os recursos do Cadu Planner para pensar o próximo plano junto com a gente."),
    "midia": ("Mídia e Veiculação", "broadcast", "Canais, plataformas, formatos e períodos de veiculação de cada campanha, em um só lugar."),
    "relatorios": ("Relatórios", "chart", "Dashboards de entrega atualizados diariamente e as prestações de contas de cada projeto."),
    "arquivos": ("Arquivos", "file", "PIs, planos de mídia, peças e documentos assinados, organizados por projeto."),
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


def _render(template, usuario, ativo, **ctx):
    nav = [
        {"id": e, "rotulo": r, "icone": i, "url": area_url(e), "ativo": e == ativo}
        for e, r, i in NAV_PRINCIPAL
    ]
    resp = current_app.make_response(render_template(
        f"area_cliente/{template}",
        usuario=usuario, nav=nav, cadu=_cadu_links(), area_url=area_url,
        pagina_ativa=ativo, busca=request.args.get("q", ""), **ctx,
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


def view_briefing(usuario):
    valores, erros = {}, {}
    if request.method == "POST":
        enviado = (request.form.get("csrf") or "").encode()
        esperado = (session.get("area_cliente_csrf") or "").encode()
        if not esperado or not secrets.compare_digest(enviado, esperado):
            abort(400)
        valores, erros = briefing.validar(request.form)
        if not erros:
            novo_id = briefing.enviar(usuario, valores)
            return redirect(f"{area_url('briefing')}?enviado={novo_id}", code=303)
    status = 422 if erros else 200
    resp = _render(
        "briefing.html", usuario, "briefing",
        canais=briefing.CANAIS, valores=valores, erros=erros, csrf=_csrf_token(),
        enviados=briefing.listar(usuario["cliente_id"]),
        enviado_id=request.args.get("enviado", type=int),
    )
    resp.status_code = status
    return resp


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
    if request.method not in {"GET", "HEAD"} and endpoint != "briefing":
        abort(405)
    if endpoint == "sair":
        return view_sair()
    usuario, bloqueio = _exigir_acesso()
    if bloqueio is not None:
        return bloqueio
    if endpoint == "inicio":
        return view_inicio(usuario)
    if endpoint == "briefing":
        return view_briefing(usuario)
    if endpoint == "projetos":
        return view_projetos(usuario)
    if endpoint == "projeto":
        return view_projeto(usuario, **args)
    return view_em_preparacao(usuario, endpoint)


def register(app) -> None:
    app.before_request(despachar)
