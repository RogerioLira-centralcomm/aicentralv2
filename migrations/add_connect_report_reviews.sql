CREATE TABLE IF NOT EXISTS cadu_connect_report_source_reviews (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES cadu_connect_report_sources(id),
    report_revision INTEGER NOT NULL,
    metrics JSONB NOT NULL CHECK (jsonb_typeof(metrics) = 'array'),
    note TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_id, report_revision)
);
