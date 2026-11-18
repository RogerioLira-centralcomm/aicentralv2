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

from . import acesso, briefing, cotacao, cotacao_envio, dados, demo, descobrir, emails, pi_envio, plataformas, videos

ROTAS = Map([
    Rule("/", endpoint="inicio"),
    Rule("/conhecer", endpoint="conhecer", defaults={"slug": None}),
    Rule("/conhecer/<slug>", endpoint="conhecer"),
    Rule("/briefing", endpoint="briefing", methods=["GET", "HEAD", "POST"]),
    Rule("/briefing/pracas", endpoint="briefing_pracas", methods=["POST"]),
    Rule("/briefing/planejamento", endpoint="briefing_planejamento", methods=["GET", "HEAD", "POST"]),
    Rule("/briefing/pi-antigo", endpoint="briefing_pi_antigo", methods=["GET", "HEAD", "POST"]),
    Rule("/briefing/todos", endpoint="briefing_todos"),
    Rule("/briefing/anexo", endpoint="briefing_anexo", methods=["POST"]),
    Rule("/briefing/anexo/<uuid>", endpoint="briefing_anexo_dados"),
    Rule("/briefing/cotacao", endpoint="briefing_cotacao", methods=["GET", "HEAD", "POST"]),
    Rule("/briefing/cotacao/<uuid>", endpoint="briefing_cotacao_rascunho"),
    Rule("/briefing/cotacao/<uuid>/status", endpoint="briefing_cotacao_status"),
    Rule("/briefing/cotacao/<uuid>/enviar", endpoint="briefing_cotacao_enviar", methods=["POST"]),
    Rule("/projetos", endpoint="projetos"),
    Rule("/projetos/<int:id_pi>", endpoint="projeto"),
    Rule("/campanhas", endpoint="campanhas"),
    Rule("/descobrir", endpoint="descobrir"),
    Rule("/descobrir/selecao", endpoint="descobrir_selecao", methods=["POST"]),
    Rule("/descobrir/<secao>", endpoint="descobrir_secao"),
    Rule("/descobrir/<secao>/<int:item_id>", endpoint="descobrir_item"),
    Rule("/descobrir/estrategias/<int:item_id>/simulacao", endpoint="descobrir_simulacao"),
    Rule("/descobrir/estrategias/<int:item_id>", endpoint="descobrir_estrategia_id"),
    Rule("/descobrir/estrategias/<endereco>", endpoint="descobrir_estrategia"),
    # Link público (sem login): /<empresa de quem compartilhou>/estrategias/<estratégia>-<código>.
    Rule("/<empresa>/estrategias/<endereco>", endpoint="estrategia_publica"),
    Rule("/<empresa>/estrategias/<endereco>/simulacao", endpoint="estrategia_publica_simulacao"),
    Rule("/planejamento", endpoint="planejamento_antigo"),
    Rule("/pis", endpoint="pis"),
    Rule("/pis/enviar", endpoint="pi_enviar", methods=["GET", "HEAD", "POST"]),
    Rule("/pis/enviados/<uuid>", endpoint="pi_enviado"),
    Rule("/pis/enviados/<uuid>/status", endpoint="pi_enviado_status"),
    Rule("/pis/enviados/<uuid>/enviar", endpoint="pi_enviado_enviar", methods=["POST"]),
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
    ("pis", "PIs", "file"),
    ("campanhas", "Campanhas", "megaphone"),
    ("relatorios", "Relatórios", "chart"),
)

EM_PREPARACAO = {
}


def _host_clientes() -> str:
    return (urlparse(str(current_app.config.get("CLIENTES_URL") or "")).hostname or "").lower()


def is_clientes_request() -> bool:
    host = _host_clientes()
    return bool(host) and (request.host.split(":", 1)[0] or "").lower() == host


def area_url(endpoint: str, **values) -> str:
    return ROTAS.bind("clientes").build(endpoint, values)


CADU_MENU_CLIENTES = {174}        # o Cadu novo ainda está em teste: o grupo "Cadu" do menu do usuário só aparece para a Centralcomm


def _cadu_links(cliente_id=None):
    if cliente_id not in CADU_MENU_CLIENTES:
        return ()
    from ..product_domains import product_url
    return (
        {"rotulo": "Workspace", "icone": "folder", "url": product_url("workspace", "/app")},
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
    # Busca do topo: nas páginas do Descobrir ela busca na seção aberta (substitui a busca da página);
    # no resto do hub, busca PIs.
    secao_busca = ctx.get("secao") if ativo == "descobrir" and ctx.get("secao") in descobrir.SECOES else ""
    busca_topo = {
        "url": area_url("descobrir_secao", secao=secao_busca),
        "rotulo": f"Buscar em {descobrir.SECOES[secao_busca][0].lower()}",
    } if secao_busca else {"url": area_url("pis"), "rotulo": "Buscar PIs por código ou título"}
    resp = current_app.make_response(render_template(
        f"area_cliente/{template}",
        usuario=usuario, nav=nav, nav_inicio=inicio, nav_descobrir=nav_descobrir, cadu=_cadu_links(usuario.get("cliente_id")), area_url=area_url,
        menu=_estado_menu(ativo), demo_ativo=demo.ativo(usuario["cliente_id"]),
        pagina_ativa=ativo, busca_topo=busca_topo,
        busca=request.args.get("q", "") if ativo == "pis" or (secao_busca and ("lista" in ctx or "vitrine" in ctx)) else "",
        n_selecao=len(descobrir.selecao(session)), csrf_global=_csrf_token(),
        n_campanhas_no_ar=dados.campanhas_em_andamento(usuario["cliente_id"]),
        ver_como_opcoes=_opcoes_ver_como() if usuario.get("pode_ver_como") else [],
        ver_como_ano=date.today().year, festa_briefing=_festa_briefing(usuario) if ativo == "briefing" else None, **ctx,
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
    resumo = dados.resumo_inicio(usuario["cliente_id"])
    # Exemplo claro para a coluna de indicadores quando não há campanha no ar (etiqueta "Exemplo" na tela).
    exemplo = [{"nome": n, "logo": plataformas.logo(n), "iniciais": plataformas.iniciais(n)} for n in ("Meta Ads", "Google Ads", "YouTube")]
    return _render("inicio.html", usuario, "inicio", resumo=resumo, exemplo_plataformas=exemplo, video=videos.destaque())


def view_conhecer(usuario, slug):
    """Vídeos do hub, em página própria: navegação lateral só dos vídeos, botão de voltar e botões grandes de avançar."""
    video = videos.obter(slug)
    if video is None:
        abort(404)
    anterior, proximo = videos.vizinhos(video["slug"])
    return _render("conhecer.html", usuario, "conhecer", video=video, anterior=anterior, proximo=proximo,
                   grupos=videos.grupos(), embed=videos.embed_url(video), total=len(videos.VIDEOS),
                   posicao=[v["slug"] for v in videos.VIDEOS].index(video["slug"]) + 1)


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
                             descricao=f"Abriu o hub de mídia como {alvo['cliente_nome']}",
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
    """/briefing: escolha dos três caminhos. O POST (formulário antigo) segue para o formulário de planejamento."""
    if request.method == "POST":
        return view_briefing_form(usuario)
    try:
        enviados = briefing.listar(usuario["cliente_id"])
    except Exception:
        current_app.logger.warning("Lista de briefings indisponível.", exc_info=True)
        enviados = []
    return _render("briefing_escolha.html", usuario, "briefing", enviados=enviados[:3], total=len(enviados),
                   enviado_id=request.args.get("enviado", type=int))


def view_briefing_todos(usuario):
    """Lista completa, sem item no menu: o acesso é por dentro da página de briefing."""
    try:
        enviados = briefing.listar(usuario["cliente_id"])
    except Exception:
        current_app.logger.warning("Lista de briefings indisponível.", exc_info=True)
        enviados = []
    return _render("briefing_todos.html", usuario, "briefing", enviados=enviados,
                   status=sorted({(e["status"], e["tom"]) for e in enviados}))


def _item_do_historico(usuario, id_item):
    try:
        return next((h for h in briefing.historico(usuario["cliente_id"]) if h["id"] == id_item), None)
    except Exception:
        current_app.logger.warning("Histórico do briefing indisponível.", exc_info=True)
        return None


def _atalho_datas(item):
    """Datas do PI anterior deslocadas para o próximo mês (botão "mesmas datas, mês que vem")."""
    if not item or not item.get("inicio_iso") or not item.get("fim_iso"):
        return None
    try:
        ini, fim = briefing.deslocar_para_proximo_mes(date.fromisoformat(item["inicio_iso"]), date.fromisoformat(item["fim_iso"]))
    except ValueError:
        return None
    return {"inicio": ini.isoformat(), "fim": fim.isoformat(), "rotulo": f"{ini:%d/%m} a {fim:%d/%m/%Y}"}


def view_briefing_pi_antigo(usuario):
    """Repetir um PI antigo: 1) escolher o PI ou briefing; 2) o formulário abre com o que dá para trazer e o que falta."""
    de = request.args.get("de", "")
    if request.method == "GET" and not de:
        try:
            historico = briefing.historico(usuario["cliente_id"])
        except Exception:
            current_app.logger.warning("Histórico do briefing indisponível.", exc_info=True)
            historico = []
        return _render("briefing_pi_antigo.html", usuario, "briefing", historico=historico)
    if request.method == "GET" and not _item_do_historico(usuario, de):
        return redirect(area_url("briefing_pi_antigo"), code=303)      # PI que não é mais desta conta: volta para a escolha
    return view_briefing_form(usuario, "pi_antigo")


CHAVE_FESTA = "area_cliente_festa_briefing"


def concluir_briefing(usuario, valores: dict, novo_id: int, arquivos=None, *, simulado=False) -> None:
    """Fim comum dos três briefings: guarda a tela cheia de sucesso (aparece uma vez, na próxima página) e manda os dois e-mails,
    ao cliente e ao executivo responsável (com os arquivos da cotação anexados).

    Na demonstração, com HUB_DEMO_EMAILS=1, os dois e-mails vão para o próprio usuário logado, como no PI: ninguém de verdade
    recebe briefing de exemplo. Sem a chave, a demonstração não manda e-mail."""
    session[CHAVE_FESTA] = {"id": novo_id, "titulo": (valores.get("titulo") or "")[:160], "modo": valores.get("modo") or "planejamento",
                            "prazo": valores.get("prazo_texto") or "", "arquivos": len(arquivos or valores.get("anexos") or []),
                            "origem": (valores.get("origem_rotulo") or "")[:160]}
    destino = usuario
    if simulado:
        if not current_app.config.get("HUB_DEMO_EMAILS") or not usuario.get("email"):
            return
        executivo = usuario.get("executivo") or {}
        destino = {**usuario, "executivo": {**executivo, "email": usuario["email"], "nome": executivo.get("nome") or "Executivo"}}
    try:
        emails.briefing_novo(destino, valores, 0 if simulado else novo_id, anexos=emails.anexos_arquivos(arquivos))
        emails.briefing_recebido(usuario, valores)
    except Exception:
        current_app.logger.warning("E-mails do briefing %s não enviados.", novo_id, exc_info=True)


def _festa_briefing(usuario):
    """Tela cheia de "briefing enviado": sai da sessão na primeira página que a mostra (recarregar não repete os fogos)."""
    festa = session.pop(CHAVE_FESTA, None)
    if not isinstance(festa, dict):
        return None
    from .pi_envio import _whatsapp_motivo
    festa["whatsapp"] = _whatsapp_motivo(usuario, f"Enviei o briefing \"{festa.get('titulo')}\" pelo hub de mídia.")
    return festa


def view_briefing_form(usuario, modo="planejamento"):
    valores, erros = {}, {}
    origem_item, trazido = None, []
    if modo == "pi_antigo":
        id_origem = request.args.get("de") or request.form.get("origem") or ""
        origem_item = _item_do_historico(usuario, id_origem) if id_origem else None
        if request.method == "GET" and origem_item:
            valores, trazido = briefing.valores_do_historico(origem_item)
    if request.method == "POST":
        _checar_csrf()
        if request.form.get("remover_item"):
            secao, _, item_id = request.form["remover_item"].partition(":")
            descobrir.alternar(session, secao, item_id, "")
            return redirect(area_url("briefing_pi_antigo" if modo == "pi_antigo" else "briefing_planejamento"), code=303)
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
            valores["modo"] = modo
            if demo.ativo(usuario["cliente_id"]):
                # Conta de demonstração: o briefing "vai" só na sessão, sem banco. E-mails só para o próprio usuário (HUB_DEMO_EMAILS).
                arquivos_demo = []
                if str(request.form.get("anexo", "")).startswith("demo-"):
                    reg = demo.envio("cotacao", request.form["anexo"]) or {}
                    arquivos_demo = reg.get("arquivos") or []
                    valores["anexos"] = reg.get("nomes") or []
                    demo.marcar_enviado("cotacao", request.form["anexo"])
                novo_id = demo.registrar_briefing(valores)
                session.pop("area_cliente_descobrir", None)
                concluir_briefing(usuario, valores, novo_id, arquivos_demo, simulado=True)
                return redirect(f"{area_url('briefing')}?enviado={novo_id}", code=303)
            extra, reservado = None, None
            anexo = cotacao_envio.rascunho_anexo(usuario, request.form.get("anexo"))
            if anexo and cotacao.situacao(anexo) in ("pronto", "erro") and cotacao.reservar(anexo["id"]):
                reservado, nomes = anexo, [a["nome"] for a in anexo.get("arquivos") or []]
                leitura = anexo.get("leitura") or {}
                notas = ["Arquivos anexados: " + ", ".join(nomes)] if nomes else []
                if leitura.get("faltou"):
                    notas.append("Não achei nos arquivos: " + "; ".join(leitura["faltou"]))
                valores["descricao"] = "\n\n".join(p for p in [valores.get("descricao"), *notas] if p)[:6000]
                valores["anexos"] = nomes
                extra = {"modo": modo if modo != "pi_antigo" else "pi_antigo", "prazo_resposta_em": None,
                         "arquivos": [{k: a[k] for k in ("nome", "sha256", "tamanho", "caminho", "tipo")} for a in anexo.get("arquivos") or []],
                         "leitura_ia": {**leitura, "rascunho_uuid": anexo["uuid"]}}
            try:
                novo_id = briefing.enviar(usuario, valores, extra) if extra else briefing.enviar(usuario, valores)
            except Exception:
                if reservado:
                    cotacao.mudar_status(reservado["id"], "lido", None)
                raise
            if reservado:
                cotacao.marcar_enviado(reservado["id"], novo_id, None)
            session.pop("area_cliente_descobrir", None)
            concluir_briefing(usuario, valores, novo_id, (reservado or {}).get("arquivos"))
            return redirect(f"{area_url('briefing')}?enviado={novo_id}", code=303)
    status = 422 if erros else 200
    if erros and request.method == "POST":
        valores["anexo"] = request.form.get("anexo", "")                # o arquivo já lido continua valendo depois de um erro
    anunciantes, anunciante_padrao = briefing.anunciantes(usuario["cliente_id"], usuario.get("cliente_nome") or "")
    if request.method == "GET" and not valores.get("anunciante"):
        valores["anunciante"] = anunciante_padrao
    historico = []
    if modo != "planejamento":                                          # planejamento não reaproveita PI: parte do que o cliente escreve e do Descobrir
        try:
            historico = briefing.historico(usuario["cliente_id"])
        except Exception:
            current_app.logger.warning("Histórico do briefing indisponível.", exc_info=True)
    opcoes = {
        "objetivos": [{"id": o[0], "rotulo": o[1], "kpis": list(o[2]), "conversao": o[3]} for o in briefing.OBJETIVOS],
        "historico": historico, "base_pracas": briefing.base_pracas(),
    }
    resp = _render(
        "briefing.html", usuario, "briefing",
        canais=briefing.CANAIS, valores=valores, erros=erros, csrf=_csrf_token(),
        b=briefing, opcoes=opcoes, historico=historico, modo=modo, origem_item=origem_item, trazido=trazido, anunciantes=anunciantes,
        atalho_datas=_atalho_datas(origem_item), falta=briefing.qualidade(valores)["pendencias"] if origem_item else [],
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
    if secao == "estrategias":
        vitrine = descobrir.vitrine_estrategias(request.args.get("q", ""), request.args.get("objetivo", ""),
                                                request.args.get("verba", ""))
        return _render("descobrir_estrategias.html", usuario, "descobrir", vitrine=vitrine, **comum)
    if secao in ("formatos", "interativos"):
        vitrine = descobrir.vitrine_formatos(secao, request.args.get("q", ""), request.args.get("canal", ""),
                                             request.args.get("ver", "canal"))
        return _render("descobrir_formatos.html", usuario, "descobrir", vitrine=vitrine,
                       visoes=descobrir.VISOES_FORMATOS, **comum)
    pagina = request.args.get("pagina", 1, type=int) or 1
    lista = descobrir.listar(secao, request.args.get("q", ""), request.args.get("categoria", ""), pagina)
    return _render("descobrir_secao.html", usuario, "descobrir", lista=lista, **comum)


def _com_query(url: str) -> str:
    return url + (f"?{request.query_string.decode()}" if request.query_string else "")


def _url_absoluta(caminho: str) -> str:
    base = (current_app.config.get("CLIENTES_URL") or request.host_url or "").rstrip("/")
    return base + caminho


def view_descobrir_estrategia_id(item_id):
    """Endereço antigo (/descobrir/estrategias/1): vai para o endereço com o nome."""
    from ..estrategias import catalogo
    e = descobrir._estrategia(item_id)
    return redirect(_com_query(area_url("descobrir_estrategia", endereco=catalogo.url_slug(e))), code=301)


def view_descobrir_estrategia(usuario, endereco):
    from ..estrategias import catalogo
    e = descobrir.estrategia_por_url(endereco)
    canonico = catalogo.url_slug(e)
    if endereco != canonico:
        return redirect(_com_query(area_url("descobrir_estrategia", endereco=canonico)), code=301)
    empresa = catalogo.slug_url(usuario.get("cliente_nome"))
    link_publico = (_url_absoluta(area_url("estrategia_publica", empresa=empresa, endereco=_endereco_publico(empresa, e)))
                    if empresa else "")
    return _render("descobrir_estrategia.html", usuario, "descobrir", secao="estrategias", secao_titulo="Estratégias",
                   item=descobrir.detalhe_estrategia(None, request.args.get("verba"), request.args.get("pracas"), estrategia=e),
                   tipo="Estratégia", csrf=_csrf_token(), marcados=descobrir.selecionados(session),
                   sim_url=area_url("descobrir_simulacao", item_id=e["id"]), link_publico=link_publico,
                   empresa_nome=usuario.get("cliente_nome") or "")


CODIGO_PUBLICO_TAM = 8


def _codigo_publico(empresa: str, estrategia_id) -> str:
    """Código do fim do link público: HMAC da empresa + id da estratégia com a SECRET_KEY.
    Só quem recebeu o link conhece; sem ele não dá para descobrir clientes nem forjar
    "Compartilhado por". Usa o id (não o nome), então renomear a estratégia não invalida o link."""
    import base64
    import hashlib
    import hmac
    chave = str(current_app.config.get("SECRET_KEY") or current_app.secret_key or "").encode()
    dig = hmac.new(chave, f"estrategia-publica:{empresa}:{int(estrategia_id)}".encode(), hashlib.sha256).digest()
    return base64.b32encode(dig).decode().lower()[:CODIGO_PUBLICO_TAM]


def _endereco_publico(empresa: str, e: dict) -> str:
    from ..estrategias import catalogo
    return f"{catalogo.url_slug(e)}-{_codigo_publico(empresa, e['id'])}"


def _estrategia_publica(empresa, endereco):
    """(nome da empresa, estratégia, endereço certo ou None) do link público; 404 sem código válido.
    O código é conferido antes de consultar a empresa: endereço sem código certo não revela se ela é cliente."""
    from ..estrategias import catalogo
    empresa_n = (empresa or "").strip().lower()
    slug, _, codigo = (endereco or "").lower().rpartition("-")
    # compare_digest recusa str não ASCII (TypeError -> 500): código fora do formato é 404 direto.
    if not slug or len(codigo) != CODIGO_PUBLICO_TAM or not (codigo.isascii() and codigo.isalnum()):
        abort(404)
    e = descobrir.estrategia_por_url(slug)
    if not secrets.compare_digest(codigo, _codigo_publico(empresa_n, e["id"])):
        abort(404)
    nome_empresa = acesso.empresa_por_slug(empresa_n)
    if not nome_empresa or catalogo.slug_url(nome_empresa) != empresa_n:
        abort(404)
    certo = _endereco_publico(empresa_n, e)
    return nome_empresa, e, (empresa_n, certo) if (empresa, endereco) != (empresa_n, certo) else None


def view_estrategia_publica(empresa, endereco):
    """Ficha da estratégia para quem não tem login, com o nome da empresa que compartilhou."""
    from ..estrategias import catalogo
    nome_empresa, e, corrigir = _estrategia_publica(empresa, endereco)
    if corrigir:
        return redirect(_com_query(area_url("estrategia_publica", empresa=corrigir[0], endereco=corrigir[1])), code=301)
    item = descobrir.detalhe_estrategia(None, request.args.get("verba"), request.args.get("pracas"), estrategia=e)
    caminho = area_url("estrategia_publica", empresa=empresa, endereco=endereco)
    resp = current_app.make_response(render_template(
        "area_cliente/estrategia_publica.html", item=item, area_url=area_url, empresa_nome=nome_empresa,
        sim_url=area_url("estrategia_publica_simulacao", empresa=empresa, endereco=endereco),
        url_publica=_url_absoluta(caminho),
        login_url="/login?" + urlencode({"next": area_url("descobrir_estrategia", endereco=catalogo.url_slug(e))}),
    ))
    resp.headers["Cache-Control"] = "public, max-age=300"
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


def view_estrategia_publica_simulacao(empresa, endereco):
    _nome, e, _corrigir = _estrategia_publica(empresa, endereco)
    return view_descobrir_simulacao(e["id"])


def view_descobrir_item(usuario, secao, item_id):
    if secao == "estrategias":
        return view_descobrir_estrategia_id(item_id)
    item = descobrir.detalhe(secao, item_id)
    titulo, _icone, _texto = descobrir.SECOES[secao]
    return _render("descobrir_item.html", usuario, "descobrir", secao=secao, secao_titulo=titulo, item=item,
                   tipo=descobrir.TIPO_ROTULO[secao], csrf=_csrf_token(),
                   marcados=descobrir.selecionados(session))


def view_descobrir_simulacao(item_id):
    """Fragmento da simulação (verba e praças) que a ficha da estratégia troca sem recarregar."""
    sim = descobrir.simulacao_estrategia(item_id, request.args.get("verba"), request.args.get("pracas"))
    resp = current_app.make_response(render_template("area_cliente/_estrategia_simulacao.html", sim=sim))
    resp.headers["Cache-Control"] = "no-store"
    return resp


def view_descobrir_selecao():
    _checar_csrf()
    nome = request.form.get("nome", "")
    # Só a ficha manda verba: aí a estratégia já incluída é atualizada com a nova simulação, não tirada.
    simulada = request.form.get("secao") == "estrategias" and bool(request.form.get("verba"))
    if simulada:
        nome = descobrir.nome_simulacao(request.form.get("id"), request.form.get("verba"), request.form.get("pracas"))
    incluido = descobrir.alternar(session, request.form.get("secao", ""), request.form.get("id"), nome, atualizar=simulada)
    if request.headers.get("X-Requested-With") == "fetch":
        # O botão troca de estado sem recarregar; "total" atualiza os contadores do menu e do CTA.
        return jsonify(incluido=incluido, total=len(descobrir.selecao(session)), limite=descobrir.LIMITE_SELECAO)
    destino = request.form.get("voltar") or area_url("descobrir_secao", secao="canais")
    if not destino.startswith("/") or destino.startswith("//"):
        destino = area_url("descobrir_secao", secao="canais")
    return redirect(destino, code=303)


def view_campanhas(usuario):
    ritmo = dados.ritmo_campanhas(usuario["cliente_id"])
    filtro = request.args.get("status")
    if filtro not in dados.GRUPOS_CAMPANHA:
        # Sem nada em andamento, a página abre nas finalizadas: é onde estão as campanhas para olhar.
        filtro = "andamento" if ritmo["grupos"]["andamento"] else "finalizadas"
    rotulos = {k: v[0] for k, v in dados.GRUPOS_CAMPANHA.items()}
    abas_itens = [(k, rotulos[k], len(ritmo["grupos"][k])) for k in rotulos]
    return _render("campanhas.html", usuario, "campanhas", ritmo=ritmo, filtro=filtro, grupos_rotulo=rotulos, abas_itens=abas_itens,
                   painel_dados=[_painel_campanha(c, rotulos[filtro], ritmo["historico"]) for c in ritmo["grupos"][filtro]])


RITMO_TXT = {"adiantado": "Adiantada", "no_ritmo": "No ritmo", "atencao": "Em otimização"}


def _br(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if iso else "—"


def _num(valor):
    try:
        return float(valor) if valor is not None else None
    except (TypeError, ValueError):
        return None


def _painel_campanha(c, status, historico=None) -> dict:
    """Painel lateral de uma campanha (sem custo): anel entrega x tempo, números, comparação com
    o histórico do cliente na mesma plataforma, projeção ao fim e ações."""
    pct, tempo = c.get("pct"), c.get("tempo_pct")
    no_ar = bool(c.get("no_ar"))
    dias = c.get("dias_restantes")
    nums = [{"rotulo": "Entregue", "valor": _num(c.get("atingido")), "texto": c.get("atingido_label") or "—"},
            {"rotulo": "Meta", "valor": _num(c.get("meta")), "texto": c.get("meta_label") or "—"}]
    proj = dados.projecao(c)
    if proj is not None:
        nums.append({"rotulo": "Projeção ao fim", "valor": proj, "formato": "pct", "nota": "no ritmo atual"})
    elif no_ar and dias is not None and dias >= 0:
        nums.append({"rotulo": "Restam", "valor": dias, "nota": "dias" if dias != 1 else "dia"})
    else:
        nums.append({"rotulo": "Período", "texto": "Encerrado" if dias is not None and dias < 0 else "—"})
    ref = (historico or {}).get(c.get("plataforma") or "Outras")
    compara = []
    if ref and pct is not None:
        base = proj if proj is not None else pct
        dif = base - ref["media"]
        compara = [{"rotulo": ("Projeção desta campanha" if proj is not None else "Esta campanha"), "pct": base, "ritmo": "adiantado" if dif >= 0 else "atencao"},
                   {"rotulo": f"Média das suas campanhas em {c.get('plataforma') or 'outras plataformas'} ({ref['n']})", "pct": ref["media"], "ritmo": "tempo"}]
    parte = c.get("contraparte") or {}
    acoes = []
    if c.get("dash_abrir"):
        acoes.append({"rotulo": "Dashboard do PI" if c.get("dash_compartilhado") else "Abrir dashboard",
                      "href": c["dash_abrir"], "primario": True, "externo": True, "icone": "chart"})
    acoes += [{"rotulo": "Abrir PI", "href": area_url("pi", id_pi=c["projeto_id"]), "primario": not c.get("dash_abrir"), "icone": "file"},
              {"rotulo": "Visão 360°", "href": area_url("projeto", id_pi=c["projeto_id"]), "icone": "layout"}]
    return {
        "tipo": "campanha", "eyebrow": status, "titulo": c["nome"], "logo": c.get("plataforma_logo") or "",
        "sub": " · ".join(x for x in (c.get("plataforma"), c.get("objetivo")) if x and x != "—"),
        "pct": pct, "tempo": tempo if no_ar else None,
        "ritmo": c.get("ritmo") if no_ar else "", "ritmo_txt": RITMO_TXT.get(c.get("ritmo") or "", ""),
        "dif": (pct - tempo) if (no_ar and pct is not None and tempo is not None) else None,
        "nums": nums,
        "barras_titulo": "Comparado ao seu histórico" if compara else ("Entrega e tempo" if no_ar and tempo is not None else ""),
        "barras": compara or ([{"rotulo": "Entrega da meta", "pct": pct, "ritmo": c.get("ritmo") or ""},
                               {"rotulo": "Tempo decorrido do período", "pct": tempo, "ritmo": "tempo"}]
                              if no_ar and pct is not None and tempo is not None else []),
        "defs": [{"rotulo": "Período", "valor": f"{_br(c['periodo']['inicio'])} a {_br(c['periodo']['fim'])}"},
                 {"rotulo": "PI", "valor": c.get("pi") or "—", "href": area_url("pi", id_pi=c["projeto_id"])},
                 {"rotulo": parte.get("rotulo") or "Agência", "valor": parte.get("nome") or "—"}],
        "acoes": acoes,
    }


def _painel_pi(p, campanhas, extras=None) -> dict:
    """Painel lateral de um PI: entrega média, campanhas em barras e atalhos (relatório, links)."""
    extras = extras or {}
    pcts = [c["pct"] for c in campanhas if c.get("pct") is not None]
    pct = round(sum(pcts) / len(pcts)) if pcts else None
    no_ar = [c for c in campanhas if c.get("no_ar")]
    tempo = p.get("tempo_pct") if no_ar else None
    parte = p.get("contraparte") or {}
    nums = [{"rotulo": "Campanhas no ar" if no_ar else "Campanhas", "valor": len(no_ar) if no_ar else len(campanhas),
             "nota": f"de {len(campanhas)}" if no_ar and len(no_ar) != len(campanhas) else ""}]
    nums += extras.get("nums", [])
    if pct is not None and tempo and tempo >= 5:
        nums.append({"rotulo": "Projeção ao fim", "valor": round(pct * 100 / tempo), "formato": "pct", "nota": "no ritmo atual"})
    media = extras.get("media_pis")
    if media is not None and pct is not None:
        nums.append({"rotulo": "Média dos seus PIs", "valor": media, "formato": "pct", "nota": "encerrados"})
    dash = dados.dash_do_pi(campanhas)
    acoes = [{"rotulo": "Ver relatório do PI", "href": f"{area_url('relatorios')}?pi={p['id']}", "primario": True, "icone": "chart"},
             {"rotulo": "Abrir PI", "href": area_url("pi", id_pi=p["id"]), "icone": "file"},
             {"rotulo": "Visão 360°", "href": area_url("projeto", id_pi=p["id"]), "icone": "layout"}]
    if dash:
        acoes.append({"rotulo": "Dashboard do PI", "href": dash, "externo": True, "icone": "chart"})
    if p.get("link_publico"):
        acoes.append({"rotulo": "Acompanhamento", "href": p["link_publico"], "externo": True, "icone": "globe"})
    if p.get("prestacao"):
        acoes.append({"rotulo": "Prestação de contas", "href": p["prestacao"], "externo": True, "icone": "file"})
    ordem = sorted(campanhas, key=lambda c: (not c.get("no_ar"), c.get("pct") if c.get("pct") is not None else -1))
    return {
        "tipo": "pi", "eyebrow": p.get("status") or "PI", "titulo": p.get("titulo") or p.get("pi"),
        "sub": f"{p.get('pi')} · {_br(p['periodo']['inicio'])} a {_br(p['periodo']['fim'])}",
        "pct": pct, "tempo": tempo, "ritmo": p.get("ritmo") if no_ar else "", "ritmo_txt": RITMO_TXT.get(p.get("ritmo") or "", ""),
        "dif": (pct - tempo) if (pct is not None and tempo is not None) else None,
        "nums": nums,
        "barras_titulo": "Entrega por campanha" if campanhas else "",
        "barras": [{"rotulo": c["nome"], "pct": c.get("pct"), "ritmo": (c.get("ritmo") or "") if c.get("no_ar") else ("adiantado" if (c.get("pct") or 0) >= 100 else ""),
                    "marca": c.get("tempo_pct") if c.get("no_ar") else None} for c in ordem[:10]],
        "defs": [{"rotulo": parte.get("rotulo") or "Agência", "valor": parte.get("nome") or "—"},
                 {"rotulo": "Situação", "valor": p.get("status") or "—"}],
        "acoes": acoes,
    }


def view_relatorios(usuario):
    """Lista de PIs por situação (abas iguais às de PIs); ?pi=<id> abre o relatório do PI."""
    pis = dados.relatorios(usuario["cliente_id"])
    escolhido = request.args.get("pi", type=int)
    atual = next((p for p in pis if p["id"] == escolhido), None) if escolhido else None
    grupos = {"abertos": [p for p in pis if p["aberto"]], "finalizados": [p for p in pis if not p["aberto"]]}
    filtro = request.args.get("status")
    if filtro not in PIS_FILTROS:
        filtro = "abertos" if grupos["abertos"] else "finalizados"          # nada em andamento: abre nos finalizados
    comp = dados.comparativos(pis) if pis else None
    media_pis = comp["media_pis"] if comp else None
    abas = [(k, v, len(grupos[k])) for k, v in PIS_FILTROS.items()]
    lista = grupos[filtro]
    for p in lista:                                                          # mesmas peças de plataforma da lista de PIs
        p["plats"] = [{"nome": n, "logo": plataformas.logo(n), "iniciais": plataformas.iniciais(n)} for n in p.get("plataformas") or []]
    painel = [] if atual else [_painel_pi(p, p["ativas"], {"nums": [
        {"rotulo": "Dashboards", "valor": p.get("dashboards") or 0},
        {"rotulo": "Em otimização", "valor": p["kpis"]["atencao"]} if p.get("no_ar") else {"rotulo": "Entrega média", "texto": f"{p['kpis']['entrega_media']}%" if p["kpis"]["entrega_media"] is not None else "—"},
    ], "media_pis": media_pis}) for p in lista]
    return _render("relatorios.html", usuario, "relatorios", pis=pis, atual=atual, filtro=filtro, filtros=PIS_FILTROS,
                   lista=lista, abas_itens=abas, painel_dados=painel, comp=comp)


PIS_FILTROS = {"abertos": "Em andamento", "finalizados": "Finalizados"}      # sem "Todos": só a busca olha os dois grupos


def _pre_pis(usuario, codigos_reais) -> list[dict]:
    """Pré-PIs (Entrada de PI) do cliente ou da agência, para a etapa "Pré-aprovação" da lista de PIs. Some quando o PI já virou PI de verdade."""
    from ..pi_entrada import hub, repositorio
    try:
        if demo.ativo(usuario["cliente_id"]):
            brutas = demo.pre_pis()
        else:
            brutas = repositorio.pre_pis_do_cliente(usuario["cliente_id"])
        linhas = [hub.linha_pre_pi(e) for e in brutas]
    except Exception:
        current_app.logger.warning("Pré-PIs indisponíveis na lista de PIs.", exc_info=True)
        return []
    saida = []
    for l in linhas:
        l["plataformas"] = [{"nome": n, "logo": plataformas.logo(n), "iniciais": plataformas.iniciais(n)} for n in l["plataformas"]]
        if l["pi"] not in codigos_reais or l["pi"] == "—":
            saida.append(l)
    return saida


def view_pis(usuario):
    termo = request.args.get("q", "").strip()[:80]
    todos = dados.listar_pis(usuario["cliente_id"])
    pre = _pre_pis(usuario, {p["pi"] for p in todos})
    contagem = {"abertos": sum(1 for p in todos if p["status_id"] in dados.SUB_STATUS_ABERTOS) + len(pre),
                "finalizados": sum(1 for p in todos if p["status_id"] not in dados.SUB_STATUS_ABERTOS),
                "todos": len(todos) + len(pre)}
    filtro = request.args.get("status")
    if filtro not in PIS_FILTROS:
        # Busca olha todos os PIs; sem busca, abre nos finalizados quando nada está em andamento.
        filtro = "todos" if termo else ("abertos" if contagem["abertos"] else "finalizados")
    if filtro == "abertos":
        pis = [p for p in todos if p["status_id"] in dados.SUB_STATUS_ABERTOS]
    elif filtro == "finalizados":
        pis = [p for p in todos if p["status_id"] not in dados.SUB_STATUS_ABERTOS]
    else:
        pis = todos
    pre_visiveis = pre if filtro in ("abertos", "todos") else []
    if termo:
        t = termo.lower()
        pis = [p for p in pis if t in p["pi"].lower() or t in (p["titulo"] or "").lower()
               or t in ((p.get("contraparte") or {}).get("nome") or "").lower()]
        pre_visiveis = [p for p in pre_visiveis if t in p["pi"].lower() or t in (p["titulo"] or "").lower() or t in (p["agencia"] or "").lower()]
    por_pi: dict = {}
    for c in dados.campanhas_dos_pis([p["id"] for p in pis]):
        por_pi.setdefault(c["id_pi"], []).append(c)
    painel = []
    for p in pis:
        p["plataformas"] = plataformas.resumo(por_pi.get(p["id"], []))
        painel.append(_painel_pi(p, por_pi.get(p["id"], []), {"nums": [
            {"rotulo": "Valor líquido", "valor": p.get("liquido"), "formato": "brl"} if p.get("liquido") is not None else {"rotulo": "Valor líquido", "texto": "—"},
            {"rotulo": "Notas fiscais", "valor": p.get("n_notas") or 0, "nota": f"{p.get('n_pagas') or 0} pagas" if p.get("n_notas") else "nenhuma ainda"},
        ]}))
    return _render("pis.html", usuario, "pis", pis=pis, pre_pis=pre_visiveis, etapas=dados.ETAPAS_PI, termo=termo,
                   filtro=filtro, filtros=PIS_FILTROS, contagem=contagem, painel_dados=painel,
                   abas_itens=[(k, v, contagem[k]) for k, v in PIS_FILTROS.items()])


def view_pi(usuario, id_pi):
    pi = dados.pi_do_cliente(usuario["cliente_id"], id_pi)
    if pi is None:
        abort(404)
    campanhas = dados.campanhas_dos_pis([id_pi])
    if pi.get("status_id") == dados.SUB_STATUS_FINALIZADO:
        # PI encerrado: campanha que ficou "Ativa" no cadastro aparece como finalizada para o cliente.
        for c in campanhas:
            if c.get("no_ar"):
                c["status"], c["no_ar"] = "Finalizada", False
    try:
        projetos = dados.listar_projetos(usuario["cliente_id"])
        historico, media_pis = dados.historico_plataformas(projetos), dados.media_pis_encerrados(projetos)
    except Exception:
        current_app.logger.warning("Histórico de comparação indisponível no PI.", exc_info=True)
        historico, media_pis = {}, None
    for c in campanhas:
        c["projecao"] = dados.projecao(c)
        ref = historico.get(c.get("plataforma") or "Outras")
        base = c["projecao"] if c["projecao"] is not None else c.get("pct")
        c["vs_media"] = {"dif": base - ref["media"], "media": ref["media"], "n": ref["n"]} if ref and base is not None else None
    pcts = [c["pct"] for c in campanhas if c.get("pct") is not None]
    comp = {"pct": round(sum(pcts) / len(pcts)) if pcts else None, "media_pis": media_pis,
            "dash_pi": dados.dash_do_pi(campanhas)}
    return _render("pi.html", usuario, "pis", pi=pi, campanhas=campanhas, plats=plataformas.resumo(campanhas), comp=comp)


def view_equipe(usuario):
    """Equipe (só consulta): pessoas da empresa e das agências parceiras cadastradas, com o acesso ao hub, e o time Centralcomm."""
    from . import equipe
    time_ = demo.equipe(usuario) if demo.ativo(usuario["cliente_id"]) else equipe.montar(usuario)
    from .pi_envio import _whatsapp_motivo
    return _render("equipe.html", usuario, "equipe", time=time_,
                   whatsapp=_whatsapp_motivo(usuario, "Quero incluir ou tirar uma pessoa do hub de mídia."))


def view_em_preparacao(usuario, endpoint):
    titulo, icone, texto = EM_PREPARACAO[endpoint]
    return _render("em_preparacao.html", usuario, endpoint, titulo=titulo, icone=icone, texto=texto)


LIMITE_IA_PRACAS = (20, 600)  # chamadas por janela de segundos, por sessão


def view_briefing_pracas():
    """Praças do briefing. ``modo=organizar`` (padrão do botão, sem IA, instantâneo): devolve a lista inteira corrigida, no
    formato único e sem repetidas, a partir das escolhidas e do texto digitado. ``modo=sugerir``: a IA lê só o que o
    organizador não reconheceu e sugere praças próximas."""
    _checar_csrf()
    from . import pracas as org
    texto = (request.form.get("texto") or "").strip()[:600]
    escolhidas = [e[:400] for e in request.form.getlist("escolhidas")][:briefing.MAX_PRACAS]
    if request.form.get("modo", "organizar") == "organizar":
        return jsonify(pracas=org.organizar(escolhidas + ([texto] if texto else []))[:briefing.MAX_PRACAS])
    agora = time.time()
    janela = [t for t in session.get("area_cliente_ia_pracas", []) if agora - t < LIMITE_IA_PRACAS[1]]
    if len(janela) >= LIMITE_IA_PRACAS[0]:
        return jsonify(erro="Muitas consultas seguidas. Tente de novo em alguns minutos."), 429
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
    if request.method not in {"GET", "HEAD"} and endpoint not in {"briefing", "briefing_pracas", "descobrir_selecao", "ver_como", "ver_como_sair", "solicitar_acesso", "pi_enviar", "pi_enviado_enviar", "briefing_planejamento", "briefing_pi_antigo", "briefing_cotacao", "briefing_cotacao_enviar", "briefing_anexo"}:
        abort(405)
    if endpoint == "sair":
        return view_sair()
    if endpoint == "ver_como_sair":
        return view_ver_como_sair()
    if endpoint == "solicitar_acesso":
        if "user_id" not in session:
            return redirect("/login")
        return view_solicitar_acesso()
    if endpoint == "estrategia_publica":
        return view_estrategia_publica(**args)
    if endpoint == "estrategia_publica_simulacao":
        return view_estrategia_publica_simulacao(**args)
    if endpoint == "descobrir_estrategia_id":
        return view_descobrir_estrategia_id(**args)
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
    if endpoint == "briefing_planejamento":
        return view_briefing_form(usuario)
    if endpoint == "briefing_pi_antigo":
        return view_briefing_pi_antigo(usuario)
    if endpoint == "briefing_todos":
        return view_briefing_todos(usuario)
    if endpoint == "briefing_anexo":
        return cotacao_envio.view_anexo(usuario)
    if endpoint == "briefing_anexo_dados":
        return cotacao_envio.view_anexo_dados(usuario, **args)
    if endpoint == "briefing_cotacao":
        return cotacao_envio.view_cotacao(usuario)
    if endpoint == "briefing_cotacao_rascunho":
        return cotacao_envio.view_cotacao_rascunho(usuario, **args)
    if endpoint == "briefing_cotacao_status":
        return cotacao_envio.view_cotacao_status(usuario, **args)
    if endpoint == "briefing_cotacao_enviar":
        return cotacao_envio.view_cotacao_enviar(usuario, **args)
    if endpoint == "planejamento_antigo":
        return redirect(area_url("descobrir_secao", secao="canais"), code=301)
    if endpoint == "midia_antigo":
        return redirect(area_url("campanhas"), code=301)
    if endpoint == "arquivos_antigo":
        return redirect(area_url("pis"), code=301)
    if endpoint == "campanhas":
        return view_campanhas(usuario)
    if endpoint == "conhecer":
        return view_conhecer(usuario, **args)
    if endpoint == "pis":
        return view_pis(usuario)
    if endpoint == "pi_enviar":
        return pi_envio.view_pi_enviar(usuario)
    if endpoint == "pi_enviado":
        return pi_envio.view_pi_enviado(usuario, **args)
    if endpoint == "pi_enviado_status":
        return pi_envio.view_pi_enviado_status(usuario, **args)
    if endpoint == "pi_enviado_enviar":
        return pi_envio.view_pi_enviado_enviar(usuario, **args)
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
    if endpoint == "descobrir_estrategia":
        return view_descobrir_estrategia(usuario, **args)
    if endpoint == "descobrir_selecao":
        return view_descobrir_selecao()
    if endpoint == "descobrir_simulacao":
        return view_descobrir_simulacao(**args)
    if endpoint == "projetos":
        destino = area_url("pis") + (f"?{urlencode({'q': request.args['q']})}" if request.args.get("q") else "")
        return redirect(destino, code=301)
    if endpoint == "projeto":
        return view_projeto(usuario, **args)
    if endpoint == "equipe":
        return view_equipe(usuario)
    return view_em_preparacao(usuario, endpoint)


def register(app) -> None:
    from .marca import GLOBAIS_JINJA
    app.jinja_env.globals.update(GLOBAIS_JINJA)
    app.before_request(despachar)
