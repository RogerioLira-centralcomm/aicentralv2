-- Suggested project for conversations without one. Nothing here links a
-- conversation: binding makes its content visible to the project team, so only
-- the conversation owner may accept (through the existing PATCH endpoint).
CREATE TABLE IF NOT EXISTS cadu_conversation_project_suggestions (
    conversation_id TEXT PRIMARY KEY REFERENCES cadu_conversations(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    project_ref TEXT NOT NULL,
    score NUMERIC(5,4) NOT NULL,
    runner_up_ref TEXT,
    runner_up_score NUMERIC(5,4),
    name_mentioned BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(12) NOT NULL DEFAULT 'suggested' CHECK (status IN ('suggested','dismissed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cadu_conversation_project_suggestions_client
    ON cadu_conversation_project_suggestions (client_id, status);
