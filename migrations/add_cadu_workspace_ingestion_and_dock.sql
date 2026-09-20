-- Unified ingestion and contextual organisation for Cadu Workspace.
--
-- These tables deliberately complement (rather than replace) the native
-- project files and Resource Registry.  An ingestion session is the durable
-- record for a user gesture; its items may be files, URLs or existing Cadu
-- resources.  Provider credentials and OAuth tokens are never stored here.

CREATE TABLE IF NOT EXISTS cadu_workspace_ingestion_sessions (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente),
    user_id BIGINT REFERENCES tbl_contato_cliente(id_contato_cliente),
    project_ref TEXT,
    -- cadu_conversations.id is a provider-neutral text identifier.
    conversation_id TEXT REFERENCES cadu_conversations(id) ON DELETE SET NULL,
    surface VARCHAR(32) NOT NULL DEFAULT 'workspace',
    origin VARCHAR(32) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'draft',
    requested_purpose VARCHAR(32),
    idempotency_key VARCHAR(128),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CHECK (organization_id = client_id),
    CHECK (surface IN ('workspace', 'conversations', 'planner', 'studio', 'reports')),
    CHECK (origin IN ('drop', 'file_picker', 'paste_url', 'dock', 'chat', 'mcp', 'api')),
    CHECK (status IN ('draft', 'awaiting_project', 'awaiting_decision', 'processing', 'completed', 'failed', 'cancelled')),
    CHECK (requested_purpose IS NULL OR requested_purpose IN ('knowledge_source', 'project_attachment', 'conversation_only'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cadu_ingestion_session_idempotency
    ON cadu_workspace_ingestion_sessions (client_id, user_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cadu_ingestion_sessions_open
    ON cadu_workspace_ingestion_sessions (client_id, user_id, status, created_at DESC)
    WHERE status NOT IN ('completed', 'cancelled');
CREATE INDEX IF NOT EXISTS idx_cadu_ingestion_sessions_project
    ON cadu_workspace_ingestion_sessions (client_id, project_ref, created_at DESC)
    WHERE project_ref IS NOT NULL;

CREATE TABLE IF NOT EXISTS cadu_workspace_ingestion_items (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES cadu_workspace_ingestion_sessions(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente),
    item_type VARCHAR(24) NOT NULL,
    original_name VARCHAR(500),
    original_url TEXT,
    provider VARCHAR(64),
    external_id VARCHAR(512),
    mime_type VARCHAR(160),
    byte_size BIGINT,
    content_hash CHAR(64),
    staging_locator TEXT,
    project_file_id BIGINT REFERENCES cadu_ci_projeto_arquivos(id) ON DELETE SET NULL,
    resource_id UUID REFERENCES cadu_project_resources(id) ON DELETE SET NULL,
    purpose VARCHAR(32),
    category VARCHAR(40),
    classification_status VARCHAR(24) NOT NULL DEFAULT 'pending',
    classification_confidence NUMERIC(4,3),
    classification_reason TEXT,
    extraction_status VARCHAR(24) NOT NULL DEFAULT 'not_requested',
    extraction_error TEXT,
    extracted_document_id UUID,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (item_type IN ('file', 'url', 'internal_resource', 'meeting', 'drive_file')),
    CHECK (purpose IS NULL OR purpose IN ('knowledge_source', 'project_attachment', 'conversation_only')),
    CHECK (classification_status IN ('pending', 'classified', 'needs_review', 'manual', 'failed')),
    CHECK (extraction_status IN ('not_requested', 'queued', 'extracting', 'completed', 'skipped', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_cadu_ingestion_items_session
    ON cadu_workspace_ingestion_items (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_cadu_ingestion_items_project_file
    ON cadu_workspace_ingestion_items (project_file_id) WHERE project_file_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cadu_ingestion_items_hash
    ON cadu_workspace_ingestion_items (client_id, content_hash) WHERE content_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cadu_ingestion_items_external
    ON cadu_workspace_ingestion_items (client_id, provider, external_id)
    WHERE provider IS NOT NULL AND external_id IS NOT NULL;

-- A cluster is an explainable, reversible interpretation of related work in a
-- project (for example: campaign, briefing, meeting or creative review).
CREATE TABLE IF NOT EXISTS cadu_project_resource_clusters (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente),
    project_ref TEXT NOT NULL,
    cluster_type VARCHAR(40) NOT NULL,
    title TEXT NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'active',
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0,
    origin VARCHAR(24) NOT NULL DEFAULT 'automatic',
    rationale TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by BIGINT REFERENCES tbl_contato_cliente(id_contato_cliente),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ,
    CHECK (cluster_type IN ('campaign', 'briefing', 'meeting', 'research', 'creative_review', 'delivery', 'custom')),
    CHECK (status IN ('active', 'needs_review', 'archived')),
    CHECK (origin IN ('automatic', 'user', 'agent'))
);

CREATE INDEX IF NOT EXISTS idx_cadu_resource_clusters_project
    ON cadu_project_resource_clusters (client_id, project_ref, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS cadu_project_resource_cluster_members (
    cluster_id UUID NOT NULL REFERENCES cadu_project_resource_clusters(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES cadu_project_resources(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente),
    role VARCHAR(40) NOT NULL DEFAULT 'related',
    confidence NUMERIC(5,4) NOT NULL DEFAULT 1,
    rationale TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (cluster_id, resource_id),
    CHECK (role IN ('primary', 'source', 'output', 'reference', 'related'))
);
CREATE INDEX IF NOT EXISTS idx_cadu_cluster_members_resource
    ON cadu_project_resource_cluster_members (client_id, resource_id);

-- The dock is a personal, ordered launch surface.  Resources remain owned by
-- their original systems; this table stores only the user's shortcut.
CREATE TABLE IF NOT EXISTS cadu_workspace_dock_shortcuts (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente),
    user_id BIGINT NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    shortcut_type VARCHAR(32) NOT NULL,
    target_ref TEXT NOT NULL,
    project_ref TEXT,
    brand_ref TEXT,
    position INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, user_id, shortcut_type, target_ref),
    CHECK (shortcut_type IN ('brand', 'project', 'conversation', 'artifact', 'resource', 'plan', 'image', 'file'))
);
CREATE INDEX IF NOT EXISTS idx_cadu_dock_shortcuts_user
    ON cadu_workspace_dock_shortcuts (client_id, user_id, position, updated_at DESC);

-- References a connection configured by the integration subsystem.  Never
-- persist OAuth access/refresh tokens or meeting content here.
CREATE TABLE IF NOT EXISTS cadu_workspace_external_references (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente),
    project_ref TEXT,
    ingestion_item_id UUID REFERENCES cadu_workspace_ingestion_items(id) ON DELETE SET NULL,
    provider VARCHAR(64) NOT NULL,
    external_id VARCHAR(512),
    locator TEXT NOT NULL,
    connection_ref VARCHAR(255),
    reference_type VARCHAR(32) NOT NULL,
    sync_status VARCHAR(24) NOT NULL DEFAULT 'pending',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (reference_type IN ('drive_file', 'meeting', 'web_page', 'external_document')),
    CHECK (sync_status IN ('pending', 'connected', 'queued', 'synced', 'needs_authorization', 'failed', 'unsupported'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cadu_external_reference_dedupe
    ON cadu_workspace_external_references (client_id, provider, external_id)
    WHERE external_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cadu_external_references_project
    ON cadu_workspace_external_references (client_id, project_ref, sync_status, updated_at DESC);

COMMENT ON TABLE cadu_workspace_ingestion_sessions IS
    'A durable user gesture that can contain files, URLs or Cadu resources before project organisation.';
COMMENT ON TABLE cadu_project_resource_clusters IS
    'Reversible, explainable grouping of resources that occurred in the same project context.';
COMMENT ON TABLE cadu_workspace_dock_shortcuts IS
    'Personal Apple-dock-style shortcuts; no source object is moved or duplicated.';
