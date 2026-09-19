-- Separate the user's intent from the technical indexing lifecycle.
-- Classification is descriptive: it must never promote an attachment to a
-- knowledge source without an explicit user choice.
ALTER TABLE cadu_ci_projeto_arquivos
    ADD COLUMN IF NOT EXISTS purpose VARCHAR(32),
    ADD COLUMN IF NOT EXISTS category VARCHAR(40),
    ADD COLUMN IF NOT EXISTS classification_status VARCHAR(24) NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS classification_confidence NUMERIC(4,3),
    ADD COLUMN IF NOT EXISTS classification_reason TEXT,
    ADD COLUMN IF NOT EXISTS classification_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE cadu_ci_projeto_arquivos
   SET purpose = CASE WHEN indexing_status = 'completed' THEN 'knowledge_source' ELSE 'project_attachment' END
 WHERE purpose IS NULL;

UPDATE cadu_ci_projeto_arquivos
   SET category = 'other',
       classification_status = 'legacy',
       classification_confidence = 0
 WHERE category IS NULL;

ALTER TABLE cadu_ci_projeto_arquivos
    ALTER COLUMN purpose SET NOT NULL,
    ALTER COLUMN purpose SET DEFAULT 'project_attachment',
    ALTER COLUMN category SET NOT NULL,
    ALTER COLUMN category SET DEFAULT 'other';

CREATE INDEX IF NOT EXISTS idx_cadu_ci_project_files_purpose
    ON cadu_ci_projeto_arquivos (projeto_id, id_cliente, purpose, category, created_at DESC);

