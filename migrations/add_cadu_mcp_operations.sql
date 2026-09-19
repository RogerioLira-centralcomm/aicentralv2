-- Durable, tenant-scoped idempotency receipts for MCP commands.
CREATE TABLE IF NOT EXISTS cadu_mcp_operations (
    request_id UUID NOT NULL,
    client_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    tool_name VARCHAR(120) NOT NULL,
    input_hash CHAR(64) NOT NULL,
    status VARCHAR(24) NOT NULL,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_code VARCHAR(80),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (request_id, client_id, user_id, tool_name),
    CHECK (status IN ('running','completed','failed'))
);

CREATE INDEX IF NOT EXISTS idx_cadu_mcp_operations_scope
    ON cadu_mcp_operations (client_id, user_id, updated_at DESC);
