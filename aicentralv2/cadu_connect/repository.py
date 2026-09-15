"""Contas, relatórios e vínculos de campanhas usados pelo produto Agentes."""
from typing import Optional


def _db():
    from ..db import get_db
    return get_db()


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
