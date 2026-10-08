-- Radar como investigação com várias execuções: o que cada pessoa já viu e quais radares favoritou.
-- Aditivo e idempotente. Depende de add_cadu_radar_v2.sql.
-- subject_id é o id do radar ativo (cadu_radar_watches) ou, para uma busca avulsa, o id da própria execução.
CREATE TABLE IF NOT EXISTS cadu_radar_user_state (
    client_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    subject_id UUID NOT NULL,
    last_seen_at TIMESTAMPTZ,
    favorite BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, subject_id)
);
CREATE INDEX IF NOT EXISTS cadu_radar_user_state_client_idx ON cadu_radar_user_state (client_id, user_id);
