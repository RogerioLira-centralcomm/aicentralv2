-- Correct the first ingestion migration already applied in environments where
-- cadu_conversations.id is TEXT.  Keep this separate so deployed databases
-- converge without rewriting migration history.

ALTER TABLE cadu_workspace_ingestion_sessions
    ALTER COLUMN conversation_id TYPE TEXT USING conversation_id::text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conrelid = 'cadu_workspace_ingestion_sessions'::regclass
           AND contype = 'c'
           AND pg_get_constraintdef(oid) LIKE '%organization_id = client_id%'
    ) THEN
        ALTER TABLE cadu_workspace_ingestion_sessions
            ADD CONSTRAINT cadu_ingestion_session_tenant_matches_client
            CHECK (organization_id = client_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint constraint_row
          JOIN pg_attribute attribute_row
            ON attribute_row.attrelid = constraint_row.conrelid
           AND attribute_row.attnum = ANY(constraint_row.conkey)
         WHERE constraint_row.contype = 'f'
           AND constraint_row.conrelid = 'cadu_workspace_ingestion_sessions'::regclass
           AND constraint_row.confrelid = 'cadu_conversations'::regclass
           AND attribute_row.attname = 'conversation_id'
    ) THEN
        ALTER TABLE cadu_workspace_ingestion_sessions
            ADD CONSTRAINT cadu_ingestion_session_conversation_fkey
            FOREIGN KEY (conversation_id) REFERENCES cadu_conversations(id) ON DELETE SET NULL;
    END IF;
END $$;
