-- Versioned manifests for the evidence and deterministic scenario updates.
-- Tool execution remains governed by the Python allowlist, not these manifests.
INSERT INTO cadu_chat_plugin_versions
    (plugin_id, version, maturity, description, manifest, changelog, is_current)
SELECT current.plugin_id, '1.2.0', current.maturity, current.description,
       CASE current.plugin_id
         WHEN 'investment-simulator' THEN
           jsonb_set(current.manifest, '{internal_tools}',
                     '["planner.research_plan_inputs","planner.simulate_investment"]'::jsonb, true)
         WHEN 'campaign-tracker' THEN
           jsonb_set(
             jsonb_set(current.manifest, '{internal_tools}', '[]'::jsonb, true),
             '{known_gaps}',
             '["Analisa somente o relatório anexado ou métricas fornecidas; não consulta Reports nem plataformas em tempo real."]'::jsonb,
             true)
       END,
       'Fontes e ferramentas declaradas alinhadas ao fluxo executado.', FALSE
  FROM cadu_chat_plugin_versions current
 WHERE current.plugin_id IN ('investment-simulator', 'campaign-tracker')
   AND current.is_current
   AND current.version IN ('1.0.0', '1.1.0')
ON CONFLICT (plugin_id, version) DO NOTHING;

UPDATE cadu_chat_plugin_versions old
   SET is_current = FALSE
 WHERE old.plugin_id IN ('investment-simulator', 'campaign-tracker')
   AND old.is_current
   AND old.version IN ('1.0.0', '1.1.0')
   AND EXISTS (SELECT 1 FROM cadu_chat_plugin_versions newer
                WHERE newer.plugin_id = old.plugin_id AND newer.version = '1.2.0');

UPDATE cadu_chat_plugin_versions current
   SET is_current = TRUE
 WHERE current.plugin_id IN ('investment-simulator', 'campaign-tracker')
   AND current.version = '1.2.0'
   AND NOT EXISTS (SELECT 1 FROM cadu_chat_plugin_versions newer
                    WHERE newer.plugin_id = current.plugin_id AND newer.is_current
                      AND newer.version NOT IN ('1.0.0', '1.1.0', '1.2.0'));
