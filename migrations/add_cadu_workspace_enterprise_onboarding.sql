-- Onboarding inicial do Cadu Workspace para clientes finais e agências.
-- O id_cliente é sempre o client_id já presente na sessão. Nenhum cliente
-- CRM novo é criado por este fluxo.

CREATE TABLE IF NOT EXISTS cadu_workspace_onboarding (
    id BIGSERIAL PRIMARY KEY,
    contato_id BIGINT NOT NULL
        REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    id_cliente BIGINT NOT NULL
        REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    operation_type VARCHAR(20) NOT NULL
        CHECK (operation_type IN ('client', 'agency')),
    organization_name VARCHAR(180) NOT NULL,
    client_name VARCHAR(180),
    brand_id INTEGER REFERENCES cx_clients(id) ON DELETE SET NULL,
    project_id UUID REFERENCES cadu_ci_projetos(id) ON DELETE SET NULL,
    current_step VARCHAR(32) NOT NULL DEFAULT 'context',
    status VARCHAR(24) NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'audit_pending', 'completed')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT uq_cadu_workspace_onboarding_contact_client
        UNIQUE (contato_id, id_cliente)
);

CREATE INDEX IF NOT EXISTS idx_cadu_workspace_onboarding_client
    ON cadu_workspace_onboarding (id_cliente, updated_at DESC);

