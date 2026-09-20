-- Personal layout preferences for the authenticated Workspace home.
-- The source records remain in their canonical tables; this table stores only
-- the signed-in user's chosen order and visibility of home widgets.
CREATE TABLE IF NOT EXISTS cadu_workspace_home_preferences (
    id UUID PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente),
    user_id BIGINT NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    widget_order JSONB NOT NULL DEFAULT '[]'::jsonb,
    visible_widgets JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_cadu_workspace_home_preferences_user
    ON cadu_workspace_home_preferences (client_id, user_id, updated_at DESC);

COMMENT ON TABLE cadu_workspace_home_preferences IS
    'Personal Workspace home layout; stores widget order and visibility per user.';
