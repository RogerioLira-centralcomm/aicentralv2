-- Contexto de projeto usado pelos agentes. A campanha e o projeto continuam
-- pertencendo ao Cadu PHP; esta tabela guarda somente o vínculo operacional.
CREATE TABLE IF NOT EXISTS cadu_agent_campaign_projects (
    campaign_id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL,
    project_id INTEGER,
    updated_by INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cadu_agent_campaign_projects_client_project
    ON cadu_agent_campaign_projects (client_id, project_id);

COMMENT ON TABLE cadu_agent_campaign_projects IS
    'Relaciona campanhas do Cadu a projetos do mesmo client_id para contexto de agentes e relatórios.';
