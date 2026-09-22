CREATE TABLE IF NOT EXISTS cadu_agent_turn_queue (
    id UUID PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES cadu_conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    position INTEGER NOT NULL CHECK (position BETWEEN 0 AND 4),
    prompt TEXT NOT NULL CHECK (char_length(prompt) BETWEEN 1 AND 20000),
    execution_mode TEXT NOT NULL DEFAULT 'analysis' CHECK (execution_mode IN ('fast', 'analysis', 'agentic')),
    selected_context JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cadu_agent_turn_queue_position UNIQUE (conversation_id, position) DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS cadu_agent_turn_queue_owner
    ON cadu_agent_turn_queue (user_id, client_id, conversation_id);
