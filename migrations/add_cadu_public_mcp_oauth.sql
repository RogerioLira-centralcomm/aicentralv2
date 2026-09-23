-- OAuth 2.1 authorization layer for the public Cadu MCP.
-- All codes and tokens are opaque; only SHA-256 digests are persisted.

CREATE TABLE IF NOT EXISTS cadu_oauth_clients (
    id UUID PRIMARY KEY,
    oauth_client_id TEXT NOT NULL UNIQUE,
    client_name VARCHAR(120) NOT NULL,
    client_uri TEXT,
    logo_uri TEXT,
    redirect_uris JSONB NOT NULL,
    grant_types JSONB NOT NULL DEFAULT '["authorization_code","refresh_token"]'::jsonb,
    response_types JSONB NOT NULL DEFAULT '["code"]'::jsonb,
    token_endpoint_auth_method VARCHAR(32) NOT NULL DEFAULT 'none'
        CHECK (token_endpoint_auth_method IN ('none')),
    metadata_document_uri TEXT,
    registration_ip INET,
    status VARCHAR(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
    client_id_issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE cadu_oauth_clients ADD COLUMN IF NOT EXISTS registration_ip INET;
CREATE INDEX IF NOT EXISTS idx_cadu_oauth_clients_registration_rate
    ON cadu_oauth_clients (registration_ip, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_oauth_grants (
    id UUID PRIMARY KEY,
    oauth_client_id UUID NOT NULL REFERENCES cadu_oauth_clients(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    default_project_ref TEXT,
    scopes JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','active','reauth_required','revoked')),
    consented_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cadu_oauth_grants_owner
    ON cadu_oauth_grants (client_id, user_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_oauth_authorization_codes (
    id UUID PRIMARY KEY,
    code_hash CHAR(64) NOT NULL UNIQUE,
    grant_id UUID NOT NULL REFERENCES cadu_oauth_grants(id) ON DELETE CASCADE,
    oauth_client_id UUID NOT NULL REFERENCES cadu_oauth_clients(id) ON DELETE CASCADE,
    redirect_uri TEXT NOT NULL,
    resource TEXT NOT NULL,
    scopes JSONB NOT NULL,
    code_challenge TEXT NOT NULL,
    code_challenge_method VARCHAR(8) NOT NULL CHECK (code_challenge_method='S256'),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cadu_oauth_access_tokens (
    id UUID PRIMARY KEY,
    token_hash CHAR(64) NOT NULL UNIQUE,
    grant_id UUID NOT NULL REFERENCES cadu_oauth_grants(id) ON DELETE CASCADE,
    oauth_client_id UUID NOT NULL REFERENCES cadu_oauth_clients(id) ON DELETE CASCADE,
    resource TEXT NOT NULL,
    scopes JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cadu_oauth_access_token_grant
    ON cadu_oauth_access_tokens (grant_id, expires_at DESC);

CREATE TABLE IF NOT EXISTS cadu_oauth_refresh_tokens (
    id UUID PRIMARY KEY,
    token_hash CHAR(64) NOT NULL UNIQUE,
    grant_id UUID NOT NULL REFERENCES cadu_oauth_grants(id) ON DELETE CASCADE,
    oauth_client_id UUID NOT NULL REFERENCES cadu_oauth_clients(id) ON DELETE CASCADE,
    family_id UUID NOT NULL,
    resource TEXT NOT NULL,
    scopes JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    rotated_at TIMESTAMPTZ,
    reuse_detected_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cadu_oauth_refresh_family
    ON cadu_oauth_refresh_tokens (family_id, created_at DESC);

ALTER TABLE cadu_public_mcp_usage ALTER COLUMN key_id DROP NOT NULL;
ALTER TABLE cadu_public_mcp_usage
    ADD COLUMN IF NOT EXISTS credential_type VARCHAR(16) NOT NULL DEFAULT 'api_key'
        CHECK (credential_type IN ('api_key','oauth'));
ALTER TABLE cadu_public_mcp_usage
    ADD COLUMN IF NOT EXISTS credential_id UUID;
UPDATE cadu_public_mcp_usage SET credential_id=key_id WHERE credential_id IS NULL;

ALTER TABLE cadu_public_mcp_usage
    DROP CONSTRAINT IF EXISTS cadu_public_mcp_usage_key_id_request_id_method_tool_name_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_cadu_public_mcp_usage_credential_request
    ON cadu_public_mcp_usage (credential_type, credential_id, request_id, method, tool_name);
