-- Private image evidence stored in the existing PostgreSQL for the initial rollout.
CREATE TABLE IF NOT EXISTS cadu_connect_report_sources (
    id BIGSERIAL PRIMARY KEY,
    report_id BIGINT NOT NULL REFERENCES cadu_connect_report_workspaces(id),
    batch_id UUID NOT NULL,
    original_name TEXT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    image_bytes BYTEA NOT NULL,
    mime_type TEXT NOT NULL CHECK (mime_type IN ('image/png','image/jpeg','image/webp')),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    supplier TEXT NOT NULL DEFAULT '',
    period_start DATE,
    period_end DATE,
    status TEXT NOT NULL DEFAULT 'pending_review' CHECK (status IN ('pending_review','reviewed')),
    created_by INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (report_id, sha256),
    CHECK (period_start IS NULL OR period_end IS NULL OR period_start <= period_end)
);
