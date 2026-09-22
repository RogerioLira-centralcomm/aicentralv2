-- Durable, provider-neutral memory for long conversations. The transcript in
-- cadu_conversation_messages remains authoritative; these rows are rebuildable
-- projections with explicit provenance.
CREATE TABLE IF NOT EXISTS cadu_conversation_memory_state (
    conversation_id TEXT PRIMARY KEY REFERENCES cadu_conversations(id) ON DELETE CASCADE,
    organization_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    covers_message_count INTEGER NOT NULL DEFAULT 0 CHECK (covers_message_count >= 0),
    opening_user_message_id UUID,
    opening_user_message TEXT NOT NULL DEFAULT '',
    current_goal TEXT NOT NULL DEFAULT '',
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_message_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    summarizer_version VARCHAR(40) NOT NULL DEFAULT 'deterministic-v1',
    status VARCHAR(16) NOT NULL DEFAULT 'ready' CHECK (status IN ('ready','stale','failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cadu_conversation_memory_scope
    ON cadu_conversation_memory_state (organization_id, client_id, user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS cadu_conversation_memory_segments (
    id UUID PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES cadu_conversations(id) ON DELETE CASCADE,
    start_position INTEGER NOT NULL CHECK (start_position > 0),
    end_position INTEGER NOT NULL CHECK (end_position >= start_position),
    summary TEXT NOT NULL,
    topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_message_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    summarizer_version VARCHAR(40) NOT NULL DEFAULT 'deterministic-v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (conversation_id, start_position, end_position)
);
CREATE INDEX IF NOT EXISTS idx_cadu_conversation_memory_segments_lookup
    ON cadu_conversation_memory_segments (conversation_id, end_position DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_conversation_memory_segments_text
    ON cadu_conversation_memory_segments USING GIN (to_tsvector('portuguese', summary));
