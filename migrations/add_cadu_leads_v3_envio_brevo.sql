-- Leads v3: envio de e-mail pela Brevo em nome do executivo e assinatura em modelo.
-- Aditivo e idempotente. Depende de add_cadu_leads_v3_ganchos.sql (cadu_lead_preferencias).
-- A assinatura passa a ter campos (nome, cargo, telefone, LinkedIn) e um modelo; o texto livre de
-- antes (coluna assinatura) continua sendo o fecho ("Abs,") acima do bloco. Os modelos vivem no
-- código (leads_v3_email.MODELOS_ASSINATURA); a coluna só guarda qual o executivo escolheu.
ALTER TABLE cadu_lead_preferencias ADD COLUMN IF NOT EXISTS modelo_assinatura VARCHAR(20) NOT NULL DEFAULT 'simples';
ALTER TABLE cadu_lead_preferencias ADD COLUMN IF NOT EXISTS nome_assinatura VARCHAR(120);
ALTER TABLE cadu_lead_preferencias ADD COLUMN IF NOT EXISTS cargo VARCHAR(120);
ALTER TABLE cadu_lead_preferencias ADD COLUMN IF NOT EXISTS telefone VARCHAR(40);
ALTER TABLE cadu_lead_preferencias ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR(300);

-- Envios do dia por executivo (limite diário) e eventos da Brevo achados pelo message-id.
CREATE INDEX IF NOT EXISTS idx_mensagem_eventos_envio_executivo
    ON cadu_lead_mensagem_eventos (((payload ->> 'id_usuario')), ocorreu_em)
    WHERE evento = 'enviado' AND provedor = 'brevo';

-- Reverso (manual):
-- DROP INDEX IF EXISTS idx_mensagem_eventos_envio_executivo;
-- ALTER TABLE cadu_lead_preferencias DROP COLUMN IF EXISTS modelo_assinatura, DROP COLUMN IF EXISTS nome_assinatura,
--     DROP COLUMN IF EXISTS cargo, DROP COLUMN IF EXISTS telefone, DROP COLUMN IF EXISTS linkedin_url;
