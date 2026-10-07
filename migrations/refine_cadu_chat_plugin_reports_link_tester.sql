-- Reports plugin 0.2.0: the manifest documents the Link Tester flows the runtime already allows
-- (list/get diagnostics as tools; test and AI review as user-approved paid actions). The Python allowlist stays
-- authoritative; this only removes the "runtime tools not documented" drift. Idempotent; keeps a later admin version.
INSERT INTO cadu_chat_plugin_versions
    (plugin_id, version, maturity, description, manifest, changelog, is_current)
SELECT current.plugin_id, '0.2.0', current.maturity,
       'Analisa relatórios revisados, compara com o plano e testa links: destino, medição de mídia (tags, IDs e Super Tag) e presença para agentes de IA, com revisão por IA sob confirmação.',
       jsonb_set(
         jsonb_set(current.manifest, '{internal_tools}',
                   '["reports.list_project_reports","reports.get_report_metrics","reports.compare_report_to_plan","reports.list_link_tests","reports.get_link_test"]'::jsonb, true),
         '{triggers}', '["analyze_report","compare_report_to_plan","link_test","link_review"]'::jsonb, true),
       'Link Tester no chat: teste de link e revisão por IA como ações aprovadas (cobradas nos créditos); diagnósticos listáveis e consultáveis.',
       FALSE
  FROM cadu_chat_plugin_versions current
 WHERE current.plugin_id = 'reports' AND current.is_current
   AND string_to_array(current.version, '.')::int[] < ARRAY[0,2,0]
ON CONFLICT (plugin_id, version) DO NOTHING;

UPDATE cadu_chat_plugin_versions old
   SET is_current = FALSE
 WHERE old.plugin_id = 'reports' AND old.is_current
   AND string_to_array(old.version, '.')::int[] < ARRAY[0,2,0]
   AND EXISTS (SELECT 1 FROM cadu_chat_plugin_versions target WHERE target.plugin_id = 'reports' AND target.version = '0.2.0');

UPDATE cadu_chat_plugin_versions target
   SET is_current = TRUE
 WHERE target.plugin_id = 'reports' AND target.version = '0.2.0'
   AND NOT EXISTS (SELECT 1 FROM cadu_chat_plugin_versions other WHERE other.plugin_id = 'reports' AND other.is_current);
