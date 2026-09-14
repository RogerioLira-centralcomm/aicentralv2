CREATE TABLE IF NOT EXISTS cx_format_variant_revisions (
    id BIGSERIAL PRIMARY KEY,
    variant_id VARCHAR(80) NOT NULL,
    campaign_id VARCHAR(80),
    format_key VARCHAR(80) NOT NULL,
    revision SMALLINT NOT NULL,
    focus TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (variant_id, revision)
);

CREATE INDEX IF NOT EXISTS cx_format_variant_revisions_variant_idx
    ON cx_format_variant_revisions (variant_id, revision);
