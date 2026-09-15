ALTER TABLE system_integration_credentials
    DROP CONSTRAINT IF EXISTS system_integration_credentials_provider_check;

ALTER TABLE system_integration_credentials
    ADD CONSTRAINT system_integration_credentials_provider_check
    CHECK (provider IN (
        'google_login_cadu', 'google_login_centralx', 'google_calendar',
        'higgsfield', 'openrouter', 'openai', 'firecrawl', 'd4sign'
    ));

INSERT INTO system_integration_credentials (provider, public_config, status)
VALUES ('firecrawl', '{}'::jsonb, 'active')
ON CONFLICT (provider) DO UPDATE SET
    status = 'active',
    updated_at = NOW();
