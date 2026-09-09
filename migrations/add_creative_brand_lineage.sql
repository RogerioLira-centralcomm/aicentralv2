ALTER TABLE cx_client_brand_assets
    DROP CONSTRAINT IF EXISTS chk_cx_client_brand_asset_role;

ALTER TABLE cx_client_brand_assets
    ADD CONSTRAINT chk_cx_client_brand_asset_role
    CHECK (role IN ('logo', 'reference', 'creative'));

CREATE INDEX IF NOT EXISTS idx_cx_client_brand_assets_creative_line
    ON cx_client_brand_assets(client_id, created_at DESC)
    WHERE role = 'creative' AND status = 'approved';
