-- User-owned Cadu memory. It is deliberately separate from project RAG and
-- institutional knowledge so privacy and deletion rules remain explicit.
CREATE TABLE IF NOT EXISTS cadu_user_memories (
    id UUID PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    client_id INTEGER REFERENCES tbl_cliente(id_cliente),
    project_ref TEXT,
    scope VARCHAR(16) NOT NULL CHECK (scope IN ('personal', 'client', 'project')),
    kind VARCHAR(32) NOT NULL CHECK (kind IN ('preference', 'role', 'expertise', 'interest', 'goal', 'decision', 'constraint')),
    memory_key VARCHAR(120) NOT NULL,
    value TEXT NOT NULL,
    confidence NUMERIC(4,3) NOT NULL DEFAULT 0.900 CHECK (confidence >= 0 AND confidence <= 1),
    source VARCHAR(16) NOT NULL CHECK (source IN ('explicit', 'inferred', 'imported')),
    source_conversation_id TEXT,
    source_message_id UUID,
    status VARCHAR(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'proposed', 'dismissed', 'expired')),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((scope = 'personal' AND client_id IS NULL AND project_ref IS NULL)
        OR (scope = 'client' AND client_id IS NOT NULL AND project_ref IS NULL)
        OR (scope = 'project' AND client_id IS NOT NULL AND project_ref IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_cadu_user_memories_retrieve
    ON cadu_user_memories (organization_id, user_id, client_id, project_ref, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_user_memories_text
    ON cadu_user_memories USING GIN (to_tsvector('portuguese', coalesce(memory_key, '') || ' ' || coalesce(value, '')));

CREATE TABLE IF NOT EXISTS cadu_user_memory_events (
    id BIGSERIAL PRIMARY KEY,
    memory_id UUID NOT NULL REFERENCES cadu_user_memories(id) ON DELETE CASCADE,
    actor_id INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
    event VARCHAR(24) NOT NULL CHECK (event IN ('created', 'updated', 'dismissed', 'deleted', 'retrieved')),
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cadu_user_memory_events_memory ON cadu_user_memory_events (memory_id, created_at DESC);
