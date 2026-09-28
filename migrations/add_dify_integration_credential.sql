INSERT INTO system_integration_credentials (provider, public_config, status)
VALUES ('dify', '{"base_url":"https://api.dify.ai/v1"}'::jsonb, 'active')
ON CONFLICT (provider) DO NOTHING;
