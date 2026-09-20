ALTER TABLE cx_studio_delivery_outbox ALTER COLUMN finalization_id DROP NOT NULL;
ALTER TABLE cx_studio_delivery_outbox ADD COLUMN IF NOT EXISTS session_id UUID REFERENCES cx_studio_sessions(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_cx_studio_delivery_outbox_session ON cx_studio_delivery_outbox (session_id) WHERE session_id IS NOT NULL;
