-- Keep old connections fully capable; new OAuth/key connections choose their
-- enabled tool modules at authorization or key creation time.
ALTER TABLE cadu_public_mcp_keys
    ADD COLUMN IF NOT EXISTS modules JSONB NOT NULL DEFAULT
    '["marketing","projects","library","media","brands","google","artifacts","account","reports"]'::jsonb;

ALTER TABLE cadu_oauth_grants
    ADD COLUMN IF NOT EXISTS modules JSONB NOT NULL DEFAULT
    '["marketing","projects","library","media","brands","google","artifacts","account","reports"]'::jsonb;

UPDATE cadu_public_mcp_keys
   SET modules='["marketing","projects","library","media","brands","google","artifacts","account","reports"]'::jsonb
 WHERE modules IS NULL OR jsonb_typeof(modules) <> 'array';

UPDATE cadu_oauth_grants
   SET modules='["marketing","projects","library","media","brands","google","artifacts","account","reports"]'::jsonb
 WHERE modules IS NULL OR jsonb_typeof(modules) <> 'array';
