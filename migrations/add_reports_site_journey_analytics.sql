ALTER TABLE cadu_reports_flow_events
    ADD COLUMN IF NOT EXISTS duration_ms INTEGER;
ALTER TABLE cadu_reports_flow_events
    DROP CONSTRAINT IF EXISTS cadu_reports_flow_event_duration_check;
ALTER TABLE cadu_reports_flow_events
    ADD CONSTRAINT cadu_reports_flow_event_duration_check
    CHECK (duration_ms IS NULL OR duration_ms BETWEEN 0 AND 600000);

ALTER TABLE cadu_reports_flow_events
    DROP CONSTRAINT IF EXISTS cadu_reports_flow_event_kind;
ALTER TABLE cadu_reports_flow_events
    ADD CONSTRAINT cadu_reports_flow_event_kind
    CHECK (event_kind IN ('page_view','page_leave','heartbeat','conversion','error_view',
        'form_submit','click','whatsapp_click','custom_event'));

ALTER TABLE cadu_reports_flow_steps
    DROP CONSTRAINT IF EXISTS cadu_reports_flow_step_kind;
ALTER TABLE cadu_reports_flow_steps
    ADD CONSTRAINT cadu_reports_flow_step_kind
    CHECK (step_kind IN ('page','conversion','form','event','whatsapp','error'));

ALTER TABLE cadu_reports_flow_discovered_pages
    DROP CONSTRAINT IF EXISTS cadu_reports_flow_discovered_pages_suggested_role_check;
ALTER TABLE cadu_reports_flow_discovered_pages
    ADD CONSTRAINT cadu_reports_flow_discovered_pages_suggested_role_check
    CHECK (suggested_role IN ('entry','intermediate','form','conversion','error'));
ALTER TABLE cadu_reports_flow_discovered_pages
    DROP CONSTRAINT IF EXISTS cadu_reports_flow_discovered_pages_selected_kind_check;
ALTER TABLE cadu_reports_flow_discovered_pages
    ADD CONSTRAINT cadu_reports_flow_discovered_pages_selected_kind_check
    CHECK (selected_kind IN ('page','form','conversion','error') OR selected_kind IS NULL);

CREATE INDEX IF NOT EXISTS cadu_reports_flow_events_journey_idx
    ON cadu_reports_flow_events (organization_id,client_id,tag_id,session_id,occurred_at,id)
    WHERE event_kind IN ('page_view','conversion','error_view','form_submit','page_leave');
