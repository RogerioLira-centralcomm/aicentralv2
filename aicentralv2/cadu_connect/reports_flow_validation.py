"""Publication checks for the authored journey; draft saving stays permissive."""

MEASURED = {'page', 'form', 'event', 'conversion', 'whatsapp', 'error'}
DETAILS = {
    'no_conversion': ('Sem conversão definida, não será possível medir a conclusão desta jornada.', 'add_conversion'),
    'unmapped_page': ('O nó não poderá ser associado a uma página ou evento recebido.', 'configure_url'),
    'unmapped_event': ('A Super Tag não conseguirá associar este evento ao nó.', 'configure_event'),
    'duplicate_page': ('A mesma visita pode ser atribuída ao nó errado.', 'review_duplicate'),
    'orphan': ('Este nó não participa de um caminho planejado.', 'connect_node'),
    'intent_without_goal': ('Não há caminho deste nó até uma conversão definida.', 'connect_to_conversion'),
    'unconfirmed_goal': ('O objetivo sugerido ainda não foi revisado.', 'confirm_goal'),
    'cycle_without_condition': ('A jornada pode ficar ambígua neste Retorno.', 'review_return'),
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
    if not any(node.get('type') == 'conversion' for node in nodes):
        issues.append({'severity': 'error', 'code': 'no_conversion',
                       'message': 'Defina um nó de Conversão antes de publicar.'})
    for node in nodes:
        node_id = node['id']
        if node.get('type') in MEASURED and (not node.get('path') or node['path'].startswith('/configurar-')):
            issues.append({'severity': 'error', 'code': 'unmapped_page', 'node_id': node_id,
                           'message': f"Configure a URL real de {node.get('title') or 'um nó'}."})
        if node.get('type') == 'event' and (not node.get('event_name') or node.get('placeholder') is True):
            issues.append({'severity': 'error', 'code': 'unmapped_event', 'node_id': node_id,
                           'message': f"Configure o nome do evento de {node.get('title') or 'um nó'}."})
        if node.get('type') == 'page' and node.get('path') and not node['path'].startswith('/configurar-'):
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
        if (node.get('stage')=='intent' or node.get('type') in ('form','whatsapp')) and node['id'] not in reachable:
            issues.append({'severity':'error','code':'intent_without_goal','node_id':node['id'],'message':f"Conecte {node.get('title') or 'o nó de Intenção'} a um nó de Conversão."})
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
