-- Evolução idempotente para instalações que criaram as tabelas do agente
-- antes do contrato atual de mensagens e tool calls.

ALTER TABLE agent_conversations
    ADD COLUMN IF NOT EXISTS title VARCHAR(160) NOT NULL DEFAULT 'Nova conversa',
    ADD COLUMN IF NOT EXISTS context_module VARCHAR(50),
    ADD COLUMN IF NOT EXISTS context_screen VARCHAR(80),
    ADD COLUMN IF NOT EXISTS context_entity_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS context_entity_id VARCHAR(80),
    ADD COLUMN IF NOT EXISTS context_entity_label VARCHAR(200),
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE agent_messages
    ADD COLUMN IF NOT EXISTS content TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS display_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS model VARCHAR(120),
    ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER,
    ADD COLUMN IF NOT EXISTS completion_tokens INTEGER,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE agent_tool_calls
    ADD COLUMN IF NOT EXISTS message_id BIGINT REFERENCES agent_messages(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS operation_type VARCHAR(20) NOT NULL DEFAULT 'read',
    ADD COLUMN IF NOT EXISTS arguments_sanitized JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS result_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'error',
    ADD COLUMN IF NOT EXISTS duration_ms INTEGER,
    ADD COLUMN IF NOT EXISTS request_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_agent_conversations_user_updated
    ON agent_conversations (user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_messages_conversation
    ON agent_messages (conversation_id, created_at, id);

CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_conversation
    ON agent_tool_calls (conversation_id, created_at DESC);
