-- Preserve the visit lifecycle needed by Funnel Flow through the shared Super Tag.
ALTER TABLE cadu_reports_supertag_events
    DROP CONSTRAINT IF EXISTS cadu_reports_supertag_events_event_kind_check;

ALTER TABLE cadu_reports_supertag_events
    ADD CONSTRAINT cadu_reports_supertag_events_event_kind_check
    CHECK (event_kind IN (
        'page_view', 'page_leave', 'heartbeat', 'click', 'whatsapp_click',
        'form_submit', 'visibility', 'scroll_depth', 'custom_event', 'conversion'
    ));
