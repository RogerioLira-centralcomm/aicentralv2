-- Retrievable excerpts of chat conversations (6 messages each). The transcript
-- in cadu_conversation_messages stays authoritative; rows are rebuildable.
-- The project is resolved at query time through
-- cadu_family_conversation_context, so rebinding a conversation needs no reindex.
-- No HNSW index: searches are always filtered by client and project, and an
-- exact scan over that subset avoids the recall loss of a filtered ANN index.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS cadu_conversation_chunks (
    id BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES cadu_conversations(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    segment_index INTEGER NOT NULL CHECK (segment_index >= 0),
    first_sequence BIGINT NOT NULL,
    last_sequence BIGINT NOT NULL,
    message_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    content TEXT NOT NULL,
    content_hash CHAR(64) NOT NULL,
    search_vector tsvector NOT NULL DEFAULT ''::tsvector,
    embedding vector(1536),
    embedding_model VARCHAR(120),
    last_message_at TIMESTAMPTZ,
    index_version VARCHAR(40) NOT NULL,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (conversation_id, segment_index)
);

CREATE INDEX IF NOT EXISTS idx_cadu_conversation_chunks_client
    ON cadu_conversation_chunks (client_id, conversation_id);
CREATE INDEX IF NOT EXISTS idx_cadu_conversation_chunks_lexical
    ON cadu_conversation_chunks USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_cadu_family_conversation_context_project
    ON cadu_family_conversation_context (client_id, project_ref)
    WHERE project_ref IS NOT NULL;
