INSERT INTO system_integration_credentials (provider, public_config, status)
VALUES ('brevo', '{}'::jsonb, 'active')
ON CONFLICT (provider) DO UPDATE SET
    status = 'active',
    updated_at = NOW();
