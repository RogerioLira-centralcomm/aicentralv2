-- Enhanced measurement (GA4-style) adds outbound links, downloads, contact links and video to the Super Tag.
-- Without these kinds in the CHECK, one such event fails the whole /collect batch with a 500.
ALTER TABLE cadu_reports_supertag_events
    DROP CONSTRAINT IF EXISTS cadu_reports_supertag_events_event_kind_check;

ALTER TABLE cadu_reports_supertag_events
    ADD CONSTRAINT cadu_reports_supertag_events_event_kind_check
    CHECK (event_kind IN (
        'page_view', 'page_leave', 'heartbeat', 'click', 'whatsapp_click',
        'form_submit', 'visibility', 'scroll_depth', 'custom_event', 'conversion',
        'outbound_click', 'file_download', 'contact_click', 'video'
    ));
