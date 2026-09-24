-- Publish Google workflows without changing the executable MCP allowlist.
-- Keep the old planned integration for historical references, but hide it
-- from the storefront once the real workflows are available.
UPDATE cadu_chat_plugins SET enabled=FALSE, updated_at=NOW()
 WHERE id='google' AND kind='integration';

INSERT INTO cadu_chat_plugins (id, kind, name, category, sort_order, selectable) VALUES
 ('google-connect', 'plugin', 'Conectar Google', 'Google Workspace', 80, TRUE),
 ('google-drive', 'plugin', 'Google Drive', 'Google Workspace', 81, TRUE),
 ('google-calendar', 'plugin', 'Google Calendar', 'Google Workspace', 82, TRUE),
 ('google-meet', 'plugin', 'Google Meet', 'Google Workspace', 83, TRUE)
ON CONFLICT (id) DO UPDATE SET
 name=EXCLUDED.name, category=EXCLUDED.category, sort_order=EXCLUDED.sort_order,
 selectable=EXCLUDED.selectable, enabled=TRUE, updated_at=NOW();

UPDATE cadu_chat_plugin_versions SET is_current=FALSE
 WHERE plugin_id IN ('google-connect','google-drive','google-calendar','google-meet')
   AND version <> '1.0.0' AND is_current;

INSERT INTO cadu_chat_plugin_versions
 (plugin_id, version, maturity, description, manifest, changelog, is_current)
VALUES
 ('google-connect','1.0.0','active','Autorize sua própria conta Google neste cliente do Cadu e acompanhe o estado da conexão.',
  '{"triggers":["connect_google","google_connection_status"],"internal_tools":["google.get_connector_status"],"context":["client_id","current Cadu user"],"external_connectors":["Google Workspace OAuth"],"inputs":["autorização individual"],"outputs":["estado da conexão","próxima ação"],"known_gaps":[]}'::jsonb,
  'Conexão individual com retorno à conversa.',TRUE),
 ('google-drive','1.0.0','active','Encontre arquivos e pastas do Drive e associe originais a projetos por referência.',
  '{"triggers":["search_google_drive","list_google_project_resources"],"internal_tools":["google.get_connector_status","google.search_drive_resources","google.list_project_resources","google.link_resource_to_project"],"context":["client_id","current Cadu user","project for association"],"external_connectors":["Google Drive"],"inputs":["termo ou projeto"],"outputs":["arquivos e pastas originais","vínculo por referência"],"known_gaps":["Um arquivo compartilhado pode exigir permissão individual no Google."]}'::jsonb,
  'Busca e associação de arquivos originais.',TRUE),
 ('google-calendar','1.0.0','active','Consulte a agenda Google da sua conta e prepare reuniões do projeto.',
  '{"triggers":["list_google_calendar","create_google_meeting"],"internal_tools":["google.get_connector_status","google.list_calendar_events","google.create_project_meeting"],"context":["client_id","current Cadu user","project for meeting creation"],"external_connectors":["Google Calendar"],"inputs":["período","reunião confirmada"],"outputs":["eventos","convite após confirmação"],"known_gaps":[]}'::jsonb,
  'Agenda e reuniões mediante confirmação.',TRUE),
 ('google-meet','1.0.0','active','Consulte registros e artefatos do Google Meet disponíveis à sua conta.',
  '{"triggers":["list_google_meet"],"internal_tools":["google.get_connector_status","google.list_meet_records","google.list_meet_artifacts"],"context":["client_id","current Cadu user"],"external_connectors":["Google Meet"],"inputs":["reunião ou período"],"outputs":["registros e artefatos"],"known_gaps":["Transcrições são preparadas somente após ação explícita."]}'::jsonb,
  'Descoberta de registros e artefatos.',TRUE)
ON CONFLICT (plugin_id, version) DO UPDATE SET
 maturity=EXCLUDED.maturity, description=EXCLUDED.description,
 manifest=EXCLUDED.manifest, changelog=EXCLUDED.changelog, is_current=TRUE;
