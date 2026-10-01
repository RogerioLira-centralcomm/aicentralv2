-- v3 reads DOCX/PDF with structure and accepts XLSX/PPTX. Rebuild every source
-- from its preserved original; previous chunks stay searchable until each
-- replacement commits, and the rebuild is not billed to the customer.
INSERT INTO cadu_project_index_jobs
    (id, client_id, project_ref, source_id, operation, actor_id, status, created_at)
SELECT gen_random_uuid(), source.id_cliente, 'ci:' || source.projeto_id::text,
       source.id, 'rebuild_v2', source.criado_por, 'queued', NOW()
  FROM cadu_ci_projeto_arquivos source
 WHERE source.purpose='knowledge_source'
   AND source.indexing_status <> 'superseded'
   AND COALESCE(source.classification_metadata->>'rag_pipeline_version', '') <> 'workspace-rag-v3'
ON CONFLICT (client_id, project_ref, source_id, operation)
    WHERE status IN ('queued','running') DO NOTHING;
