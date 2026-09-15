-- Contas publicitárias e fontes de relatórios no escopo de cada cliente.
-- Credenciais OAuth/API permanecem no cofre de integrações; esta tabela não
-- armazena segredos e apenas descreve onde cada conta pode ser utilizada.
CREATE TABLE IF NOT EXISTS cadu_connect_accounts (
    id BIGSERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL,
    provider VARCHAR(64) NOT NULL,
    external_account_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    credential_provider VARCHAR(64),
    last_synced_at TIMESTAMPTZ,
    created_by INTEGER,
    updated_by INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_connect_accounts_status_check
        CHECK (status IN ('active', 'pending', 'error', 'disabled')),
    CONSTRAINT cadu_connect_accounts_organization_provider_external_key
        UNIQUE (organization_id, provider, external_account_id)
);

CREATE INDEX IF NOT EXISTS idx_cadu_connect_accounts_organization
    ON cadu_connect_accounts (organization_id, status);

CREATE TABLE IF NOT EXISTS cadu_connect_account_scopes (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES cadu_connect_accounts(id) ON DELETE CASCADE,
    workspace_client_id INTEGER NOT NULL,
    workspace_project_ref TEXT,
    workspace_brand_ref TEXT,
    created_by INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_connect_account_scopes_project_ref_check
        CHECK (workspace_project_ref IS NULL OR workspace_project_ref LIKE '%:%'),
    CONSTRAINT cadu_connect_account_scopes_brand_ref_check
        CHECK (workspace_brand_ref IS NULL OR workspace_brand_ref LIKE '%:%')
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cadu_connect_account_scope_unique
    ON cadu_connect_account_scopes (account_id, workspace_client_id,
        COALESCE(workspace_project_ref, ''), COALESCE(workspace_brand_ref, ''));
CREATE INDEX IF NOT EXISTS idx_cadu_connect_account_scopes_workspace
    ON cadu_connect_account_scopes (workspace_client_id, workspace_project_ref);

CREATE TABLE IF NOT EXISTS cadu_connect_reports (
    id BIGSERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL,
    account_id BIGINT REFERENCES cadu_connect_accounts(id) ON DELETE SET NULL,
    scope_id BIGINT REFERENCES cadu_connect_account_scopes(id) ON DELETE SET NULL,
    source_kind VARCHAR(32) NOT NULL,
    provider VARCHAR(64),
    name VARCHAR(255) NOT NULL,
    period_start DATE,
    period_end DATE,
    source_url TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'ready',
    imported_by INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_connect_reports_source_kind_check
        CHECK (source_kind IN ('mcp', 'import', 'link')),
    CONSTRAINT cadu_connect_reports_status_check
        CHECK (status IN ('ready', 'processing', 'error', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_cadu_connect_reports_organization
    ON cadu_connect_reports (organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_connect_reports_account
    ON cadu_connect_reports (account_id, created_at DESC);

COMMENT ON TABLE cadu_connect_accounts IS
    'Contas de anúncio da organização; credenciais ficam no cofre de integrações.';
COMMENT ON TABLE cadu_connect_account_scopes IS
    'Vínculos muitos-para-muitos da conta com contextos do Workspace: cliente, projeto e marca.';
COMMENT ON TABLE cadu_connect_reports IS
    'Relatórios MCP, arquivos importados ou links vinculados à organização e a um escopo opcional.';
