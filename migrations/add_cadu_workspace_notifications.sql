-- Durable, user-scoped Workspace notifications and long-job projection.
CREATE TABLE IF NOT EXISTS cadu_workspace_notifications (
    id UUID PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    client_id INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    user_id INTEGER NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
    project_ref TEXT,
    brand_ref TEXT,
    conversation_id TEXT,
    run_id UUID,
    long_job_id UUID UNIQUE,
    source_id BIGINT,
    notification_type TEXT NOT NULL CHECK (notification_type IN ('complete','attention','approval','progress','failure','automation','sharing')),
    status TEXT NOT NULL DEFAULT 'unread' CHECK (status IN ('unread','read','waiting_user','processing','completed','failed','resolved','archived')),
    title TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    action_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cadu_workspace_notifications_inbox
    ON cadu_workspace_notifications (client_id, user_id, created_at DESC)
    WHERE archived_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_cadu_workspace_notifications_project
    ON cadu_workspace_notifications (client_id, project_ref, created_at DESC)
    WHERE archived_at IS NULL;

CREATE OR REPLACE FUNCTION cadu_notify_long_job_change() RETURNS trigger AS $$
DECLARE
    target_type TEXT;
    target_status TEXT;
    target_detail TEXT;
BEGIN
    IF NEW.status NOT IN ('waiting','completed','failed','budget_exhausted') THEN
        RETURN NEW;
    END IF;
    target_type := CASE
        WHEN NEW.status = 'waiting' THEN 'approval'
        WHEN NEW.status = 'completed' THEN 'complete'
        ELSE 'failure'
    END;
    target_status := CASE
        WHEN NEW.status = 'waiting' THEN 'waiting_user'
        WHEN NEW.status = 'completed' THEN 'completed'
        ELSE 'failed'
    END;
    target_detail := CASE
        WHEN NEW.status = 'waiting' THEN 'O agente precisa de uma decisão para continuar.'
        WHEN NEW.status = 'completed' THEN 'O trabalho longo foi concluído e está pronto para revisão.'
        WHEN NEW.status = 'budget_exhausted' THEN 'A execução foi interrompida pelo limite de tokens.'
        ELSE 'A execução não foi concluída. Revise o resultado e tente novamente.'
    END;
    INSERT INTO cadu_workspace_notifications
        (id, organization_id, client_id, user_id, project_ref, conversation_id, run_id,
         long_job_id, notification_type, status, title, detail, action_payload, created_at, updated_at)
    VALUES
        (NEW.id, NEW.organization_id, NEW.client_id, NEW.user_id, NEW.project_ref,
         NEW.conversation_id, NEW.run_id, NEW.id, target_type, target_status, NEW.title,
         target_detail, jsonb_build_object('conversation_id', NEW.conversation_id,
                                           'artifact_id', NEW.artifact_id,
                                           'long_job_id', NEW.id), NOW(), NOW())
    ON CONFLICT (long_job_id) DO UPDATE SET
        notification_type = EXCLUDED.notification_type,
        status = EXCLUDED.status,
        title = EXCLUDED.title,
        detail = EXCLUDED.detail,
        action_payload = EXCLUDED.action_payload,
        updated_at = NOW(),
        archived_at = NULL;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_cadu_notify_long_job_change ON cadu_agent_long_jobs;
CREATE TRIGGER trg_cadu_notify_long_job_change
AFTER INSERT OR UPDATE OF status, result_summary, checkpoint ON cadu_agent_long_jobs
FOR EACH ROW EXECUTE FUNCTION cadu_notify_long_job_change();
