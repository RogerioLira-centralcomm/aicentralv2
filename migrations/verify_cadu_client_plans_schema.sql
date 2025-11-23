-- Verificação e correção do schema da tabela cadu_client_plans
-- Execute este script no servidor de produção para garantir compatibilidade

-- 1. Verificar estrutura atual da tabela
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'cadu_client_plans'
ORDER BY ordinal_position;

-- 2. Verificar constraints e índices
SELECT 
    conname AS constraint_name,
    contype AS constraint_type,
    pg_get_constraintdef(c.oid) AS constraint_definition
FROM pg_constraint c
JOIN pg_namespace n ON n.oid = c.connamespace
JOIN pg_class cl ON cl.oid = c.conrelid
WHERE cl.relname = 'cadu_client_plans'
  AND n.nspname = 'public';

-- 3. Se necessário renomear coluna id para id_plan (descomente se aplicável):
-- ALTER TABLE cadu_client_plans RENAME COLUMN id TO id_plan;

-- 4. Garantir que todas as colunas necessárias existam
-- Descomente as linhas necessárias:

-- ALTER TABLE cadu_client_plans ADD COLUMN IF NOT EXISTS plan_start_date TIMESTAMP;
-- ALTER TABLE cadu_client_plans ADD COLUMN IF NOT EXISTS plan_end_date TIMESTAMP;
-- ALTER TABLE cadu_client_plans ADD COLUMN IF NOT EXISTS valid_from TIMESTAMP;
-- ALTER TABLE cadu_client_plans ADD COLUMN IF NOT EXISTS valid_until TIMESTAMP;

-- 5. Verificar se a coluna features é JSONB
-- ALTER TABLE cadu_client_plans ALTER COLUMN features TYPE JSONB USING features::JSONB;

-- 6. Verificar dados existentes
SELECT COUNT(*) as total_planos FROM cadu_client_plans;
SELECT plan_type, plan_status, COUNT(*) as qtd 
FROM cadu_client_plans 
GROUP BY plan_type, plan_status;
