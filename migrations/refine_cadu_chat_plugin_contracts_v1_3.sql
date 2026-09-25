-- Align public plugin manifests with code allowlists and actual workflow behavior.
-- Manifests describe capabilities; the Python allowlist remains authoritative.
WITH current_plugins AS (
    SELECT current.*
      FROM cadu_chat_plugin_versions current
     WHERE current.is_current
       AND current.plugin_id IN (
           'market-radar', 'audience-map', 'investment-simulator', 'campaign-tracker',
           'page-review', 'meeting-copilot', 'client-delivery', 'insights',
           'campaign-search', 'project-search', 'market-intelligence'
       )
), revised AS (
    SELECT source.*,
           CASE source.plugin_id
             WHEN 'campaign-search' THEN '0.2.0'
             WHEN 'project-search' THEN '0.2.0'
             WHEN 'market-intelligence' THEN '1.1.0'
             WHEN 'investment-simulator' THEN '1.3.0'
             WHEN 'campaign-tracker' THEN '1.3.0'
             ELSE '1.2.0'
           END AS next_version,
           CASE source.plugin_id
             WHEN 'market-radar' THEN '["web.search","brands.get_context"]'::jsonb
             WHEN 'audience-map' THEN '["web.search","planner.research_plan_inputs","workspace.get_project_context","brands.get_context"]'::jsonb
             WHEN 'investment-simulator' THEN '["planner.research_plan_inputs","planner.simulate_investment","workspace.get_project_context","brands.get_context"]'::jsonb
             WHEN 'campaign-tracker' THEN '["campaign.review_supplied_metrics"]'::jsonb
             WHEN 'page-review' THEN '["web.read","workspace.get_project_context","brands.get_context"]'::jsonb
             WHEN 'meeting-copilot' THEN '["google.list_meet_artifacts","workspace.get_project_context","brands.get_context"]'::jsonb
             WHEN 'client-delivery' THEN '["projects.list_tasks","projects.list_resources","workspace.get_project_context","brands.get_context"]'::jsonb
             WHEN 'insights' THEN '["workspace.get_project_context","brands.get_context","insights.research_market"]'::jsonb
             WHEN 'campaign-search' THEN '["brands.get_context","workspace.search_project_content"]'::jsonb
             WHEN 'project-search' THEN '["workspace.search_project_content","workspace.get_project_context","projects.search_knowledge","projects.list_resources","resources.search","projects.get_source_chunks","artifacts.list"]'::jsonb
             WHEN 'market-intelligence' THEN '[]'::jsonb
           END AS next_tools
      FROM current_plugins source
)
INSERT INTO cadu_chat_plugin_versions
    (plugin_id, version, maturity, description, manifest, changelog, is_current)
SELECT plugin_id, next_version, maturity,
       CASE plugin_id
         WHEN 'campaign-tracker' THEN 'Analisa relatórios anexados ou métricas fornecidas na conversa e sugere próximos passos.'
         WHEN 'campaign-search' THEN 'Busca campanhas, cases e recursos na marca ou no projeto selecionado.'
         ELSE description
       END,
       jsonb_set(
         CASE plugin_id
           WHEN 'campaign-tracker' THEN jsonb_set(
             jsonb_set(manifest, '{inputs}', '["report attachment or supplied metrics"]'::jsonb, true),
             '{known_gaps}', '["Não consulta o módulo Reports nem plataformas de mídia em tempo real."]'::jsonb, true)
           WHEN 'campaign-search' THEN jsonb_set(manifest, '{known_gaps}', '["Busca limitada à marca ou projeto selecionado; não pesquisa entre projetos."]'::jsonb, true)
           ELSE manifest
         END,
         '{internal_tools}', next_tools, true
       ),
       CASE plugin_id
         WHEN 'market-intelligence' THEN 'Manifesto alinhado à execução worker; Firecrawl e OpenRouter são dependências internas do fluxo, não MCPs externos dinâmicos.'
         ELSE 'Manifesto sincronizado com a allowlist e os limites de execução do fluxo.'
       END, FALSE
  FROM revised
ON CONFLICT (plugin_id, version) DO NOTHING;

UPDATE cadu_chat_plugin_versions old
   SET is_current = FALSE
 WHERE old.plugin_id IN (
       'market-radar', 'audience-map', 'investment-simulator', 'campaign-tracker',
       'page-review', 'meeting-copilot', 'client-delivery', 'insights',
       'campaign-search', 'project-search', 'market-intelligence'
   )
   AND old.is_current
   AND string_to_array(old.version, '.')::int[] < string_to_array(CASE old.plugin_id
         WHEN 'campaign-search' THEN '0.2.0'
         WHEN 'project-search' THEN '0.2.0'
         WHEN 'market-intelligence' THEN '1.1.0'
         WHEN 'investment-simulator' THEN '1.3.0'
         WHEN 'campaign-tracker' THEN '1.3.0'
         ELSE '1.2.0'
       END, '.')::int[]
   AND EXISTS (
       SELECT 1 FROM cadu_chat_plugin_versions newer
        WHERE newer.plugin_id = old.plugin_id
          AND newer.version = CASE old.plugin_id
                WHEN 'campaign-search' THEN '0.2.0'
                WHEN 'project-search' THEN '0.2.0'
                WHEN 'market-intelligence' THEN '1.1.0'
                WHEN 'investment-simulator' THEN '1.3.0'
                WHEN 'campaign-tracker' THEN '1.3.0'
                ELSE '1.2.0'
              END
   );

UPDATE cadu_chat_plugin_versions current
   SET is_current = TRUE
 WHERE current.plugin_id IN (
       'market-radar', 'audience-map', 'investment-simulator', 'campaign-tracker',
       'page-review', 'meeting-copilot', 'client-delivery', 'insights',
       'campaign-search', 'project-search', 'market-intelligence'
   )
   AND current.version = CASE current.plugin_id
         WHEN 'campaign-search' THEN '0.2.0'
         WHEN 'project-search' THEN '0.2.0'
         WHEN 'market-intelligence' THEN '1.1.0'
         WHEN 'investment-simulator' THEN '1.3.0'
         WHEN 'campaign-tracker' THEN '1.3.0'
         ELSE '1.2.0'
       END
   AND NOT EXISTS (
       SELECT 1 FROM cadu_chat_plugin_versions newer
        WHERE newer.plugin_id = current.plugin_id AND newer.is_current
          AND string_to_array(newer.version, '.')::int[] > string_to_array(CASE current.plugin_id
                WHEN 'campaign-search' THEN '0.2.0'
                WHEN 'project-search' THEN '0.2.0'
                WHEN 'market-intelligence' THEN '1.1.0'
                WHEN 'investment-simulator' THEN '1.3.0'
                WHEN 'campaign-tracker' THEN '1.3.0'
                ELSE '1.2.0'
              END, '.')::int[]
   );
