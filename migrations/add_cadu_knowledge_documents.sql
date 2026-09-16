CREATE TABLE IF NOT EXISTS cadu_knowledge_documents (
    id BIGSERIAL PRIMARY KEY,
    slug VARCHAR(120) NOT NULL UNIQUE,
    title VARCHAR(180) NOT NULL,
    kind VARCHAR(24) NOT NULL DEFAULT 'markdown' CHECK (kind IN ('markdown', 'csv')),
    status VARCHAR(16) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    published_version INTEGER,
    created_by INTEGER,
    updated_by INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cadu_knowledge_document_versions (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES cadu_knowledge_documents(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    source_note VARCHAR(500) NOT NULL DEFAULT '',
    model VARCHAR(100) NOT NULL DEFAULT 'gpt-5.6-sol',
    created_by INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, version)
);

CREATE INDEX IF NOT EXISTS idx_cadu_knowledge_documents_status ON cadu_knowledge_documents(status, updated_at DESC);
