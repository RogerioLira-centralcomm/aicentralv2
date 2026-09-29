-- Link consented anonymous Super Tag sessions to identities explicitly supplied
-- by the website. Contact identifiers are stored only as keyed digests.
CREATE TABLE IF NOT EXISTS cadu_reports_supertag_known_visitors (
    id UUID PRIMARY KEY,
    site_id UUID NOT NULL REFERENCES cadu_reports_supertag_sites(id) ON DELETE CASCADE,
    campaign_scope VARCHAR(160) NOT NULL DEFAULT '',
    identity_digest CHAR(64) NOT NULL,
    identity_kind VARCHAR(8) NOT NULL CHECK (identity_kind IN ('email','phone')),
    display_name VARCHAR(120) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    UNIQUE (site_id,campaign_scope,identity_digest),
    UNIQUE (id,site_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_supertag_known_visitors_expiry_idx
    ON cadu_reports_supertag_known_visitors(expires_at,id);

CREATE TABLE IF NOT EXISTS cadu_reports_supertag_sessions (
    site_id UUID NOT NULL REFERENCES cadu_reports_supertag_sites(id) ON DELETE CASCADE,
    session_id UUID NOT NULL,
    campaign_scope VARCHAR(160) NOT NULL DEFAULT '',
    visitor_id UUID NOT NULL,
    ip_digest CHAR(64),
    started_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (site_id,session_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_supertag_sessions_expiry_idx
    ON cadu_reports_supertag_sessions(expires_at,site_id,last_seen_at DESC);
CREATE INDEX IF NOT EXISTS cadu_reports_supertag_sessions_cohort_idx
    ON cadu_reports_supertag_sessions(site_id,campaign_scope,visitor_id,started_at);

CREATE TABLE IF NOT EXISTS cadu_reports_supertag_visitor_sessions (
    site_id UUID NOT NULL REFERENCES cadu_reports_supertag_sites(id) ON DELETE CASCADE,
    session_id UUID NOT NULL,
    campaign_scope VARCHAR(160) NOT NULL DEFAULT '',
    visitor_id UUID NOT NULL,
    known_visitor_id UUID NOT NULL,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (site_id,session_id,campaign_scope),
    FOREIGN KEY (site_id,session_id)
        REFERENCES cadu_reports_supertag_sessions(site_id,session_id) ON DELETE CASCADE,
    FOREIGN KEY (known_visitor_id,site_id)
        REFERENCES cadu_reports_supertag_known_visitors(id,site_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS cadu_reports_supertag_visitor_sessions_expiry_idx
    ON cadu_reports_supertag_visitor_sessions(expires_at,site_id,session_id);
