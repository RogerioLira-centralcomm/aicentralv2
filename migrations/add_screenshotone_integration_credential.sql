-- ScreenshotOne no cofre de credenciais: prints desktop e mobile do Link Tester (URLs assinadas).
INSERT INTO system_integration_credentials (provider, public_config, status)
VALUES ('screenshotone', '{}'::jsonb, 'active')
ON CONFLICT (provider) DO UPDATE SET
    status = 'active',
    updated_at = NOW();
