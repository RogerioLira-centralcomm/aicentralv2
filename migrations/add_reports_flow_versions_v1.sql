-- Apply before deploying the continuous-editing Flow API. Keep config as live
-- configuration: existing collectors and availability workers read it unchanged.
BEGIN;
ALTER TABLE cadu_reports_flow_registry
    ADD COLUMN IF NOT EXISTS draft_config JSONB,
    ADD COLUMN IF NOT EXISTS draft_revision BIGINT NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS published_revision BIGINT;
UPDATE cadu_reports_flow_registry SET draft_config=config WHERE draft_config IS NULL;
ALTER TABLE cadu_reports_flow_registry ALTER COLUMN draft_config SET DEFAULT '{}'::jsonb;
ALTER TABLE cadu_reports_flow_registry ALTER COLUMN draft_config SET NOT NULL;
CREATE TABLE IF NOT EXISTS cadu_reports_flow_versions (
    flow_id UUID NOT NULL,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    revision BIGINT NOT NULL,
    name VARCHAR(120) NOT NULL,
    config JSONB NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(flow_id,revision),
    FOREIGN KEY(flow_id,organization_id,client_id)
        REFERENCES cadu_reports_flow_registry(id,organization_id,client_id)
);
INSERT INTO cadu_reports_flow_versions(flow_id,organization_id,client_id,revision,name,config,created_by,created_at)
SELECT id,organization_id,client_id,draft_revision,name,config,created_by,COALESCE(published_at,updated_at)
FROM cadu_reports_flow_registry WHERE status='published'
ON CONFLICT(flow_id,revision) DO NOTHING;
UPDATE cadu_reports_flow_registry SET published_revision=draft_revision
WHERE status='published' AND published_revision IS NULL;
COMMIT;
