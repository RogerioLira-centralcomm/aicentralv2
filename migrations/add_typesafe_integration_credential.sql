-- Obsoleto no deploy: use migrations/run_sync_integration_provider_check.py
-- (aplica integration_provider_check.sql).

INSERT INTO system_integration_credentials (provider, public_config, status)
VALUES ('typesafe', '{}'::jsonb, 'active')
ON CONFLICT (provider) DO NOTHING;
