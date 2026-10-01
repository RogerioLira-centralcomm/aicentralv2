-- Watermark for the LLM memory extractor: each conversation is read once per
-- new message, never reprocessed from the start.
CREATE TABLE IF NOT EXISTS cadu_working_memory_extraction (
    conversation_id TEXT PRIMARY KEY REFERENCES cadu_conversations(id) ON DELETE CASCADE,
    last_sequence BIGINT NOT NULL DEFAULT 0,
    extractor_version VARCHAR(40) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
