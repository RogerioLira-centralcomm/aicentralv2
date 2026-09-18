ALTER TABLE cadu_workspace_email_events
    DROP CONSTRAINT IF EXISTS cadu_workspace_email_events_status_check;

ALTER TABLE cadu_workspace_email_events
    ADD COLUMN IF NOT EXISTS last_event_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_workspace_email_events_provider_message
    ON cadu_workspace_email_events (provider_message_id)
    WHERE provider_message_id IS NOT NULL;
