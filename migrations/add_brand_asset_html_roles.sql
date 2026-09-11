ALTER TABLE cx_client_brand_assets
    DROP CONSTRAINT IF EXISTS chk_cx_client_brand_asset_role;

ALTER TABLE cx_client_brand_assets
    ADD CONSTRAINT chk_cx_client_brand_asset_role
    CHECK (role IN (
        'logo',
        'reference',
        'creative',
        'background',
        'support',
        'icon',
        'cta_style'
    ));
