-- Alerta de indisponibilidade das páginas do fluxo: estado da queda e último aviso (aditivo, idempotente).
ALTER TABLE cadu_reports_flow_registry
    ADD COLUMN IF NOT EXISTS monitor_down_since TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS monitor_last_alert_at TIMESTAMPTZ;

-- Fluxos já publicados e nunca verificados passam a ser monitorados a cada 5 minutos.
UPDATE cadu_reports_flow_registry
   SET monitor_enabled=TRUE, monitor_interval_minutes=5, monitor_next_check_at=NOW()
 WHERE status='published' AND monitor_enabled=FALSE AND monitor_checked_at IS NULL;
