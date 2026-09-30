"""Describe observed edge traffic without confusing missing data with zero."""


def edge_observation(edge, measured_ids, node_totals, transition_totals, has_events):
    source, target = edge['from'], edge['to']
    if source not in measured_ids or target not in measured_ids:
        return {'status': 'unmeasured', 'sessions': None, 'rate': None, 'denominator': None}
    if not has_events:
        return {'status': 'no_data', 'sessions': None, 'rate': None, 'denominator': None}
    denominator = int(node_totals.get(source, {}).get('sessions') or 0)
    sessions = int(transition_totals.get((source, target), 0))
    return {'status': 'measured' if denominator else 'no_origin',
            'sessions': sessions, 'rate': round(100 * sessions / denominator, 1) if denominator else None,
            'denominator': denominator}
