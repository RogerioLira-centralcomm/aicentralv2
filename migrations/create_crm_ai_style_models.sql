-- Espelho do DDL em aicentralv2/db.py (`CRM_AI_STYLE_MODELS_DDL`).
-- O Python cria esta tabela sozinho no primeiro uso (IF NOT EXISTS).
-- Rodar este arquivo só antecipa isso no painel de migrations.
CREATE TABLE IF NOT EXISTS crm_ai_style_models (
    executivo_id INTEGER PRIMARY KEY,
    texto TEXT NOT NULL,
    formato VARCHAR(20) NOT NULL DEFAULT 'roteiro',
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
