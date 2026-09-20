-- Public Cadu MCP beta: personal bearer keys and a metered request trail.
-- The key itself is never persisted; only a SHA-256 digest is stored.

CREATE TABLE IF NOT EXISTS cadu_public_mcp_keys (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    client_type VARCHAR(24) NOT NULL CHECK (client_type IN ('gpt','codex','cursor','vscode','generic')),
    label VARCHAR(120) NOT NULL,
    default_project_ref TEXT,
    key_prefix VARCHAR(32) NOT NULL UNIQUE,
    key_hash CHAR(64) NOT NULL UNIQUE,
    status VARCHAR(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cadu_public_mcp_keys_scope
    ON cadu_public_mcp_keys (client_id, user_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_public_mcp_usage (
    id BIGSERIAL PRIMARY KEY,
    key_id UUID NOT NULL REFERENCES cadu_public_mcp_keys(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    client_type VARCHAR(24) NOT NULL,
    method VARCHAR(40) NOT NULL,
    tool_name VARCHAR(120) NOT NULL DEFAULT '',
    request_id VARCHAR(160) NOT NULL DEFAULT '',
    status VARCHAR(24) NOT NULL CHECK (status IN ('started','completed','failed')),
    credit_cost BIGINT NOT NULL DEFAULT 0 CHECK (credit_cost >= 0),
    duration_ms BIGINT NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
    input_bytes BIGINT NOT NULL DEFAULT 0 CHECK (input_bytes >= 0),
    output_bytes BIGINT NOT NULL DEFAULT 0 CHECK (output_bytes >= 0),
    error_code VARCHAR(120),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (key_id, request_id, method, tool_name)
);

CREATE INDEX IF NOT EXISTS idx_cadu_public_mcp_usage_scope
    ON cadu_public_mcp_usage (client_id, user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cadu_public_mcp_usage_tool
    ON cadu_public_mcp_usage (tool_name, created_at DESC);
