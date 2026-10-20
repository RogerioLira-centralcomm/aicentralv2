"""Read a flow's events across publications with one drawing.

Each event keeps the publication its session was pinned to, but the metrics of a period are read
with the drawing being viewed: a page added in v67 also counts the visits it had under v65, and
publishing again never resets the numbers. Matching mirrors match_flow_node.
"""
import json

from .reports_flow_lifecycle import is_measured
from .reports_page_identity import sql_normalized_path as _norm_path


def norm_host_sql(column):
    return f"REGEXP_REPLACE(LOWER({column}),'^www[.]','')"


def node_match_json(config):
    """The measured nodes of a drawing, as the rows the matching CTE reads."""
    return json.dumps([{'node_id': node['id'], 'node_type': node['type'], 'path': node['path'],
                        'host': node.get('host') or None, 'event_name': str(node.get('event_name') or '')}
                       for node in (config or {}).get('nodes', [])
                       if isinstance(node, dict) and node.get('id') and node.get('path') and is_measured(node)])


CONFIGURED_NODES_SQL = f"""configured_nodes AS (
            SELECT node_id,node_type,event_name,{_norm_path('path')} AS npath,
                CASE WHEN host IS NULL THEN NULL ELSE {norm_host_sql('host')} END AS nhost
            FROM jsonb_to_recordset(%s::jsonb) AS n(node_id TEXT,node_type TEXT,path TEXT,host TEXT,event_name TEXT)
        )"""


def node_match_condition(event_name='e.event_name'):
    """Join condition of an event `e` with a row `n` of configured_nodes, as match_flow_node decides.

    ``event_name`` is the SQL for the event's custom name (older databases have no event_name column).
    Order the matches by ``(n.node_type='page')`` so a conversion or error rule outranks a generic page.
    """
    page_like = "e.event_kind IN ('page_view','conversion','error_view','page_leave')"
    return f"""n.npath={_norm_path('e.page_path')}
                AND (n.nhost IS NULL OR n.nhost={norm_host_sql('e.page_host')})
                AND ((n.node_type='page' AND {page_like})
                  OR (n.node_type IN ('conversion','error') AND n.event_name='' AND {page_like}
                      AND (n.node_type='conversion' OR e.event_kind<>'conversion'))
                  OR (n.node_type='conversion' AND e.event_kind='conversion' AND n.event_name=COALESCE({event_name},''))
                  OR (n.node_type='form' AND e.event_kind='form_submit')
                  OR (n.node_type='whatsapp' AND e.event_kind='whatsapp_click')
                  OR (n.node_type='event' AND e.event_kind='custom_event' AND (n.event_name='' OR n.event_name={event_name})))"""


def matched_events_cte(where, columns):
    """`WITH configured_nodes, scoped, matches, mapped`: every scoped event with the node it matches, or NULL.

    Parameters, in order: the node json, then the ones `where` uses. `where` filters
    cadu_reports_flow_events e, with c (campaign) and a (account) joined for the report filters.
    """
    return f"""WITH {CONFIGURED_NODES_SQL}, scoped AS (
            SELECT {columns} FROM cadu_reports_flow_events e
            LEFT JOIN cadu_reports_campaigns c ON c.id=e.campaign_id AND c.client_id=e.client_id
            LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id AND a.client_id=e.client_id
            WHERE {where}
        ), matches AS (
            SELECT DISTINCT ON (e.id) e.id,n.node_id FROM scoped e
            JOIN configured_nodes n ON {node_match_condition()}
            ORDER BY e.id,(n.node_type='page')
        ), mapped AS (
            SELECT e.*,m.node_id FROM scoped e LEFT JOIN matches m USING (id)
        )"""


def publications_in_period(rows, current_revision):
    """Which publications the period's events came from, newest first."""
    items = [{'revision': int(row['flow_revision']), 'events': int(row['events']),
              'first_event_at': row['first_event_at'].isoformat() if row.get('first_event_at') else None,
              'last_event_at': row['last_event_at'].isoformat() if row.get('last_event_at') else None,
              'current': int(row['flow_revision']) == current_revision}
             for row in rows if row.get('flow_revision') is not None]
    return sorted(items, key=lambda item: item['revision'], reverse=True)
