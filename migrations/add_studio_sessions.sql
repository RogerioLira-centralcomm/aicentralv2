-- Sessões persistentes, lineage, finalização, entrega e limpeza do Cadu Studio.
-- Seguro para reaplicação em bancos que já possuem o histórico de criação.

CREATE TABLE IF NOT EXISTS cx_studio_assets (
    id UUID PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES cx_clients(id) ON DELETE CASCADE,
    owner_user_id INTEGER,
    project_id UUID REFERENCES cx_studio_projects(id) ON DELETE SET NULL,
    kind VARCHAR(24) NOT NULL CHECK (kind IN ('reference', 'image', 'video', 'document')),
    source_type VARCHAR(48) NOT NULL DEFAULT 'studio',
    source_id VARCHAR(180) NOT NULL DEFAULT '',
    title VARCHAR(160) NOT NULL DEFAULT '',
    asset_url TEXT NOT NULL DEFAULT '',
    storage_key TEXT NOT NULL DEFAULT '',
    status VARCHAR(24) NOT NULL DEFAULT 'working'
        CHECK (status IN ('working', 'accepted', 'final', 'discarded', 'pending_delete', 'deleted')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cx_studio_assets_owner
    ON cx_studio_assets (client_id, owner_user_id, updated_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_cx_studio_assets_project
    ON cx_studio_assets (project_id, updated_at DESC)
    WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_studio_assets_source
    ON cx_studio_assets (client_id, source_type, source_id)
    WHERE source_id <> '' AND deleted_at IS NULL;

ALTER TABLE cx_studio_project_items
    ADD COLUMN IF NOT EXISTS asset_id UUID REFERENCES cx_studio_assets(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_cx_studio_project_items_asset
    ON cx_studio_project_items (asset_id)
    WHERE asset_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS cx_studio_sessions (
    id UUID PRIMARY KEY,
    root_session_id UUID NOT NULL,
    parent_session_id UUID,
    project_id UUID REFERENCES cx_studio_projects(id) ON DELETE SET NULL,
    client_id INTEGER NOT NULL REFERENCES cx_clients(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    studio_type VARCHAR(24) NOT NULL
        CHECK (studio_type IN ('create', 'edit', 'adapt')),
    status VARCHAR(24) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'ready', 'finalizing', 'finalized', 'archived', 'failed', 'cancelled')),
    title VARCHAR(160) NOT NULL DEFAULT '',
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    active_asset_id UUID REFERENCES cx_studio_assets(id) ON DELETE SET NULL,
    base_asset_id UUID REFERENCES cx_studio_assets(id) ON DELETE SET NULL,
    original_prompt TEXT NOT NULL DEFAULT '',
    optimized_prompt TEXT NOT NULL DEFAULT '',
    prompt_language VARCHAR(16) NOT NULL DEFAULT 'pt-BR',
    prompt_version VARCHAR(40) NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalized_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_cx_studio_sessions_root
        FOREIGN KEY (root_session_id) REFERENCES cx_studio_sessions(id)
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_cx_studio_sessions_parent
        FOREIGN KEY (parent_session_id) REFERENCES cx_studio_sessions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_cx_studio_sessions_project
    ON cx_studio_sessions (client_id, project_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cx_studio_sessions_free
    ON cx_studio_sessions (client_id, user_id, updated_at DESC)
    WHERE project_id IS NULL AND status <> 'archived';
CREATE INDEX IF NOT EXISTS idx_cx_studio_sessions_root
    ON cx_studio_sessions (root_session_id, created_at);

CREATE TABLE IF NOT EXISTS cx_studio_session_assets (
    session_id UUID NOT NULL REFERENCES cx_studio_sessions(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES cx_studio_assets(id) ON DELETE CASCADE,
    role VARCHAR(24) NOT NULL
        CHECK (role IN ('reference', 'base', 'attempt', 'accepted', 'final', 'discard')),
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (session_id, asset_id, role)
);
CREATE INDEX IF NOT EXISTS idx_cx_studio_session_assets_asset
    ON cx_studio_session_assets (asset_id, session_id);

CREATE TABLE IF NOT EXISTS cx_studio_session_events (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES cx_studio_sessions(id) ON DELETE CASCADE,
    event_type VARCHAR(48) NOT NULL,
    request_id VARCHAR(160),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cx_studio_session_events_session
    ON cx_studio_session_events (session_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_studio_session_events_request
    ON cx_studio_session_events (session_id, request_id, event_type)
    WHERE request_id IS NOT NULL AND request_id <> '';

CREATE TABLE IF NOT EXISTS cx_studio_finalizations (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL UNIQUE REFERENCES cx_studio_sessions(id) ON DELETE CASCADE,
    root_session_id UUID NOT NULL REFERENCES cx_studio_sessions(id) ON DELETE CASCADE,
    final_asset_id UUID NOT NULL REFERENCES cx_studio_assets(id),
    snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    generation_count INTEGER NOT NULL DEFAULT 0 CHECK (generation_count >= 0),
    edit_count INTEGER NOT NULL DEFAULT 0 CHECK (edit_count >= 0),
    format_count INTEGER NOT NULL DEFAULT 0 CHECK (format_count >= 0),
    handoff_count INTEGER NOT NULL DEFAULT 0 CHECK (handoff_count >= 0),
    active_seconds INTEGER NOT NULL DEFAULT 0 CHECK (active_seconds >= 0),
    estimated_minutes_saved INTEGER NOT NULL DEFAULT 0 CHECK (estimated_minutes_saved >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cx_studio_finalizations_root
    ON cx_studio_finalizations (root_session_id, created_at);

CREATE TABLE IF NOT EXISTS cx_studio_delivery_outbox (
    id UUID PRIMARY KEY,
    root_session_id UUID NOT NULL REFERENCES cx_studio_sessions(id) ON DELETE CASCADE,
    finalization_id UUID NOT NULL REFERENCES cx_studio_finalizations(id) ON DELETE CASCADE,
    recipient_email VARCHAR(320) NOT NULL,
    recipient_name VARCHAR(160) NOT NULL DEFAULT '',
    kind VARCHAR(40) NOT NULL DEFAULT 'first_finalization',
    status VARCHAR(24) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'sent', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    provider_message_id VARCHAR(180) NOT NULL DEFAULT '',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_error TEXT NOT NULL DEFAULT '',
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (root_session_id, kind)
);
CREATE INDEX IF NOT EXISTS idx_cx_studio_delivery_outbox_pending
    ON cx_studio_delivery_outbox (available_at, created_at)
    WHERE status IN ('pending', 'failed');

CREATE TABLE IF NOT EXISTS cx_studio_asset_deletions (
    id BIGSERIAL PRIMARY KEY,
    asset_id UUID NOT NULL UNIQUE REFERENCES cx_studio_assets(id) ON DELETE CASCADE,
    storage_key TEXT NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'deleted', 'failed', 'cancelled')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    available_at TIMESTAMPTZ NOT NULL,
    deleted_at TIMESTAMPTZ,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cx_studio_asset_deletions_pending
    ON cx_studio_asset_deletions (available_at, created_at)
    WHERE status IN ('pending', 'failed');
