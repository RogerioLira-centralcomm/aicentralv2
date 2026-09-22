-- Durable, provider-neutral memory for long conversations. The transcript in
-- cadu_conversation_messages remains authoritative; these rows are rebuildable
-- projections with explicit provenance.
ALTER TABLE cadu_conversation_messages
    ADD COLUMN IF NOT EXISTS conversation_sequence BIGINT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_cadu_conversation_messages_sequence
    ON cadu_conversation_messages (conversation_id, conversation_sequence)
    WHERE conversation_sequence IS NOT NULL;

CREATE OR REPLACE FUNCTION cadu_assign_conversation_sequence() RETURNS trigger AS $$
BEGIN
    IF NEW.conversation_sequence IS NULL AND NEW.role IN ('user','assistant') THEN
        PERFORM pg_advisory_xact_lock(hashtextextended(NEW.conversation_id::text, 0));
        SELECT COALESCE(MAX(conversation_sequence),0)+1 INTO NEW.conversation_sequence
        FROM cadu_conversation_messages WHERE conversation_id=NEW.conversation_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_cadu_assign_conversation_sequence ON cadu_conversation_messages;
CREATE TRIGGER trg_cadu_assign_conversation_sequence BEFORE INSERT ON cadu_conversation_messages
FOR EACH ROW EXECUTE FUNCTION cadu_assign_conversation_sequence();

CREATE TABLE IF NOT EXISTS cadu_conversation_memory_state (
    conversation_id TEXT PRIMARY KEY REFERENCES cadu_conversations(id) ON DELETE CASCADE,
    organization_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    covers_message_count INTEGER NOT NULL DEFAULT 0 CHECK (covers_message_count >= 0),
    observed_message_count INTEGER NOT NULL DEFAULT 0 CHECK (observed_message_count >= 0),
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
ALTER TABLE cadu_conversation_memory_state
    ADD COLUMN IF NOT EXISTS observed_message_count INTEGER NOT NULL DEFAULT 0;
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
