-- Manual rollback for add_cadu_link_reader_artifact.sql.
-- Never remove a valid type while rows still depend on it.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM cadu_workspace_artifacts WHERE type = 'link_reader') THEN
        RAISE EXCEPTION 'Rollback bloqueado: existem artefatos link_reader. Arquive ou migre esses registros antes de remover o tipo.';
    END IF;
END $$;

ALTER TABLE cadu_workspace_artifacts DROP CONSTRAINT IF EXISTS cadu_workspace_artifacts_type_check;
ALTER TABLE cadu_workspace_artifacts ADD CONSTRAINT cadu_workspace_artifacts_type_check
    CHECK (type IN ('brief', 'document', 'note', 'executive_summary', 'media_plan', 'scenario', 'research', 'project_map', 'html', 'meeting_summary', 'meeting_agenda'));
