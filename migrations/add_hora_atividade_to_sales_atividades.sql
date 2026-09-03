-- Adiciona a coluna opcional `hora_atividade` (TIME) em sales_atividades.
-- Introduzida em set/2026 para o CRM v3 permitir persistir a hora
-- prevista da atividade (drawer de edição). Bases sem a coluna
-- continuam funcionando normalmente — o backend detecta a presença
-- via `_atividades_tem_hora` em `aicentralv2/db.py`.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sales_atividades'
          AND column_name = 'hora_atividade'
    ) THEN
        ALTER TABLE sales_atividades ADD COLUMN hora_atividade TIME;
    END IF;
END $$;
