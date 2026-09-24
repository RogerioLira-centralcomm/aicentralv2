-- Conversation organization, unread state, branches and revocable read-only shares.
-- Existing conversation rows and the recent/pinned/automation behavior remain valid.

CREATE TABLE IF NOT EXISTS cadu_conversation_sections (
    id UUID PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    name VARCHAR(64) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (length(trim(name)) BETWEEN 1 AND 64)
);
CREATE UNIQUE INDEX IF NOT EXISTS cadu_conversation_sections_owner_name
    ON cadu_conversation_sections (organization_id, client_id, user_id, lower(name));
CREATE INDEX IF NOT EXISTS cadu_conversation_sections_order
    ON cadu_conversation_sections (organization_id, client_id, user_id, sort_order, name);

-- The organization table was an optional earlier migration. Create its base
-- shape here too so this migration can safely bootstrap a fresh environment.
CREATE TABLE IF NOT EXISTS cadu_conversation_organization (
    conversation_id TEXT PRIMARY KEY REFERENCES cadu_conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    section TEXT NOT NULL DEFAULT 'recent' CHECK (section IN ('recent', 'pinned', 'automation')),
    automation_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    schedule_label TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cadu_conversation_organization_owner
    ON cadu_conversation_organization (user_id, client_id, section, updated_at DESC);

ALTER TABLE cadu_conversation_organization
    ADD COLUMN IF NOT EXISTS custom_section_id UUID REFERENCES cadu_conversation_sections(id);
ALTER TABLE cadu_conversation_organization
    ADD COLUMN IF NOT EXISTS is_unread BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE cadu_conversation_organization
    DROP CONSTRAINT IF EXISTS cadu_conversation_organization_section_check;
ALTER TABLE cadu_conversation_organization
    ADD CONSTRAINT cadu_conversation_organization_section_check
    CHECK (section IN ('recent', 'pinned', 'automation', 'custom'));
ALTER TABLE cadu_conversation_organization
    DROP CONSTRAINT IF EXISTS cadu_conversation_organization_custom_section_check;
ALTER TABLE cadu_conversation_organization
    ADD CONSTRAINT cadu_conversation_organization_custom_section_check
    CHECK ((section = 'custom') = (custom_section_id IS NOT NULL));
CREATE INDEX IF NOT EXISTS cadu_conversation_organization_custom_section
    ON cadu_conversation_organization (user_id, client_id, custom_section_id, updated_at DESC);

ALTER TABLE cadu_conversations
    ADD COLUMN IF NOT EXISTS parent_conversation_id TEXT REFERENCES cadu_conversations(id) ON DELETE SET NULL;
ALTER TABLE cadu_conversations
    ADD COLUMN IF NOT EXISTS forked_from_sequence BIGINT;

CREATE TABLE IF NOT EXISTS cadu_conversation_shares (
    id UUID PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES cadu_conversations(id) ON DELETE CASCADE,
    organization_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    token_hash CHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '30 days',
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (expires_at > created_at)
);
CREATE INDEX IF NOT EXISTS cadu_conversation_shares_active
    ON cadu_conversation_shares (conversation_id, user_id, client_id, expires_at DESC)
    WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS cadu_conversation_shares_lookup
    ON cadu_conversation_shares (token_hash, expires_at)
    WHERE revoked_at IS NULL;
