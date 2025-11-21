-- Adicionar coluna valid_until se não existir
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='cadu_client_plans' AND column_name='valid_until'
    ) THEN
        ALTER TABLE cadu_client_plans ADD COLUMN valid_until DATE;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='cadu_client_plans' AND column_name='valid_from'
    ) THEN
        ALTER TABLE cadu_client_plans ADD COLUMN valid_from DATE NOT NULL DEFAULT CURRENT_DATE;
    END IF;
END $$;
