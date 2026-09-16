ALTER TABLE system_integration_credentials
    DROP CONSTRAINT IF EXISTS system_integration_credentials_provider_check;

ALTER TABLE system_integration_credentials
    ADD CONSTRAINT system_integration_credentials_provider_check
    CHECK (provider IN (
        'google_login_cadu', 'google_login_centralx', 'google_calendar',
        'higgsfield', 'openrouter', 'openai', 'firecrawl', 'brevo', 'd4sign'
    ));

INSERT INTO system_integration_credentials (provider, public_config, status)
VALUES
    ('google_login_cadu', '{"redirect_uri":"https://auth.centralcomm.media/auth/google/callback"}'::jsonb, 'active'),
    ('google_login_centralx', '{"redirect_uri":"https://auth.centralcomm.media/auth/google/callback","allowed_domain":"centralcomm.media"}'::jsonb, 'active')
ON CONFLICT (provider) DO NOTHING;
