-- Preserve source dimensions (for example, ad/creative name) beside each
-- channel-specific key/value metric so imported detail remains explainable.
ALTER TABLE cadu_reports_import_custom_values
  ADD COLUMN IF NOT EXISTS dimensions JSONB NOT NULL DEFAULT '{}'::jsonb;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
      WHERE conname='cadu_reports_import_custom_values_dimensions_object_check') THEN
    ALTER TABLE cadu_reports_import_custom_values
      ADD CONSTRAINT cadu_reports_import_custom_values_dimensions_object_check
      CHECK (jsonb_typeof(dimensions)='object');
  END IF;
END $$;

UPDATE cadu_reports_import_custom_values v
SET dimensions=CASE
    WHEN jsonb_typeof(r.parsed->'source_dimensions')='object'
         AND r.parsed->'source_dimensions'<>'{}'::jsonb
      THEN r.parsed->'source_dimensions'
    WHEN COALESCE(r.raw->>'Anúncios','')<>''
      THEN jsonb_build_object('anuncios',jsonb_build_object('label','Anúncios','value',r.raw->>'Anúncios'))
    ELSE '{}'::jsonb END
FROM cadu_reports_import_rows r
WHERE r.id=v.import_row_id AND r.organization_id=v.organization_id
  AND r.client_id=v.client_id AND v.dimensions='{}'::jsonb
  AND ((r.parsed ? 'source_dimensions' AND r.parsed->'source_dimensions'<>'{}'::jsonb)
       OR COALESCE(r.raw->>'Anúncios','')<>'');
