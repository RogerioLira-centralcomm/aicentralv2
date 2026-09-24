-- Google Workspace access is scoped only by the Cadu client and authorizing
-- person. Remove the unused organization key so it cannot block OAuth saves.
ALTER TABLE google_workspace_connections
    DROP CONSTRAINT IF EXISTS google_workspace_connections_organization_id_key;

ALTER TABLE google_workspace_connections
    DROP COLUMN IF EXISTS organization_id;
