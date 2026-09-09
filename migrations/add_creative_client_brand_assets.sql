CREATE TABLE IF NOT EXISTS cx_client_brand_assets (
    id BIGSERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL
        REFERENCES cx_clients(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    source_kind VARCHAR(20) NOT NULL DEFAULT 'website',
    source_url TEXT,
    page_url TEXT,
    asset_path TEXT,
    mime_type VARCHAR(100),
    width INTEGER,
    height INTEGER,
    sha256 VARCHAR(64),
    score NUMERIC(5, 2),
    status VARCHAR(20) NOT NULL DEFAULT 'approved',
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_client_brand_asset_role
        CHECK (role IN ('logo', 'reference')),
    CONSTRAINT chk_cx_client_brand_asset_source
        CHECK (source_kind IN ('website', 'upload')),
    CONSTRAINT chk_cx_client_brand_asset_status
        CHECK (status IN ('candidate', 'approved', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_cx_client_brand_assets_client
    ON cx_client_brand_assets(client_id, status, role, is_primary DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_client_brand_assets_hash
    ON cx_client_brand_assets(client_id, sha256)
    WHERE sha256 IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_client_brand_assets_primary_logo
    ON cx_client_brand_assets(client_id)
    WHERE role = 'logo' AND is_primary = TRUE AND status = 'approved';
