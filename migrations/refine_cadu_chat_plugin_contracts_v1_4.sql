-- Align remaining plugin manifests with runtime allowlists and preserve any
-- later administrator-published version. The Python allowlist stays authoritative.
WITH current_plugins AS (
    SELECT current.*
      FROM cadu_chat_plugin_versions current
     WHERE current.is_current
       AND current.plugin_id IN ('channel-copy', 'creative-concept', 'planner', 'studio')
), revised AS (
    SELECT source.*,
           CASE source.plugin_id
             WHEN 'channel-copy' THEN '1.2.0'
             WHEN 'creative-concept' THEN '1.2.0'
             WHEN 'planner' THEN '0.3.0'
             WHEN 'studio' THEN '0.2.0'
           END AS next_version,
           CASE source.plugin_id
             WHEN 'channel-copy' THEN '["workspace.get_project_context","brands.get_context"]'::jsonb
             WHEN 'creative-concept' THEN '["workspace.get_project_context","brands.get_context"]'::jsonb
             WHEN 'planner' THEN '["workspace.search_project_content","brands.get_context","planner.research_plan_inputs","planner.search_catalog","planner.get_media_plan","artifacts.create_draft","artifacts.update_draft"]'::jsonb
             WHEN 'studio' THEN '["media.creation_capabilities"]'::jsonb
           END AS next_tools
      FROM current_plugins source
)
INSERT INTO cadu_chat_plugin_versions
    (plugin_id, version, maturity, description, manifest, changelog, is_current)
SELECT plugin_id, next_version, maturity, description,
       jsonb_set(manifest, '{internal_tools}', next_tools, true),
       'Manifesto alinhado às ferramentas realmente permitidas; ações pagas do Studio continuam no fluxo de aprovação.',
       FALSE
  FROM revised
ON CONFLICT (plugin_id, version) DO NOTHING;

UPDATE cadu_chat_plugin_versions old
   SET is_current = FALSE
 WHERE old.plugin_id IN ('channel-copy', 'creative-concept', 'planner', 'studio')
   AND old.is_current
   AND string_to_array(old.version, '.')::int[] < string_to_array(CASE old.plugin_id
         WHEN 'channel-copy' THEN '1.2.0'
         WHEN 'creative-concept' THEN '1.2.0'
         WHEN 'planner' THEN '0.3.0'
         WHEN 'studio' THEN '0.2.0'
       END, '.')::int[]
   AND EXISTS (
       SELECT 1 FROM cadu_chat_plugin_versions target
        WHERE target.plugin_id = old.plugin_id
          AND target.version = CASE old.plugin_id
                WHEN 'channel-copy' THEN '1.2.0'
                WHEN 'creative-concept' THEN '1.2.0'
                WHEN 'planner' THEN '0.3.0'
                WHEN 'studio' THEN '0.2.0'
              END
   );

UPDATE cadu_chat_plugin_versions target
   SET is_current = TRUE
 WHERE target.plugin_id IN ('channel-copy', 'creative-concept', 'planner', 'studio')
   AND target.version = CASE target.plugin_id
         WHEN 'channel-copy' THEN '1.2.0'
         WHEN 'creative-concept' THEN '1.2.0'
         WHEN 'planner' THEN '0.3.0'
         WHEN 'studio' THEN '0.2.0'
       END
   AND NOT EXISTS (
       SELECT 1 FROM cadu_chat_plugin_versions newer
        WHERE newer.plugin_id = target.plugin_id AND newer.is_current
          AND string_to_array(newer.version, '.')::int[] > string_to_array(CASE target.plugin_id
                WHEN 'channel-copy' THEN '1.2.0'
                WHEN 'creative-concept' THEN '1.2.0'
                WHEN 'planner' THEN '0.3.0'
                WHEN 'studio' THEN '0.2.0'
              END, '.')::int[]
   );
