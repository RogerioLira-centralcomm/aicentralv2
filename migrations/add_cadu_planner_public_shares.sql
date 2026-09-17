-- Links públicos são opt-in: sem share_enabled, nenhum plano pode ser lido fora da sessão.
ALTER TABLE cadu_planner_plans
    ADD COLUMN IF NOT EXISTS share_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS share_token VARCHAR(96);

CREATE UNIQUE INDEX IF NOT EXISTS cadu_planner_plans_share_token_unique
    ON cadu_planner_plans (share_token)
    WHERE share_token IS NOT NULL;
