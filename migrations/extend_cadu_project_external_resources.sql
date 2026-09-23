-- Provider-neutral resources are canonical external references. The legacy
-- project-links table remains a compatibility projection for existing UI.
ALTER TABLE cadu_ci_projeto_links
    DROP CONSTRAINT IF EXISTS cadu_ci_projeto_links_provider_check;

ALTER TABLE cadu_ci_projeto_links
    ALTER COLUMN provider TYPE VARCHAR(64);

ALTER TABLE cadu_workspace_external_references
    DROP CONSTRAINT IF EXISTS cadu_workspace_external_references_reference_type_check,
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

-- Artifacts keep their lifecycle state when temporarily archived.
ALTER TABLE cadu_workspace_artifacts
    ADD COLUMN IF NOT EXISTS archived_from_status TEXT;

ALTER TABLE cadu_workspace_external_references
    ADD CONSTRAINT cadu_workspace_external_references_reference_type_check CHECK (
        reference_type IN (
            'web_page','document','spreadsheet','presentation','design','image','video','audio',
            'folder','board','campaign','dashboard','calendar_event','meeting','workspace_item',
            'ads_resource','social_or_ads','internal_resource','drive_file','event','other',
            'external_document'
        )
    );

UPDATE cadu_workspace_external_references
   SET reference_type = metadata->>'resource_kind', updated_at = NOW()
 WHERE metadata->>'resource_kind' IN (
    'web_page','document','spreadsheet','presentation','design','image','video','audio',
    'folder','board','campaign','dashboard','calendar_event','meeting','workspace_item',
    'ads_resource','social_or_ads','internal_resource','drive_file','event','other','external_document'
 ) AND reference_type IS DISTINCT FROM metadata->>'resource_kind';

CREATE INDEX IF NOT EXISTS idx_cadu_external_reference_locator
    ON cadu_workspace_external_references (client_id, project_ref, locator);

CREATE INDEX IF NOT EXISTS idx_cadu_external_reference_active
    ON cadu_workspace_external_references (client_id, project_ref, updated_at DESC)
    WHERE archived_at IS NULL;

-- One external item may legitimately participate in multiple projects. Its
-- association is unique only inside each project boundary.
DROP INDEX IF EXISTS idx_cadu_external_reference_dedupe;
CREATE UNIQUE INDEX idx_cadu_external_reference_dedupe
    ON cadu_workspace_external_references (client_id, project_ref, provider, external_id)
    WHERE external_id IS NOT NULL;
