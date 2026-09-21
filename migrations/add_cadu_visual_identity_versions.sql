CREATE TABLE IF NOT EXISTS cadu_visual_identity_versions (
    id BIGSERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    owner_type TEXT NOT NULL CHECK (owner_type IN ('brand', 'project')),
    owner_ref TEXT NOT NULL,
    source_brand_ref TEXT,
    visual_type TEXT NOT NULL CHECK (visual_type IN ('icon', 'avatar', 'background', 'hero')),
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'processing', 'ready', 'approved', 'archived', 'failed')),
    image_url TEXT,
    vector_url TEXT,
    prompt TEXT,
    model TEXT,
    token_usage INTEGER NOT NULL DEFAULT 0,
    contrast_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
    approved_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS cadu_visual_identity_versions_owner
    ON cadu_visual_identity_versions (client_id, owner_type, owner_ref, visual_type, version DESC);

CREATE UNIQUE INDEX IF NOT EXISTS cadu_visual_identity_versions_active
    ON cadu_visual_identity_versions (client_id, owner_type, owner_ref, visual_type)
    WHERE status = 'approved';

CREATE UNIQUE INDEX IF NOT EXISTS cadu_visual_identity_versions_number
    ON cadu_visual_identity_versions (client_id, owner_type, owner_ref, visual_type, version);
