"""Área autenticada de conta e administração do workspace.centralcomm.media."""

from pathlib import Path
import json
import re
from typing import Optional
from urllib.parse import urlparse
from uuid import uuid4
import secrets

from werkzeug.exceptions import HTTPException

from flask import Blueprint, Response, abort, current_app, jsonify, redirect, render_template, request, send_file, session, url_for

from ..auth import login_required
from ..cadu_family import repository as family_repository
from ..cadu_skills.repository import credit_position, customization_targets, list_customizations
from ..db import get_db
from ..product_domains import product_url


bp = Blueprint("cadu_workspace", __name__)
# The advanced brand editor has a Workspace-owned API prefix.  Its handlers
# are registered during app setup, alongside this product blueprint.
brand_api_bp = Blueprint("workspace_brand_api", __name__, url_prefix="/workspace")


@bp.before_request
def prepare_shared_cadu_chat():
    if session.get("user_id"):
        session.setdefault("family_csrf", secrets.token_urlsafe(32))


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
    try:
        invites = [dict(row) for row in db.obter_invites_cliente(client_id)]
    except Exception:
        invites = []
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT m.id, m.movement_type, m.amount, m.created_at
                     FROM cadu_credit_movements m
                     JOIN cadu_client_plans p ON p.id = m.plan_id
                    WHERE p.id_cliente = %s ORDER BY m.created_at DESC LIMIT 20""",
                (client_id,),
            )
            movements = [dict(row) for row in cursor.fetchall()]
    except Exception:
        movements = []
    return {"people": people, "invites": invites, "plan": plan, "credit": credit,
            "position": position, "movements": movements}


def _workspace_host_only():
    expected = (urlparse(str(current_app.config.get("WORKSPACE_URL") or "")).hostname or "").lower()
    actual = request.host.split(":", 1)[0].lower()
    if actual not in {expected, "localhost", "127.0.0.1"}:
        abort(404)


def _cadu_area(config_key: str, path: str) -> str:
    return str(current_app.config.get(config_key) or product_url("cadu", path))


def _workspace_brands(client_id: int, query: str = "") -> list[dict]:
    """Read brand records owned by the active Workspace organization."""
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT c.id, c.name, c.sector, c.website_url, c.primary_color,
                          c.secondary_color, c.logo_upload_path, c.brand_profile,
                          c.analysis_metadata, c.updated_at,
                          COUNT(a.id) FILTER (WHERE a.status = 'approved') AS asset_count,
                          COUNT(a.id) FILTER (WHERE a.role = 'logo' AND a.is_primary) AS has_logo
                     FROM cx_clients c
                LEFT JOIN cx_client_brand_assets a ON a.client_id = c.id
                    WHERE c.crm_client_id = %s
                      AND c.name ILIKE %s
                 GROUP BY c.id
                 ORDER BY c.updated_at DESC NULLS LAST, c.name""",
                (client_id, '%' + query[:100] + '%'),
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []


def _workspace_brand(client_id: int, brand_id: int) -> Optional[dict]:
    brands = _workspace_brands(client_id)
    brand = next((item for item in brands if int(item['id']) == brand_id), None)
    if not brand:
        return None
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, role, source_kind, source_url, page_url, asset_path,
                          mime_type, width, height, score, status, is_primary,
                          metadata, created_at
                     FROM cx_client_brand_assets
                    WHERE client_id = %s
                 ORDER BY is_primary DESC, score DESC NULLS LAST, id DESC""",
                (brand_id,),
            )
            brand['assets'] = [dict(row) for row in cursor.fetchall()]
    except Exception:
        brand['assets'] = []
    for field in ('brand_profile', 'analysis_metadata'):
        value = brand.get(field)
        if isinstance(value, str):
            try:
                brand[field] = json.loads(value)
            except (TypeError, ValueError):
                brand[field] = {}
        elif not isinstance(value, dict):
            brand[field] = {}
    profile = brand['brand_profile']
    identity_fields = ('tone_of_voice', 'target_audience', 'positioning', 'brand_values')
    identity_total = sum(bool(profile.get(field)) for field in identity_fields)
    score = round((identity_total / len(identity_fields)) * 55)
    score += 25 if brand.get('analysis_metadata') else 0
    score += 10 if brand.get('has_logo') else 0
    score += 10 if brand.get('assets') else 0
    missing = []
    if not brand.get('has_logo'):
        missing.append('logo principal')
    if not brand.get('analysis_metadata'):
        missing.append('auditoria de marca')
    if identity_total < len(identity_fields):
        missing.append('diretrizes de identidade')
    brand['readiness'] = {'score': score, 'missing': missing}
    brand['activity'] = sorted((
        {'title': 'Ativo registrado', 'detail': item.get('role') or 'Ativo de marca', 'at': item.get('created_at')}
        for item in brand['assets'] if item.get('created_at')
    ), key=lambda item: str(item['at']), reverse=True)[:6]
    return brand


def _brand_linked_projects(client_id: int, brand_id: int) -> list[dict]:
    """Return only projects from this organization that explicitly use a brand."""
    try:
        links = family_repository.project_brand_links(client_id)
        project_refs = {
            str(item.get('project_ref') or '')
            for item in links
            if str(item.get('brand_ref') or '') == f'studio:{brand_id}'
        }
    except Exception:
        return []
    return [
        project for project in _workspace_projects(client_id, status='todos')
        if f"ci:{project['id']}" in project_refs
    ]


def _workspace_projects(client_id: int, query: str = "", status: str = "ativos") -> list[dict]:
    """Project dossiers retained from Cadu, always isolated by organization."""
    status = status if status in {'ativos', 'arquivados', 'todos'} else 'ativos'
    status_clause = "p.status = 'ativo'" if status == 'ativos' else "p.status = 'arquivado'" if status == 'arquivados' else "p.status <> 'deletado'"
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT p.id, p.nome, p.descricao, p.tipo, p.cor, p.status,
                          p.instrucoes, p.tom_de_voz, p.publico, p.posicionamento,
                          p.total_arquivos, p.total_conversas, p.updated_at,
                          COUNT(DISTINCT a.id) FILTER (WHERE a.indexing_status = 'completed') AS fontes_prontas,
                          COUNT(DISTINCT a.id) AS fontes_total, COUNT(DISTINCT ch.id) AS chunks_total
                     FROM cadu_ci_projetos p
                LEFT JOIN cadu_ci_projeto_arquivos a ON a.projeto_id = p.id
                LEFT JOIN cadu_ci_chunks ch ON ch.projeto_id = p.id
                    WHERE p.id_cliente = %s AND """ + status_clause + """
                      AND (p.nome ILIKE %s OR COALESCE(p.descricao, '') ILIKE %s)
                 GROUP BY p.id ORDER BY p.updated_at DESC""",
                (client_id, '%' + query[:100] + '%', '%' + query[:100] + '%'),
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        # Older Cadu databases may still be missing narrative/RAG migrations.
        # Keep the dossier visible and let its missing capabilities read as empty.
        try:
            with get_db().cursor() as cursor:
                cursor.execute(
                    """SELECT id, nome, descricao, tipo, cor, status, instrucoes,
                              total_arquivos, total_conversas, updated_at,
                              0 AS fontes_prontas, 0 AS fontes_total, 0 AS chunks_total
                         FROM cadu_ci_projetos
                        WHERE id_cliente = %s AND """ + status_clause.replace('p.', '') + """
                          AND (nome ILIKE %s OR COALESCE(descricao, '') ILIKE %s)
                     ORDER BY updated_at DESC""",
                    (client_id, '%' + query[:100] + '%', '%' + query[:100] + '%'),
                )
                records = [dict(row) for row in cursor.fetchall()]
                for record in records:
                    record.update({'tom_de_voz': '', 'publico': '', 'posicionamento': ''})
                return records
        except Exception:
            return []


def _project_context_health(project: dict) -> dict:
    """Make the readiness of a dossier explicit from records the team owns."""
    score = 0
    missing = []
    if project.get('descricao'):
        score += 15
    else:
        missing.append('uma descrição')
    if int(project.get('fontes_prontas') or 0):
        score += 25
    elif int(project.get('fontes_total') or 0):
        score += 12
        missing.append('fontes indexadas')
    else:
        missing.append('fontes para consulta')
    identity_fields = ('publico', 'tom_de_voz', 'posicionamento', 'instrucoes')
    identity_total = sum(bool(project.get(field)) for field in identity_fields)
    score += round(identity_total * 25 / len(identity_fields))
    if identity_total < len(identity_fields):
        missing.append('orientações de identidade')
    if project.get('conversations'):
        score += 15
    else:
        missing.append('conversas de trabalho')
    if project.get('smartdocs') or project.get('images'):
        score += 10
    else:
        missing.append('referências produzidas')
    if project.get('brands'):
        score += 10
    else:
        missing.append('uma marca vinculada')
    if score >= 80:
        label = 'Pronto para orientar o trabalho'
    elif score >= 45:
        label = 'Contexto em construção'
    else:
        label = 'Comece estruturando o contexto'
    return {'score': score, 'label': label, 'missing': missing[:3]}


def _project_recent_activity(project: dict) -> list[dict]:
    """A chronological, factual timeline assembled from the dossier records."""
    activity = []
    if project.get('updated_at'):
        activity.append({'title': 'Projeto atualizado', 'detail': project.get('nome'), 'at': project['updated_at']})
    for item in project.get('files', [])[:4]:
        activity.append({'title': 'Fonte adicionada', 'detail': item.get('nome_arquivo') or 'Arquivo', 'at': item.get('created_at')})
    for item in project.get('conversations', [])[:3]:
        activity.append({'title': 'Conversa atualizada', 'detail': item.get('titulo') or 'Conversa sem título', 'at': item.get('updated_at')})
    for item in project.get('smartdocs', [])[:3]:
        activity.append({'title': 'SmartDoc atualizado', 'detail': item.get('titulo') or 'Documento sem título', 'at': item.get('updated_at')})
    for item in project.get('images', [])[:3]:
        activity.append({'title': 'Referência visual adicionada', 'detail': item.get('title') or 'Imagem sem título', 'at': item.get('created_at')})
    return sorted(activity, key=lambda item: str(item.get('at') or ''), reverse=True)[:8]


def _workspace_project(client_id: int, project_id: str) -> Optional[dict]:
    # Archived dossiers remain readable and can be reactivated from their detail page.
    project = next((item for item in _workspace_projects(client_id, status='todos') if str(item['id']) == project_id), None)
    if not project:
        return None
    try:
        refs = family_repository.project_brand_links(client_id)
        linked = {str(item.get('brand_ref') or '') for item in refs if item.get('project_ref') == f'ci:{project_id}'}
        project['brands'] = [brand for brand in _workspace_brands(client_id) if f"studio:{brand['id']}" in linked]
    except Exception:
        project['brands'] = []
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, nome_arquivo, mime, tamanho, doc_form, indexing_status,
                          word_count, tokens, erro_msg, created_at
                     FROM cadu_ci_projeto_arquivos
                    WHERE projeto_id = %s AND id_cliente = %s ORDER BY created_at DESC""",
                (project_id, client_id),
            )
            project['files'] = [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                """SELECT id, titulo, total_mensagens, updated_at FROM cadu_conversations
                    WHERE projeto_id = %s AND id_cliente = %s ORDER BY updated_at DESC LIMIT 8""",
                (project_id, client_id),
            )
            project['conversations'] = [dict(row) for row in cursor.fetchall()]
    except Exception:
        project['files'] = []
        project['conversations'] = []
    # SmartDocs and visual references were part of the original dossier.  They
    # live in optional legacy tables, so each lookup degrades independently.
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, titulo, tipo, status, updated_at
                     FROM cadu_artifacts
                    WHERE projeto_id = %s AND id_cliente = %s
                 ORDER BY updated_at DESC LIMIT 12""",
                (project_id, client_id),
            )
            project['smartdocs'] = [dict(row) for row in cursor.fetchall()]
    except Exception:
        project['smartdocs'] = []
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT id, title, source, mime, file_path, created_at
                     FROM cadu_docs_client_images
                    WHERE projeto_id = %s AND id_cliente = %s AND ativo = true
                 ORDER BY created_at DESC LIMIT 12""",
                (project_id, client_id),
            )
            project['images'] = [dict(row) for row in cursor.fetchall()]
    except Exception:
        project['images'] = []
    project['context_health'] = _project_context_health(project)
    project['activity'] = _project_recent_activity(project)
    return project


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
    projects = _workspace_projects(client_id)
    brands = _workspace_brands(client_id)
    customizations = list_customizations(client_id=client_id)
    sections = (
        ("Usuários e equipe", "Pessoas, convites e permissões da organização.", url_for("cadu_workspace.account_page", section="equipe"), "Workspace"),
        ("Planos", "Plano contratado, limites e recursos habilitados.", url_for("cadu_workspace.account_page", section="planos"), "Workspace"),
        ("Créditos", "Saldo, consumo e histórico compartilhado entre produtos.", url_for("cadu_workspace.account_page", section="creditos"), "Workspace"),
        ("Financeiro", "Faturas, pagamentos e dados de cobrança.", _cadu_area("CADU_FINANCE_URL", "/financeiro"), "Conta"),
        ("Integrações", "Conexões autorizadas para os produtos da organização.", _cadu_area("CADU_INTEGRATIONS_URL", "/integracoes"), "Conta"),
        ("Ajuda", "Orientação de uso e canais de atendimento.", _cadu_area("CADU_HELP_URL", "/ajuda"), "Suporte"),
    )
    return render_template(
        "cadu_workspace/index.html", sections=sections, projects=projects, brands=brands,
        customizations=customizations, credit=credit_position(client_id),
    )


@bp.get('/workspace/app/conversas')
@login_required
def conversations():
    """Dedicated Cadu surface; message delivery remains in the shared guarded API."""
    return render_template('cadu_workspace/conversations.html')


@bp.get('/workspace/app/marcas')
@login_required
def brands():
    client_id = int(session.get('cliente_id') or 0)
    query = request.args.get('q', '')
    filter_name = request.args.get('filtro', 'todas')
    filter_name = filter_name if filter_name in {'todas', 'auditadas', 'com-ativos'} else 'todas'
    records = _workspace_brands(client_id, query)
    if filter_name == 'auditadas':
        records = [brand for brand in records if brand.get('analysis_metadata')]
    elif filter_name == 'com-ativos':
        records = [brand for brand in records if int(brand.get('asset_count') or 0)]
    return render_template('cadu_workspace/brands.html', brands=records, query=query, filter_name=filter_name)


@bp.get('/workspace/app/projetos')
@login_required
def projects():
    client_id = int(session.get('cliente_id') or 0)
    query = request.args.get('q', '')
    status = request.args.get('status', 'ativos')
    return render_template('cadu_workspace/projects.html', projects=_workspace_projects(client_id, query, status), query=query,
                           status=status if status in {'ativos', 'arquivados', 'todos'} else 'ativos')


@bp.post('/workspace/app/projetos')
@login_required
def create_project():
    name = ' '.join((request.form.get('name') or '').split())[:150]
    if len(name) < 2:
        abort(400, description='Informe um nome de projeto com ao menos dois caracteres.')
    client_id = int(session.get('cliente_id') or 0)
    project_id = str(uuid4())
    description = (request.form.get('description') or '').strip()[:4000]
    instructions = (request.form.get('instructions') or '').strip()[:12000]
    connection = None
    try:
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO cadu_ci_projetos
                       (id, id_cliente, criado_por, nome, descricao, instrucoes, tipo, cor, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'projeto', %s, 'ativo')""",
                (project_id, client_id, session.get('user_id'), name, description, instructions,
                 '#176b5e'),
            )
        connection.commit()
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass
        abort(503, description='Não foi possível criar o projeto agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.get('/workspace/app/projetos/<project_id>')
@login_required
def project_detail(project_id):
    client_id = int(session.get('cliente_id') or 0)
    project = _workspace_project(client_id, project_id)
    if not project:
        abort(404)
    return render_template('cadu_workspace/project_detail.html', project=project, brands=_workspace_brands(client_id))


@bp.post('/workspace/app/projetos/<project_id>/contexto')
@login_required
def update_project_context(project_id):
    client_id = int(session.get('cliente_id') or 0)
    if not _workspace_project(client_id, project_id):
        abort(404)
    name = ' '.join((request.form.get('name') or '').split())[:150]
    if len(name) < 2:
        abort(400, description='O projeto precisa de um nome com ao menos dois caracteres.')
    description = (request.form.get('description') or '').strip()[:4000]
    instructions = (request.form.get('instructions') or '').strip()[:12000]
    tone = (request.form.get('tone_of_voice') or '').strip()[:4000]
    audience = (request.form.get('audience') or '').strip()[:4000]
    positioning = (request.form.get('positioning') or '').strip()[:4000]
    color = (request.form.get('color') or '#176b5e').strip()[:20]
    connection = None
    try:
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cadu_ci_projetos SET nome = %s, descricao = %s, instrucoes = %s,
                          tom_de_voz = %s, publico = %s, posicionamento = %s, cor = %s, updated_at = NOW()
                    WHERE id = %s AND id_cliente = %s""",
                (name, description, instructions, tone, audience, positioning, color, project_id, client_id),
            )
        connection.commit()
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass
        abort(503, description='Não foi possível salvar o contexto agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.post('/workspace/app/projetos/<project_id>/marcas')
@login_required
def update_project_brands(project_id):
    client_id = int(session.get('cliente_id') or 0)
    if not _workspace_project(client_id, project_id):
        abort(404)
    valid_ids = {str(item['id']) for item in _workspace_brands(client_id)}
    wanted = {value for value in request.form.getlist('brand_ids') if value in valid_ids}
    project_ref = f'ci:{project_id}'
    try:
        existing = {str(item.get('brand_ref') or '') for item in family_repository.project_brand_links(client_id)
                    if item.get('project_ref') == project_ref and str(item.get('brand_ref') or '').startswith('studio:')}
        selected = {f'studio:{brand_id}' for brand_id in wanted}
        for brand_ref in existing - selected:
            family_repository.set_project_brand_link(client_id, session.get('user_id'), project_ref, brand_ref, False)
        for brand_ref in selected - existing:
            family_repository.set_project_brand_link(client_id, session.get('user_id'), project_ref, brand_ref, True)
    except Exception:
        current_app.logger.exception('Não foi possível atualizar marcas do projeto')
        abort(503, description='Não foi possível atualizar as marcas agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.post('/workspace/app/projetos/<project_id>/status')
@login_required
def update_project_status(project_id):
    client_id = int(session.get('cliente_id') or 0)
    project = _workspace_project(client_id, project_id)
    if not project:
        abort(404)
    status = 'ativo' if project.get('status') == 'arquivado' else 'arquivado'
    connection = None
    try:
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute('UPDATE cadu_ci_projetos SET status = %s, updated_at = NOW() WHERE id = %s AND id_cliente = %s',
                           (status, project_id, client_id))
        connection.commit()
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass
        abort(503, description='Não foi possível alterar o estado do projeto agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.project_detail', project_id=project_id), code=303)


@bp.post('/workspace/api/projetos/<project_id>/consultar')
@login_required
def query_project_knowledge(project_id):
    """Search the existing indexed project chunks without leaving Workspace."""
    client_id = int(session.get('cliente_id') or 0)
    if not _workspace_project(client_id, project_id):
        abort(404)
    payload = request.get_json(silent=True) or {}
    query = ' '.join(str(payload.get('query') or '').split())[:400]
    if len(query) < 3:
        return jsonify({'error': 'Escreva ao menos três caracteres para consultar a base.'}), 400
    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """SELECT titulo, LEFT(conteudo, 900) AS conteudo,
                          ts_rank_cd(to_tsvector('portuguese', conteudo), plainto_tsquery('portuguese', %s)) AS score
                     FROM cadu_ci_chunks
                    WHERE projeto_id = %s AND id_cliente = %s
                      AND to_tsvector('portuguese', conteudo) @@ plainto_tsquery('portuguese', %s)
                 ORDER BY score DESC, ordem ASC LIMIT 6""",
                (query, project_id, client_id, query),
            )
            return jsonify({'query': query, 'results': [dict(row) for row in cursor.fetchall()]})
    except Exception:
        return jsonify({'error': 'Não foi possível consultar a base agora. Tente novamente.'}), 503


@bp.get('/workspace/app/marcas/<int:brand_id>')
@login_required
def brand_detail(brand_id):
    client_id = int(session.get('cliente_id') or 0)
    brand = _workspace_brand(client_id, brand_id)
    if not brand:
        abort(404)
    # Keep the view resilient while a legacy brand is still being enriched.
    # The normal repository path already supplies these fields; defaults avoid
    # a partially migrated record turning the entire detail page into a 500.
    brand.setdefault('assets', [])
    brand.setdefault('brand_profile', {})
    brand.setdefault('analysis_metadata', {})
    brand.setdefault('activity', [])
    brand.setdefault('readiness', {'score': 0, 'missing': ['diretrizes de identidade']})
    studio_base = product_url('studio', '/studio/modelagem-criativos')
    return render_template(
        'cadu_workspace/brand_detail.html', brand=brand,
        linked_projects=_brand_linked_projects(client_id, brand_id),
        legacy_creatives_url=f'{studio_base}/trocar?client_id={brand_id}',
        legacy_uploads_url=f'{studio_base}/trocar?client_id={brand_id}&panel=uploads',
    )


@bp.get('/workspace/app/marcas/<int:brand_id>/sistema')
@login_required
def brand_system(brand_id):
    """Keep the complete creative-brand system inside the Workspace shell."""
    brand = _workspace_brand(int(session.get('cliente_id') or 0), brand_id)
    if not brand:
        abort(404)
    return render_template('cadu_workspace/brand_system_app.html', brand=brand)


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


@bp.post('/workspace/app/equipe/convites')
@login_required
def create_team_invite():
    """Create the established Cadu invite and dispatch it only after a user submits the form."""
    from .. import db
    from ..email_service import send_invite_email

    email = (request.form.get('email') or '').strip().lower()
    role = request.form.get('role') if request.form.get('role') in {'member', 'admin'} else 'member'
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        abort(400, description='Informe um e-mail válido para o convite.')
    client_id = int(session.get('cliente_id') or 0)
    try:
        pending_invite = db.verificar_convite_pendente(email, client_id)
    except Exception:
        current_app.logger.exception('Não foi possível validar convite de equipe')
        abort(503, description='Não foi possível validar o convite agora. Tente novamente.')
    if pending_invite:
        abort(409, description='Já existe um convite pendente para este e-mail.')
    try:
        invite_id = db.criar_invite(client_id, session.get('user_id'), email, role)
        invite = db.obter_invite_por_id(invite_id)
        plans = db.obter_planos_clientes({'cliente_id': client_id})
        company_name = (plans[0].get('nome_fantasia') if plans else '') or 'sua organização'
        result = send_invite_email(email, invite['invite_token'], company_name,
                                   session.get('user_name') or 'Equipe', invite['expires_at'])
        if not result.get('success'):
            current_app.logger.warning('Convite %s criado, mas o envio do e-mail falhou: %s', invite_id, result.get('error'))
    except Exception:
        current_app.logger.exception('Não foi possível criar convite de equipe')
        abort(503, description='Não foi possível criar o convite agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.account_page', section='equipe'), code=303)


@bp.post('/workspace/app/equipe/convites/<int:invite_id>/reenviar')
@login_required
def resend_team_invite(invite_id):
    from .. import db
    from ..email_service import send_invite_email

    client_id = int(session.get('cliente_id') or 0)
    try:
        invite = db.obter_invite_por_id(invite_id)
        if not invite or int(invite.get('id_cliente') or 0) != client_id or invite.get('status') != 'pending':
            abort(404)
        if not db.reenviar_invite(invite_id):
            abort(409, description='Este convite não pode mais ser reenviado.')
        invite = db.obter_invite_por_id(invite_id)
        plans = db.obter_planos_clientes({'cliente_id': client_id})
        company_name = (plans[0].get('nome_fantasia') if plans else '') or 'sua organização'
        result = send_invite_email(invite['email'], invite['invite_token'], company_name,
                                   session.get('user_name') or 'Equipe', invite['expires_at'])
        if not result.get('success'):
            current_app.logger.warning('Reenvio do convite %s falhou: %s', invite_id, result.get('error'))
    except HTTPException:
        raise
    except Exception:
        current_app.logger.exception('Não foi possível reenviar convite de equipe')
        abort(503, description='Não foi possível reenviar o convite agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.account_page', section='equipe'), code=303)


@bp.post('/workspace/app/equipe/convites/<int:invite_id>/cancelar')
@login_required
def cancel_team_invite(invite_id):
    from .. import db

    client_id = int(session.get('cliente_id') or 0)
    try:
        invite = db.obter_invite_por_id(invite_id)
        if not invite or int(invite.get('id_cliente') or 0) != client_id or invite.get('status') != 'pending':
            abort(404)
        if not db.cancelar_invite(invite_id):
            abort(409, description='Este convite não pode mais ser cancelado.')
    except HTTPException:
        raise
    except Exception:
        current_app.logger.exception('Não foi possível cancelar convite de equipe')
        abort(503, description='Não foi possível cancelar o convite agora. Tente novamente.')
    return redirect(url_for('cadu_workspace.account_page', section='equipe'), code=303)


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
