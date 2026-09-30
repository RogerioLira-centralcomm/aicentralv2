"""Publication checks for the authored journey; draft saving stays permissive."""

MEASURED = {'page', 'form', 'event', 'conversion', 'whatsapp', 'error'}


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
                       'message': 'Adicione uma etapa de conversão antes de publicar.'})
    for node in nodes:
        node_id = node['id']
        if node.get('type') in MEASURED and (not node.get('path') or node['path'].startswith('/configurar-')):
            issues.append({'severity': 'error', 'code': 'unmapped_page', 'node_id': node_id,
                           'message': f"Configure a URL real de {node.get('title') or 'uma etapa'}."})
        if node.get('type') == 'event' and (not node.get('event_name') or node.get('placeholder') is True):
            issues.append({'severity': 'error', 'code': 'unmapped_event', 'node_id': node_id,
                           'message': f"Configure o nome do evento de {node.get('title') or 'uma etapa'}."})
        if node.get('type') == 'page' and node.get('path') and not node['path'].startswith('/configurar-'):
            key = (node.get('host') or allowed_host, node['path'])
            if key in page_paths:
                issues.append({'severity': 'error', 'code': 'duplicate_page', 'node_id': node_id,
                               'message': f"A URL {node['path']} já está em outra página do fluxo."})
            page_paths.add(key)
        if len(nodes) > 1 and not incoming[node_id] and not outgoing[node_id]:
            issues.append({'severity': 'warning', 'code': 'orphan', 'node_id': node_id,
                           'message': f"{node.get('title') or 'Uma etapa'} está sem conexões."})
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
            issues.append({'severity':'error','code':'intent_without_goal','node_id':node['id'],'message':f"Conecte {node.get('title') or 'a etapa de intenção'} a uma conversão."})
    if any(n.get('origin')=='blueprint' for n in nodes) and config.get('blueprintGoalConfirmed') is not True:
        issues.append({'severity':'error','code':'unconfirmed_goal','message':'Confirme o objetivo da montagem antes de publicar.'})
    stack, visited = [], set()
    unsafe_cycle = False

    def walk(node_id):
        nonlocal unsafe_cycle
        if node_id in stack:
            cycle_nodes = stack[stack.index(node_id):]
            unsafe_cycle |= not any(by_id[item].get('type') == 'condition' for item in cycle_nodes)
            return
        if node_id in visited:
            return
        stack.append(node_id)
        for target in outgoing[node_id]:
            walk(target)
        stack.pop()
        visited.add(node_id)

    for node_id in by_id:
        walk(node_id)
    if unsafe_cycle:
        issues.append({'severity': 'error', 'code': 'cycle_without_condition',
                       'message': 'Há um ciclo sem bloco de condição. Revise as conexões.'})
    return issues
