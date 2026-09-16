"""Contas, relatórios e vínculos de campanhas usados pelo produto Agentes."""
from typing import Optional


def _db():
    from ..db import get_db
    return get_db()


def accounts_for_workspace_context(organization_id: int, *, workspace_client_id: int,
                                   workspace_project_ref: Optional[str] = None) -> list[dict]:
    try:
        with _db().cursor() as cursor:
            cursor.execute(
                """SELECT DISTINCT a.id, a.organization_id, a.provider,
                          a.external_account_id, a.name, a.status,
                          a.credential_provider, a.last_synced_at
                     FROM cadu_connect_accounts a
                LEFT JOIN cadu_connect_account_scopes scope ON scope.account_id = a.id
                    WHERE a.organization_id = %s
                      AND scope.workspace_client_id = %s
                      AND (%s IS NULL OR scope.workspace_project_ref = %s)
                 ORDER BY a.provider, a.name""",
                (organization_id, workspace_client_id, workspace_project_ref, workspace_project_ref),
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        # A instalação sem a migration continua navegável até o deploy do schema.
        return []


def files_for_workspace_context(client_id: int) -> list[dict]:
    """Read the existing Workspace, brand and Studio file indexes in one view."""
    if not client_id:
        return []
    try:
        with _db().cursor() as cursor:
            cursor.execute("""SELECT name, kind, created_at, 'workspace' AS source
                                FROM cadu_family_chat_uploads WHERE client_id = %s
                               ORDER BY created_at DESC LIMIT 30""", (client_id,))
            files = [dict(row) for row in cursor.fetchall()]
            cursor.execute("""SELECT filename AS name, role AS kind, created_at, 'marca' AS source
                                FROM cx_client_brand_assets
                               WHERE client_id = %s AND status = 'approved'
                               ORDER BY created_at DESC LIMIT 30""", (client_id,))
            files.extend(dict(row) for row in cursor.fetchall())
            cursor.execute("""SELECT COALESCE(filename, 'Criativo gerado') AS name,
                                     COALESCE(media_type, 'creative') AS kind,
                                     created_at, 'studio' AS source
                                FROM cx_generated_assets WHERE client_id = %s
                               ORDER BY created_at DESC LIMIT 30""", (client_id,))
            files.extend(dict(row) for row in cursor.fetchall())
    except Exception:
        return []
    return sorted(files, key=lambda item: item.get("created_at") or "", reverse=True)[:60]


def create_account(*, organization_id: int, provider: str,
                   external_account_id: str, name: str, credential_provider: Optional[str],
                   user_id: int) -> dict:
    conn = _db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO cadu_connect_accounts
                    (organization_id, provider, external_account_id, name,
                     credential_provider, created_by, updated_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                 RETURNING id, organization_id, provider, external_account_id,
                           name, status, credential_provider, last_synced_at""",
                (organization_id, provider, external_account_id, name,
                 credential_provider, user_id, user_id),
            )
            row = cursor.fetchone()
        conn.commit()
        return dict(row)
    except Exception:
        conn.rollback()
        raise


def add_account_scope(*, account_id: int, organization_id: int, workspace_client_id: int,
                      workspace_project_ref: Optional[str] = None,
                      workspace_brand_ref: Optional[str] = None, user_id: int) -> dict:
    """Attach an account to a validated Workspace client/project/brand context."""
    conn = _db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM cadu_connect_accounts WHERE id = %s AND organization_id = %s", (account_id, organization_id))
            if not cursor.fetchone():
                raise ValueError("Conta não encontrada nesta organização.")
            cursor.execute(
                """INSERT INTO cadu_connect_account_scopes
                    (account_id, workspace_client_id, workspace_project_ref, workspace_brand_ref, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                 RETURNING id, account_id, workspace_client_id, workspace_project_ref, workspace_brand_ref""",
                (account_id, workspace_client_id, workspace_project_ref, workspace_brand_ref, user_id),
            )
            row = cursor.fetchone()
        conn.commit()
        return dict(row)
    except Exception:
        conn.rollback()
        raise


def campaigns_for_client(client_id: int, *, project_id: Optional[int] = None) -> list[dict]:
    try:
        with _db().cursor() as cursor:
            cursor.execute(
                """SELECT c.id_campanha, c.id_cliente, c.nome_campanha, c.link_dash,
                          c.periodo_inicio, c.periodo_fim, c.mes_ref_comp,
                          st.descricao AS status_name, plt.descricao AS platform_name,
                          link.project_id, p.nome AS project_name
                     FROM cadu_pi_campanha c
                LEFT JOIN cadu_pi_camp_status st ON st.id = c.id_status
                LEFT JOIN cadu_pi_camp_plataforma plt ON plt.id_plataforma = c.id_plataforma
                LEFT JOIN cadu_agent_campaign_projects link ON link.campaign_id = c.id_campanha
                LEFT JOIN cadu_projetos p ON p.id = link.project_id
                    WHERE c.id_cliente = %s
                      AND (%s IS NULL OR link.project_id = %s)
                 ORDER BY COALESCE(c.updated_at, c.created_at) DESC, c.id_campanha DESC
                    LIMIT 50""",
                (client_id, project_id, project_id),
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []


def portfolio_for_clients(clients: list[dict]) -> list[dict]:
    """Return a compact operational health row for each permitted client.

    The portfolio deliberately carries no media performance figures: Connect is
    used first to resolve access, freshness and missing report coverage.
    """
    client_ids = [int(client["id"]) for client in clients if client.get("id")]
    if not client_ids:
        return []
    try:
        with _db().cursor() as cursor:
            cursor.execute(
                """SELECT id_cliente,
                          COUNT(*) AS campaign_count,
                          COUNT(*) FILTER (WHERE COALESCE(link_dash, '') <> '') AS report_count
                     FROM cadu_pi_campanha
                    WHERE id_cliente = ANY(%s)
                 GROUP BY id_cliente""",
                (client_ids,),
            )
            health = {int(row["id_cliente"]): dict(row) for row in cursor.fetchall()}
    except Exception:
        health = {}
    return [
        {
            **client,
            "campaign_count": int(health.get(int(client["id"]), {}).get("campaign_count") or 0),
            "report_count": int(health.get(int(client["id"]), {}).get("report_count") or 0),
        }
        for client in clients
    ]


def link_campaign_project(campaign_id: int, *, client_id: int, project_id=None, user_id: int) -> bool:
    conn = _db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM cadu_pi_campanha WHERE id_campanha = %s AND id_cliente = %s", (campaign_id, client_id))
            if not cursor.fetchone():
                return False
            if project_id:
                cursor.execute("SELECT 1 FROM cadu_projetos WHERE id = %s AND id_cliente = %s", (project_id, client_id))
                if not cursor.fetchone():
                    raise ValueError("O projeto selecionado não pertence ao cliente da campanha.")
            cursor.execute(
                """INSERT INTO cadu_agent_campaign_projects (campaign_id, client_id, project_id, updated_by)
                     VALUES (%s, %s, %s, %s)
                     ON CONFLICT (campaign_id) DO UPDATE SET project_id = EXCLUDED.project_id,
                         client_id = EXCLUDED.client_id, updated_by = EXCLUDED.updated_by, updated_at = NOW()""",
                (campaign_id, client_id, project_id, user_id),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
