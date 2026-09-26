-- Optional, explicit association from an independent Reports campaign to a
-- Workspace project. Reports ownership and campaign identity remain separate.
ALTER TABLE cadu_reports_campaigns
    ADD COLUMN IF NOT EXISTS workspace_project_id VARCHAR(160);

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname='cadu_reports_campaign_workspace_project_fk'
           AND conrelid='public.cadu_reports_campaigns'::regclass
    ) THEN
        ALTER TABLE cadu_reports_campaigns
            ADD CONSTRAINT cadu_reports_campaign_workspace_project_fk
            FOREIGN KEY (workspace_project_id)
            REFERENCES cadu_ci_projetos(id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS cadu_reports_campaign_workspace_project_idx
    ON cadu_reports_campaigns (organization_id,client_id,workspace_project_id)
    WHERE workspace_project_id IS NOT NULL;
