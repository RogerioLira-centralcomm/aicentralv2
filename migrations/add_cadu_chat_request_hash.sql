-- Phase 3a: apply after add_cadu_family.sql, before deploying retry recovery.
-- Existing runs deliberately retain NULL: they cannot be safely replayed.
ALTER TABLE cadu_family_chat_runs ADD COLUMN IF NOT EXISTS request_hash TEXT;
