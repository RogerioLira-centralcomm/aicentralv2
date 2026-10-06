-- Índices das leituras por projeto do Workspace, validados com EXPLAIN ANALYZE em Postgres 17 local
-- (300 mil linhas por tabela, 300 projetos): Seq Scan -> Index Scan.
--   studio      203 ms -> 0,06 ms   (detalhe do projeto: ativos de Studio por workspace_project_ref)
--   artefatos   222 ms -> 0,25 ms   (client_id + project_ref)
--   memórias     28 ms -> 0,05 ms   (client_id + project_ref + status)
-- Os índices existentes começam por organization_id e não servem a consultas que filtram só por client_id.
-- Cada tabela é tratada só se existir, para bancos que ainda não receberam a migração dela.
DO $$
BEGIN
    IF to_regclass('public.cx_studio_sessions') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS idx_cx_studio_sessions_workspace_project_ref
            ON cx_studio_sessions ((metadata->>'workspace_project_ref'));
    END IF;
    IF to_regclass('public.cadu_workspace_artifacts') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS idx_cadu_workspace_artifacts_client_project
            ON cadu_workspace_artifacts (client_id, project_ref, updated_at DESC);
    END IF;
    IF to_regclass('public.cadu_working_memories') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS idx_cadu_working_memories_client_project
            ON cadu_working_memories (client_id, project_ref, status, updated_at DESC);
    END IF;
END
$$;
