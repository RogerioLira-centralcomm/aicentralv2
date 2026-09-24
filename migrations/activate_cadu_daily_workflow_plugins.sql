-- Activate the new cards once, after the matching code has reached the server.
CREATE TABLE IF NOT EXISTS cadu_chat_plugin_rollouts (
    id TEXT PRIMARY KEY,
    activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

WITH activation AS (
    INSERT INTO cadu_chat_plugin_rollouts (id)
    VALUES ('daily-workflows-1.1.0')
    ON CONFLICT (id) DO NOTHING
    RETURNING id
)
UPDATE cadu_chat_plugins
   SET selectable=TRUE, enabled=TRUE, updated_at=NOW()
 WHERE id IN (
    'market-radar', 'audience-map', 'investment-simulator', 'media-plan-audit',
    'campaign-tracker', 'creative-concept', 'channel-copy', 'page-review',
    'meeting-copilot', 'client-delivery'
 ) AND EXISTS (SELECT 1 FROM activation);
