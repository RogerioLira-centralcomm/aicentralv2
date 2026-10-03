-- "Quem converteu": contacts captured by the Super Tag on valid form submits (and identify()).
-- Name, e-mail, phone and extra fields are stored only as Fernet ciphertext (SUPERTAG_LEADS_KEY, or a key derived
-- from SECRET_KEY with its own domain separator); digests allow matching without decrypting. Rows expire with the
-- site's retention and are removed by scripts/purge_reports_supertag_events.py.
CREATE TABLE IF NOT EXISTS cadu_reports_supertag_leads (
    id UUID PRIMARY KEY,
    site_id UUID NOT NULL REFERENCES cadu_reports_supertag_sites(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL,
    session_id UUID NOT NULL,
    visitor_id UUID,
    source_event_id UUID NOT NULL,
    source VARCHAR(16) NOT NULL DEFAULT 'form' CHECK (source IN ('form','identify')),
    form_id VARCHAR(80),
    page_path VARCHAR(500) NOT NULL DEFAULT '/',
    submitted_at TIMESTAMPTZ NOT NULL,
    confirmed_at TIMESTAMPTZ,
    confirmation VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (confirmation IN ('pending','rule','conversion','valid_submit')),
    display_name_enc TEXT,
    email_enc TEXT,
    phone_enc TEXT,
    fields_enc TEXT,
    email_digest CHAR(64),
    phone_digest CHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT cadu_reports_supertag_leads_idempotent UNIQUE (site_id,source_event_id)
);
CREATE INDEX IF NOT EXISTS cadu_reports_supertag_leads_client_time_idx
    ON cadu_reports_supertag_leads (client_id,submitted_at DESC);
CREATE INDEX IF NOT EXISTS cadu_reports_supertag_leads_session_idx
    ON cadu_reports_supertag_leads (site_id,session_id,submitted_at)
    WHERE confirmed_at IS NULL;
CREATE INDEX IF NOT EXISTS cadu_reports_supertag_leads_expiry_idx
    ON cadu_reports_supertag_leads (expires_at,id);
