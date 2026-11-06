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

from flask import abort, current_app, jsonify, redirect, render_template, request, session
from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing import Map, Rule

from . import acesso, briefing, dados, descobrir, emails, plataformas

ROTAS = Map([
    Rule("/", endpoint="inicio"),
    Rule("/briefing", endpoint="briefing", methods=["GET", "HEAD", "POST"]),
    Rule("/briefing/pracas", endpoint="briefing_pracas", methods=["POST"]),
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
    Rule("/solicitar-acesso", endpoint="solicitar_acesso", methods=["POST"]),
    Rule("/emails", endpoint="emails_previa_lista"),
    Rule("/emails/<modelo>", endpoint="emails_previa"),
    Rule("/ver-como/sair", endpoint="ver_como_sair", methods=["POST"]),
], strict_slashes=False)

# Rotas do app que continuam valendo no host de clientes: login e seus links
# (senha, cadastro, Google), estáticos. O resto dá 404.
PASSAGEM_EXATA = {"/login", "/logout", "/acesso-confirmado", "/favicon.ico",
                  "/forgot-password", "/signup", "/bem-vindo"}
PASSAGEM_PREFIXO = ("/static/", "/reset-password/", "/auth/", "/campanha/p/")

# Menu: Início pelo logo; Descobrir (título com as vitrines abertas); depois
# Briefing, Campanhas, Relatórios e PIs. Equipe fica no menu do usuário e a
# visão 360° do PI (antigo "Projetos") é aberta a partir de cada PI.
NAV_INICIO = ("inicio", "Início", "home")
NAV_PRINCIPAL = (
    ("briefing", "Briefing", "send"),
    ("campanhas", "Campanhas", "megaphone"),
    ("relatorios", "Relatórios", "chart"),
    ("pis", "PIs", "file"),
)

EM_PREPARACAO = {
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
    ativo = {"projetos": "pis"}.get(ativo, ativo)
    nav = [
        {"id": e, "rotulo": r, "icone": i, "url": area_url(e), "ativo": e == ativo}
        for e, r, i in NAV_PRINCIPAL
    ]
    inicio = {"id": "inicio", "rotulo": "Início", "icone": "home", "url": area_url("inicio"), "ativo": ativo == "inicio"}
    nav_descobrir = [
        {"id": s, "rotulo": t, "icone": i, "url": area_url("descobrir_secao", secao=s),
         "ativo": ativo == "descobrir" and ctx.get("secao") == s}
        for s, (t, i, _texto) in descobrir.SECOES.items()
    ]
    resp = current_app.make_response(render_template(
        f"area_cliente/{template}",
        usuario=usuario, nav=nav, nav_inicio=inicio, nav_descobrir=nav_descobrir, cadu=_cadu_links(), area_url=area_url,
        menu=_estado_menu(ativo),
        pagina_ativa=ativo, busca=request.args.get("q", "") if ativo == "pis" else "",
        n_selecao=len(descobrir.selecao(session)), csrf_global=_csrf_token(),
        n_campanhas_no_ar=dados.campanhas_em_andamento(usuario["cliente_id"]),
        ver_como_opcoes=_opcoes_ver_como() if usuario.get("pode_ver_como") else [],
        ver_como_ano=date.today().year, **ctx,
    ))
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


# Grupos do menu e as páginas de cada um (para abrir sozinho o grupo da página atual).
GRUPOS_MENU = {"descobrir": ("descobrir",), "planejar": ("briefing",), "acompanhar": ("campanhas", "relatorios", "pis")}
COOKIE_SIDEBAR, COOKIE_GRUPOS = "ac_side", "ac_nav"


def _estado_menu(ativo) -> dict:
    """Estado do menu lido dos cookies e aplicado já no HTML do servidor (sem piscar no carregamento).

    ac_side: "aberta" ou "recolhida" (padrão: recolhida em ícones).
    ac_nav: grupos que o usuário recolheu, separados por vírgula. O grupo da página
    atual fica sempre aberto, mesmo se recolhido antes.
    """
    recolhidos = {g for g in (request.cookies.get(COOKIE_GRUPOS) or "").split(",") if g in GRUPOS_MENU}
    atual = next((g for g, paginas in GRUPOS_MENU.items() if ativo in paginas), None)
    return {
        "sidebar_aberta": request.cookies.get(COOKIE_SIDEBAR) == "aberta",
        "tem_cookie_sidebar": COOKIE_SIDEBAR in request.cookies,
        "recolhidos": recolhidos - {atual},
        "grupo_atual": atual,
    }


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
            "area_cliente/sem_acesso.html", usuario=usuario, area_url=area_url, csrf=_csrf_token(),
            pedido_enviado=_pedido_recente(),
        ), 403))
        resp.headers["Cache-Control"] = "no-store"
        return None, resp
    return usuario, None


def view_inicio(usuario):
    return _render("inicio.html", usuario, "inicio", resumo=dados.resumo_inicio(usuario["cliente_id"]))


def view_projeto(usuario, id_pi):
    projeto = dados.projeto_do_cliente(usuario["cliente_id"], id_pi)
    if projeto is None:
        abort(404)
    if not projeto.get("vazio"):
        dados.marcar_encerradas(projeto["payload"].get("resultados"))
    resumo = dados.resumo_projeto(usuario["cliente_id"], id_pi)
    plats = plataformas.resumo(dados.campanhas_dos_pis([id_pi]))
    return _render("projeto.html", usuario, "projetos", projeto=projeto, resumo=resumo, plats=plats,
                   logos={p["nome"]: p for p in plats})


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


PEDIDO_INTERVALO = 12 * 3600


def _pedido_recente() -> bool:
    return time.time() - float(session.get("area_cliente_pedido_em") or 0) < PEDIDO_INTERVALO


def view_solicitar_acesso():
    """Contato com login do Cadu, mas sem liberação: avisa o executivo (uma vez a cada 12 h)."""
    _checar_csrf()
    usuario = acesso.contexto_usuario(session.get("user_id"))
    if not usuario:
        abort(403)
    if not usuario["liberado"] and not _pedido_recente():
        emails.pedido_acesso(usuario)
        session["area_cliente_pedido_em"] = time.time()
    return redirect(area_url("inicio"), code=303)


def view_emails_previa(usuario, modelo=None):
    """Prévia dos e-mails da área (sem envio), só para admins da Centralcomm."""
    if not usuario.get("pode_ver_como"):
        abort(404)
    if modelo is None:
        itens = "".join(f'<li><a href="{area_url("emails_previa", modelo=m)}">{m}</a></li>' for m in emails.MODELOS)
        return current_app.make_response(f"<!doctype html><meta charset='utf-8'><title>E-mails</title><ul style='font:15px/1.8 sans-serif'>{itens}</ul>")
    if modelo not in emails.MODELOS:
        abort(404)
    resp = current_app.make_response(emails.previa(modelo))
    resp.headers["Cache-Control"] = "no-store"
    return resp


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
            try:
                origem = next((h for h in briefing.historico(usuario["cliente_id"]) if h["id"] == valores.get("origem")), None) if valores.get("origem") else None
            except Exception:
                current_app.logger.warning("Histórico do briefing indisponível no envio.", exc_info=True)
                origem = None
            if origem:
                valores["origem_rotulo"] = f"{origem['fonte']} {origem['titulo']}" + (f" ({origem['quando']})" if origem["quando"] else "")
            novo_id = briefing.enviar(usuario, valores)
            session.pop("area_cliente_descobrir", None)
            try:
                emails.briefing_novo(usuario, valores, novo_id)
                emails.briefing_recebido(usuario, valores)
            except Exception:
                current_app.logger.warning("E-mails do briefing %s não enviados.", novo_id, exc_info=True)
            return redirect(f"{area_url('briefing')}?enviado={novo_id}", code=303)
    status = 422 if erros else 200
    try:
        historico = briefing.historico(usuario["cliente_id"])
    except Exception:
        current_app.logger.warning("Histórico do briefing indisponível.", exc_info=True)
        historico = []
    opcoes = {
        "objetivos": [{"id": o[0], "rotulo": o[1], "kpis": list(o[2]), "conversao": o[3]} for o in briefing.OBJETIVOS],
        "historico": historico, "base_pracas": briefing.base_pracas(),
    }
    resp = _render(
        "briefing.html", usuario, "briefing",
        canais=briefing.CANAIS, valores=valores, erros=erros, csrf=_csrf_token(),
        b=briefing, opcoes=opcoes, historico=historico,
        itens_descobrir=descobrir.selecao(session),
        enviados=briefing.listar(usuario["cliente_id"]),
        enviado_id=request.args.get("enviado", type=int),
    )
    resp.status_code = status
    return resp


def view_descobrir(usuario):
    # Sem página geral: o Descobrir começa pelos canais (os itens ficam abertos no menu).
    return redirect(area_url("descobrir_secao", secao="canais"))


def view_descobrir_secao(usuario, secao):
    if secao not in descobrir.SECOES:
        abort(404)
    titulo, icone, texto = descobrir.SECOES[secao]
    comum = dict(secao=secao, titulo=titulo, icone=icone, texto=texto, secoes=descobrir.SECOES, csrf=_csrf_token(),
                 marcados=descobrir.selecionados(session))
    if secao in ("formatos", "interativos"):
        vitrine = descobrir.vitrine_formatos(secao, request.args.get("q", ""), request.args.get("canal", ""),
                                             request.args.get("ver", "canal"))
        return _render("descobrir_formatos.html", usuario, "descobrir", vitrine=vitrine,
                       visoes=descobrir.VISOES_FORMATOS, **comum)
    pagina = request.args.get("pagina", 1, type=int) or 1
    lista = descobrir.listar(secao, request.args.get("q", ""), request.args.get("categoria", ""), pagina)
    return _render("descobrir_secao.html", usuario, "descobrir", lista=lista, **comum)


def view_descobrir_item(usuario, secao, item_id):
    item = descobrir.detalhe(secao, item_id)
    titulo, _icone, _texto = descobrir.SECOES[secao]
    return _render("descobrir_item.html", usuario, "descobrir", secao=secao, secao_titulo=titulo, item=item,
                   tipo=descobrir.TIPO_ROTULO[secao], csrf=_csrf_token(),
                   marcados=descobrir.selecionados(session))


def view_descobrir_selecao():
    _checar_csrf()
    incluido = descobrir.alternar(session, request.form.get("secao", ""), request.form.get("id"), request.form.get("nome", ""))
    if request.headers.get("X-Requested-With") == "fetch":
        # O botão troca de estado sem recarregar; "total" atualiza os contadores do menu e do CTA.
        return jsonify(incluido=incluido, total=len(descobrir.selecao(session)), limite=descobrir.LIMITE_SELECAO)
    destino = request.form.get("voltar") or area_url("descobrir_secao", secao="canais")
    if not destino.startswith("/") or destino.startswith("//"):
        destino = area_url("descobrir_secao", secao="canais")
    return redirect(destino, code=303)


def view_campanhas(usuario):
    filtro = request.args.get("status", "andamento")
    if filtro not in dados.GRUPOS_CAMPANHA:
        filtro = "andamento"
    ritmo = dados.ritmo_campanhas(usuario["cliente_id"])
    rotulos = {k: v[0] for k, v in dados.GRUPOS_CAMPANHA.items()}
    return _render("campanhas.html", usuario, "campanhas", ritmo=ritmo, filtro=filtro, grupos_rotulo=rotulos,
                   drawer_dados=[_drawer_campanha(c, rotulos[filtro]) for c in ritmo["grupos"][filtro]])


def _drawer_campanha(c, status) -> dict:
    """Campos do painel lateral de uma campanha (sem custo), já formatados."""
    def br(iso):
        return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if iso else "—"
    ritmos = {"adiantado": "Adiantada", "no_ritmo": "No ritmo", "atencao": "Atenção"}
    tempo = "—"
    if c.get("tempo_pct") is not None:
        tempo = f"{c['tempo_pct']}%"
        if c.get("dias_restantes") is not None and c["dias_restantes"] >= 0 and c["tempo_pct"] < 100:
            tempo += f" · {c['dias_restantes']} dias restantes"
    return {
        "nome": c["nome"], "status": status, "objetivo": c.get("objetivo") or "—", "logo": c.get("plataforma_logo") or "",
        "plataforma": c.get("plataforma") or "—", "responsavel": c.get("responsavel") or "Centralcomm",
        "pct": f"{c['pct']}%" if c.get("pct") is not None else "—", "pct_num": c.get("pct") or 0,
        "atingido": c.get("atingido_label") or "—", "meta": c.get("meta_label") or "—",
        "ritmo": ritmos.get(c.get("ritmo"), "—"), "tempo": tempo,
        "periodo": f"{br(c['periodo']['inicio'])} a {br(c['periodo']['fim'])}",
        "pi": c.get("pi") or "—", "pi_url": area_url("pi", id_pi=c["projeto_id"]),
        "pi_360": area_url("projeto", id_pi=c["projeto_id"]), "dash": c.get("dash_abrir") or "",
    }


def view_relatorios(usuario):
    return _render("relatorios.html", usuario, "relatorios", pis=dados.relatorios(usuario["cliente_id"]))


PIS_FILTROS = {"abertos": "Em andamento", "finalizados": "Finalizados", "todos": "Todos"}


def view_pis(usuario):
    termo = request.args.get("q", "").strip()[:80]
    filtro = request.args.get("status", "abertos" if not termo else "todos")
    filtro = filtro if filtro in PIS_FILTROS else "abertos"
    todos = dados.listar_pis(usuario["cliente_id"])
    contagem = {"abertos": sum(1 for p in todos if p["status_id"] in dados.SUB_STATUS_ABERTOS),
                "finalizados": sum(1 for p in todos if p["status_id"] not in dados.SUB_STATUS_ABERTOS),
                "todos": len(todos)}
    if filtro == "abertos":
        pis = [p for p in todos if p["status_id"] in dados.SUB_STATUS_ABERTOS]
    elif filtro == "finalizados":
        pis = [p for p in todos if p["status_id"] not in dados.SUB_STATUS_ABERTOS]
    else:
        pis = todos
    if termo:
        t = termo.lower()
        pis = [p for p in pis if t in p["pi"].lower() or t in (p["titulo"] or "").lower()]
    por_pi: dict = {}
    for c in dados.campanhas_dos_pis([p["id"] for p in pis]):
        por_pi.setdefault(c["id_pi"], []).append(c)
    for p in pis:
        p["plataformas"] = plataformas.resumo(por_pi.get(p["id"], []))
    return _render("pis.html", usuario, "pis", pis=pis, etapas=dados.ETAPAS_PI, termo=termo,
                   filtro=filtro, filtros=PIS_FILTROS, contagem=contagem)


def view_pi(usuario, id_pi):
    pi = dados.pi_do_cliente(usuario["cliente_id"], id_pi)
    if pi is None:
        abort(404)
    campanhas = dados.campanhas_dos_pis([id_pi])
    return _render("pi.html", usuario, "pis", pi=pi, campanhas=campanhas, plats=plataformas.resumo(campanhas))


def view_em_preparacao(usuario, endpoint):
    titulo, icone, texto = EM_PREPARACAO[endpoint]
    return _render("em_preparacao.html", usuario, endpoint, titulo=titulo, icone=icone, texto=texto)


LIMITE_IA_PRACAS = (20, 600)  # chamadas por janela de segundos, por sessão


def view_briefing_pracas():
    """Autocompletar de praças com IA: normaliza o texto e sugere praças próximas."""
    _checar_csrf()
    agora = time.time()
    janela = [t for t in session.get("area_cliente_ia_pracas", []) if agora - t < LIMITE_IA_PRACAS[1]]
    if len(janela) >= LIMITE_IA_PRACAS[0]:
        return jsonify(erro="Muitas consultas seguidas. Tente de novo em alguns minutos."), 429
    texto = (request.form.get("texto") or "").strip()
    escolhidas = request.form.getlist("escolhidas")
    if len(texto) < 2 and not escolhidas:
        return jsonify(pracas=[], sugestoes=[], observacao="")
    session["area_cliente_ia_pracas"] = janela + [agora]
    try:
        return jsonify(briefing.pracas_ia(texto, escolhidas))
    except Exception:
        current_app.logger.warning("IA de praças indisponível.", exc_info=True)
        return jsonify(erro="A IA não respondeu agora. Você pode digitar as praças à mão."), 503


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
    if request.method not in {"GET", "HEAD"} and endpoint not in {"briefing", "briefing_pracas", "descobrir_selecao", "ver_como", "ver_como_sair", "solicitar_acesso"}:
        abort(405)
    if endpoint == "sair":
        return view_sair()
    if endpoint == "ver_como_sair":
        return view_ver_como_sair()
    if endpoint == "solicitar_acesso":
        if "user_id" not in session:
            return redirect("/login")
        return view_solicitar_acesso()
    usuario, bloqueio = _exigir_acesso()
    if bloqueio is not None:
        return bloqueio
    if endpoint == "inicio":
        return view_inicio(usuario)
    if endpoint == "ver_como":
        return view_ver_como(usuario)
    if endpoint in ("emails_previa", "emails_previa_lista"):
        return view_emails_previa(usuario, args.get("modelo"))
    if endpoint == "briefing":
        return view_briefing(usuario)
    if endpoint == "briefing_pracas":
        return view_briefing_pracas()
    if endpoint == "planejamento_antigo":
        return redirect(area_url("descobrir_secao", secao="canais"), code=301)
    if endpoint == "midia_antigo":
        return redirect(area_url("campanhas"), code=301)
    if endpoint == "arquivos_antigo":
        return redirect(area_url("pis"), code=301)
    if endpoint == "campanhas":
        return view_campanhas(usuario)
    if endpoint == "pis":
        return view_pis(usuario)
    if endpoint == "relatorios":
        return view_relatorios(usuario)
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
        destino = area_url("pis") + (f"?{urlencode({'q': request.args['q']})}" if request.args.get("q") else "")
        return redirect(destino, code=301)
    if endpoint == "projeto":
        return view_projeto(usuario, **args)
    return view_em_preparacao(usuario, endpoint)


def register(app) -> None:
    app.before_request(despachar)
