CREATE TABLE IF NOT EXISTS cadu_project_tasks (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente),
    project_ref TEXT NOT NULL,
    title VARCHAR(180) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status VARCHAR(24) NOT NULL DEFAULT 'todo' CHECK (status IN ('todo','in_progress','blocked','done')),
    priority VARCHAR(16) NOT NULL DEFAULT 'normal' CHECK (priority IN ('low','normal','high')),
    starts_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    assignee_id BIGINT REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    source_provider VARCHAR(64) NOT NULL DEFAULT 'cadu',
    external_url TEXT,
    external_id VARCHAR(512),
    created_by BIGINT REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ,
    CHECK (organization_id = client_id)
);

CREATE INDEX IF NOT EXISTS idx_cadu_project_tasks_project
    ON cadu_project_tasks (organization_id, client_id, project_ref, status, due_at) WHERE archived_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_cadu_project_tasks_external
    ON cadu_project_tasks (client_id, project_ref, source_provider, external_id)
    WHERE external_id IS NOT NULL AND archived_at IS NULL;
