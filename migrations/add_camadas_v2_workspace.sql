ALTER TABLE cx_camadas_collections
  ADD COLUMN IF NOT EXISTS cover_thumb_path TEXT,
  ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_camadas_collections_client_name
  ON cx_camadas_collections (client_id, lower(name));

ALTER TABLE cx_camadas_assets
  ADD COLUMN IF NOT EXISTS thumb_width INTEGER,
  ADD COLUMN IF NOT EXISTS thumb_height INTEGER,
  ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_cx_camadas_assets_collection
  ON cx_camadas_assets (collection_id, kind, created_at DESC);

ALTER TABLE cx_camadas_elements
  ADD COLUMN IF NOT EXISTS coverage REAL,
  ADD COLUMN IF NOT EXISTS needs_review BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_cx_camadas_jobs_stage
  ON cx_camadas_jobs (stage);
