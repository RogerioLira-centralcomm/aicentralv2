-- Estúdio técnico e visual para formatos criativos.
-- Migração aditiva e idempotente.

ALTER TABLE cx_format_templates
    ADD COLUMN IF NOT EXISTS placement_spec JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS behavior_spec JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS cx_format_modeling_jobs (
    id BIGSERIAL PRIMARY KEY,
    format_template_id INTEGER NOT NULL
        REFERENCES cx_format_templates(id) ON DELETE CASCADE,
    client_id INTEGER REFERENCES cx_clients(id) ON DELETE SET NULL,
    parent_job_id BIGINT
        REFERENCES cx_format_modeling_jobs(id) ON DELETE SET NULL,
    slot INTEGER NOT NULL,
    reference_type VARCHAR(20) NOT NULL DEFAULT 'full_mockup',
    model VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    prompt TEXT NOT NULL,
    refinement_instruction TEXT,
    input_references JSONB NOT NULL DEFAULT '[]'::jsonb,
    asset_url TEXT,
    response_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    estimated_cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    actual_cost_usd NUMERIC(12, 6),
    error_message TEXT,
    created_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente)
        ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_format_modeling_slot CHECK (slot BETWEEN 1 AND 4),
    CONSTRAINT chk_cx_format_modeling_reference_type
        CHECK (reference_type IN ('background', 'full_mockup')),
    CONSTRAINT chk_cx_format_modeling_status
        CHECK (status IN (
            'queued', 'generating', 'review', 'approved', 'failed', 'archived'
        )),
    CONSTRAINT chk_cx_format_modeling_cost
        CHECK (
            estimated_cost_usd >= 0
            AND (actual_cost_usd IS NULL OR actual_cost_usd >= 0)
        )
);

CREATE INDEX IF NOT EXISTS idx_cx_format_modeling_jobs_format
    ON cx_format_modeling_jobs(format_template_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cx_format_modeling_jobs_parent
    ON cx_format_modeling_jobs(parent_job_id);

ALTER TABLE cx_format_references
    ADD COLUMN IF NOT EXISTS source_modeling_job_id BIGINT
        REFERENCES cx_format_modeling_jobs(id) ON DELETE SET NULL;

