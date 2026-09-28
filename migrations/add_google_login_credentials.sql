INSERT INTO system_integration_credentials (provider, public_config, status)
VALUES
    ('google_login_cadu', '{"redirect_uri":"https://auth.centralcomm.media/auth/google/callback"}'::jsonb, 'active'),
    ('google_login_centralx', '{"redirect_uri":"https://auth.centralcomm.media/auth/google/callback","allowed_domain":"centralcomm.media"}'::jsonb, 'active')
ON CONFLICT (provider) DO NOTHING;
