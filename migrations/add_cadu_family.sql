-- Additive rollout. Existing projects, brands and conversations remain in place.
CREATE TABLE IF NOT EXISTS cadu_family_client_access (
    organization_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    role TEXT NOT NULL CHECK (role IN ('viewer', 'member', 'admin')),
    revoked_at TIMESTAMPTZ,
    PRIMARY KEY (organization_id, user_id, client_id)
);
CREATE TABLE IF NOT EXISTS cadu_family_entity_links (
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    source TEXT NOT NULL CHECK (source IN ('ci', 'projects', 'studio')),
    source_id TEXT NOT NULL,
    canonical_source TEXT NOT NULL CHECK (canonical_source IN ('ci', 'projects', 'studio')),
    canonical_id TEXT NOT NULL,
    reviewed_by INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source, source_id),
    CHECK (source <> canonical_source OR source_id <> canonical_id)
);
CREATE TABLE IF NOT EXISTS cadu_family_conversation_context (
    conversation_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    organization_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    profile TEXT NOT NULL CHECK (profile IN ('workspace', 'planner', 'connect')),
    project_ref TEXT,
    brand_ref TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cadu_family_conversation_owner
    ON cadu_family_conversation_context (organization_id, user_id, client_id);
CREATE TABLE IF NOT EXISTS cadu_family_report_projects (
    campaign_id INTEGER PRIMARY KEY REFERENCES cadu_pi_campanha(id_campanha),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    project_ref TEXT NOT NULL,
    updated_by INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS cadu_family_action_previews (
    id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    organization_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    action TEXT NOT NULL CHECK (action = 'link_report_project'),
    payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed')),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '10 minutes',
    confirmed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS cadu_family_chat_runs (
    id UUID PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES cadu_conversations(id),
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'stopped')),
    task_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS cadu_family_chat_one_running
    ON cadu_family_chat_runs(conversation_id) WHERE status = 'running';
CREATE TABLE IF NOT EXISTS cadu_family_chat_uploads (
    id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    provider_id TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('image', 'document')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
