-- Remove vínculo entre audiência de cotação e item da proposta
ALTER TABLE cadu_cotacao_audiencias DROP COLUMN IF EXISTS id_linha_cotacao;
