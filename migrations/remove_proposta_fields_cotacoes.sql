-- Rollback: remove campos da Proposta CentralComm Programmatic em cadu_cotacoes
-- Reverte migrations/add_proposta_fields_cotacoes.sql

ALTER TABLE cadu_cotacoes DROP COLUMN IF EXISTS praca;
ALTER TABLE cadu_cotacoes DROP COLUMN IF EXISTS frequencia_impacto;
ALTER TABLE cadu_cotacoes DROP COLUMN IF EXISTS estimativa_impactos_unicos;
ALTER TABLE cadu_cotacoes DROP COLUMN IF EXISTS dados_demograficos;
ALTER TABLE cadu_cotacoes DROP COLUMN IF EXISTS perfil_audiencia_interesses;
ALTER TABLE cadu_cotacoes DROP COLUMN IF EXISTS data_envio;
ALTER TABLE cadu_cotacoes DROP COLUMN IF EXISTS validade_dias;
ALTER TABLE cadu_cotacoes DROP COLUMN IF EXISTS premissas;
