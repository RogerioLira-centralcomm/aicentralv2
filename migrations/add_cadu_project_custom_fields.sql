ALTER TABLE cadu_ci_projetos
    ADD COLUMN IF NOT EXISTS campos_personalizados JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE cadu_ci_projetos
    ADD COLUMN IF NOT EXISTS context_revision INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS cadu_project_context_revisions (
    id UUID PRIMARY KEY,
    client_id INTEGER NOT NULL,
    project_id VARCHAR(64) NOT NULL,
    revision INTEGER NOT NULL,
    actor_id INTEGER NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'workspace',
    changed_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    before_context JSONB NOT NULL,
    after_context JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, project_id, revision)
);

CREATE INDEX IF NOT EXISTS idx_cadu_project_context_revisions_project
    ON cadu_project_context_revisions (client_id, project_id, revision DESC);

COMMENT ON COLUMN cadu_ci_projetos.campos_personalizados IS
    'Campos de contexto variáveis por projeto, armazenados como {chave: {label, value}}.';
