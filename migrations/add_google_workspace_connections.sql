-- Individual Google Workspace authorizations per Cadu client and person.
-- OAuth secrets are encrypted by the application and never exposed to the UI.

ALTER TABLE system_integration_credentials
    DROP CONSTRAINT IF EXISTS system_integration_credentials_provider_check;

ALTER TABLE system_integration_credentials
    ADD CONSTRAINT system_integration_credentials_provider_check
    CHECK (provider IN (
        'google_login_cadu', 'google_login_centralx', 'google_workspace',
        'google_calendar', 'higgsfield', 'openrouter', 'openai', 'firecrawl',
        'brevo', 'd4sign', 'dify'
    ));

INSERT INTO system_integration_credentials (provider, public_config, status)
VALUES (
    'google_workspace',
    '{"redirect_uri":"https://auth.centralcomm.media/auth/google/workspace/callback"}'::jsonb,
    'active'
)
ON CONFLICT (provider) DO NOTHING;

CREATE TABLE IF NOT EXISTS google_workspace_connections (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    google_sub VARCHAR(255) NOT NULL,
    google_email VARCHAR(320) NOT NULL,
    google_domain VARCHAR(255),
    encrypted_refresh_token TEXT NOT NULL,
    granted_scopes TEXT NOT NULL DEFAULT '',
    status VARCHAR(24) NOT NULL DEFAULT 'connected'
        CHECK (status IN ('connected', 'needs_reauthorization', 'error', 'revoked')),
    last_sync_at TIMESTAMPTZ,
    last_error TEXT,
    created_by BIGINT REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (client_id > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_google_workspace_connections_client_authorizer
    ON google_workspace_connections (client_id, created_by)
    WHERE created_by IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_google_workspace_connections_email
    ON google_workspace_connections (LOWER(google_email));

CREATE TABLE IF NOT EXISTS google_workspace_resources (
    id UUID PRIMARY KEY,
    connection_id UUID NOT NULL REFERENCES google_workspace_connections(id) ON DELETE CASCADE,
    provider VARCHAR(40) NOT NULL,
    external_id VARCHAR(1024) NOT NULL,
    name VARCHAR(500) NOT NULL,
    mime_type VARCHAR(255),
    external_url TEXT,
    parent_external_id VARCHAR(1024),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(24) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived', 'error')),
    source_created_at TIMESTAMPTZ,
    source_updated_at TIMESTAMPTZ,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (connection_id, provider, external_id)
);

CREATE INDEX IF NOT EXISTS idx_google_workspace_resources_connection
    ON google_workspace_resources (connection_id, provider, status, source_updated_at DESC);

CREATE TABLE IF NOT EXISTS google_workspace_resource_links (
    id UUID PRIMARY KEY,
    resource_id UUID NOT NULL REFERENCES google_workspace_resources(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    project_ref TEXT NOT NULL,
    linked_by BIGINT REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE SET NULL,
    purpose VARCHAR(40) NOT NULL DEFAULT 'project_knowledge'
        CHECK (purpose IN ('project_knowledge', 'project_attachment', 'reference')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (resource_id, project_ref)
);

CREATE INDEX IF NOT EXISTS idx_google_workspace_resource_links_project
    ON google_workspace_resource_links (client_id, project_ref, created_at DESC);
