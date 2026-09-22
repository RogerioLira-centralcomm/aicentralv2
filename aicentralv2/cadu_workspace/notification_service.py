"""Durable Workspace notification inbox with safe rollout fallback."""
from __future__ import annotations

from uuid import UUID
import json

from aicentralv2.db import get_db


def _available(cursor) -> bool:
    cursor.execute("SELECT to_regclass('public.cadu_workspace_notifications') IS NOT NULL AS available")
    return bool(cursor.fetchone()['available'])


def list_notifications(client_id: int, user_id: int, *, project_ref: str | None = None, limit: int = 60) -> dict:
    try:
        with get_db().cursor() as cursor:
            if not _available(cursor):
                return {'available': False, 'items': [], 'unread': 0}
            params = [client_id, user_id]
            project_clause = ''
            if project_ref:
                project_clause = ' AND (project_ref = %s OR project_ref IS NULL)'
                params.append(project_ref)
            params.append(max(1, min(int(limit), 100)))
            cursor.execute(
                f"""SELECT id::text, project_ref, brand_ref, conversation_id, run_id::text,
                           long_job_id::text, source_id, notification_type, status, title, detail,
                           action_payload, created_at, updated_at, read_at
                      FROM cadu_workspace_notifications
                     WHERE client_id = %s AND user_id = %s AND archived_at IS NULL
                           {project_clause}
                  ORDER BY CASE WHEN status = 'waiting_user' THEN 0 WHEN status = 'failed' THEN 1 ELSE 2 END,
                           created_at DESC LIMIT %s""",
                tuple(params),
            )
            items = [dict(row) for row in cursor.fetchall()]
            if not project_ref:
                cursor.execute("SELECT to_regclass('public.cadu_workspace_brand_audit_runs') IS NOT NULL AS available")
                if bool(cursor.fetchone()['available']):
                    cursor.execute(
                        """SELECT r.job_id, r.brand_id, r.analysis_mode, r.status, r.sources,
                                  r.collected_data, r.costs, r.human_effort, r.created_at,
                                  r.updated_at, r.completed_at, b.name AS brand_name
                             FROM cadu_workspace_brand_audit_runs r
                        LEFT JOIN cx_clients b ON b.id = r.brand_id AND b.crm_client_id = r.client_id
                            WHERE r.client_id = %s
                         ORDER BY r.created_at DESC LIMIT 30""",
                        (client_id,),
                    )
                    for row in cursor.fetchall():
                        audit = dict(row)
                        for key in ('sources', 'collected_data', 'costs', 'human_effort'):
                            if isinstance(audit.get(key), str):
                                try:
                                    audit[key] = json.loads(audit[key])
                                except (TypeError, ValueError):
                                    audit[key] = [] if key == 'sources' else {}
                        status = str(audit.get('status') or 'queued')
                        complete = status in {'pending_approval', 'approved'}
                        failed = status in {'failed', 'insufficient_evidence'}
                        collected = audit.get('collected_data') or {}
                        costs = audit.get('costs') or {}
                        effort = audit.get('human_effort') or {}
                        fields = collected.get('fields') or []
                        action = {
                            'brand_id': audit.get('brand_id'),
                            'analysis_mode': audit.get('analysis_mode'),
                            'pages_analyzed': collected.get('pages_analyzed') or 0,
                            'assets_found': collected.get('assets_found') or 0,
                            'fields_generated': len(fields),
                            'sources_count': len(audit.get('sources') or []),
                            'estimated_hours_saved': effort.get('estimated_person_hours') or 0,
                            'cost_brl': costs.get('actual_cost_brl') or costs.get('estimated_cost_brl'),
                        }
                        if complete:
                            detail = 'A base da marca foi consolidada e está pronta para revisão.'
                        elif failed:
                            detail = str(collected.get('error') or 'A análise precisa de ajustes antes de continuar.')
                        elif status == 'running':
                            detail = 'Pesquisa, leitura de fontes e consolidação estão em andamento.'
                        else:
                            detail = 'A análise entrou na fila e começará em instantes.'
                        items.append({
                            'id': f"brand-audit:{audit.get('job_id')}",
                            'brand_ref': str(audit.get('brand_id') or ''),
                            'notification_type': 'failure' if failed else ('approval' if status == 'pending_approval' else ('complete' if complete else 'progress')),
                            'status': 'failed' if failed else ('waiting_user' if status == 'pending_approval' else ('completed' if complete else 'processing')),
                            'title': f"Análise de {audit.get('brand_name') or 'marca'}",
                            'detail': detail,
                            'action_payload': action,
                            'created_at': audit.get('created_at'),
                            'updated_at': audit.get('updated_at'),
                            'read_at': None,
                        })
                cursor.execute("SELECT to_regclass('public.cadu_workspace_ingestion_sessions') IS NOT NULL AS available")
                if bool(cursor.fetchone()['available']):
                    cursor.execute(
                        """SELECT s.id::text, s.project_ref, s.conversation_id, s.status,
                                  s.origin, s.created_at, s.updated_at, s.completed_at,
                                  COUNT(i.id)::int AS item_count,
                                  COUNT(i.id) FILTER (WHERE i.extraction_status = 'completed')::int AS processed_count,
                                  COUNT(i.id) FILTER (WHERE i.extraction_status = 'failed')::int AS failed_count,
                                  COALESCE(array_agg(i.original_name ORDER BY i.created_at)
                                           FILTER (WHERE i.original_name IS NOT NULL), ARRAY[]::text[]) AS names
                             FROM cadu_workspace_ingestion_sessions s
                        LEFT JOIN cadu_workspace_ingestion_items i ON i.session_id = s.id
                            WHERE s.client_id = %s AND s.user_id = %s
                         GROUP BY s.id
                         ORDER BY s.created_at DESC LIMIT 30""",
                        (client_id, user_id),
                    )
                    for row in cursor.fetchall():
                        ingestion = dict(row)
                        status = str(ingestion.get('status') or 'processing')
                        failed = status == 'failed' or int(ingestion.get('failed_count') or 0) > 0
                        complete = status == 'completed'
                        names = list(ingestion.get('names') or [])
                        count = int(ingestion.get('item_count') or 0)
                        if complete:
                            detail = f"{count} arquivo{'s' if count != 1 else ''} {'disponíveis' if count != 1 else 'disponível'} para uso no Workspace."
                        elif failed:
                            detail = 'Um ou mais arquivos precisam ser enviados ou processados novamente.'
                        else:
                            detail = f"Processando {count} arquivo{'s' if count != 1 else ''} e preparando o conteúdo para consulta."
                        items.append({
                            'id': f"ingestion:{ingestion.get('id')}",
                            'project_ref': ingestion.get('project_ref'),
                            'conversation_id': ingestion.get('conversation_id'),
                            'notification_type': 'failure' if failed else ('complete' if complete else 'progress'),
                            'status': 'failed' if failed else ('completed' if complete else 'processing'),
                            'title': names[0] if len(names) == 1 else (f"{count} arquivos adicionados" if count else 'Preparando arquivos'),
                            'detail': detail,
                            'action_payload': {
                                'item_count': count,
                                'processed_count': int(ingestion.get('processed_count') or 0),
                                'failed_count': int(ingestion.get('failed_count') or 0),
                                'origin': ingestion.get('origin'),
                            },
                            'created_at': ingestion.get('created_at'),
                            'updated_at': ingestion.get('updated_at'),
                            'read_at': None,
                        })
            items.sort(key=lambda item: item.get('updated_at') or item.get('created_at'), reverse=True)
            items = items[:max(1, min(int(limit), 100))]
            return {'available': True, 'items': items,
                    'unread': sum(1 for item in items if item.get('status') in {'unread', 'waiting_user', 'failed'})}
    except Exception:
        return {'available': False, 'items': [], 'unread': 0}


def update_notification(client_id: int, user_id: int, notification_id: str, action: str) -> bool:
    UUID(str(notification_id))
    assignments = {
        'read': "status = CASE WHEN status = 'unread' THEN 'read' ELSE status END, read_at = COALESCE(read_at, NOW())",
        'resolve': "status = 'resolved', resolved_at = NOW(), read_at = COALESCE(read_at, NOW())",
        'archive': "status = 'archived', archived_at = NOW(), read_at = COALESCE(read_at, NOW())",
    }
    if action not in assignments:
        raise ValueError('Ação de notificação inválida.')
    connection = get_db()
    with connection.cursor() as cursor:
        if not _available(cursor):
            return False
        cursor.execute(
            f"""UPDATE cadu_workspace_notifications SET {assignments[action]}, updated_at = NOW()
                  WHERE id = %s AND client_id = %s AND user_id = %s AND archived_at IS NULL""",
            (notification_id, client_id, user_id),
        )
        changed = cursor.rowcount > 0
    connection.commit()
    return changed
