-- Conversations V2 is additive. Legacy chat tables and Dify state remain valid.
-- The legacy document generator already owns `cadu_artifacts`. Conversations
-- V2 uses an explicitly Workspace-scoped name instead of mutating that schema.
CREATE TABLE IF NOT EXISTS cadu_workspace_artifacts (
    id UUID PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    project_ref TEXT,
    conversation_id TEXT REFERENCES cadu_conversations(id),
    type TEXT NOT NULL CHECK (type IN ('brief', 'document', 'note', 'executive_summary', 'media_plan', 'scenario', 'research', 'project_map', 'html', 'meeting_summary', 'meeting_agenda')),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'published', 'archived')),
    current_version INTEGER NOT NULL DEFAULT 1 CHECK (current_version > 0),
    created_by INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE cadu_workspace_artifacts DROP CONSTRAINT IF EXISTS cadu_workspace_artifacts_type_check;
ALTER TABLE cadu_workspace_artifacts ADD CONSTRAINT cadu_workspace_artifacts_type_check
    CHECK (type IN ('brief', 'document', 'note', 'executive_summary', 'media_plan', 'scenario', 'research', 'project_map', 'html', 'meeting_summary', 'meeting_agenda'));
CREATE INDEX IF NOT EXISTS cadu_workspace_artifacts_scope
    ON cadu_workspace_artifacts (organization_id, client_id, project_ref, updated_at DESC);
CREATE INDEX IF NOT EXISTS cadu_workspace_artifacts_conversation
    ON cadu_workspace_artifacts (conversation_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS cadu_workspace_artifact_versions (
    id UUID PRIMARY KEY,
    artifact_id UUID NOT NULL REFERENCES cadu_workspace_artifacts(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    content JSONB NOT NULL,
    change_summary TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (artifact_id, version)
);

CREATE TABLE IF NOT EXISTS cadu_agent_tool_calls (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES cadu_family_chat_runs(id),
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    input_redacted JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS cadu_agent_tool_calls_run
    ON cadu_agent_tool_calls (run_id, created_at);

ALTER TABLE cadu_family_chat_runs ADD COLUMN IF NOT EXISTS runtime_version TEXT NOT NULL DEFAULT 'legacy';
ALTER TABLE cadu_family_chat_runs ADD COLUMN IF NOT EXISTS route JSONB;
ALTER TABLE cadu_family_chat_runs ADD COLUMN IF NOT EXISTS request_context JSONB;
ALTER TABLE cadu_family_chat_runs ADD COLUMN IF NOT EXISTS response_policy JSONB;
ALTER TABLE cadu_family_chat_runs ADD COLUMN IF NOT EXISTS context_chars INTEGER;
ALTER TABLE cadu_family_chat_runs ADD COLUMN IF NOT EXISTS first_token_ms INTEGER;
ALTER TABLE cadu_family_chat_runs ADD COLUMN IF NOT EXISTS total_duration_ms INTEGER;
