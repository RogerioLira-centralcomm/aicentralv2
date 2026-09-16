ALTER TABLE system_integration_credentials
    DROP CONSTRAINT IF EXISTS system_integration_credentials_provider_check;

ALTER TABLE system_integration_credentials
    ADD CONSTRAINT system_integration_credentials_provider_check
    CHECK (provider IN (
        'google_login_cadu', 'google_login_centralx', 'google_calendar',
        'higgsfield', 'openrouter', 'openai', 'firecrawl', 'brevo', 'd4sign', 'dify'
    ));

INSERT INTO system_integration_credentials (provider, public_config, status)
VALUES ('dify', '{"base_url":"https://api.dify.ai/v1"}'::jsonb, 'active')
ON CONFLICT (provider) DO NOTHING;
