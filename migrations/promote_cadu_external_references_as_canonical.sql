-- Promote provider-neutral external references to the only write model for
-- project links. cadu_ci_projeto_links remains read-only during migration so
-- old rows can still be displayed and reconciled.

ALTER TABLE cadu_workspace_external_references
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

ALTER TABLE cadu_workspace_external_references
    DROP CONSTRAINT IF EXISTS cadu_workspace_external_references_reference_type_check;

ALTER TABLE cadu_workspace_external_references
    ADD CONSTRAINT cadu_workspace_external_references_reference_type_check CHECK (
        reference_type IN (
            'web_page','document','spreadsheet','presentation','design','image','video','audio',
            'folder','board','campaign','dashboard','calendar_event','meeting','workspace_item',
            'ads_resource','social_or_ads','internal_resource','drive_file','event','other',
            'external_document'
        )
    );

DROP INDEX IF EXISTS idx_cadu_external_reference_dedupe;
CREATE UNIQUE INDEX IF NOT EXISTS idx_cadu_external_reference_project_locator
    ON cadu_workspace_external_references (client_id, project_ref, locator)
    WHERE archived_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_cadu_external_reference_provider_id
    ON cadu_workspace_external_references (client_id, project_ref, provider, external_id)
    WHERE external_id IS NOT NULL AND archived_at IS NULL;

-- Import historical shortcuts once. The canonical id is deterministic, so the
-- migration is repeatable and never duplicates a legacy row.
INSERT INTO cadu_workspace_external_references
    (id, client_id, project_ref, ingestion_item_id, provider, external_id, locator,
     connection_ref, reference_type, sync_status, metadata, created_at, updated_at)
SELECT
    link.id,
    link.id_cliente,
    'ci:' || link.projeto_id::text,
    NULL,
    CASE WHEN link.provider = 'generic' THEN 'generic' ELSE link.provider END,
    NULL,
    link.url,
    NULL,
    CASE WHEN link.provider = 'google_drive' THEN 'drive_file' ELSE 'web_page' END,
    'pending',
    jsonb_strip_nulls(jsonb_build_object(
        'title', link.titulo,
        'platform', link.provider,
        'resource_kind', CASE WHEN link.provider = 'google_drive' THEN 'drive_file' ELSE 'web_page' END,
        'origin', 'legacy_migration',
        'icon', to_jsonb(link)->'icon_metadata'
    )),
    link.created_at,
    link.updated_at
FROM cadu_ci_projeto_links link
ON CONFLICT (id) DO NOTHING;

