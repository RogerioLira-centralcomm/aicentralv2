-- Google Workspace authorizations belong to a Cadu client and the individual
-- Cadu user who granted consent; client_id is the tenant boundary.
ALTER TABLE google_workspace_connections
    DROP CONSTRAINT IF EXISTS google_workspace_connections_organization_id_key;

ALTER TABLE google_workspace_connections
    DROP CONSTRAINT IF EXISTS google_workspace_connections_client_id_key;

CREATE UNIQUE INDEX IF NOT EXISTS idx_google_workspace_connections_client_authorizer
    ON google_workspace_connections (client_id, created_by)
    WHERE created_by IS NOT NULL;

COMMENT ON COLUMN google_workspace_connections.created_by IS
    'Cadu user who authorized this Google account; Google access is scoped by client_id and this user.';
