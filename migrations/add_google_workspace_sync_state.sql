ALTER TABLE google_workspace_connections
    ADD COLUMN IF NOT EXISTS sync_state JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN google_workspace_connections.sync_state IS
    'Provider cursors for incremental Drive/Calendar synchronization; never stores OAuth secrets.';
