-- Move Link Tester storage ownership to Reports without copying or dropping
-- historical runs. The old relation name remains as a compatibility view for
-- external queries and already deployed integrations.
DO $$
BEGIN
    IF to_regclass('cadu_reports_link_test_runs') IS NULL
       AND to_regclass('cadu_planner_link_test_runs') IS NOT NULL THEN
        ALTER TABLE cadu_planner_link_test_runs RENAME TO cadu_reports_link_test_runs;
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('cadu_planner_link_test_runs') IS NULL
       AND to_regclass('cadu_reports_link_test_runs') IS NOT NULL THEN
        EXECUTE 'CREATE VIEW cadu_planner_link_test_runs AS SELECT * FROM cadu_reports_link_test_runs';
    END IF;
END $$;

ALTER INDEX IF EXISTS cadu_planner_link_test_runs_client_created_idx
    RENAME TO cadu_reports_link_test_runs_client_created_idx;
ALTER INDEX IF EXISTS cadu_planner_link_test_runs_domain_idx
    RENAME TO cadu_reports_link_test_runs_domain_idx;
ALTER INDEX IF EXISTS cadu_planner_link_test_runs_public_idx
    RENAME TO cadu_reports_link_test_runs_public_idx;
ALTER INDEX IF EXISTS cadu_planner_link_test_runs_project_idx
    RENAME TO cadu_reports_link_test_runs_project_idx;
