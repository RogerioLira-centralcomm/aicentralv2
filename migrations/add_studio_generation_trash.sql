ALTER TABLE cx_studio_image_generations
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_cx_studio_image_generations_owner_library
    ON cx_studio_image_generations (client_id, user_id, created_at DESC)
    WHERE project_id IS NULL AND status = 'completed' AND deleted_at IS NULL;
