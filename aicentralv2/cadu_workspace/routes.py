"""Área autenticada de conta e administração do workspace.centralcomm.media."""

from pathlib import Path
from urllib.parse import urlparse

from flask import Blueprint, Response, abort, current_app, redirect, render_template, request, send_file, session, url_for

from ..auth import login_required
from ..cadu_skills.repository import credit_position, customization_targets, list_customizations
from ..product_domains import product_url


bp = Blueprint("cadu_workspace", __name__)


def _php_account_data(client_id: int) -> dict:
    """Read the established Cadu PHP records; Workspace owns no account copy."""
    from .. import db
    from ..cadu_credits import calculate_credit_position

    try:
        people = [dict(row) for row in db.obter_contatos_por_cliente(client_id)]
        plans = [dict(row) for row in db.obter_planos_clientes({"cliente_id": client_id})]
        credit_rows = [dict(row) for row in db.obter_gestao_creditos_clientes({
            "cliente_id": client_id, "plan_status": "active",
        })]
    except Exception:
        people, plans, credit_rows = [], [], []

    plan = next((row for row in plans if row.get("plan_status") == "active"), plans[0] if plans else {})
    credit = credit_rows[0] if credit_rows else {}
    monthly_limit = int(credit.get("monthly_limit", plan.get("pd_limit_image_generation", plan.get("image_credits_monthly", 0))) or 0) or 500
    position = calculate_credit_position(
        monthly_limit,
        credit.get("used", plan.get("image_credits_used_current_month", 0)),
        credit.get("adjustments", 0),
    ) if plan or credit else None
    return {"people": people, "plan": plan, "credit": credit, "position": position}


def _workspace_host_only():
    expected = (urlparse(str(current_app.config.get("WORKSPACE_URL") or "")).hostname or "").lower()
    actual = request.host.split(":", 1)[0].lower()
    if actual not in {expected, "localhost", "127.0.0.1"}:
        abort(404)


def _cadu_area(config_key: str, path: str) -> str:
    return str(current_app.config.get(config_key) or product_url("cadu", path))


@bp.get("/workspace")
@bp.get("/workspace/")
def index():
    return render_template(
        "cadu_workspace/public.html",
        canonical=product_url("workspace"),
        description="O ambiente Cadu que reúne conta, projetos, contexto, créditos e acesso aos produtos da organização.",
    )


PUBLIC_PAGES = {
    "como-funciona": {
        "title": "Como funciona",
        "description": "Entenda como o Cadu Workspace preserva o contexto entre projetos, pessoas e produtos.",
        "lead": "Um ponto de partida para o time organizar o trabalho antes de planejar, criar ou conectar dados.",
    },
    "planos": {
        "title": "Planos",
        "description": "Conheça a estrutura de planos e créditos do ecossistema Cadu.",
        "lead": "A mesma conta atende todo o time no Cadu. Capacidade, créditos e número de pessoas variam por plano.",
    },
    "ajuda": {
        "title": "Ajuda",
        "description": "Respostas sobre acesso, projetos, créditos, privacidade e produtos Cadu.",
        "lead": "Orientações curtas para começar e saber onde administrar cada parte da conta.",
    },
    "contato": {
        "title": "Contato",
        "description": "Fale com a CentralComm sobre acesso, implantação ou suporte ao Cadu Workspace.",
        "lead": "Conte o que sua equipe precisa organizar. Direcionamos a conversa para produto, implantação ou suporte.",
    },
}

PRODUCT_ENTRIES = {
    "cadu": ("Cadu", "Inteligência de mídia", "Traga a decisão de mídia para um só lugar.", "Pesquise públicos, formatos, canais e ferramentas de campanha a partir do contexto do seu time."),
    "workspace": ("Workspace", "Conta e contexto", "Comece pelo contexto certo.", "Organize o time, os projetos, os créditos e os acessos antes de abrir uma solução especializada."),
    "planner": ("Planner", "Planejamento de mídia", "Planeje antes de investir.", "Estruture objetivos, público, canais e recomendações em um plano pronto para a próxima decisão."),
    "studio": ("Studio", "Criação de conteúdo", "Crie para o formato que importa.", "Transforme uma direção criativa em peças, variações e formatos preparados para a campanha."),
    "skills": ("Skills", "Conhecimento especialista", "Aplique o método certo no momento certo.", "Encontre skills e agentes especializados para pesquisar, decidir e executar com mais contexto."),
    "connect": ("Connect", "Conexões e operação", "Conecte a operação ao trabalho.", "Organize integrações, campanhas e agentes que fazem os sistemas avançarem juntos."),
}


@bp.get("/entrada/<product>")
def product_entry(product):
    product = str(product or "").lower()
    item = PRODUCT_ENTRIES.get(product)
    if not item:
        abort(404)
    entry = dict(zip(("name", "eyebrow", "title", "description"), item))
    entry["icon_family"] = "workspace" if product == "cadu" else product
    # A página pública do Cadu também mora no Workspace: o domínio cadu.* é a
    # aplicação PHP autenticada e não deve receber links para uma rota Flask.
    entry_host = "workspace" if product == "cadu" else product
    return render_template("cadu_workspace/product_entry.html", product=product, entry=entry, canonical=product_url(entry_host, f"/entrada/{product}"))


@bp.get("/workspace/<page>")
def public_page(page):
    content = PUBLIC_PAGES.get(page)
    if not content:
        abort(404)
    return render_template(
        "cadu_workspace/public_page.html", page=page, content=content,
        canonical=product_url("workspace", f"/{page}"), description=content["description"],
        help_url=_cadu_area("CADU_HELP_URL", "/ajuda"),
    )


@bp.get("/workspace/assets/workspace-icon-<int:size>.png")
def workspace_icon(size):
    if size not in {32, 64, 128, 192}:
        abort(404)
    asset = Path(__file__).resolve().parents[2] / "output" / "mockups" / "brand-assets" / "icons-2d" / "workspace" / f"icon-{size}.png"
    return send_file(asset, mimetype="image/png", max_age=86400)


@bp.get("/workspace/app")
@login_required
def dashboard():
    client_id = int(session.get("cliente_id") or 0)
    targets = customization_targets()
    projects = [item for item in targets["projects"] if int(item.get("client_id") or 0) == client_id]
    customizations = list_customizations(client_id=client_id)
    sections = (
        ("Usuários e equipe", "Pessoas, convites e permissões da organização.", url_for("cadu_workspace.account_page", section="equipe"), "Workspace"),
        ("Planos", "Plano contratado, limites e recursos habilitados.", url_for("cadu_workspace.account_page", section="planos"), "Workspace"),
        ("Créditos", "Saldo, consumo e histórico compartilhado entre produtos.", url_for("cadu_workspace.account_page", section="creditos"), "Workspace"),
        ("Financeiro", "Faturas, pagamentos e dados de cobrança.", _cadu_area("CADU_FINANCE_URL", "/financeiro"), "PHP Cadu"),
        ("Integrações", "Conexões multiproduto já administradas pelo Cadu.", _cadu_area("CADU_INTEGRATIONS_URL", "/integracoes"), "PHP Cadu"),
        ("Ajuda", "Orientação de uso e canais de atendimento.", _cadu_area("CADU_HELP_URL", "/ajuda"), "PHP Cadu"),
    )
    return render_template(
        "cadu_workspace/index.html", sections=sections, projects=projects,
        customizations=customizations, credit=credit_position(client_id),
    )


@bp.get("/workspace/app/<section>")
@login_required
def account_page(section):
    aliases = {"usuarios": "equipe", "equipe": "equipe", "planos": "planos", "creditos": "creditos"}
    section = aliases.get(section)
    if section is None:
        abort(404)
    return render_template(
        "cadu_workspace/account.html", section=section,
        account=_php_account_data(int(session.get("cliente_id") or 0)),
    )


@bp.get("/workspace/agentes")
def agents():
    return redirect(url_for("cadu_skills.agents"), code=302)


@bp.get("/workspace/minhas-skills")
@login_required
def my_skills():
    return render_template(
        "cadu_workspace/my_skills.html",
        customizations=list_customizations(client_id=int(session.get("cliente_id") or 0)),
    )


@bp.get("/robots.txt")
def robots():
    _workspace_host_only()
    body = "\n".join((
        "User-agent: *", "Allow: /workspace/", "Allow: /workspace/como-funciona",
        "Allow: /workspace/planos", "Allow: /workspace/ajuda", "Allow: /workspace/contato",
        "Disallow: /workspace/app", "Disallow: /workspace/minhas-skills",
        f"Sitemap: {product_url('workspace', '/sitemap.xml')}", "",
    ))
    return Response(body, mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap():
    _workspace_host_only()
    paths = ("/", "/como-funciona", "/planos", "/ajuda", "/contato")
    urls = "".join(f"<url><loc>{product_url('workspace', path)}</loc></url>" for path in paths)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>', mimetype="application/xml")


@bp.get("/llms.txt")
def llms():
    _workspace_host_only()
    lines = [
        "# Cadu Workspace", "",
        "> O ponto de partida público e autenticado para organizar o trabalho na família Cadu.", "",
        "## Páginas públicas", "",
        f"- [Visão geral]({product_url('workspace')})",
        f"- [Como funciona]({product_url('workspace', '/como-funciona')})",
        f"- [Planos]({product_url('workspace', '/planos')})",
        f"- [Ajuda]({product_url('workspace', '/ajuda')})",
        f"- [Contato]({product_url('workspace', '/contato')})", "",
        "## Conteúdo público relacionado", "",
        f"- [Agentes e capacidades]({product_url('skills', '/agentes')})",
        f"- [Skills públicas testáveis]({product_url('skills')})", "",
        "Áreas autenticadas", "",
        "Projetos, skills personalizadas, créditos, clientes, campanhas, contas, MCPs e relatórios são privados e não fazem parte do sitemap.", "",
    ]
    return Response("\n".join(lines), mimetype="text/plain")
