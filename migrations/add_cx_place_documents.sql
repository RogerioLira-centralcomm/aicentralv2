-- Histórico imutável de documentos comerciais do Places.
-- Idempotente: pode ser executada no deploy e pelo painel administrativo.

CREATE TABLE IF NOT EXISTS cx_place_documents (
    id BIGSERIAL PRIMARY KEY,
    place_id BIGINT NOT NULL REFERENCES cx_places(id) ON DELETE CASCADE,
    document_type VARCHAR(32) NOT NULL,
    agency_name VARCHAR(160),
    campaign_name VARCHAR(200),
    brand_name VARCHAR(160),
    version INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(24) NOT NULL DEFAULT 'draft',
    agent_instruction TEXT NOT NULL DEFAULT '',
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_report JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by INTEGER,
    updated_by INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_cx_place_documents_type CHECK (document_type IN ('proposal_deck', 'technical_sheet')),
    CONSTRAINT chk_cx_place_documents_status CHECK (status IN ('draft', 'reviewed', 'exported')),
    CONSTRAINT chk_cx_place_documents_version CHECK (version > 0),
    CONSTRAINT ux_cx_place_documents_version UNIQUE (place_id, document_type, version)
);

CREATE INDEX IF NOT EXISTS idx_cx_place_documents_place_status
    ON cx_place_documents(place_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS cx_place_document_exports (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES cx_place_documents(id) ON DELETE CASCADE,
    export_format VARCHAR(16) NOT NULL DEFAULT 'pdf',
    filename VARCHAR(300) NOT NULL,
    content_hash CHAR(64) NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    mime_type VARCHAR(100) NOT NULL DEFAULT 'application/pdf',
    artifact BYTEA NOT NULL,
    created_by INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_cx_place_document_exports_format CHECK (export_format = 'pdf'),
    CONSTRAINT chk_cx_place_document_exports_pages CHECK (page_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_cx_place_document_exports_document
    ON cx_place_document_exports(document_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_cx_place_document_exports_hash
    ON cx_place_document_exports(document_id, content_hash);

COMMENT ON TABLE cx_place_documents IS 'Rascunhos e versões de documentos comerciais gerados para Places.';
COMMENT ON TABLE cx_place_document_exports IS 'PDFs históricos, armazenados junto ao snapshot que os originou.';
