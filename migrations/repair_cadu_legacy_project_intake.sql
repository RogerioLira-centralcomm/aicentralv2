-- Reconcile legacy chat uploads without silently promoting them to knowledge.
-- Safe to run repeatedly: links use their natural project/url key and files
-- already repaired no longer match the legacy/queued predicates.

INSERT INTO cadu_ci_projeto_links
    (id, projeto_id, id_cliente, criado_por, provider, url, titulo, position,
     created_at, updated_at)
SELECT gen_random_uuid(), file.projeto_id, file.id_cliente, file.criado_por,
       CASE
           WHEN file.nome_arquivo ~* '^https://(www\.)?drive\.google\.com/' THEN 'google_drive'
           WHEN file.nome_arquivo ~* '^https://(www\.)?trello\.com/' THEN 'trello'
           WHEN file.nome_arquivo ~* '^https://(www\.)?miro\.com/' THEN 'miro'
           WHEN file.nome_arquivo ~* '^https://(www\.)?clickup\.com/' THEN 'clickup'
           ELSE 'generic'
       END,
       file.nome_arquivo,
       LEFT(regexp_replace(file.nome_arquivo, '^https?://(www\.)?', '', 'i'), 180),
       COALESCE((SELECT MAX(link.position) + 1
                   FROM cadu_ci_projeto_links link
                  WHERE link.projeto_id=file.projeto_id
                    AND link.id_cliente=file.id_cliente), 0),
       file.created_at, NOW()
  FROM cadu_ci_projeto_arquivos file
 WHERE file.mime='text/uri-list'
   AND file.nome_arquivo ~* '^https://'
   AND NOT EXISTS (
       SELECT 1 FROM cadu_ci_projeto_links link
        WHERE link.projeto_id=file.projeto_id
          AND link.id_cliente=file.id_cliente
          AND link.url=file.nome_arquivo
   );

UPDATE cadu_ci_projeto_arquivos
   SET indexing_status='paused',
       purpose='project_attachment',
       category=CASE
           WHEN mime='text/uri-list' THEN 'reference'
           WHEN lower(nome_arquivo) ~ '\.(xlsx?|ods)$' THEN 'spreadsheet'
           WHEN lower(nome_arquivo) ~ '(logo|marca|brandbook|manual.de.marca)' THEN 'brand_asset'
           WHEN lower(nome_arquivo) ~ '(relat[oó]rio|report|dashboard)' THEN 'report'
           WHEN lower(nome_arquivo) ~ '(briefing|(^|[^a-z])brief([^a-z]|$))' THEN 'brief'
           WHEN lower(nome_arquivo) ~ '(plano.de.m[ií]dia|media.plan)' THEN 'media_plan'
           ELSE COALESCE(category, 'other')
       END,
       classification_status=CASE
           WHEN mime='text/uri-list'
             OR lower(nome_arquivo) ~ '\.(xlsx?|ods)$'
             OR lower(nome_arquivo) ~ '(logo|marca|brandbook|manual.de.marca|relat[oó]rio|report|dashboard|briefing|plano.de.m[ií]dia|media.plan)'
           THEN 'classified'
           ELSE 'needs_review'
       END,
       classification_confidence=CASE WHEN mime='text/uri-list' THEN 1 ELSE 0.82 END,
       classification_reason=CASE
           WHEN mime='text/uri-list' THEN 'Link legado preservado como referência do projeto.'
           ELSE 'Anexo legado preservado sem indexação automática; classificação reconciliada.'
       END,
       classification_metadata=COALESCE(classification_metadata, '{}'::jsonb)
           || '{"reconciled_by":"repair_cadu_legacy_project_intake","automatic_indexing":false}'::jsonb,
       updated_at=NOW()
 WHERE purpose='project_attachment'
   AND (indexing_status='queued' OR classification_status='legacy');

UPDATE cadu_workspace_ingestion_items item
   SET extraction_status='skipped',
       extraction_error=NULL,
       metadata=COALESCE(item.metadata, '{}'::jsonb)
           || jsonb_build_object('project_link_id', link.id::text),
       updated_at=NOW()
  FROM cadu_workspace_ingestion_sessions session,
       cadu_ci_projeto_links link
 WHERE item.session_id=session.id
   AND item.item_type='url'
   AND item.original_url=link.url
   AND item.client_id=link.id_cliente
   AND session.project_ref='ci:' || link.projeto_id::text
   AND item.extraction_status IN ('not_requested', 'queued', 'extracting');

UPDATE cadu_workspace_ingestion_sessions session
   SET status='completed', completed_at=COALESCE(completed_at, NOW()), updated_at=NOW()
 WHERE session.status='processing'
   AND EXISTS (
       SELECT 1 FROM cadu_workspace_ingestion_items item
        WHERE item.session_id=session.id
          AND item.item_type='url'
          AND item.extraction_status='skipped'
   );
