CREATE TABLE IF NOT EXISTS cadu_conversation_organization (
    conversation_id TEXT PRIMARY KEY REFERENCES cadu_conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    section TEXT NOT NULL DEFAULT 'recent' CHECK (section IN ('recent', 'pinned', 'automation')),
    automation_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    schedule_label TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cadu_conversation_organization_owner
    ON cadu_conversation_organization (user_id, client_id, section, updated_at DESC);
