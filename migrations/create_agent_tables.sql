CREATE TABLE IF NOT EXISTS agent_conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    title VARCHAR(160) NOT NULL DEFAULT 'Nova conversa',
    context_module VARCHAR(50),
    context_screen VARCHAR(80),
    context_entity_type VARCHAR(50),
    context_entity_id VARCHAR(80),
    context_entity_label VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_conversations_user_updated
    ON agent_conversations (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS agent_messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES agent_conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL DEFAULT '',
    display_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    model VARCHAR(120),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_messages_conversation
    ON agent_messages (conversation_id, created_at, id);

CREATE TABLE IF NOT EXISTS agent_tool_calls (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES agent_conversations(id) ON DELETE CASCADE,
    message_id BIGINT REFERENCES agent_messages(id) ON DELETE SET NULL,
    tool_name VARCHAR(80) NOT NULL,
    operation_type VARCHAR(20) NOT NULL DEFAULT 'read',
    arguments_sanitized JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL,
    duration_ms INTEGER,
    request_id VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_conversation
    ON agent_tool_calls (conversation_id, created_at DESC);
