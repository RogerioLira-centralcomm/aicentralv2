-- Apply to existing CentralX databases after add_creative_media.sql.
-- Kept in the base media schema too so a fresh install has the same tables.
CREATE TABLE IF NOT EXISTS cx_studio_creation_runs (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES cx_studio_projects(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES cx_clients(id) ON DELETE CASCADE,
    user_id INTEGER,
    prompt TEXT NOT NULL DEFAULT '', context JSONB NOT NULL DEFAULT '{}'::jsonb,
    requested_count SMALLINT NOT NULL DEFAULT 1 CHECK (requested_count BETWEEN 1 AND 5),
    returned_count SMALLINT NOT NULL DEFAULT 0 CHECK (returned_count BETWEEN 0 AND 5),
    model VARCHAR(180) NOT NULL DEFAULT '', charged_credits INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(24) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed')),
    error_message TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_cx_studio_creation_runs_project ON cx_studio_creation_runs (project_id, created_at DESC);
CREATE TABLE IF NOT EXISTS cx_studio_creation_directions (
    id UUID PRIMARY KEY, run_id UUID NOT NULL REFERENCES cx_studio_creation_runs(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES cx_studio_projects(id) ON DELETE CASCADE,
    position SMALLINT NOT NULL CHECK (position BETWEEN 1 AND 5), title VARCHAR(120) NOT NULL,
    summary TEXT NOT NULL DEFAULT '', prompt TEXT NOT NULL, selected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE (run_id, position)
);
CREATE INDEX IF NOT EXISTS idx_cx_studio_creation_directions_project ON cx_studio_creation_directions (project_id, created_at DESC);
CREATE TABLE IF NOT EXISTS cx_studio_project_items (
    id UUID PRIMARY KEY, project_id UUID NOT NULL REFERENCES cx_studio_projects(id) ON DELETE CASCADE,
    direction_id UUID REFERENCES cx_studio_creation_directions(id) ON DELETE SET NULL,
    client_id INTEGER NOT NULL REFERENCES cx_clients(id) ON DELETE CASCADE, user_id INTEGER,
    kind VARCHAR(24) NOT NULL CHECK (kind IN ('reference', 'direction', 'image', 'video')),
    title VARCHAR(160) NOT NULL DEFAULT '', asset_url TEXT NOT NULL DEFAULT '',
    source_type VARCHAR(48) NOT NULL DEFAULT 'studio', metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cx_studio_project_items_project ON cx_studio_project_items (project_id, created_at DESC);
