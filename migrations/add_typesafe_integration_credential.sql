ALTER TABLE system_integration_credentials
    DROP CONSTRAINT IF EXISTS system_integration_credentials_provider_check;

ALTER TABLE system_integration_credentials
    ADD CONSTRAINT system_integration_credentials_provider_check
    CHECK (provider IN (
        'google_login_cadu', 'google_login_centralx', 'google_workspace',
        'google_calendar', 'higgsfield', 'openrouter', 'openai', 'typesafe',
        'firecrawl', 'dify', 'dify_cadu_chat', 'brevo', 'd4sign'
    ));
