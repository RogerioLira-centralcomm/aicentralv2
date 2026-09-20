-- Durable metadata and optional transcript text for Google Meet artifacts.
-- Content is fetched only by an explicit sync/link flow; discovery remains safe.

CREATE TABLE IF NOT EXISTS google_workspace_meeting_artifacts (
    id UUID PRIMARY KEY,
    connection_id UUID NOT NULL REFERENCES google_workspace_connections(id) ON DELETE CASCADE,
    conference_record VARCHAR(1024) NOT NULL,
    artifact_type VARCHAR(32) NOT NULL
        CHECK (artifact_type IN ('transcript','transcript_entry','recording','smart_note')),
    external_name VARCHAR(1024) NOT NULL,
    title VARCHAR(500),
    locator TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    content TEXT,
    content_hash CHAR(64),
    source_created_at TIMESTAMPTZ,
    source_updated_at TIMESTAMPTZ,
    status VARCHAR(24) NOT NULL DEFAULT 'discovered'
        CHECK (status IN ('discovered','fetched','linked','archived','error')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (connection_id, artifact_type, external_name)
);

CREATE INDEX IF NOT EXISTS idx_google_workspace_meet_artifacts_record
    ON google_workspace_meeting_artifacts (connection_id, conference_record, artifact_type);

CREATE INDEX IF NOT EXISTS idx_google_workspace_meet_artifacts_content
    ON google_workspace_meeting_artifacts (connection_id, status, updated_at DESC)
    WHERE content IS NOT NULL;
