ALTER TABLE cadu_pi_campanha
    ADD COLUMN IF NOT EXISTS link_dash_incorporar BOOLEAN NOT NULL DEFAULT TRUE;
