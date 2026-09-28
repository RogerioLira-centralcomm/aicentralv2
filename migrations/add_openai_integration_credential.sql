-- CHECK canônico: run_sync_integration_provider_check.py

INSERT INTO system_integration_credentials (provider, public_config, status)
VALUES ('openai', '{}'::jsonb, 'active')
ON CONFLICT (provider) DO NOTHING;
