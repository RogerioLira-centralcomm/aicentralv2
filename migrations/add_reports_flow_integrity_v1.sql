-- Run after add_reports_flow_versions_v1.sql, before deploying the new collectors.
BEGIN;
ALTER TABLE cadu_reports_flow_steps ADD COLUMN IF NOT EXISTS node_id TEXT,
    ADD COLUMN IF NOT EXISTS flow_revision BIGINT;
CREATE UNIQUE INDEX IF NOT EXISTS reports_flow_step_version_node
    ON cadu_reports_flow_steps(tag_id,flow_revision,node_id);
ALTER TABLE cadu_reports_flow_events ADD COLUMN IF NOT EXISTS flow_revision BIGINT;
-- Legacy events intentionally retain NULL: their original graph cannot be proved.
CREATE INDEX IF NOT EXISTS reports_flow_event_revision
    ON cadu_reports_flow_events(organization_id,client_id,tag_id,flow_revision,occurred_at);
CREATE TABLE IF NOT EXISTS cadu_reports_flow_sessions (
    flow_id UUID NOT NULL, organization_id BIGINT NOT NULL, client_id BIGINT NOT NULL,
    session_id UUID NOT NULL, revision BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(flow_id,session_id),
    FOREIGN KEY(flow_id,organization_id,client_id) REFERENCES cadu_reports_flow_registry(id,organization_id,client_id),
    FOREIGN KEY(flow_id,revision) REFERENCES cadu_reports_flow_versions(flow_id,revision)
);
CREATE TABLE IF NOT EXISTS cadu_reports_flow_suggestions (
    id UUID PRIMARY KEY, flow_id UUID NOT NULL, organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL, page_id UUID NOT NULL, base_revision BIGINT NOT NULL,
    evidence_hash TEXT NOT NULL, result JSONB, status TEXT NOT NULL DEFAULT 'pending',
    created_by BIGINT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), applied_at TIMESTAMPTZ,
    FOREIGN KEY(flow_id,organization_id,client_id) REFERENCES cadu_reports_flow_registry(id,organization_id,client_id)
);
CREATE INDEX IF NOT EXISTS reports_flow_suggestion_budget
    ON cadu_reports_flow_suggestions(organization_id,client_id,created_at);
COMMIT;
