-- Add the read-only calculation review for metrics pasted into chat.
-- Tool authorization remains in the Python registry and plugin allowlist.
INSERT INTO cadu_chat_plugin_versions
    (plugin_id, version, maturity, description, manifest, changelog, is_current)
SELECT current.plugin_id, '1.3.0', current.maturity, current.description,
       jsonb_set(
         jsonb_set(current.manifest, '{internal_tools}',
                   '["campaign.review_supplied_metrics"]'::jsonb, true),
         '{known_gaps}',
         '["Relatórios anexados são interpretados pelo agente; cálculos a partir de métricas coladas no chat são condicionais ao mesmo período e escopo. Não consulta Reports nem plataformas em tempo real."]'::jsonb,
         true),
       'Revisão numérica de métricas fornecidas sem acesso implícito a plataformas.', FALSE
  FROM cadu_chat_plugin_versions current
 WHERE current.plugin_id = 'campaign-tracker'
   AND current.version = '1.2.0'
ON CONFLICT (plugin_id, version) DO NOTHING;

UPDATE cadu_chat_plugin_versions
   SET is_current = FALSE
 WHERE plugin_id = 'campaign-tracker' AND version = '1.2.0'
   AND EXISTS (SELECT 1 FROM cadu_chat_plugin_versions newer
                WHERE newer.plugin_id = 'campaign-tracker' AND newer.version = '1.3.0');

UPDATE cadu_chat_plugin_versions
   SET is_current = TRUE
 WHERE plugin_id = 'campaign-tracker' AND version = '1.3.0'
   AND NOT EXISTS (SELECT 1 FROM cadu_chat_plugin_versions newer
                    WHERE newer.plugin_id = 'campaign-tracker' AND newer.is_current
                      AND newer.version <> '1.3.0');
