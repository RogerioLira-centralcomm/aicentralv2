CREATE TABLE IF NOT EXISTS cx_camadas_collections (
    id BIGSERIAL PRIMARY KEY,
    public_id VARCHAR(40) NOT NULL UNIQUE,
    client_id INTEGER REFERENCES cx_clients(id) ON DELETE SET NULL,
    name VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_camadas_collections_client
    ON cx_camadas_collections (client_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cx_camadas_creatives (
    id BIGSERIAL PRIMARY KEY,
    public_id VARCHAR(40) NOT NULL UNIQUE,
    client_id INTEGER REFERENCES cx_clients(id) ON DELETE SET NULL,
    collection_id BIGINT REFERENCES cx_camadas_collections(id) ON DELETE SET NULL,
    name VARCHAR(200) NOT NULL DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    original_path TEXT NOT NULL,
    original_name TEXT,
    mime_type VARCHAR(100),
    sha256 VARCHAR(64),
    width INTEGER,
    height INTEGER,
    reading JSONB NOT NULL DEFAULT '{}'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_camadas_creative_status
        CHECK (status IN ('queued', 'running', 'ready', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_cx_camadas_creatives_client
    ON cx_camadas_creatives (client_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cx_camadas_jobs (
    id BIGSERIAL PRIMARY KEY,
    public_id VARCHAR(40) NOT NULL UNIQUE,
    creative_id BIGINT NOT NULL REFERENCES cx_camadas_creatives(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    stage VARCHAR(40) NOT NULL DEFAULT 'queued',
    progress INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cx_camadas_job_status
        CHECK (status IN ('queued', 'running', 'done', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_cx_camadas_jobs_creative
    ON cx_camadas_jobs (creative_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cx_camadas_elements (
    id BIGSERIAL PRIMARY KEY,
    public_id VARCHAR(40) NOT NULL UNIQUE,
    creative_id BIGINT NOT NULL REFERENCES cx_camadas_creatives(id) ON DELETE CASCADE,
    role VARCHAR(40) NOT NULL,
    label VARCHAR(200) NOT NULL DEFAULT '',
    layer_type VARCHAR(20) NOT NULL DEFAULT 'image',
    bbox JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality VARCHAR(40) NOT NULL DEFAULT '',
    provenance VARCHAR(40) NOT NULL DEFAULT 'html',
    visible BOOLEAN NOT NULL DEFAULT TRUE,
    locked BOOLEAN NOT NULL DEFAULT FALSE,
    z_index INTEGER NOT NULL DEFAULT 0,
    approved BOOLEAN NOT NULL DEFAULT FALSE,
    text_content TEXT NOT NULL DEFAULT '',
    png_path TEXT,
    mask_path TEXT,
    thumb_path TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_camadas_elements_creative
    ON cx_camadas_elements (creative_id, z_index, id);

CREATE TABLE IF NOT EXISTS cx_camadas_masks (
    id BIGSERIAL PRIMARY KEY,
    element_id BIGINT NOT NULL REFERENCES cx_camadas_elements(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    mask_path TEXT,
    contours JSONB NOT NULL DEFAULT '[]'::jsonb,
    points JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cx_camadas_scenes (
    id BIGSERIAL PRIMARY KEY,
    creative_id BIGINT NOT NULL UNIQUE REFERENCES cx_camadas_creatives(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    document JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cx_camadas_assets (
    id BIGSERIAL PRIMARY KEY,
    public_id VARCHAR(40) NOT NULL UNIQUE,
    client_id INTEGER REFERENCES cx_clients(id) ON DELETE CASCADE,
    collection_id BIGINT REFERENCES cx_camadas_collections(id) ON DELETE SET NULL,
    element_id BIGINT REFERENCES cx_camadas_elements(id) ON DELETE SET NULL,
    creative_id BIGINT REFERENCES cx_camadas_creatives(id) ON DELETE SET NULL,
    name VARCHAR(200) NOT NULL,
    kind VARCHAR(40) NOT NULL,
    provenance VARCHAR(40) NOT NULL,
    sha256 VARCHAR(64),
    asset_path TEXT,
    thumb_path TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cx_camadas_assets_client
    ON cx_camadas_assets (client_id, kind, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_camadas_assets_client_sha
    ON cx_camadas_assets (client_id, sha256)
    WHERE sha256 IS NOT NULL AND sha256 <> '';

CREATE TABLE IF NOT EXISTS cx_camadas_generations (
    id BIGSERIAL PRIMARY KEY,
    public_id VARCHAR(40) NOT NULL UNIQUE,
    creative_id BIGINT REFERENCES cx_camadas_creatives(id) ON DELETE CASCADE,
    provider VARCHAR(40) NOT NULL DEFAULT 'openrouter',
    model VARCHAR(120) NOT NULL,
    resolution VARCHAR(20) NOT NULL DEFAULT '1K',
    prompt TEXT NOT NULL DEFAULT '',
    output_path TEXT,
    input_hashes JSONB NOT NULL DEFAULT '[]'::jsonb,
    accepted BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
