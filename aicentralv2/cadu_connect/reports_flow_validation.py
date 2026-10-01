"""Publication checks for the authored journey; draft saving stays permissive.

Kept free of package imports: parity tests load this file on its own.
"""

MEASURED = {'page', 'form', 'event', 'conversion', 'whatsapp', 'error'}
NODE_STATUSES = ('planned', 'in_production', 'ready', 'live')
# Older drafts marked a step without a real URL with a fake "/configurar-…" path.
PLACEHOLDER_PREFIX = '/configurar-'


def has_real_path(node):
    path = node.get('path')
    return (isinstance(path, str) and path.startswith('/') and not path.startswith('//')
            and not path.startswith(PLACEHOLDER_PREFIX))


def node_status(node):
    """A step can exist in the plan before its page does; only ready/live steps are measured.

    Planning is an explicit choice: a step without a status and without a real URL is
    "ready" with a missing address, so publication still asks for it.
    """
    status = node.get('status')
    if status in NODE_STATUSES:
        return status
    if node.get('type') not in MEASURED or has_real_path(node):
        return 'live'
    return 'ready'


def is_measured(node):
    return (isinstance(node, dict) and node.get('type') in MEASURED
            and node_status(node) in ('ready', 'live') and has_real_path(node))
PAGE_TYPES = {'page', 'form', 'conversion', 'error'}
# A flow follows a few pages that matter; the explorer is where the rest of the site lives.
MAX_FLOW_PAGES = 6
DETAILS = {
    'no_conversion': ('Sem conversão definida, não será possível medir a conclusão desta jornada.', 'add_conversion'),
    'unmapped_page': ('O nó não poderá ser associado a uma página ou evento recebido.', 'configure_url'),
    'unmapped_event': ('A Super Tag não conseguirá associar este evento ao nó.', 'configure_event'),
    'duplicate_page': ('A mesma visita pode ser atribuída ao nó errado.', 'review_duplicate'),
    'orphan': ('Este nó não participa de um caminho planejado.', 'connect_node'),
    'intent_without_goal': ('Não há caminho deste nó até uma conversão definida.', 'connect_to_conversion'),
    'unconfirmed_goal': ('O objetivo sugerido ainda não foi revisado.', 'confirm_goal'),
    'cycle_without_condition': ('A jornada pode ficar ambígua neste Retorno.', 'review_return'),
    'too_many_pages': ('Com muitas páginas o fluxo deixa de mostrar o caminho principal.', 'reduce_pages'),
    'planned_step': ('Este passo fica fora da medição até ter uma página no ar.', 'link_page'),
    'planned_conversion': ('A medição não registrará conclusões enquanto a conversão estiver planejada.', 'link_page'),
}


def validate_flow_config(config, allowed_host=''):
    nodes = config.get('nodes') or []
    edges = config.get('edges') or []
    issues = []
    by_id = {node['id']: node for node in nodes}
    outgoing = {node['id']: [] for node in nodes}
    incoming = {node['id']: [] for node in nodes}
    page_paths = set()
    for edge in edges:
        if edge.get('from') in outgoing and edge.get('to') in incoming:
            outgoing[edge['from']].append(edge['to'])
            incoming[edge['to']].append(edge['from'])
    # Institutional sites are read by engagement (time, depth, exits); a conversion is optional there.
    engagement = config.get('site_kind') == 'institucional'
    conversions = [node for node in nodes if node.get('type') == 'conversion']
    if not engagement and not conversions:
        issues.append({'severity': 'error', 'code': 'no_conversion',
                       'message': 'Defina um nó de Conversão antes de publicar.'})
    elif not engagement and all(node_status(node) in ('planned', 'in_production') for node in conversions):
        issues.append({'severity': 'warning', 'code': 'planned_conversion',
                       'message': 'Todas as conversões estão planejadas; a medição não registrará conclusões.'})
    for node in nodes:
        node_id = node['id']
        planned = node.get('type') in MEASURED and node_status(node) in ('planned', 'in_production')
        if planned:
            issues.append({'severity': 'info', 'code': 'planned_step', 'node_id': node_id,
                           'message': f"{node.get('title') or 'Um passo'} está planejado e ainda não é medido."})
        elif node.get('type') in MEASURED and not has_real_path(node):
            issues.append({'severity': 'error', 'code': 'unmapped_page', 'node_id': node_id,
                           'message': f"Configure a URL real de {node.get('title') or 'um nó'} ou marque o passo como Planejado."})
        if not planned and node.get('type') == 'event' and (not node.get('event_name') or node.get('placeholder') is True):
            issues.append({'severity': 'error', 'code': 'unmapped_event', 'node_id': node_id,
                           'message': f"Configure o nome do evento de {node.get('title') or 'um nó'}."})
        if node.get('type') == 'page' and is_measured(node):
            key = (node.get('host') or allowed_host, node['path'])
            if key in page_paths:
                issues.append({'severity': 'error', 'code': 'duplicate_page', 'node_id': node_id,
                               'message': f"A URL {node['path']} já está em outra página do fluxo."})
            page_paths.add(key)
        if len(nodes) > 1 and not incoming[node_id] and not outgoing[node_id]:
            issues.append({'severity': 'warning', 'code': 'orphan', 'node_id': node_id,
                           'message': f"{node.get('title') or 'Um nó'} está sem conexões."})
    goals={node['id'] for node in nodes if node.get('type')=='conversion'}
    reachable=set(goals)
    changed=True
    while changed:
        before=len(reachable)
        for edge in edges:
            if edge.get('to') in reachable:reachable.add(edge.get('from'))
        changed=len(reachable)!=before
    for node in nodes:
        if not engagement and (node.get('stage')=='intent' or node.get('type') in ('form','whatsapp')) and node['id'] not in reachable:
            issues.append({'severity':'error','code':'intent_without_goal','node_id':node['id'],'message':f"Conecte {node.get('title') or 'o nó de Intenção'} a um nó de Conversão."})
    # A group of similar pages reads as one step.
    pages = len({node.get('groupId') or node['id'] for node in nodes if node.get('type') in PAGE_TYPES})
    if pages > MAX_FLOW_PAGES:
        issues.append({'severity': 'warning', 'code': 'too_many_pages',
                       'message': f'O fluxo tem {pages} páginas; mantenha até {MAX_FLOW_PAGES} no caminho principal.'})
    if any(n.get('origin')=='blueprint' for n in nodes) and config.get('blueprintGoalConfirmed') is not True:
        issues.append({'severity':'error','code':'unconfirmed_goal','message':'Confirme o objetivo da montagem antes de publicar.'})
    stack, visited = [], set()
    unsafe_cycle = False
    unsafe_edge_id = None

    def walk(node_id, edge_id=None):
        nonlocal unsafe_cycle, unsafe_edge_id
        if node_id in stack:
            cycle_nodes = stack[stack.index(node_id):]
            if not any(by_id[item].get('type') == 'condition' for item in cycle_nodes):
                unsafe_cycle = True
                unsafe_edge_id = unsafe_edge_id or edge_id
            return
        if node_id in visited:
            return
        stack.append(node_id)
        for edge in edges:
            if edge.get('from') == node_id and edge.get('to') in by_id:
                walk(edge['to'], edge.get('id'))
        stack.pop()
        visited.add(node_id)

    for node_id in by_id:
        walk(node_id)
    if unsafe_cycle:
        issues.append({'severity': 'error', 'code': 'cycle_without_condition', 'edge_id': unsafe_edge_id,
                       'message': 'Há um Retorno sem nó de condição. Revise as conexões.'})
    return [{**issue, 'consequence': DETAILS[issue['code']][0], 'action': DETAILS[issue['code']][1]}
            for issue in issues]
