INSERT INTO system_integration_credentials (provider, public_config, status)
VALUES (
    'openrouter',
    jsonb_build_object(
        'default_model', 'openai/gpt-4o-mini',
        'image_model', 'openai/gpt-image-2'
    ),
    'active'
)
ON CONFLICT (provider) DO UPDATE SET
    public_config = COALESCE(system_integration_credentials.public_config, '{}'::jsonb)
        || jsonb_build_object('image_model', 'openai/gpt-image-2'),
    status = 'active',
    updated_at = NOW();
