CREATE TABLE IF NOT EXISTS user_google_connections (
    user_id INTEGER PRIMARY KEY
        REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    google_sub VARCHAR(255) NOT NULL UNIQUE,
    google_email VARCHAR(320) NOT NULL,
    encrypted_refresh_token TEXT NOT NULL,
    granted_scopes TEXT NOT NULL DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'connected'
        CHECK (status IN ('connected', 'revoked', 'error')),
    token_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_google_connections_email
    ON user_google_connections (LOWER(google_email));

CREATE TABLE IF NOT EXISTS crm_activity_meetings (
    activity_id INTEGER PRIMARY KEY
        REFERENCES sales_atividades(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL
        REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE RESTRICT,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    timezone VARCHAR(80) NOT NULL DEFAULT 'America/Sao_Paulo',
    google_calendar_id VARCHAR(255) NOT NULL DEFAULT 'primary',
    google_event_id VARCHAR(1024),
    meet_url TEXT,
    sync_status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (sync_status IN ('draft', 'syncing', 'synced', 'error', 'cancelled')),
    sync_error TEXT,
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (ends_at > starts_at)
);

CREATE INDEX IF NOT EXISTS idx_crm_activity_meetings_user
    ON crm_activity_meetings (user_id, starts_at);
CREATE INDEX IF NOT EXISTS idx_crm_activity_meetings_event
    ON crm_activity_meetings (google_event_id)
    WHERE google_event_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS crm_activity_meeting_attendees (
    id BIGSERIAL PRIMARY KEY,
    activity_id INTEGER NOT NULL
        REFERENCES crm_activity_meetings(activity_id) ON DELETE CASCADE,
    name VARCHAR(255),
    email VARCHAR(320) NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'manual'
        CHECK (source IN ('contact', 'manual', 'internal')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_crm_activity_attendee_email
    ON crm_activity_meeting_attendees (activity_id, LOWER(email));
