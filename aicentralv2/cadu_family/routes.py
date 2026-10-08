"""Pilot surface with explicit availability and a fail-closed context boundary."""
import hashlib
import json
import secrets
from uuid import UUID
from urllib.parse import quote, urlencode

from flask import Blueprint, Response, abort, current_app, g, jsonify, make_response, redirect, render_template, request, session, stream_with_context, url_for
from werkzeug.exceptions import HTTPException
from urllib.parse import urlparse
import click

from ..auth import login_url
from ..cadu_tool_billing import InsufficientToolCredits
from ..product_domains import canonical_workspace_legacy_path, product_url, workspace_public_url
from . import context, repository
from .catalog import ADMIN_MODULES, LANDINGS, PRODUCTS, PROFILES
from . import product_pages

bp = Blueprint('cadu_family', __name__, url_prefix='/familia')
from ..cadu_workspace.conversations.jobs import worker_command
from ..cadu_workspace.conversations.conversation_memory import rebuild_command as memory_rebuild_command
from ..cadu_workspace.agent_v2.memory_checkpoint import (
    worker_command as memory_worker_command,
    worker_loop_command as memory_worker_loop_command,
)
bp.cli.add_command(worker_command)
bp.cli.add_command(memory_rebuild_command)
bp.cli.add_command(memory_worker_command)
bp.cli.add_command(memory_worker_loop_command)


@bp.cli.command('crawl-planner-portals')
@click.option('--limit', default=10, type=click.IntRange(1, 50), help='Máximo de domínios por execução.')
def crawl_planner_portals_command(limit):
    """Crawl public metadata for already curated portal domains, subject to robots.txt."""
    from time import sleep
    from ..cadu_planner import portals
    from . import repository
    domains = repository.rows('''SELECT domain FROM cadu_planner_portals
                                  WHERE active = TRUE ORDER BY last_crawled_at NULLS FIRST LIMIT %s''', (limit,))
    for index, item in enumerate(domains):
        result = portals.crawl_public_metadata(item['domain'])
        saved = portals.save_crawl_result(result) if result.get('status') == 'ok' else False
        click.echo(f"{item['domain']}: {result.get('status')}" + (' (updated)' if saved else ''))
        if index < len(domains) - 1:
            sleep(1.5)


@bp.cli.command('import-planner-portals')
@click.argument('csv_path', type=click.Path(exists=True, dir_okay=False, readable=True, path_type=str))
@click.option('--dry-run', is_flag=True, help='Valida o CSV sem gravar no banco.')
@click.option('--allow-pending', is_flag=True,
              help='Aceita candidatos ainda sem aprovação editorial e ignora linhas inválidas.')
@click.option('--check-dns/--no-check-dns', default=True, show_default=True,
              help='Rejeita linhas cujo domínio não resolve (DNS inválido).')
def import_planner_portals_command(csv_path, dry_run, allow_pending, check_dns):
    """Import curated portal records from a UTF-8 CSV file."""
    from ..cadu_planner import portals
    try:
        with open(csv_path, 'r', encoding='utf-8-sig', newline='') as csv_file:
            summary = portals.import_curated_csv(csv_file, dry_run=dry_run, allow_pending=allow_pending, check_dns=check_dns)
    except (OSError, UnicodeError) as exc:
        raise click.ClickException(f'Não foi possível ler o CSV: {exc}') from exc
    action = 'validados' if dry_run else 'importados'
    click.echo(f"{summary['rows']} portais {action}; {len(summary['skipped'])} linhas ignoradas.")
    for reason in summary['skipped'][:20]:
        click.echo(f'  - {reason}')


@bp.cli.command('crawl-planner-portals-ads')
@click.option('--limit', default=100, type=click.IntRange(1, 2000), help='Máximo de portais por execução.')
@click.option('--scope', type=click.Choice(['nacional_premium', 'regional']), help='Restringe a um escopo.')
@click.option('--stale-days', default=30, type=click.IntRange(0, 365),
              help='Reverifica portais checados há mais de N dias (0 = todos).')
@click.option('--workers', default=8, type=click.IntRange(1, 16), help='Hosts verificados em paralelo.')
def crawl_planner_portals_ads_command(limit, scope, stale_days, workers):
    """Check ads.txt and programmatic tags of portals, oldest check first."""
    from ..cadu_planner import portal_ads
    clauses, params = ['active = TRUE', "(programmatic_checked_at IS NULL OR programmatic_checked_at < NOW() - make_interval(days => %s))"], [stale_days]
    if scope:
        clauses.append('scope = %s')
        params.append(scope)
    domains = [row['domain'] for row in repository.rows(
        f"SELECT domain FROM cadu_planner_portals WHERE {' AND '.join(clauses)} "
        'ORDER BY programmatic_checked_at NULLS FIRST, scope, name LIMIT %s', tuple(params + [limit]))]
    for result in portal_ads.crawl_many(domains, workers=workers):
        portal_ads.save_result(result)
        if result.get('status') != 'ok':
            click.echo(f"{result['domain']}: {result['status']}")
            continue
        ads, home = result['ads_txt'], result['home']
        alert = portal_ads.deactivation_alert(ads['status'], home.get('programmatic_status'))
        click.echo(f"{result['domain']}: ads.txt={ads['status']} ({ads['records']}) "
                   f"programático={home.get('programmatic_status') or home['status']}"
                   + (f'  ** ALERTA: candidato a desativar ({alert}) **' if alert else ''))
    click.echo(f'{len(domains)} portais verificados.')


@bp.cli.command('rank-planner-portals-top')
def rank_planner_portals_top_command():
    """Mark the curated national Top 10 of portals in the showcase."""
    from ..cadu_planner import portals
    applied = portals.apply_top_ranking()
    missing = [domain for domain in portals.TOP_PORTAL_DOMAINS if domain not in applied]
    click.echo(f'{len(applied)} portais marcados no Top 10.' + (f' Fora do catálogo: {", ".join(missing)}' if missing else ''))


@bp.cli.command('estimate-planner-portals')
@click.option('--tranco-file', type=click.Path(exists=True, dir_okay=False, path_type=str),
              help='Lista Tranco já baixada (zip ou csv); sem ela, baixa de tranco-list.eu.')
def estimate_planner_portals_command(tranco_file):
    """Fill public popularity (Tranco), size tier and estimated demographics of every active portal."""
    from ..cadu_planner import portal_estimates
    ranks = portal_estimates.load_tranco(tranco_file)
    click.echo(f'{len(ranks)} domínios na lista Tranco.')
    items = repository.rows("""SELECT id, domain, category, to_jsonb(p)->>'uf' AS uf, to_jsonb(p)->>'scope' AS scope
                                 FROM cadu_planner_portals p WHERE active = TRUE ORDER BY id""")
    tiers = {}
    for item in items:
        values = portal_estimates.estimate(item, ranks)
        portal_estimates.save_estimates(item['id'], values)
        tiers[values['traffic_tier']] = tiers.get(values['traffic_tier'], 0) + 1
    click.echo(f'{len(items)} portais estimados: {tiers}')


@bp.cli.command('audit-planner-portals')
@click.option('--apply', 'apply_changes', is_flag=True, help='Desativa os candidatos listados (reversível: active = FALSE).')
@click.option('--keep-top', default=10, show_default=True, help='Nunca desativa os N primeiros do Top 10 nacional.')
def audit_planner_portals_command(apply_changes, keep_top):
    """List portals that should leave the catalog: invalid DNS and no ads.txt/programmatic signal."""
    from ..cadu_planner import portal_ads
    items = repository.rows("""SELECT id, name, domain, featured_rank, to_jsonb(p)->>'scope' AS scope,
                                      ads_txt_status, programmatic_status
                                 FROM cadu_planner_portals p WHERE active = TRUE ORDER BY name""")
    flagged = []
    for item in items:
        if item['featured_rank'] and item['featured_rank'] <= keep_top:
            continue
        reason = portal_ads.deactivation_alert(item['ads_txt_status'], item['programmatic_status'])
        if reason:
            flagged.append((reason, item))
    for reason, item in flagged:
        click.echo(f"{reason}\t{item['id']}\t{item['domain']}\t{item['scope']}\tads.txt={item['ads_txt_status']}")
    counts = {}
    for reason, _ in flagged:
        counts[reason] = counts.get(reason, 0) + 1
    click.echo(f'{len(flagged)} candidatos a desativar: {counts}')
    if apply_changes and flagged:
        from ..db import get_db
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('UPDATE cadu_planner_portals SET active = FALSE, featured_rank = NULL WHERE id = ANY(%s)',
                        ([item['id'] for _, item in flagged],))
        conn.commit()
        click.echo('Desativados.')


@bp.cli.command('radar-due')
@click.option('--limit', default=3, show_default=True, help='Máximo de radares rodados nesta chamada.')
def radar_due(limit):
    """Roda os radares ativos que chegaram no horário (chamado pelo timer do systemd)."""
    from ..cadu_radar import repository as radar, watches
    if not current_app.config.get('CADU_RADAR_ENABLED') or not radar.watches_available():
        click.echo('Radar desligado ou sem a migration v2; nada a fazer.')
        return
    results = watches.run_due(limit)
    for item in results:
        click.echo(f"{item['watch']}: {item['status']}")
    click.echo(f'{len(results)} radares rodados.')


@bp.cli.command('monitor-planner-sites')
@click.option('--limit', default=50, type=click.IntRange(1, 200), help='Máximo de sites por execução.')
def monitor_planner_sites_command(limit):
    """Check due Planner sites and purge expired anonymous events."""
    from ..cadu_planner import site_monitoring
    results = site_monitoring.check_due_sites(limit)
    expired = site_monitoring.purge_old_events()
    for item in results:
        click.echo(f"{item['site_id']}: {item['status']} ({item['response_ms']} ms)")
    click.echo(f'{len(results)} sites verificados; {expired} eventos antigos removidos.')


def planner_url(path='', **query):
    """Build clean, product-owned Planner URLs for templates and shares."""
    target = product_url('planner', '/' + str(path or '').lstrip('/'))
    values = {key: value for key, value in query.items() if value not in (None, '')}
    return f"{target}?{urlencode(values)}" if values else target


def marketplace_facets(product, module):
    """Optional catalog filters must not make an otherwise valid page fail."""
    if product != 'planner' or module not in {'audiencias', 'canais', 'formatos', 'interativos', 'places', 'portais'}:
        return {'categories': [], 'platforms': [], 'types': [], 'segments': [], 'cities': []}
    try:
        if module == 'audiencias':
            return repository.audience_catalog_facets()
        if module == 'canais':
            return repository.channel_catalog_facets()
        if module == 'places':
            from ..cadu_planner.places import catalog_facets
            return {**catalog_facets(), 'platforms': [], 'types': [], 'segments': []}
        if module == 'portais':
            from ..cadu_planner.portals import catalog_facets
            return {**catalog_facets(), 'platforms': [], 'types': [], 'segments': [], 'cities': []}
        return repository.format_catalog_facets(module == 'interativos')
    except Exception:
        current_app.logger.warning('Filtros do catálogo indisponíveis; exibindo catálogo sem filtros.')
        return {'categories': [], 'platforms': [], 'types': [], 'segments': []}


@bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@bp.before_request
def protect():
    planner_host = (urlparse(str(current_app.config.get('PLANNER_URL') or '')).hostname or '').lower()
    workspace_host = (urlparse(str(current_app.config.get('WORKSPACE_URL') or '')).hostname or '').lower()
    request_host = (request.host.split(':', 1)[0] or '').lower()
    planner_surface = request_host == planner_host and (
        request.path.startswith('/familia/planner/')
        or request.path.startswith('/familia/public/link-tester/')
        or request.path == '/familia/api/context'
        or request.path.startswith('/familia/api/planner/')
    )
    workspace_chat_surface = request_host == workspace_host and (
        request.path == '/familia/api/context'
        or request.path.startswith('/familia/api/conversations')
        or request.path.startswith('/familia/api/conversation-sections')
    )
    public_conversation_surface = request.path.startswith('/familia/public/conversations/')
    # Planner is a released Cadu product. It must not depend on the broader
    # family rollout flag, otherwise planner.centralcomm.media lands on the
    # CentralX 404 shell instead of its own product experience.
    if not current_app.config.get('CADU_FAMILY_ENABLED') and not (planner_surface or workspace_chat_surface or public_conversation_surface):
        abort(404)
    family_product = request.path.removeprefix('/familia/').split('/', 1)[0]
    if (
        request.method in ('GET', 'HEAD')
        and not session.get('user_id')
        and family_product in PRODUCTS
        and not request.path.startswith('/familia/api/')
        and not (
            request.path.startswith('/familia/public/link-tester/')
            or request.path.startswith('/familia/planner/docs/public/')
            or request.path.startswith('/familia/planner/planos/public/')
        )
    ):
        return redirect(workspace_public_url(), code=302)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not session.get('user_id'):
            abort(401)
        token = session.get('family_csrf')
        if not token or not secrets.compare_digest(token, request.headers.get('X-CSRF-Token', '')):
            abort(403, description='Atualize a página e tente novamente.')
        # Fail closed for new mutation routes too. Context changes only the
        # session; Copy Ads validation only reads the catalog.
        # Conversar é uma capacidade própria do Cadu. Ela pode registrar o
        # histórico e os arquivos da conversa sem liberar alterações no
        # Workspace (entidades, marcas, projetos ou configurações).
        read_only_posts = {'cadu_family.set_context', 'cadu_family.copy_validate',
                           'cadu_family.conversation_send', 'cadu_family.conversation_preflight',
                           'cadu_family.conversation_upload', 'cadu_family.conversation_stop',
                           'cadu_family.conversation_work_memory_review',
                           'cadu_family.planner_link_test'}
        conversation_action_posts = {
            'cadu_family.conversation_update', 'cadu_family.conversation_fork',
            'cadu_family.conversation_share_create', 'cadu_family.conversation_shares_revoke',
            'cadu_family.conversation_section_create', 'cadu_family.conversation_section_update',
            'cadu_family.conversation_section_delete',
        }
        if (not current_app.config.get('CADU_FAMILY_WRITES_ENABLED', False)
                and request.endpoint not in read_only_posts | conversation_action_posts):
            abort(403, description='Migração em modo de consulta. Gravações não estão habilitadas.')


@bp.errorhandler(Exception)
def error(exc):
    if isinstance(exc, HTTPException):
        code, message = exc.code, exc.description
    else:
        current_app.logger.exception('Falha no serviço da família Cadu')
        code, message = 503, 'Não foi possível carregar os dados. Tente novamente.'
        try:
            repository.get_db().rollback()
        except Exception:
            pass
    if '/api/' in request.path:
        return jsonify(error=message), code
    return render_template('cadu_family/error.html', message=message), code


@bp.errorhandler(403)
def forbidden(exc):
    """O tratador global de 403 devolve HTML e esconde o motivo; nas rotas da API o motivo vai em JSON."""
    if '/api/' in request.path:
        # abort(403) sem descrição traz o texto padrão em inglês do Werkzeug: a tela mostraria isso ao usuário.
        reason = exc.description if exc.description and not str(exc.description).startswith("You don't have") else 'Você não tem permissão para esta ação.'
        return jsonify(error=reason), 403
    return render_template('errors/403.html'), 403


@bp.get('/api/context')
def get_context():
    selected = context.resolve()
    entities = context.inventory(selected['client_id'])
    # Revalidate persisted references too, including deleted records and revoked grants.
    saved = session.get('family_context') or {}
    for key, kind in (('project_ref', 'project'), ('brand_ref', 'brand')):
        ref = saved.get(key)
        selected[key] = ref if any(row['ref'] == ref and row['kind'] == kind for row in entities) else None
    return jsonify(context=selected, clients=context.authorized_clients(), entities=entities)


@bp.post('/api/context')
def set_context():
    return jsonify(context=context.select(request.get_json(silent=True) or {}))


def writable_context():
    selected = context.resolve()
    if selected.get('role') not in ('admin', 'member'):
        abort(403)
    return selected


@bp.post('/api/actions/link-report-project')
def propose_report_link():
    from .actions import prepare
    selected = writable_context()
    data = request.get_json(silent=True) or {}
    try:
        campaign_id = int(data.get('campaign_id'))
    except (TypeError, ValueError):
        abort(400)
    return jsonify(prepare(campaign_id, data.get('project_ref'), selected)), 201


@bp.post('/api/actions/<uuid:action_id>/confirm')
def confirm_action(action_id):
    from .actions import confirm
    return jsonify(confirm(str(action_id), writable_context()))


def entity_payload():
    data = request.get_json(silent=True) or {}
    name = str(data.get('name') or '').strip()
    if not 2 <= len(name) <= 150 or data.get('kind') not in ('project', 'brand'):
        abort(400, description='Informe um nome de 2 a 150 caracteres e um tipo válido.')
    result = {'name': name, 'kind': data['kind']}
    for key, maximum in (('description', 10000), ('instructions', 20000)):
        if key in data:
            result[key] = str(data[key] or '')[:maximum]
    return result


@bp.post('/api/entities')
def create_entity():
    selected = writable_context()
    try:
        ref = repository.create_entity(selected['client_id'], context.identity()['id'], entity_payload())
    except ValueError as exc:
        abort(409, description=str(exc))
    return jsonify(ref=ref), 201


@bp.patch('/api/entities/<ref>')
def edit_entity(ref):
    selected = writable_context()
    if not any(item['ref'] == ref for item in context.inventory(selected['client_id'])):
        abort(404)
    repository.update_entity(selected['client_id'], ref, entity_payload())
    return jsonify(success=True)


@bp.put('/api/project-brand-links')
def set_project_brand_link():
    selected = writable_context()
    data = request.get_json(silent=True) or {}
    project_ref, brand_ref, linked = data.get('project_ref'), data.get('brand_ref'), data.get('linked')
    if not isinstance(project_ref, str) or not isinstance(brand_ref, str) or not isinstance(linked, bool):
        abort(400, description='Informe projeto, marca e o estado do vínculo.')
    items = {item['ref']: item for item in context.inventory(selected['client_id'])}
    if (items.get(project_ref) or {}).get('kind') != 'project' or (items.get(brand_ref) or {}).get('kind') != 'brand':
        abort(403, description='Projeto ou marca não pertencem ao cliente selecionado.')
    repository.set_project_brand_link(selected['client_id'], context.identity()['id'], project_ref, brand_ref, linked)
    return jsonify(success=True)


@bp.patch('/api/profile')
def edit_profile():
    user = context.identity()
    data = request.get_json(silent=True) or {}
    name, phone = str(data.get('name') or '').strip(), str(data.get('phone') or '').strip()
    if not 2 <= len(name) <= 150 or len(phone) > 40:
        abort(400, description='Confira o nome e o telefone.')
    repository.profile_update(user['id'], name, phone)
    session['user_name'] = name
    return jsonify(success=True)


@bp.get('/api/conversations')
def conversation_history():
    user = context.identity()
    selected = context.resolve()
    query = request.args.get('q', '').strip()
    if len(query) > 150:
        abort(400, description='Use até 150 caracteres na busca.')
    paginated = 'page_size' in request.args
    if paginated:
        try:
            limit = min(100, max(1, int(request.args.get('page_size', 50))))
            offset = min(1000000, max(0, int(request.args.get('offset', 0))))
        except (TypeError, ValueError):
            abort(400, description='Paginação de conversas inválida.')
        page = repository.conversation_history_all(
            user, selected['client_id'], query=query, limit=limit + 1, offset=offset,
        )
        has_more = len(page) > limit
        records = page[:limit]
    else:
        try:
            limit = min(100, max(1, int(request.args.get('limit', 50))))
        except (TypeError, ValueError):
            abort(400, description='Limite de conversas inválido.')
        records = repository.conversation_history_all(
            user, selected['client_id'], query=query, **({'limit': limit} if 'limit' in request.args else {}),
        )
    sections = repository.conversation_sections(user['id'], user['organization_id'], selected['client_id']) \
        if repository.family_table_available('cadu_conversation_sections') else []
    payload = {
        'conversations': records,
        'sections': sections,
        'can_manage': bool(current_app.config.get('CADU_FAMILY_WRITES_ENABLED', False)
                           and selected.get('role') in ('admin', 'member')),
    }
    if paginated:
        payload.update(has_more=has_more, next_offset=offset + len(records))
    return jsonify(payload)


@bp.get('/api/conversation-sections')
def conversation_sections():
    user, selected = context.identity(), context.resolve()
    if not repository.family_table_available('cadu_conversation_sections'):
        abort(409, description='As seções personalizadas ainda não estão disponíveis.')
    return jsonify(sections=repository.conversation_sections(user['id'], user['organization_id'], selected['client_id']))


@bp.post('/api/conversation-sections')
def conversation_section_create():
    selected, user = writable_context(), context.identity()
    if not repository.family_table_available('cadu_conversation_sections'):
        abort(409, description='As seções personalizadas ainda não estão disponíveis.')
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or set(data) != {'name'}:
        abort(400, description='Informe o nome da seção.')
    name = data.get('name')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64 or '\x00' in name:
        abort(400, description='Use um nome de seção de 1 a 64 caracteres.')
    name = name.strip()
    existing = repository.conversation_sections(user['id'], user['organization_id'], selected['client_id'])
    if any(item['name'].casefold() == name.casefold() for item in existing):
        abort(409, description='Já existe uma seção com esse nome.')
    section = repository.create_conversation_section(user['id'], user['organization_id'], selected['client_id'], name)
    return jsonify(section=section), 201


@bp.patch('/api/conversation-sections/<uuid:section_id>')
def conversation_section_update(section_id):
    selected, user = writable_context(), context.identity()
    if not repository.family_table_available('cadu_conversation_sections'):
        abort(409, description='As seções personalizadas ainda não estão disponíveis.')
    data = request.get_json(silent=True) or {}
    name = data.get('name') if isinstance(data, dict) and set(data) == {'name'} else None
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64 or '\x00' in name:
        abort(400, description='Use um nome de seção de 1 a 64 caracteres.')
    name = name.strip()
    existing = repository.conversation_sections(user['id'], user['organization_id'], selected['client_id'])
    if any(item['id'] != str(section_id) and item['name'].casefold() == name.casefold() for item in existing):
        abort(409, description='Já existe uma seção com esse nome.')
    section = repository.rename_conversation_section(user['id'], user['organization_id'], selected['client_id'], str(section_id), name)
    if not section:
        abort(404)
    return jsonify(section=section)


@bp.delete('/api/conversation-sections/<uuid:section_id>')
def conversation_section_delete(section_id):
    selected, user = writable_context(), context.identity()
    if not repository.family_table_available('cadu_conversation_sections'):
        abort(409, description='As seções personalizadas ainda não estão disponíveis.')
    if not repository.delete_conversation_section(user['id'], user['organization_id'], selected['client_id'], str(section_id)):
        abort(404)
    return jsonify(success=True)


@bp.get('/api/memories')
def memories():
    from ..cadu_workspace.conversations import memory
    return jsonify(memories=memory.list_memories(context.identity(), context.resolve()))


@bp.delete('/api/memories/<uuid:memory_id>')
def dismiss_memory(memory_id):
    from ..cadu_workspace.conversations import memory
    selected = writable_context()
    if not memory.dismiss(str(memory_id), context.identity(), selected):
        abort(404)
    return jsonify(success=True)


@bp.patch('/api/conversations/<conversation_id>')
def conversation_update(conversation_id):
    selected = writable_context()
    user = context.identity()
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data or set(data) - {
            'title', 'archived', 'section', 'automation_enabled', 'custom_section_id', 'is_unread', 'project_ref'}:
        abort(400, description='Informe um título ou estado de arquivamento.')
    title = data.get('title')
    if 'title' in data:
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 150 or '\x00' in title:
            abort(400, description='Use um título de 1 a 150 caracteres.')
        title = title.strip()
    if 'archived' in data and not isinstance(data['archived'], bool):
        abort(400, description='Estado de arquivamento inválido.')
    if 'automation_enabled' in data and not isinstance(data['automation_enabled'], bool):
        abort(400, description='Estado da automação inválido.')
    if 'is_unread' in data:
        if not isinstance(data['is_unread'], bool):
            abort(400, description='Estado de leitura inválido.')
        if not repository.family_table_available('cadu_conversation_organization'):
            abort(409, description='A organização de conversas ainda não está disponível.')
        result = repository.set_conversation_unread(user['id'], selected['client_id'], conversation_id, data['is_unread'])
        if not result:
            abort(404)
        return jsonify(conversation=result)
    if 'section' in data:
        if data['section'] not in {'recent', 'pinned', 'custom'}:
            if data['section'] == 'automation':
                abort(400, description='Configure automações pelo fluxo de agendamento.')
            abort(400, description='Destino da conversa inválido.')
        if not repository.family_table_available('cadu_conversation_organization'):
            abort(409, description='A organização de conversas ainda não está disponível.')
        custom_section_id = data.get('custom_section_id')
        if data['section'] == 'custom':
            if not custom_section_id or not repository.family_table_available('cadu_conversation_sections'):
                abort(400, description='Selecione uma seção personalizada válida.')
            try:
                custom_section_id = str(UUID(str(custom_section_id)))
            except (TypeError, ValueError):
                abort(400, description='Seção personalizada inválida.')
            allowed_sections = repository.conversation_sections(user['id'], user['organization_id'], selected['client_id'])
            if not any(section['id'] == custom_section_id for section in allowed_sections):
                abort(403, description='A seção não pertence a este ambiente.')
        elif custom_section_id is not None:
            abort(400, description='Uma seção personalizada exige o destino personalizado.')
        result = repository.organize_conversation(user['id'], selected['client_id'], conversation_id,
                                                  data['section'], data.get('automation_enabled'), custom_section_id)
        if not result:
            abort(404)
        if custom_section_id:
            section = next((item for item in repository.conversation_sections(user['id'], user['organization_id'], selected['client_id'])
                            if item['id'] == custom_section_id), None)
            result['custom_section_name'] = section['name'] if section else None
        return jsonify(conversation=result)
    if 'automation_enabled' in data:
        if not repository.family_table_available('cadu_conversation_organization'):
            abort(409, description='A organização de conversas ainda não está disponível.')
        result = repository.set_conversation_automation(user['id'], selected['client_id'], conversation_id,
                                                        data['automation_enabled'])
        if not result:
            abort(409, description='Mova a conversa para Automações antes de ativá-la.')
        return jsonify(conversation=result)
    if 'project_ref' in data:
        project_ref = data['project_ref']
        if project_ref is not None:
            if not isinstance(project_ref, str) or not any(
                    entity.get('ref') == project_ref and entity.get('kind') == 'project'
                    for entity in context.inventory(selected['client_id'])):
                abort(403, description='O projeto não pertence a este ambiente.')
        result = repository.move_conversation_project(user, selected['client_id'], conversation_id, project_ref)
        if not result:
            abort(404)
        return jsonify(conversation={'id': conversation_id, **result})
    result = repository.update_conversation(user['id'], selected['client_id'], conversation_id, title, data.get('archived'))
    if not result:
        abort(404)
    return jsonify(conversation=result)


@bp.get('/api/conversations/<conversation_id>/project-suggestion')
def conversation_project_suggestion(conversation_id):
    """Open project suggestion for the caller's own project-less conversation, if any."""
    from ..cadu_workspace import conversation_project_suggestions as suggestions
    user, selected = context.identity(), context.resolve()
    if not repository.family_table_available('cadu_conversation_project_suggestions'):
        return jsonify(suggestion=None)
    result = suggestions.pending_for_owner(user['id'], selected['client_id'], conversation_id)
    if result and not any(entity.get('ref') == result['project_ref'] and entity.get('kind') == 'project'
                          for entity in context.inventory(selected['client_id'])):
        result = None
    response = jsonify(suggestion=result)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.post('/api/conversations/<conversation_id>/project-suggestion/dismiss')
def conversation_project_suggestion_dismiss(conversation_id):
    from ..cadu_workspace import conversation_project_suggestions as suggestions
    selected, user = writable_context(), context.identity()
    if not suggestions.dismiss(user['id'], selected['client_id'], conversation_id):
        abort(404)
    return jsonify(dismissed=True)


@bp.post('/api/conversations/<conversation_id>/fork')
def conversation_fork(conversation_id):
    selected, user = writable_context(), context.identity()
    try:
        fork = repository.fork_conversation(user, selected['client_id'], conversation_id)
    except ValueError as exc:
        if str(exc) == 'running':
            abort(409, description='Aguarde a resposta atual terminar antes de criar uma ramificação.')
        raise
    if not fork:
        abort(404)
    return jsonify(conversation=fork), 201


@bp.post('/api/conversations/<conversation_id>/shares')
def conversation_share_create(conversation_id):
    selected, user = writable_context(), context.identity()
    if repository.conversation_messages(user['id'], selected['client_id'], conversation_id) is None:
        abort(404)
    token = secrets.token_urlsafe(32)
    share = repository.create_conversation_share(user, selected, conversation_id, hashlib.sha256(token.encode()).hexdigest())
    if not share:
        abort(404)
    url = url_for('cadu_family.public_conversation', token=token, _external=True)
    return jsonify(share={**share[0], 'url': url}), 201


@bp.delete('/api/conversations/<conversation_id>/shares')
def conversation_shares_revoke(conversation_id):
    selected, user = writable_context(), context.identity()
    if repository.conversation_messages(user['id'], selected['client_id'], conversation_id) is None:
        abort(404)
    repository.revoke_conversation_share(user['id'], selected['client_id'], conversation_id)
    return jsonify(success=True)


@bp.get('/public/conversations/<token>')
def public_conversation(token):
    if not 32 <= len(token) <= 128:
        abort(404)
    shared = repository.public_conversation_share(hashlib.sha256(token.encode()).hexdigest())
    if not shared:
        abort(404)
    response = make_response(render_template('cadu_family/public_conversation.html', shared=shared))
    response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    response.headers['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"
    return response


@bp.get('/api/studio/copy-ads/formats')
def copy_formats():
    from . import copy_ads
    context.resolve()
    return jsonify(formats=copy_ads.formats())


@bp.get('/api/planner/catalog/<kind>')
def planner_catalog(kind):
    """Read-only catalog for SmartPlanner and future approved chat cards."""
    from ..cadu_planner import catalog
    context.identity()
    context.resolve()
    if kind == 'audiencias':
        return jsonify(kind=kind, **_audience_page(request.args))
    if kind in {'canais', 'formatos', 'interativos'}:
        records = repository.catalog(
            kind, request.args.get('q', ''), category=request.args.get('category', ''),
            platform=request.args.get('platform', ''), sort=request.args.get('sort', 'relevant'),
            format_type=request.args.get('type', ''), segment=request.args.get('segment', ''))
        if kind == 'canais':
            from ..cadu_planner.channels import decorate_logos
            decorate_logos(records)
        return jsonify(kind=kind, records=records)
    if kind == 'portais':
        from ..cadu_planner import portals
        filters = {key: request.args.get(key, '') for key in ('scope', 'uf', 'ads_txt', 'programmatic')}
        return jsonify(portals.catalog(request.args.get('q', ''), request.args.get('category', ''),
                                       request.args.get('sort', 'featured'), request.args.get('limit', 100),
                                       request.args.get('offset', 0), **filters))
    return jsonify(kind=kind, records=catalog.query(kind, request.args.get('q', ''), request.args.get('limit', 100)))


@bp.get('/api/planner/catalog/portais/ids')
def planner_portal_ids():
    """Ids of every portal matching the current filters, to select a whole group at once."""
    from ..cadu_planner import portals
    context.identity()
    context.resolve()
    filters = {key: request.args.get(key, '') for key in ('scope', 'uf', 'ads_txt', 'programmatic')}
    return jsonify(ids=portals.catalog_ids(request.args.get('q', ''), request.args.get('category', ''), **filters))


@bp.get('/api/planner/catalog/<kind>/<item_id>')
def planner_catalog_detail(kind, item_id):
    from ..cadu_planner import catalog
    context.identity()
    context.resolve()
    return jsonify(kind=kind, record=catalog.client_detail(kind, item_id))


@bp.get('/api/planner/documents')
def planner_documents():
    """Read-only SmartPlanner document index in the selected authorized client."""
    from ..cadu_planner import docs
    user, selected = context.identity(), context.resolve()
    return jsonify(documents=docs.list_documents(selected['client_id'], user['id']))


@bp.get('/api/planner/documents/<int:document_id>')
def planner_document_preview(document_id):
    from ..cadu_planner import docs
    user, selected = context.identity(), context.resolve()
    document, preview = docs.document_preview(selected['client_id'], user['id'], document_id)
    return jsonify(document=document, preview=preview)


@bp.get('/api/planner/places')
def planner_places():
    from ..cadu_planner import places
    context.identity()
    context.resolve()
    return jsonify(records=places.catalog(request.args.get('q', ''), category=request.args.get('category', ''),
                                          city=request.args.get('city', '')))


@bp.get('/api/planner/places/<slug>')
def planner_place_detail(slug):
    from ..cadu_planner import places
    context.identity()
    context.resolve()
    return jsonify(record=places.detail(slug))


@bp.get('/api/planner/portals')
def planner_portals():
    from ..cadu_planner import portals
    context.identity()
    context.resolve()
    result = portals.catalog(request.args.get('q', ''), request.args.get('category', ''),
                             request.args.get('sort', 'featured'), request.args.get('limit', 50),
                             request.args.get('offset', 0))
    return jsonify(result)


@bp.get('/api/planner/portals/<int:portal_id>')
def planner_portal_detail(portal_id):
    from ..cadu_planner import portals
    context.identity()
    context.resolve()
    return jsonify(record=portals.detail(portal_id))


@bp.post('/api/planner/monitor/analyze')
def planner_monitor_analyze():
    from ..cadu_credit_connector import CreditActor
    from ..cadu_planner import site_monitoring
    user = context.identity()
    # A análise usa IA paga (TypeSafe): exige papel de edição e debita o cliente.
    selected = writable_context()
    data = request.get_json(silent=True) or {}
    if set(data) - {'entry_url'}:
        abort(400, description='Informe somente a URL inicial do site.')
    actor = CreditActor.from_values(selected['client_id'], user['id'])
    return jsonify(analysis=site_monitoring.analyze_url(data.get('entry_url'), actor=actor))


@bp.get('/api/planner/monitor/sites')
def planner_monitor_sites():
    from ..cadu_planner import site_monitoring
    selected = context.resolve()
    return jsonify(sites=site_monitoring.list_sites(selected['client_id']))


@bp.post('/api/planner/monitor/sites')
def planner_monitor_site_create():
    from ..cadu_planner import site_monitoring
    selected, user = writable_context(), context.identity()
    data = request.get_json(silent=True) or {}
    site = site_monitoring.create_site(selected['client_id'], user['id'], data)
    return jsonify(site=_planner_monitor_installation(site)), 201


@bp.get('/api/planner/monitor/sites/<uuid:site_id>')
def planner_monitor_site_detail(site_id):
    from ..cadu_planner import site_monitoring
    selected = context.resolve()
    site = site_monitoring.detail(selected['client_id'], str(site_id))
    return jsonify(site=_planner_monitor_installation(site))


@bp.post('/api/planner/monitor/sites/<uuid:site_id>/funnels')
def planner_monitor_funnel_create(site_id):
    from ..cadu_planner import site_monitoring
    selected = writable_context()
    site = site_monitoring.save_funnel(selected['client_id'], str(site_id), request.get_json(silent=True) or {})
    return jsonify(site=_planner_monitor_installation(site)), 201


@bp.put('/api/planner/monitor/sites/<uuid:site_id>/funnels/<uuid:funnel_id>')
def planner_monitor_funnel_update(site_id, funnel_id):
    from ..cadu_planner import site_monitoring
    selected = writable_context()
    site = site_monitoring.save_funnel(selected['client_id'], str(site_id),
                                       request.get_json(silent=True) or {}, str(funnel_id))
    return jsonify(site=_planner_monitor_installation(site))


def _planner_monitor_installation(site):
    token = str(site.get('collector_token') or '')
    if token:
        script_url = url_for('static', filename='cadu_planner/react/monitor.js', _external=True)
        endpoint = url_for('cadu_family.planner_monitor_collect', token=token, _external=True)
        site['install_snippet'] = (
            f'<script async src="{script_url}" data-site-token="{token}" data-endpoint="{endpoint}" '
            '></script>'
        )
        site['test_url'] = site['entry_url'].split('?', 1)[0] + ('&' if '?' in site['entry_url'] else '?') + 'cadu_test=1'
    return site


@bp.post('/api/planner/monitor/collect/<uuid:token>')
def planner_monitor_collect(token):
    from ..cadu_planner import site_monitoring
    try:
        data = request.get_json(silent=True)
        if data is None:
            data = json.loads(request.get_data(cache=False, as_text=True) or '{}')
    except (ValueError, UnicodeError):
        abort(400, description='Evento inválido.')
    result = site_monitoring.collect(str(token), request.headers.get('Origin', ''), data,
                                     request.cookies.get('cadu_monitor_test') == '1')
    response = jsonify(result)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Vary'] = 'Origin'
    return response


@bp.get('/api/planner/selections')
def planner_selections():
    from ..cadu_planner import selections
    user, selected = context.identity(), context.resolve()
    return jsonify(selections=selections.list_selected(selected['client_id'], user['id']))


@bp.get('/api/planner/plans')
def planner_plans():
    from ..cadu_planner import plans
    user, selected = context.identity(), context.resolve()
    return jsonify(plans=plans.list_plans(selected['client_id'], user['id']))


def _planner_refs(client_id, brand_ref=None, project_ref=None):
    """Marca e projeto só valem se pertencem ao inventário do cliente selecionado."""
    if not brand_ref and not project_ref:
        return None, None
    items = {row['ref']: row for row in context.inventory(client_id)}
    for ref, kind in ((brand_ref, 'brand'), (project_ref, 'project')):
        if ref and (not isinstance(ref, str) or (items.get(ref) or {}).get('kind') != kind):
            abort(403, description='Marca ou projeto não pertencem ao cliente selecionado.')
    return brand_ref or None, project_ref or None


def _planner_context_bar(client_id):
    """Marcas, projetos e a escolha salva na sessão para a barra de contexto."""
    try:
        entities = context.inventory(client_id)
    except Exception:
        current_app.logger.warning('Inventário de marcas e projetos indisponível no Planner.')
        return {'brands': [], 'projects': [], 'brand_ref': None, 'project_ref': None}
    saved = session.get('family_context') or {}
    known = {row['ref']: row['kind'] for row in entities}
    pick = lambda kind: [{'ref': row['ref'], 'name': row['name'], 'logo_url': row.get('logo_url') or '',
                          'related_refs': row.get('related_refs') or []}
                         for row in entities if row['kind'] == kind and row.get('status') not in ('arquivado',)]
    return {'brands': pick('brand'), 'projects': pick('project'),
            'brand_ref': saved.get('brand_ref') if known.get(saved.get('brand_ref')) == 'brand' else None,
            'project_ref': saved.get('project_ref') if known.get(saved.get('project_ref')) == 'project' else None}


@bp.get('/api/planner/context')
def planner_context_details():
    """Contexto de marca e projeto do workspace usado para planejar e achar oportunidades."""
    from ..cadu_planner.context import load_plan_context
    selected = context.resolve()
    brand_ref, project_ref = _planner_refs(selected['client_id'], request.args.get('brand_ref'),
                                           request.args.get('project_ref'))
    return jsonify(context=load_plan_context(selected['client_id'], brand_ref, project_ref))


@bp.post('/api/planner/plans')
def planner_plan_create():
    from ..cadu_planner import plans
    selected = writable_context()
    user = context.identity()
    payload = request.get_json(silent=True) or {}
    payload['brand_ref'], payload['project_ref'] = _planner_refs(
        selected['client_id'], payload.get('brand_ref'), payload.get('project_ref'))
    return jsonify(plan=plans.create_plan(selected['client_id'], user['id'], payload, selected)), 201


@bp.get('/api/planner/plans/<plan_id>/workbench')
def planner_plan_workbench(plan_id):
    """Seções, propostas pendentes e a linha do tempo da co-construção."""
    from ..cadu_planner import plans, proposals
    user, selected = context.identity(), context.resolve()
    plan = plans.get_plan(selected['client_id'], user['id'], plan_id)
    return jsonify(overview=plan['workbench_overview'], proposals=proposals.list_proposals(plan['id']),
                   events=proposals.list_events(plan['id']), cobuild_enabled=proposals.cobuild_enabled())


@bp.post('/api/planner/plans/<plan_id>/proposals/<proposal_id>/decision')
def planner_plan_proposal_decision(plan_id, proposal_id):
    from ..cadu_planner import proposals
    selected = writable_context()
    user = context.identity()
    return jsonify(plan=proposals.decide(selected['client_id'], user['id'], plan_id, proposal_id,
                                         request.get_json(silent=True) or {}))


@bp.post('/api/planner/plans/<plan_id>/sections/<section>/propose')
def planner_plan_propose_section(plan_id, section):
    from ..cadu_planner import proposals
    selected = writable_context()
    user = context.identity()
    try:
        return jsonify(proposals.propose_section(selected['client_id'], user['id'], plan_id, section))
    except NotImplementedError as exc:
        abort(501, description=str(exc))


@bp.get('/api/planner/radar/opportunities')
def planner_radar_opportunities():
    from ..cadu_radar import repository as radar
    selected = context.resolve()
    brand_ref, _project = _planner_refs(selected['client_id'], request.args.get('brand_ref'))
    return jsonify(opportunities=radar.list_opportunities(selected['client_id'], brand_ref=brand_ref,
                                                          status=request.args.get('status') or None),
                   enabled=bool(current_app.config.get('CADU_RADAR_ENABLED')))


@bp.get('/api/planner/radar/estimate')
def planner_radar_estimate():
    """Teto de tokens que uma busca do Radar reserva, mostrado antes de começar."""
    from ..cadu_radar import pipeline
    selected = context.resolve()
    return jsonify(estimated_tokens=pipeline.estimate_tokens(selected['client_id']),
                   steps=[{'key': key, 'label': label, 'hint': hint, 'parallel': key in pipeline.PARALLEL}
                          for key, label, hint in pipeline.STEPS])


@bp.post('/api/planner/radar/runs')
def planner_radar_start():
    from ..cadu_radar import pipeline
    selected = writable_context()
    user = context.identity()
    payload = request.get_json(silent=True) or {}
    brand_ref, project_ref = _planner_refs(selected['client_id'], payload.get('brand_ref'), payload.get('project_ref'))
    try:
        run = pipeline.start_run(selected['client_id'], user['id'], focus=payload.get('focus') or '',
                                 brand_ref=brand_ref, project_ref=project_ref, params=payload.get('params'))
    except pipeline.RadarDisabled as exc:
        abort(403, description=str(exc))
    except InsufficientToolCredits as exc:
        abort(409, description=str(exc))
    return jsonify(run=run), 202


@bp.get('/api/planner/radar/runs')
def planner_radar_runs():
    """Consultas realizadas, da mais recente para a mais antiga."""
    from ..cadu_radar import pipeline, repository as radar
    selected = context.resolve()
    if not radar.available():
        return jsonify(runs=[])
    return jsonify(runs=pipeline.list_runs(selected['client_id'], limit=request.args.get('limit', 30, type=int),
                                           watch_id=request.args.get('watch_id') or None))


@bp.get('/api/planner/radar/feed')
def planner_radar_feed():
    """Resultados dos radares: sinais verificados, com tema, fonte e os ângulos que eles sustentam."""
    from ..cadu_radar import feed
    selected = context.resolve()
    return jsonify(feed.list_feed(selected['client_id'], days=request.args.get('days', 30, type=int)))


@bp.put('/api/planner/radar/signals/<signal_id>/saved')
def planner_radar_signal_saved(signal_id):
    from ..cadu_radar import feed
    selected = writable_context()
    saved = bool((request.get_json(silent=True) or {}).get('saved'))
    return jsonify(saved=feed.set_saved(selected['client_id'], signal_id, saved))


@bp.get('/api/planner/radar/radars')
def planner_radar_radars():
    """Vitrine: cada radar (ativo ou busca avulsa) com a última execução e o que mudou desde a última visita."""
    from ..cadu_radar import radars, repository as radar
    selected = context.resolve()
    user = context.identity()
    if not radar.available():
        return jsonify(radars=[], state=False)
    return jsonify(radars=radars.list_radars(selected['client_id'], user['id']), state=radars.state_available())


@bp.get('/api/planner/radar/radars/<radar_id>')
def planner_radar_radar(radar_id):
    from ..cadu_radar import radars
    selected = context.resolve()
    user = context.identity()
    return jsonify(radars.get_radar(selected['client_id'], user['id'], radar_id))


@bp.post('/api/planner/radar/radars/<radar_id>/seen')
def planner_radar_seen(radar_id):
    from ..cadu_radar import radars
    selected = context.resolve()
    user = context.identity()
    radars.mark_seen(selected['client_id'], user['id'], radar_id)
    return jsonify(ok=True)


@bp.put('/api/planner/radar/radars/<radar_id>/favorite')
def planner_radar_favorite(radar_id):
    from ..cadu_radar import radars
    selected = context.resolve()
    user = context.identity()
    favorite = bool((request.get_json(silent=True) or {}).get('favorite'))
    return jsonify(favorite=radars.set_favorite(selected['client_id'], user['id'], radar_id, favorite))


@bp.post('/api/planner/radar/brand-profile/research')
def planner_radar_brand_research():
    """Fluxo separado: pesquisa concorrentes, posicionamento e público da marca e PROPÕE; nada é gravado aqui."""
    from ..cadu_radar import brand_profile, pipeline
    selected = writable_context()
    user = context.identity()
    if not pipeline.enabled():
        abort(403, description='O Radar ainda não está habilitado neste ambiente.')
    brand_ref, _project = _planner_refs(selected['client_id'], (request.get_json(silent=True) or {}).get('brand_ref'))
    try:
        return jsonify(proposal=brand_profile.propose(selected['client_id'], user['id'], brand_ref))
    except InsufficientToolCredits as exc:
        abort(409, description=str(exc))


@bp.post('/api/planner/radar/brand-profile')
def planner_radar_brand_save():
    """Grava o que o usuário aprovou, somando ao que a marca já tem (lista não repete; texto só troca se pedido)."""
    from ..cadu_radar import brand_profile
    selected = writable_context()
    user = context.identity()
    payload = request.get_json(silent=True) or {}
    brand_ref, _project = _planner_refs(selected['client_id'], payload.get('brand_ref'))
    return jsonify(brand_profile.save(selected['client_id'], user['id'], brand_ref, competitors=payload.get('competitors'),
                                      positioning=payload.get('positioning'), target_audience=payload.get('target_audience'),
                                      replace=payload.get('replace'), sources=payload.get('sources')))


def _radar_watches_ready():
    from ..cadu_radar import repository as radar
    if not radar.watches_available():
        abort(409, description='Aplique a migration do Radar v2 antes de criar radares ativos.')


@bp.get('/api/planner/radar/watches')
def planner_radar_watches():
    from ..cadu_radar import repository as radar, watches
    selected = context.resolve()
    return jsonify(watches=watches.list_watches(selected['client_id']) if radar.watches_available() else [],
                   enabled=bool(current_app.config.get('CADU_RADAR_ENABLED')))


@bp.post('/api/planner/radar/watches')
def planner_radar_watch_create():
    from ..cadu_radar import watches
    selected = writable_context()
    user = context.identity()
    _radar_watches_ready()
    payload = request.get_json(silent=True) or {}
    brand_ref, project_ref = _planner_refs(selected['client_id'], payload.get('brand_ref'), payload.get('project_ref'))
    return jsonify(watch=watches.create_watch(
        selected['client_id'], user['id'], focus=payload.get('focus') or '', brand_ref=brand_ref, project_ref=project_ref,
        params=payload.get('params'), frequency=payload.get('frequency') or 1, min_score=payload.get('min_score') or 70,
        adopt_run_id=payload.get('run_id') or None)), 201


@bp.patch('/api/planner/radar/watches/<watch_id>')
def planner_radar_watch_update(watch_id):
    from ..cadu_radar import watches
    selected = writable_context()
    _radar_watches_ready()
    payload = request.get_json(silent=True) or {}
    return jsonify(watch=watches.update_watch(selected['client_id'], watch_id, status=payload.get('status'),
                                              frequency=payload.get('frequency')))


@bp.delete('/api/planner/radar/watches/<watch_id>')
def planner_radar_watch_delete(watch_id):
    from ..cadu_radar import watches
    selected = writable_context()
    _radar_watches_ready()
    watches.delete_watch(selected['client_id'], watch_id)
    return jsonify(ok=True)


@bp.get('/api/planner/radar/runs/latest')
def planner_radar_latest():
    from ..cadu_radar import pipeline, repository as radar
    selected = context.resolve()
    return jsonify(run=pipeline.latest_run(selected['client_id']) if radar.available() else None)


@bp.get('/api/planner/radar/runs/<run_id>')
def planner_radar_run(run_id):
    from ..cadu_radar import pipeline
    selected = context.resolve()
    run = pipeline.get_run(selected['client_id'], run_id)
    if not run:
        abort(404)
    return jsonify(run=run)


@bp.get('/api/planner/radar/pautas')
def planner_radar_pautas():
    from ..cadu_radar import repository as radar
    selected = context.resolve()
    return jsonify(pautas=radar.list_pautas(selected['client_id']))


@bp.post('/api/planner/radar/opportunities/<opportunity_id>/briefing')
def planner_radar_brief_plan(opportunity_id):
    """Leva um ângulo de inteligência ao briefing de um plano existente (``plan_id``) ou de um plano novo."""
    from ..cadu_radar import repository as radar
    selected = writable_context()
    user = context.identity()
    plan_id = (request.get_json(silent=True) or {}).get('plan_id') or None
    return jsonify(plan=radar.brief_plan(selected['client_id'], user['id'], opportunity_id, plan_id, selected))


@bp.put('/api/planner/radar/opportunities/<opportunity_id>/pauta')
def planner_radar_pauta(opportunity_id):
    """Guarda (ou tira) um ângulo de conteúdo da lista de pautas; o que já virou plano não muda."""
    from ..cadu_radar import repository as radar
    selected = writable_context()
    saved = bool((request.get_json(silent=True) or {}).get('saved'))
    return jsonify(status=radar.set_pauta(selected['client_id'], opportunity_id, saved))


@bp.post('/api/planner/radar/opportunities/<opportunity_id>/plan')
def planner_radar_create_plan(opportunity_id):
    """Cria um planejamento que nasce da oportunidade (source='radar')."""
    from ..cadu_radar import repository as radar
    selected = writable_context()
    user = context.identity()
    return jsonify(plan=radar.create_plan(selected['client_id'], user['id'], opportunity_id, selected)), 201


@bp.post('/api/planner/radar/signals/<signal_id>/plan')
def planner_radar_signal_plan(signal_id):
    """Cria um planejamento que nasce de uma notícia do Radar: ela vira o briefing."""
    from ..cadu_radar import repository as radar
    selected = writable_context()
    user = context.identity()
    return jsonify(plan=radar.create_plan_from_signal(selected['client_id'], user['id'], signal_id, selected)), 201


@bp.get('/api/planner/plans/<plan_id>')
def planner_plan_detail(plan_id):
    from ..cadu_planner import plans
    user, selected = context.identity(), context.resolve()
    return jsonify(plan=plans.get_plan(selected['client_id'], user['id'], plan_id))


@bp.put('/api/planner/plans/<plan_id>')
def planner_plan_update(plan_id):
    from ..cadu_planner import plans
    selected = writable_context()
    user = context.identity()
    return jsonify(plan=plans.update_briefing(selected['client_id'], user['id'], plan_id, request.get_json(silent=True) or {}))


@bp.post('/api/planner/plans/<plan_id>/briefing-review')
def planner_plan_briefing_review(plan_id):
    """Apply the Planner's transparent three-pass review to a saved briefing."""
    from ..cadu_planner import revisions
    selected = writable_context()
    user = context.identity()
    try:
        return jsonify(revisions.review_briefing(selected['client_id'], user['id'], plan_id))
    except InsufficientToolCredits as exc:
        abort(409, description=str(exc))


@bp.get('/api/planner/plans/<plan_id>/briefing-review/estimate')
def planner_plan_briefing_review_estimate(plan_id):
    from ..cadu_planner import revisions
    user, selected = context.identity(), context.resolve()
    return jsonify(estimated_tokens=revisions.briefing_billing_estimate(selected['client_id'], user['id'], plan_id), passes=3)


@bp.get('/api/planner/plans/<plan_id>/final-plan')
def planner_final_plan(plan_id):
    from ..cadu_planner import final_plan
    user, selected = context.identity(), context.resolve()
    return jsonify(final_plan=final_plan.get_state(selected['client_id'], user['id'], plan_id))


@bp.get('/api/planner/plans/<plan_id>/final-plan/estimate')
def planner_final_plan_estimate(plan_id):
    from ..cadu_planner import final_plan
    user, selected = context.identity(), context.resolve()
    return jsonify(estimated_tokens=final_plan.estimate(selected['client_id'], user['id'], plan_id))


@bp.post('/api/planner/plans/<plan_id>/final-plan')
def planner_final_plan_generate(plan_id):
    """Generate a new version of the final plan; sections the user edited survive unless overwrite is confirmed."""
    from ..cadu_planner import final_plan
    selected = writable_context()
    user = context.identity()
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(final_plan=final_plan.generate(selected['client_id'], user['id'], plan_id,
                                                      overwrite_edited=bool(body.get('overwrite_edited')),
                                                      instructions=str(body.get('instructions') or '')[:2000]))
    except InsufficientToolCredits as exc:
        abort(409, description=str(exc))


@bp.put('/api/planner/plans/<plan_id>/final-plan/sections/<section>')
def planner_final_plan_section(plan_id, section):
    from ..cadu_planner import final_plan
    selected = writable_context()
    user = context.identity()
    body = request.get_json(silent=True) or {}
    return jsonify(final_plan=final_plan.update_section(selected['client_id'], user['id'], plan_id, section,
                                                        body.get('body'), expected_version=body.get('expected_version')))


@bp.post('/api/planner/plans/<plan_id>/final-plan/share')
def planner_final_plan_share(plan_id):
    from ..cadu_planner import final_plan
    selected = writable_context()
    user = context.identity()
    body = request.get_json(silent=True) or {}
    return jsonify(final_plan=final_plan.set_share(selected['client_id'], user['id'], plan_id, bool(body.get('enabled')),
                                                    rotate=bool(body.get('rotate'))))


@bp.post('/api/planner/plans/<plan_id>/final-plan/project')
def planner_final_plan_to_project(plan_id):
    from ..cadu_planner import final_plan
    selected = writable_context()
    user = context.identity()
    try:
        return jsonify(final_plan=final_plan.add_to_project(selected['client_id'], user['id'], plan_id))
    except InsufficientToolCredits as exc:
        abort(409, description=str(exc))


@bp.put('/api/planner/plans/<plan_id>/allocations')
def planner_plan_allocations(plan_id):
    from ..cadu_planner import plans
    selected = writable_context()
    user = context.identity()
    return jsonify(plan=plans.save_allocations(selected['client_id'], user['id'], plan_id, request.get_json(silent=True) or {}))


@bp.get('/api/planner/plans/<plan_id>/balance')
def planner_plan_balance(plan_id):
    """Proposta de balanceamento (não grava): método, fatias, reais, calendário e alertas."""
    from ..cadu_planner import balance, plans
    user, selected = context.identity(), context.resolve()
    plan = plans.get_plan(selected['client_id'], user['id'], plan_id)
    manual = {key[2:]: request.args.get(key) for key in request.args if key.startswith('w.')}
    return jsonify(balance=balance.compute(plan, request.args.get('method') or None, manual,
                                           progress=request.args.get('progress', '1') != '0'))


@bp.post('/api/planner/plans/<plan_id>/balance')
def planner_plan_balance_apply(plan_id):
    """Grava o balanceamento escolhido pelo usuário como a distribuição do plano."""
    from ..cadu_planner import balance
    selected = writable_context()
    user = context.identity()
    return jsonify(plan=balance.apply(selected['client_id'], user['id'], plan_id, request.get_json(silent=True) or {}))


@bp.put('/api/planner/plans/<plan_id>/status')
def planner_plan_status(plan_id):
    from ..cadu_planner import plans
    selected = writable_context()
    user = context.identity()
    return jsonify(plan=plans.update_status(selected['client_id'], user['id'], plan_id, request.get_json(silent=True) or {}))


@bp.post('/api/planner/plans/<plan_id>/items/toggle')
def planner_plan_item_toggle(plan_id):
    from ..cadu_planner import plans
    selected = writable_context()
    user = context.identity()
    return jsonify(plans.toggle_item(selected['client_id'], user['id'], plan_id, request.get_json(silent=True) or {}))


@bp.post('/api/planner/plans/<plan_id>/items/bulk')
def planner_plan_items_bulk(plan_id):
    from ..cadu_planner import plans
    selected = writable_context()
    user = context.identity()
    return jsonify(plans.add_items(selected['client_id'], user['id'], plan_id, request.get_json(silent=True) or {}))


@bp.post('/api/planner/plans/<plan_id>/quote-requests')
def planner_plan_quote_request(plan_id):
    """Freeze the customer plan for commercial review; pricing remains in CRM."""
    from ..cadu_planner import plans
    selected = writable_context()
    user = context.identity()
    return jsonify(plan=plans.request_quote(selected['client_id'], user['id'], plan_id,
                                             request.get_json(silent=True) or {})), 201


@bp.post('/api/planner/plans/<plan_id>/share')
def planner_plan_share(plan_id):
    from ..cadu_planner import plans
    selected = writable_context()
    user = context.identity()
    data = request.get_json(silent=True) or {}
    return jsonify(plan=plans.share_plan(selected['client_id'], user['id'], plan_id,
                                         data.get('enabled', True)))


@bp.post('/api/planner/selections/bulk')
def planner_selections_bulk():
    from ..cadu_planner import selections
    selected = writable_context()
    user = context.identity()
    return jsonify(selections.add_many(selected['client_id'], user['id'], request.get_json(silent=True) or {}))


@bp.post('/api/planner/selections/toggle')
def planner_selection_toggle():
    from ..cadu_planner import selections
    selected = writable_context()
    user = context.identity()
    return jsonify(selections.toggle(selected['client_id'], user['id'], request.get_json(silent=True) or {}))


@bp.post('/api/planner/link-tester')
def planner_link_test():
    from ..cadu_connect import reports_link_tester as link_tester
    user, selected = context.identity(), context.resolve()
    return jsonify(result=link_tester.test(request.get_json(silent=True) or {}, selected['client_id'], user['id']))


@bp.get('/api/planner/link-tester/history')
def planner_link_test_history():
    from ..cadu_connect import reports_link_tester as link_tester
    selected = context.resolve()
    return jsonify(runs=link_tester.history(selected['client_id']))


@bp.get('/api/planner/link-tester/<run_id>')
def planner_link_test_detail(run_id):
    from ..cadu_connect import reports_link_tester as link_tester
    selected = context.resolve()
    report = link_tester.detail(selected['client_id'], run_id)
    if not report:
        abort(404)
    return jsonify(run=report)


@bp.get('/public/link-tester/<token>')
def public_link_test(token):
    return redirect(url_for('cadu_connect.reports_v1_public_link_test', token=token), code=302)


@bp.get('/api/planner/docs')
def planner_docs():
    from ..cadu_planner import docs
    user, selected = context.identity(), context.resolve()
    return jsonify(documents=docs.list_documents(selected['client_id'], user['id']), templates=docs.templates(selected['client_id']))


@bp.post('/api/planner/docs')
def planner_docs_create():
    from ..cadu_planner import docs
    selected = writable_context()
    user = context.identity()
    return jsonify(document=docs.create_document(selected['client_id'], user['id'], request.get_json(silent=True) or {})), 201


@bp.get('/api/planner/docs/<doc_id>')
def planner_doc_detail(doc_id):
    from ..cadu_planner import docs
    user, selected = context.identity(), context.resolve()
    return jsonify(document=docs.get_document(selected['client_id'], user['id'], doc_id))


@bp.put('/api/planner/docs/<doc_id>')
def planner_doc_save(doc_id):
    from ..cadu_planner import docs
    selected = writable_context()
    user = context.identity()
    return jsonify(document=docs.save_document(selected['client_id'], user['id'], doc_id, request.get_json(silent=True) or {}))


@bp.post('/api/planner/docs/<doc_id>/review')
def planner_doc_review(doc_id):
    from ..cadu_planner import revisions
    selected = writable_context()
    user = context.identity()
    try:
        return jsonify(revisions.review_document(selected['client_id'], user['id'], doc_id))
    except InsufficientToolCredits as exc:
        abort(409, description=str(exc))


@bp.get('/api/planner/docs/<doc_id>/review/estimate')
def planner_doc_review_estimate(doc_id):
    from ..cadu_planner import revisions
    user, selected = context.identity(), context.resolve()
    return jsonify(estimated_tokens=revisions.document_billing_estimate(selected['client_id'], user['id'], doc_id), passes=3)


@bp.post('/api/planner/docs/<doc_id>/duplicate')
def planner_doc_duplicate(doc_id):
    from ..cadu_planner import docs
    selected = writable_context()
    user = context.identity()
    return jsonify(document=docs.duplicate_document(selected['client_id'], user['id'], doc_id)), 201


@bp.post('/api/planner/docs/<doc_id>/share')
def planner_doc_share(doc_id):
    from ..cadu_planner import docs
    selected = writable_context()
    user = context.identity()
    data = request.get_json(silent=True) or {}
    return jsonify(document=docs.share_document(selected['client_id'], user['id'], doc_id, data.get('enabled', True)))


@bp.get('/planner/docs/public/<token>')
def planner_doc_public(token):
    from ..cadu_planner import docs
    document = docs.public_document(token)
    response = make_response(_render_planner('public-doc', 'docs', document.get('title') or 'Documento',
                                             public=True, document=document))
    response.headers['Content-Security-Policy'] = "sandbox; default-src 'none'; script-src 'self'; style-src 'self'; img-src https: data:; font-src https: data:"
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@bp.get('/planner/links/public/<token>')
def planner_public_link_report(token):
    """Move old public Link Tester URLs to the Reports-owned page."""
    target = product_url('connect', f'/connect/public/link-tests/{quote(token, safe="")}')
    return redirect(target, code=302)


@bp.get('/planner/planos/<plan_id>')
def planner_plan_media_desk(plan_id):
    if not session.get('user_id'):
        return redirect(workspace_public_url(), code=302)
    from ..cadu_planner import plans
    user = context.identity()
    selected = context.resolve()
    plan = plans.get_plan(selected['client_id'], user['id'], plan_id)
    return _render_planner('plan-detail', 'planos', plan['title'], plan=plan)


@bp.get('/planner/planos/<plan_id>/final')
def planner_plan_final_page(plan_id):
    """The final plan has its own page: the document is the end of the plan, not a block inside it."""
    if not session.get('user_id'):
        return redirect(workspace_public_url(), code=302)
    from ..cadu_planner import plans
    user = context.identity()
    selected = context.resolve()
    plan = plans.get_plan(selected['client_id'], user['id'], plan_id)
    return _render_planner('plan-final', 'planos', f"Plano final — {plan['title']}", plan=plan)


@bp.get('/planner/planos/public/<token>')
def planner_public_plan(token):
    from ..cadu_planner import plans
    plan = plans.public_plan(token)
    return _render_planner('public-plan', 'planos', plan['title'], public=True, plan=plan)


@bp.get('/planner/planos/public/final/<token>')
def planner_public_final_plan(token):
    """Open link to the current final plan: read-only, no login, no internal data."""
    from ..cadu_planner import final_plan
    document = final_plan.public_by_token(token)
    response = make_response(_render_planner('public-final-plan', 'planos', document['title'] or 'Plano final',
                                             public=True, document=document))
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/planner/<kind>/<int:item_id>')
def planner_catalog_detail_page(kind, item_id):
    if kind not in {'audiencias', 'canais', 'formatos', 'interativos', 'portais'}:
        abort(404)
    if not session.get('user_id'):
        return redirect(workspace_public_url(), code=302)
    context.resolve()
    from ..cadu_planner import catalog
    if kind == 'portais':
        from ..cadu_planner import portals
        record, view = portals.detail(item_id), 'catalog-detail'
    elif kind == 'canais':
        record, view = catalog.channel_profile(item_id), 'channel-detail'
    elif kind == 'audiencias':
        record, view = catalog.audience_profile(item_id), 'audience-detail'
    else:
        record, view = catalog.format_profile(kind, item_id), 'format-detail'
    return _render_planner(view, kind, record['name'], record=record)


@bp.get('/planner/places/<slug>')
def planner_place_detail_page(slug):
    """Private marketplace fiche with the full curated Place gallery."""
    if not session.get('user_id'):
        return redirect(workspace_public_url(), code=302)
    from ..cadu_planner import places
    context.resolve()
    record = places.detail(slug)
    return _render_planner('catalog-detail', 'places', record['name'], record=record)


@bp.post('/api/planner/docs/<doc_id>/export')
def planner_doc_export(doc_id):
    from io import BytesIO
    from flask import send_file
    from ..cadu_planner import docs
    selected = writable_context()
    user = context.identity()
    document = docs.get_document(selected['client_id'], user['id'], doc_id)
    return send_file(BytesIO(docs.export_pdf(document)), mimetype='application/pdf', as_attachment=True,
                     download_name='documento-%s.pdf' % doc_id)


@bp.post('/api/studio/copy-ads/validate')
def copy_validate():
    from . import copy_ads
    context.resolve()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400)
    spec = next((row for row in copy_ads.formats() if str(row['id']) == str(data.get('format_id'))), None)
    if spec is None:
        abort(404, description='Formato indisponível. Atualize o catálogo.')
    return jsonify(copy_ads.validate_copy(spec, data.get('values')))


@bp.post('/api/conversations/send')
def conversation_send():
    selected = writable_context()
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or data.get('profile') not in PROFILES:
        abort(400, description='Esta solução não utiliza o agente compartilhado.')
    from . import chat
    run = chat.prepare(data, selected)
    if run.get('queued'):
        return jsonify(accepted=True, run_id=run['run_id'], conversation_id=run['conversation_id']), 202
    if run.get('recovered'):
        response = jsonify(run)
        response.headers['Cache-Control'] = 'no-store'
        return response
    return Response(stream_with_context(chat.stream(run)), mimetype='text/event-stream',
                    headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache, no-store',
                             'Connection': 'keep-alive'})


@bp.get('/api/conversations/runs/<uuid:run_id>')
def conversation_run_state(run_id):
    from ..cadu_workspace.conversations import recovery
    user = context.identity()
    selected = context.resolve()
    result = recovery.state(str(run_id), user, selected['client_id'])
    if result is None:
        abort(404)
    result = {**result, 'replay': bool(current_app.config.get('CADU_CHAT_WORKER_ENABLED', False)
        and repository.rows('SELECT run_id FROM cadu_family_chat_jobs WHERE run_id = %s', (str(run_id),)))}
    response = jsonify(result)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/api/conversations/runs/<uuid:run_id>/events')
def conversation_run_events(run_id):
    from ..cadu_workspace.conversations import recovery, jobs
    user = context.identity()
    selected = context.resolve()
    result = recovery.state(str(run_id), user, selected['client_id'])
    if result is None:
        abort(404)
    if not current_app.config.get('CADU_CHAT_WORKER_ENABLED', False):
        abort(503, description='Retomada de eventos ainda não habilitada.')
    try:
        after = int(request.args.get('after', '0'))
        if after < 0 or after > 9223372036854775807:
            raise ValueError()
    except ValueError:
        abort(400)
    return jsonify(**jobs.page(str(run_id), after), status=result['status'])


@bp.get('/api/conversations/capabilities')
def conversation_capabilities():
    from ..cadu_workspace.conversations.attachments import ACCEPT, MAX_BYTES
    from . import dify
    context.identity()
    selected = context.resolve()
    enabled = selected['role'] in ('admin', 'member')
    reason = ''
    if selected['role'] not in ('admin', 'member'):
        reason = 'Sua conta não tem permissão para iniciar conversas neste espaço.'
    else:
        try:
            dify.settings()
        except dify.DifyUnavailable:
            # A indisponibilidade do provedor não deve bloquear a escrita.
            # O envio exibirá o estado real da conexão ao ser iniciado.
            reason = 'A conexão do Cadu está sendo configurada. O envio será validado ao iniciar a conversa.'
    return jsonify(send=enabled, attachments=enabled, replay=bool(current_app.config.get('CADU_CHAT_WORKER_ENABLED', False)), max_files=3, max_bytes=MAX_BYTES,
                   accept=ACCEPT, external_tools=False, reason=reason)


@bp.post('/api/conversations/preflight')
def conversation_preflight():
    from ..cadu_workspace.conversations.guardrails import validate_message, require_available_intent
    from ..cadu_workspace.conversations.orchestration import classify
    writable_context()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400)
    message = validate_message(data.get('message'))
    return jsonify(intent=require_available_intent(message), routing=classify(message))


@bp.post('/api/conversations/uploads')
def conversation_upload():
    from ..cadu_workspace.conversations import attachments
    selected = writable_context()
    user = context.identity()
    # Bound multipart parsing as well as the individual file read.
    attachments.bound_multipart_request(request)
    files = request.files.getlist('file')
    if len(files) != 1 or len(request.files) != 1:
        abort(400, description='Envie um arquivo de cada vez.')
    return jsonify(file=attachments.upload(files[0], user, selected)), 201


@bp.get('/api/conversations/modes')
def conversation_modes():
    from .chat import modes
    user = context.identity()
    context.resolve()
    return jsonify(modes=modes(user['id']))


@bp.post('/api/conversations/modes/active')
def conversation_mode_active():
    from .chat import set_active_mode
    writable_context()
    data = request.get_json(silent=True) or {}
    return jsonify(modes=set_active_mode(context.identity()['id'], data.get('mode')))


@bp.put('/api/conversations/modes/<slug>')
def conversation_mode_update(slug):
    from .chat import update_mode_prompt
    writable_context()
    data = request.get_json(silent=True) or {}
    if set(data) != {'prompt'}:
        abort(400, description='Informe somente as instruções do modo.')
    return jsonify(modes=update_mode_prompt(context.identity()['id'], slug, data['prompt']))


@bp.delete('/api/conversations/modes/<slug>')
def conversation_mode_reset(slug):
    from .chat import reset_mode_prompt
    writable_context()
    return jsonify(modes=reset_mode_prompt(context.identity()['id'], slug))


@bp.post('/api/conversations/runs/<uuid:run_id>/stop')
def conversation_stop(run_id):
    from . import dify
    selected = writable_context()
    user = context.identity()
    runs = repository.rows('''SELECT task_id, status FROM cadu_family_chat_runs
                              WHERE id = %s AND user_id = %s AND client_id = %s''',
                           (str(run_id), user['id'], selected['client_id']))
    if not runs:
        abort(404)
    if runs[0]['status'] != 'running':
        return jsonify(stopped=True)
    if current_app.config.get('CADU_CHAT_WORKER_ENABLED', False):
        from ..cadu_workspace.conversations.jobs import cancel_pending
        if cancel_pending(str(run_id)):
            return jsonify(stopped=True)
    if not runs[0]['task_id']:
        abort(409, description='A geração ainda está iniciando. Tente novamente.')
    dify.stop(runs[0]['task_id'], 'user-' + str(user['id']))
    return jsonify(stopped=True)


@bp.get('/api/conversations/<conversation_id>/messages')
def messages(conversation_id):
    user = context.identity()
    selected = context.resolve()
    result = repository.conversation_messages(user['id'], selected['client_id'], conversation_id)
    if result is None:
        abort(404)
    return jsonify(messages=result, context=repository.conversation_context(user, selected['client_id'], conversation_id))


def _work_memory_project(selected, project_ref):
    if not isinstance(project_ref, str) or not any(item['ref'] == project_ref and item['kind'] == 'project'
                                                   for item in context.inventory(selected['client_id'])):
        abort(403, description='O projeto não pertence a este ambiente.')
    if not repository.project_user_can_view(selected['client_id'], project_ref, context.identity()['id']):
        abort(403, description='Você não tem acesso a este projeto.')
    return project_ref


def _can_review_work_memory(client_id, project_ref, user):
    if repository.account_role(user) == 'admin':
        return True
    return any(int(item.get('user_id') or 0) == int(user['id'])
               and item.get('role') in {'owner', 'admin', 'editor'}
               for item in repository.project_access(client_id, project_ref))


@bp.get('/api/conversations/work-memory')
def conversation_work_memory():
    from ..cadu_workspace.conversations import working_memory
    user = context.identity()
    selected = context.resolve()
    project_ref = _work_memory_project(selected, request.args.get('project'))
    return jsonify(working_memory.board(user, selected['client_id'], project_ref))


@bp.patch('/api/conversations/work-memory/<uuid:memory_id>')
def conversation_work_memory_review(memory_id):
    from ..cadu_workspace.conversations import working_memory
    selected = writable_context()
    data = request.get_json(silent=True) or {}
    if set(data) - {'action', 'summary'} or not isinstance(data.get('action'), str):
        abort(400, description='Informe a ação da memória.')
    if 'summary' in data and not isinstance(data['summary'], str):
        abort(400, description='O resumo da memória é inválido.')
    rows = repository.rows('''SELECT project_ref FROM cadu_working_memories
        WHERE id=%s AND client_id=%s AND scope='project' LIMIT 1''',
        (str(memory_id), selected['client_id']))
    if not rows:
        abort(404)
    project_ref = _work_memory_project(selected, rows[0]['project_ref'])
    user = context.identity()
    if not _can_review_work_memory(selected['client_id'], project_ref, user):
        abort(403, description='Você não pode revisar memórias deste projeto.')
    try:
        item = working_memory.review(str(memory_id), user, selected['client_id'],
                                     project_ref, data['action'], data.get('summary'))
    except ValueError as exc:
        abort(400, description=str(exc))
    if not item:
        abort(404)
    return jsonify(memory=item)


@bp.get('/workspace/marcas/sistema')
def workspace_brand_system():
    """Keep shared links alive without maintaining a second brand interface."""
    brand_id = (request.args.get('creative_client_id') or request.args.get('brand_id')
                or request.args.get('crm_client_id') or request.args.get('client_id'))
    target = product_url('workspace', canonical_workspace_legacy_path('marcas/sistema', brand_id))
    if request.query_string:
        target = f"{target}?{request.query_string.decode('utf-8')}"
    return redirect(target, code=302)


@bp.get('/<product>/')
@bp.get('/<product>/<module>')
def page(product, module=None):
    if product not in PRODUCTS:
        abort(404)
    if product == 'workspace':
        if not session.get('user_id'):
            return redirect(workspace_public_url(), code=302)
        target = product_url('workspace', canonical_workspace_legacy_path(module or ''))
        if request.query_string:
            target = f"{target}?{request.query_string.decode('utf-8')}"
        return redirect(target, code=302)
    if product == 'planner':
        if not session.get('user_id'):
            return redirect(workspace_public_url(), code=302)
        return _planner_react_page(module)
    # The product family no longer maintains separate guest landing pages.
    # Unauthenticated visitors start with the shared Workspace context page;
    # public shares have dedicated routes above and do not pass through here.
    if not session.get('user_id'):
        return redirect(workspace_public_url(), code=302)
    if (product, module) == ('studio', 'link-tester'):
        target = url_for('cadu_connect.reports_v1_app')
        if request.query_string:
            target = f"{target}?{request.query_string.decode('utf-8')}"
        target += '#links'
        return redirect(target, code=302)
    spec = PRODUCTS[product]
    module = module or next(iter(spec['modules']))
    if module not in spec['modules']:
        abort(404)
    title, legacy = spec['modules'][module]
    user, selected, clients, entities, records = None, None, [], [], []
    if session.get('user_id'):
        user = context.identity()
        selected = context.resolve()
        clients = context.authorized_clients()
        # Planner no longer works with a selectable project/brand context.
        # Avoid loading those legacy records on every Planner request.
        if product != 'planner':
            entities = context.inventory(selected['client_id'])
        if product == 'workspace' and module in ADMIN_MODULES:
            context.require_admin()
        records = product_pages.load_records(product, module, user, selected, request.args.get('q', ''), request.args)
    token = session.setdefault('family_csrf', secrets.token_urlsafe(32))
    # PHP currently knows the actor's organization, not an agency's selected client.
    # Never hand off to the wrong tenant while the adapter is pending.
    legacy_url = None
    if user and legacy and selected['client_id'] == user['organization_id']:
        legacy_url = product_url('auth', '/auth/sso/to-cadu') + '?' + urlencode({'next': product_url('cadu', legacy)})
    template = product_pages.page_template(product)
    return render_template(template, product=product, spec=spec, module=module,
        title=title, products=PRODUCTS, landing=LANDINGS[product], user=user, selected=selected, clients=clients,
        entities=entities, records=records, profile=PROFILES.get(product), csrf=token,
        legacy_url=legacy_url, login_url=login_url(), product_url=product_url, planner_url=planner_url,
        planner_view='page', marketplace_facets=marketplace_facets(product, module))


def _audience_page(args):
    """Audience marketplace page from URL args (Portuguese names on the page, English in the API)."""
    pick = lambda *names: next((args.get(name) for name in names if args.get(name)), '')
    return repository.audience_search(
        query=pick('q'), category=pick('categoria', 'category'), platform=pick('canal', 'platform'),
        subcategory=pick('subcategoria', 'subcategory'), sort=pick('ordem', 'sort') or 'relevant',
        limit=pick('limit') or 48, offset=pick('offset') or 0)


def _planner_react_page(module=None):
    """Render every Planner route through the single React application."""
    spec = PRODUCTS['planner']
    module = module or next(iter(spec['modules']))
    if module not in spec['modules']:
        abort(404)
    if module == 'inicio':
        # The home is the channel shelf: people start by where the media runs.
        module = 'canais'
    title, _legacy = spec['modules'][module]
    if module == 'audiencias':
        # The largest showcase: paged, faceted and filterable from the URL.
        page = _audience_page(request.args)
        return _render_planner('page', module, title, records=page.pop('records'), catalog_meta=page)
    records = product_pages.load_records('planner', module, context.identity(), context.resolve(),
                                         request.args.get('q', ''), request.args)
    return _render_planner('page', module, title, records=records,
                           marketplace_facets=marketplace_facets('planner', module))


def _active_plan(selected, user):
    """Plano em que as vitrines adicionam itens: ``?plan=`` ou o último aberto na sessão."""
    from werkzeug.exceptions import HTTPException
    from ..cadu_planner import plans
    requested = request.args.get('plan')
    plan_id = requested or session.get('planner_active_plan')
    if not plan_id:
        return None
    try:
        plan = plans.get_plan(selected['client_id'], user['id'], plan_id)
    except HTTPException:
        session.pop('planner_active_plan', None)
        return None
    session['planner_active_plan'] = str(plan['id'])
    return plan


def _render_planner(view, module, title, *, public=False, **data):
    """Every Planner page boots the same React app; shared links carry no session data."""
    session_data = {'user': None, 'selected': None, 'csrf': '', 'cadu_family_writes_enabled': False} if public else {
        'user': context.identity(), 'selected': context.resolve(),
        'csrf': session.setdefault('family_csrf', secrets.token_urlsafe(32)),
    }
    features = {'cobuild': bool(current_app.config.get('CADU_PLANNER_COBUILD_ENABLED')),
                'radar': bool(current_app.config.get('CADU_RADAR_ENABLED'))}
    if not public:
        selected, user = session_data['selected'], session_data['user']
        data.setdefault('context_bar', _planner_context_bar(selected['client_id']))
        if view in ('plan-detail', 'plan-final') and data.get('plan'):
            session['planner_active_plan'] = str(data['plan']['id'])
        elif 'plan' not in data and view != 'public-doc':
            data['plan'] = _active_plan(selected, user)
    g.light_shell = True  # react.html only reads the avatar from the global shell context
    return render_template('cadu_planner/react.html', planner_view=view, module=module, title=title,
                           planner_url=planner_url, product_url=product_url, planner_features=features,
                           **session_data, **data)
