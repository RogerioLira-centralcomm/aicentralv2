-- Fluxos em modo plano: nascem sem site e sem tag interna. Só podem ser publicados
-- (ligar a medição) depois de conectar um site; a coleta continua exigindo tag.
ALTER TABLE cadu_reports_flow_registry ALTER COLUMN tag_id DROP NOT NULL;
ALTER TABLE cadu_reports_flow_registry ALTER COLUMN site_id DROP NOT NULL;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'reports_flow_plan_only_site') THEN
        ALTER TABLE cadu_reports_flow_registry ADD CONSTRAINT reports_flow_plan_only_site
            CHECK ((tag_id IS NULL) = (site_id IS NULL) AND (tag_id IS NOT NULL OR status = 'draft'));
    END IF;
END $$;
