ALTER TABLE system_integration_credentials
    DROP CONSTRAINT IF EXISTS system_integration_credentials_provider_check;

ALTER TABLE system_integration_credentials
    ADD CONSTRAINT system_integration_credentials_provider_check
    CHECK (provider IN ('google_calendar', 'higgsfield', 'openrouter', 'd4sign'));
