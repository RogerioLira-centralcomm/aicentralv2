-- Queue V2 reconstruction from preserved project sources. Run after
-- add_cadu_project_index_jobs.sql and the V2 application code are deployed.
-- Existing completed chunks stay searchable until each replacement commits.
-- Do not truncate cadu_ci_chunks or remove original project files here.
INSERT INTO cadu_project_index_jobs
    (id, client_id, project_ref, source_id, operation, actor_id, status, created_at)
SELECT gen_random_uuid(), source.id_cliente, 'ci:' || source.projeto_id::text,
       source.id, 'reindex', source.criado_por, 'queued', NOW()
  FROM cadu_ci_projeto_arquivos source
 WHERE source.purpose='knowledge_source'
   AND source.indexing_status <> 'superseded'
   AND COALESCE(source.classification_metadata->>'rag_pipeline_version', '') <> 'workspace-rag-v2'
ON CONFLICT (client_id, project_ref, source_id, operation)
    WHERE status IN ('queued','running') DO NOTHING;
