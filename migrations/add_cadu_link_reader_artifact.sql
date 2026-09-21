-- Link-reader artifacts persist a user-owned reference in the personal space.
-- Existing rows and projects remain untouched.
ALTER TABLE cadu_workspace_artifacts DROP CONSTRAINT IF EXISTS cadu_workspace_artifacts_type_check;
ALTER TABLE cadu_workspace_artifacts ADD CONSTRAINT cadu_workspace_artifacts_type_check
    CHECK (type IN ('brief', 'document', 'note', 'executive_summary', 'media_plan', 'scenario', 'research', 'project_map', 'html', 'meeting_summary', 'meeting_agenda', 'link_reader'));
