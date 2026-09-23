-- Per-field reliability metadata for reproducible brand decisions.
ALTER TABLE cadu_workspace_brand_identity_fields
    ADD COLUMN IF NOT EXISTS field_category VARCHAR(32),
    ADD COLUMN IF NOT EXISTS value_origin VARCHAR(24) NOT NULL DEFAULT 'observed',
    ADD COLUMN IF NOT EXISTS reason_code VARCHAR(64),
    ADD COLUMN IF NOT EXISTS confidence_components JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS pipeline_version VARCHAR(64),
    ADD COLUMN IF NOT EXISTS contract_version VARCHAR(64),
    ADD COLUMN IF NOT EXISTS score_version VARCHAR(64),
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE cadu_workspace_brand_profile_snapshots
    ADD COLUMN IF NOT EXISTS pipeline_version VARCHAR(64),
    ADD COLUMN IF NOT EXISTS contract_version VARCHAR(64),
    ADD COLUMN IF NOT EXISTS score_version VARCHAR(64),
    ADD COLUMN IF NOT EXISTS evidence_hash VARCHAR(128);

ALTER TABLE cadu_workspace_brand_audit_sources
    ADD COLUMN IF NOT EXISTS canonical_url TEXT,
    ADD COLUMN IF NOT EXISTS authority VARCHAR(32) NOT NULL DEFAULT 'first_party',
    ADD COLUMN IF NOT EXISTS status VARCHAR(24) NOT NULL DEFAULT 'valid';

CREATE INDEX IF NOT EXISTS cadu_workspace_brand_identity_fields_status_idx
    ON cadu_workspace_brand_identity_fields
    (client_id, brand_id, field_category, status, confidence DESC);

CREATE INDEX IF NOT EXISTS cadu_workspace_brand_audit_sources_canonical_idx
    ON cadu_workspace_brand_audit_sources
    (client_id, brand_id, canonical_url);

-- Backfill every existing snapshot. Missing values are explicit states, not
-- absent rows; this makes historical coverage measurable immediately.
WITH metadata_fields(field_name) AS (
    VALUES
      ('name'), ('sector'), ('website_url'), ('brand_summary'), ('tone_of_voice'),
      ('target_audience'), ('audience_segments'), ('personas'), ('archetype'), ('ad_segments'),
      ('products_services'), ('differentiators'), ('proof_points'), ('competitors'),
      ('campaign_opportunities'), ('campaigns'), ('logo_url'), ('primary_color'),
      ('secondary_color'), ('color_palette'), ('product_palettes'), ('fonts'), ('visual_motifs'),
      ('mandatory_elements'), ('forbidden_elements'), ('creative_guidelines'), ('visual_opinions'),
      ('contacts'), ('addresses'), ('digital_policies'), ('social_links'), ('sources'),
      ('evidence_ledger'), ('field_provenance'), ('confidence'), ('quality_dimensions'),
      ('review_evidence_summary'), ('output_packages'), ('analysis_metadata')
), expanded AS (
    SELECT s.id AS snapshot_id, s.client_id, s.brand_id, s.profile,
           s.pipeline_version AS snapshot_pipeline_version,
           s.contract_version AS snapshot_contract_version,
           s.score_version AS snapshot_score_version,
           f.field_name,
           COALESCE(s.profile -> f.field_name, 'null'::jsonb) AS field_value,
           COALESCE(s.field_provenance -> f.field_name, '{}'::jsonb) AS provenance,
           EXISTS (
               SELECT 1
                 FROM jsonb_array_elements_text(COALESCE(
                     s.profile -> 'analysis_metadata' -> 'automatic_decision' -> 'blocked_fields',
                     '[]'::jsonb
                 )) blocked(value)
                WHERE blocked.value = f.field_name
                   OR split_part(blocked.value, ':', 1) = f.field_name
           ) AS decision_blocked
      FROM cadu_workspace_brand_profile_snapshots s
      CROSS JOIN metadata_fields f
)
INSERT INTO cadu_workspace_brand_identity_fields
    (client_id, brand_id, snapshot_id, field_name, field_category, value, value_origin,
     status, reason_code, confidence, confidence_components, evidence_ids, evidence_count,
     pipeline_version, contract_version, score_version, last_verified_at)
SELECT client_id, brand_id, snapshot_id, field_name,
       CASE
         WHEN field_name IN ('name','sector','website_url','brand_summary','tone_of_voice') THEN 'identity'
         WHEN field_name IN ('target_audience','audience_segments','personas','archetype','ad_segments') THEN 'audience'
         WHEN field_name IN ('products_services','differentiators','proof_points','competitors') THEN 'market'
         WHEN field_name IN ('campaign_opportunities','campaigns') THEN 'campaign'
         WHEN field_name IN ('logo_url','primary_color','secondary_color','color_palette','product_palettes','fonts',
                             'visual_motifs','mandatory_elements','forbidden_elements','creative_guidelines','visual_opinions') THEN 'visual'
         WHEN field_name IN ('contacts','addresses','digital_policies','social_links') THEN 'presence'
         ELSE 'governance'
       END,
       field_value,
       CASE WHEN field_name IN ('personas','archetype') THEN 'inferred'
            WHEN field_name = 'campaign_opportunities' THEN 'generated'
            ELSE 'observed' END,
       CASE
         WHEN decision_blocked THEN 'blocked'
         WHEN provenance ->> 'evidence_status' IN ('verified','partial','blocked','conflicting','invalid','not_found','not_applicable')
           THEN provenance ->> 'evidence_status'
         WHEN field_value IN ('null'::jsonb, '""'::jsonb, '[]'::jsonb, '{}'::jsonb) THEN 'not_found'
         ELSE 'partial'
       END AS status,
       CASE
         WHEN decision_blocked THEN 'evidence_gate_blocked'
         WHEN provenance ->> 'evidence_status' = 'blocked' THEN 'evidence_gate_blocked'
         WHEN provenance ->> 'evidence_status' = 'partial' THEN 'insufficient_direct_evidence'
         WHEN field_value IN ('null'::jsonb, '""'::jsonb, '[]'::jsonb, '{}'::jsonb) THEN 'no_evidence_found'
         ELSE NULL
       END,
       LEAST(1, GREATEST(0,
           CASE WHEN provenance ->> 'confidence' ~ '^[0-9]+([.][0-9]+)?$'
                THEN (provenance ->> 'confidence')::numeric ELSE 0 END
       )),
       jsonb_build_object(
           'evidence_status', COALESCE(provenance ->> 'evidence_status', 'unknown'),
           'source_count', COALESCE((provenance ->> 'source_count')::integer, 0),
           'backfilled', true
       ),
       COALESCE((
           SELECT jsonb_agg('source:' || substr(md5(url), 1, 16))
             FROM jsonb_array_elements_text(COALESCE(provenance -> 'source_urls', '[]'::jsonb)) urls(url)
       ), '[]'::jsonb),
       COALESCE((provenance ->> 'source_count')::integer, 0),
       COALESCE(snapshot_pipeline_version, profile -> 'analysis_metadata' ->> 'pipeline_version', 'legacy'),
       COALESCE(snapshot_contract_version, 'brand-metadata-v1-legacy'),
       COALESCE(snapshot_score_version, profile -> 'analysis_metadata' -> 'automatic_decision' ->> 'score_version', 'legacy'),
       CASE WHEN provenance ->> 'evidence_status' = 'verified' THEN NOW() ELSE NULL END
  FROM expanded
ON CONFLICT (brand_id, snapshot_id, field_name) DO UPDATE SET
    field_category = EXCLUDED.field_category,
    value = EXCLUDED.value,
    value_origin = EXCLUDED.value_origin,
    status = EXCLUDED.status,
    reason_code = EXCLUDED.reason_code,
    confidence = EXCLUDED.confidence,
    confidence_components = EXCLUDED.confidence_components,
    evidence_ids = EXCLUDED.evidence_ids,
    evidence_count = EXCLUDED.evidence_count,
    pipeline_version = EXCLUDED.pipeline_version,
    contract_version = EXCLUDED.contract_version,
    score_version = EXCLUDED.score_version,
    last_verified_at = EXCLUDED.last_verified_at,
    updated_at = NOW();
