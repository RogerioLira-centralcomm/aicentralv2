-- Additive identity and inventory status. Older readers continue using path_prefix.
ALTER TABLE cadu_reports_flow_discovered_pages ADD COLUMN IF NOT EXISTS locale TEXT;
ALTER TABLE cadu_reports_flow_discovered_pages ADD COLUMN IF NOT EXISTS normalized_path TEXT;
ALTER TABLE cadu_reports_flow_discovered_pages ADD COLUMN IF NOT EXISTS translation_key TEXT;
ALTER TABLE cadu_reports_flow_discovered_pages ADD COLUMN IF NOT EXISTS page_status TEXT NOT NULL DEFAULT 'valida';
CREATE INDEX IF NOT EXISTS cadu_reports_discovered_pages_norm_m2_idx
  ON cadu_reports_flow_discovered_pages (client_id,tag_id,run_id,normalized_path);
CREATE INDEX IF NOT EXISTS cadu_reports_discovered_pages_translation_m2_idx
  ON cadu_reports_flow_discovered_pages (client_id,tag_id,run_id,translation_key);
