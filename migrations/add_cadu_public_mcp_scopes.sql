ALTER TABLE cadu_public_mcp_keys
    ADD COLUMN IF NOT EXISTS scopes JSONB NOT NULL
        DEFAULT '["resources:read","projects:read","google:read"]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_cadu_public_mcp_keys_scopes
    ON cadu_public_mcp_keys USING GIN (scopes);
