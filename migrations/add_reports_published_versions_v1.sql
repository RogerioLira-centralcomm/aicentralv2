-- Reports: publicação com versão congelada, link principal, senha opcional e relatórios principais.
-- A versão publicada guarda o documento e o retrato dos resultados; editar depois não muda o link até nova publicação.
ALTER TABLE cadu_connect_report_workspace_versions ADD COLUMN IF NOT EXISTS snapshot JSONB;
ALTER TABLE cadu_connect_report_workspace_versions ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
ALTER TABLE cadu_connect_report_workspace_versions ADD COLUMN IF NOT EXISTS published_by INTEGER;
ALTER TABLE cadu_connect_report_workspaces ADD COLUMN IF NOT EXISTS published_revision INTEGER;
ALTER TABLE cadu_connect_report_workspaces ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE cadu_connect_report_public_links ADD COLUMN IF NOT EXISTS password_hash TEXT;
CREATE INDEX IF NOT EXISTS cadu_connect_report_versions_published_idx
    ON cadu_connect_report_workspace_versions (report_id, revision) WHERE published_at IS NOT NULL;
-- Senha do link: tentativas erradas bloqueiam por 15 minutos depois de 5 erros.
ALTER TABLE cadu_connect_report_public_links ADD COLUMN IF NOT EXISTS failed_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cadu_connect_report_public_links ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ;
