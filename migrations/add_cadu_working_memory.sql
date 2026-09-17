-- Shared, reviewable work memory. It never replaces the private user memory.
CREATE TABLE IF NOT EXISTS cadu_working_memories (
    id UUID PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    project_ref TEXT,
    scope VARCHAR(16) NOT NULL CHECK (scope IN ('project','client')),
    kind VARCHAR(32) NOT NULL CHECK (kind IN ('decision','constraint','risk','next_step','brand_context')),
    summary TEXT NOT NULL,
    confidence NUMERIC(4,3) NOT NULL DEFAULT .700 CHECK (confidence >= 0 AND confidence <= 1),
    status VARCHAR(16) NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','confirmed','dismissed')),
    source_conversation_id TEXT REFERENCES cadu_conversations(id),
    source_message_id UUID,
    source_author_id INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
    reviewed_by INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((scope = 'project' AND project_ref IS NOT NULL) OR (scope = 'client' AND project_ref IS NULL))
);
CREATE INDEX IF NOT EXISTS cadu_working_memories_scope
    ON cadu_working_memories (organization_id, client_id, project_ref, scope, status, updated_at DESC);
CREATE TABLE IF NOT EXISTS cadu_working_memory_events (
    id BIGSERIAL PRIMARY KEY,
    memory_id UUID NOT NULL REFERENCES cadu_working_memories(id) ON DELETE CASCADE,
    actor_id INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
    event VARCHAR(24) NOT NULL CHECK (event IN ('proposed','confirmed','edited','dismissed','promoted')),
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
