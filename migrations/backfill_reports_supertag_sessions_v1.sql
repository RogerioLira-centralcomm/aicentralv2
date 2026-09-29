-- Rebuild retained, consented sessions collected before the session rollup
-- was introduced. Existing session records always take precedence.
BEGIN;
INSERT INTO cadu_reports_supertag_sessions
    (site_id, session_id, campaign_scope, visitor_id, ip_digest,
     started_at, last_seen_at, expires_at)
SELECT e.site_id, e.session_id,
    COALESCE((ARRAY_AGG(
        LOWER(TRIM(COALESCE(NULLIF(e.attribution->>'utm_id', ''),
                            NULLIF(e.attribution->>'utm_campaign', ''), '')))
        ORDER BY e.occurred_at, e.id)
        FILTER (WHERE e.event_kind = 'page_view'))[1], ''),
    COALESCE((ARRAY_AGG(e.visitor_id ORDER BY e.occurred_at, e.id)
        FILTER (WHERE e.visitor_id IS NOT NULL))[1], e.session_id),
    NULL, MIN(e.occurred_at), MAX(e.occurred_at), MAX(e.expires_at)
FROM cadu_reports_supertag_events e
WHERE e.expires_at > NOW() AND e.consent_state = 'granted'
GROUP BY e.site_id, e.session_id
ON CONFLICT (site_id, session_id) DO NOTHING;
COMMIT;
