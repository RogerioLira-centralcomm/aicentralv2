-- Async visual identity for project links; existing references remain intact.
ALTER TABLE cadu_ci_projeto_links
  ADD COLUMN IF NOT EXISTS icon_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS cadu_workspace_link_icon_jobs (
  id UUID PRIMARY KEY,
  client_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  target_type VARCHAR(12) NOT NULL CHECK (target_type IN ('dock', 'project')),
  target_id UUID NOT NULL,
  project_id TEXT,
  host TEXT NOT NULL,
  status VARCHAR(12) NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'running', 'completed', 'failed')),
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  claimed_at TIMESTAMPTZ,
  heartbeat_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS cadu_workspace_link_icon_jobs_active_idx
  ON cadu_workspace_link_icon_jobs (client_id, target_type, target_id)
  WHERE status IN ('queued', 'running');

CREATE INDEX IF NOT EXISTS cadu_workspace_link_icon_jobs_queue_idx
  ON cadu_workspace_link_icon_jobs (created_at, id)
  WHERE status = 'queued';
