-- Provider-neutral state for the canonical Cadu resource projection.
-- Existing provider tables remain the source of truth; these fields describe
-- the Cadu-side projection and its derived processing stages.

ALTER TABLE cadu_project_resources
    ADD COLUMN IF NOT EXISTS permission_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS capability_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS index_status VARCHAR(24) NOT NULL DEFAULT 'not_requested',
    ADD COLUMN IF NOT EXISTS ocr_status VARCHAR(24) NOT NULL DEFAULT 'not_requested',
    ADD COLUMN IF NOT EXISTS embedding_status VARCHAR(24) NOT NULL DEFAULT 'not_requested',
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_cadu_project_resources_index_state
    ON cadu_project_resources (client_id, project_ref, index_status, ocr_status, embedding_status);

CREATE INDEX IF NOT EXISTS idx_cadu_project_resources_deleted
    ON cadu_project_resources (client_id, deleted_at)
    WHERE deleted_at IS NOT NULL;

COMMENT ON COLUMN cadu_project_resources.permission_snapshot IS
    'Last known provider permission state; it is not a replacement for provider authorization.';
COMMENT ON COLUMN cadu_project_resources.capability_snapshot IS
    'Actions currently supported by the registered Cadu connector for this resource.';
