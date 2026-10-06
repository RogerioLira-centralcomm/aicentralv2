-- Renomeia tabelas órfãs com o prefixo _old_ para que nunca mais sejam usadas.
-- Idempotente. NÃO registrado em ORDER.txt e NÃO aplicado: depende de Q1–Q8 em produção.
--
-- Cobertura (2026-10-06): só entram tabelas sem leitor/escritor no código.
-- cadu_credit_movements e cadu_credit_purchases AINDA são usadas pelo admin legado
-- /cadu/creditos (db.registrar_compra_creditos, db.criar_movimento_creditos,
-- aicentralv2/routes.py). Enquanto esse admin não for migrado para cadu_credits_extras,
-- as linhas abaixo ficam comentadas. cadu_credit_packages foi ADOTADA como catálogo
-- (add_cadu_credit_packages_catalog_v1.sql) e não é órfã.
--
-- ALTER TABLE IF EXISTS cadu_credit_movements RENAME TO _old_cadu_credit_movements;
-- ALTER TABLE IF EXISTS cadu_credit_purchases RENAME TO _old_cadu_credit_purchases;
--
-- Colunas mortas (não renomeadas; só marcação):
COMMENT ON COLUMN cadu_client_plans.tokens_used_current_month IS
  'OBSOLETA: nenhum fluxo de IA atualiza. Consumo real em cadu_tools_token_usage.';

-- Reverso (manual):
-- ALTER TABLE IF EXISTS _old_cadu_credit_movements RENAME TO cadu_credit_movements;
-- ALTER TABLE IF EXISTS _old_cadu_credit_purchases RENAME TO cadu_credit_purchases;
-- COMMENT ON COLUMN cadu_client_plans.tokens_used_current_month IS NULL;
