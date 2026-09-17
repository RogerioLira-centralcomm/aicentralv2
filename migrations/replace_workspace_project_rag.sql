-- Replace the placeholder Workspace RAG.  The prior rows stored no vectors
-- (embedding='[]', dim=0) and are intentionally discarded with approval.
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE cadu_ci_projeto_arquivos
    ADD COLUMN IF NOT EXISTS extracted_text TEXT;

-- Notes have no original file. Preserve their extracted source text before
-- deleting the unusable old chunks, so they can be reindexed afterwards.
UPDATE cadu_ci_projeto_arquivos f
   SET extracted_text = grouped.content
  FROM (
        SELECT arquivo_id, string_agg(conteudo, E'\n\n' ORDER BY ordem) AS content
          FROM cadu_ci_chunks
         WHERE arquivo_id IS NOT NULL
         GROUP BY arquivo_id
       ) grouped
 WHERE f.id = grouped.arquivo_id
   AND COALESCE(f.extracted_text, '') = '';

TRUNCATE TABLE cadu_ci_chunks;

ALTER TABLE cadu_ci_chunks
    DROP COLUMN IF EXISTS embedding_norm,
    DROP COLUMN IF EXISTS dim,
    DROP COLUMN IF EXISTS modelo,
    DROP COLUMN IF EXISTS embedding;

ALTER TABLE cadu_ci_chunks
    ADD COLUMN embedding vector(1536) NOT NULL,
    ADD COLUMN embedding_model VARCHAR(120) NOT NULL,
    ADD COLUMN content_hash CHAR(64) NOT NULL,
    ADD COLUMN search_vector tsvector NOT NULL DEFAULT ''::tsvector;

CREATE INDEX IF NOT EXISTS idx_cadu_ci_chunks_project_lexical
    ON cadu_ci_chunks USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_cadu_ci_chunks_project_vector
    ON cadu_ci_chunks USING hnsw (embedding vector_cosine_ops);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cadu_ci_chunks_source_hash
    ON cadu_ci_chunks (arquivo_id, content_hash);

-- Files remain private and downloadable, but must be explicitly reprocessed
-- so the new, real embedding is generated from their current content.
UPDATE cadu_ci_projeto_arquivos
   SET indexing_status = 'queued', tokens = 0, erro_msg = NULL, updated_at = NOW();
