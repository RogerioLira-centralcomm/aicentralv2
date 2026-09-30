-- Destructive reset of Reports test data, explicitly requested for the v2 cutover.
-- Shared identity, Workspace and Link Tester runs are preserved. Stop Reports writers first.
BEGIN;
SELECT pg_advisory_xact_lock(hashtext('reports-client-scope-v2'));
CREATE TABLE IF NOT EXISTS cadu_reports_schema_version(version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM cadu_reports_schema_version WHERE version=2) THEN
  RAISE EXCEPTION 'Reports v2 already installed; refusing to reset again';
 END IF;
END $$;
CREATE TEMP TABLE reports_v2_tables ON COMMIT DROP AS
 SELECT c.oid,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relkind='r'
 AND c.relname IN ('cadu_connect_report_ai_runs','cadu_connect_report_imports','cadu_connect_report_public_links','cadu_connect_report_source_reviews','cadu_connect_report_sources','cadu_connect_report_workspace_versions','cadu_connect_report_workspaces','cadu_reports_accounts','cadu_reports_campaign_daily_metrics','cadu_reports_campaigns','cadu_reports_clients','cadu_reports_external_conversions','cadu_reports_flow_discovered_pages','cadu_reports_flow_discovery_runs','cadu_reports_flow_events','cadu_reports_flow_events_test','cadu_reports_flow_monitor_checks','cadu_reports_flow_rate_limits','cadu_reports_flow_registry','cadu_reports_flow_sessions','cadu_reports_flow_steps','cadu_reports_flow_suggestions','cadu_reports_flow_tag_isolation_audit','cadu_reports_flow_versions','cadu_reports_import_column_maps','cadu_reports_import_column_suggestions','cadu_reports_import_custom_values','cadu_reports_import_decisions','cadu_reports_import_files','cadu_reports_import_observations','cadu_reports_import_projection_decisions','cadu_reports_import_range_metrics','cadu_reports_import_range_snapshots','cadu_reports_import_rows','cadu_reports_import_visual_runs','cadu_reports_ingest_keys','cadu_reports_link_association_history','cadu_reports_site_tags','cadu_reports_source_runs','cadu_reports_supertag_events','cadu_reports_supertag_ip_rate_limits','cadu_reports_supertag_known_visitors','cadu_reports_supertag_rate_limits','cadu_reports_supertag_sessions','cadu_reports_supertag_sites','cadu_reports_supertag_visitor_sessions','cadu_reports_user_access');
-- Refuse unreviewed incoming dependencies instead of cascading into another product.
DO $$ DECLARE names TEXT; BEGIN
 IF EXISTS(SELECT 1 FROM pg_constraint WHERE contype='f'
   AND confrelid IN(SELECT oid FROM reports_v2_tables)
   AND conrelid NOT IN(SELECT oid FROM reports_v2_tables)) THEN
  RAISE EXCEPTION 'External foreign keys reference Reports: inspect before resetting';
 END IF;
 SELECT string_agg(format('%I',relname),',') INTO names FROM reports_v2_tables;
 IF names IS NOT NULL THEN EXECUTE 'TRUNCATE TABLE '||names; END IF;
END $$;
-- The Link Tester is shared with Planner. Keep runs, clear only their Reports associations.
UPDATE cadu_reports_link_test_runs SET account_id=NULL,media_campaign_id=NULL,report_workspace_id=NULL;
CREATE TEMP TABLE reports_v2_constraints ON COMMIT DROP AS
 SELECT c.conrelid::regclass::text AS table_name,c.conname,c.contype,pg_get_constraintdef(c.oid) AS definition
 FROM pg_constraint c WHERE c.conrelid IN(SELECT oid FROM reports_v2_tables)
 AND pg_get_constraintdef(c.oid) LIKE '%organization_id%';
CREATE TEMP TABLE reports_v2_indexes ON COMMIT DROP AS
 SELECT indexdef FROM pg_indexes WHERE schemaname='public' AND tablename IN(SELECT relname FROM reports_v2_tables)
 AND indexdef LIKE '%organization_id%' AND indexname NOT IN(SELECT conname FROM pg_constraint);
CREATE TEMP TABLE reports_v2_views ON COMMIT DROP AS
 SELECT schemaname,viewname,definition FROM pg_views
 WHERE schemaname='public' AND viewname='cadu_reports_import_metric_projection';
DO $$ DECLARE r RECORD; definition TEXT; BEGIN
 FOR r IN SELECT * FROM reports_v2_views LOOP
  EXECUTE format('DROP VIEW %I.%I',r.schemaname,r.viewname);
 END LOOP;
 FOR r IN SELECT * FROM reports_v2_constraints ORDER BY (contype='f') DESC LOOP
  EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I',r.table_name,r.conname);
 END LOOP;
 -- Native customers formerly only had organization_id, so rename that owner column.
 ALTER TABLE cadu_reports_clients RENAME COLUMN organization_id TO client_id;
 ALTER TABLE cadu_reports_clients RENAME TO cadu_reports_customers;
 FOR r IN SELECT t.relname FROM reports_v2_tables t JOIN pg_attribute a ON a.attrelid=t.oid
   WHERE a.attname='organization_id' AND NOT a.attisdropped LOOP
  EXECUTE format('ALTER TABLE %I DROP COLUMN organization_id',r.relname);
 END LOOP;
 FOR r IN SELECT * FROM reports_v2_constraints ORDER BY (contype='f') ASC LOOP
  IF r.table_name='cadu_reports_clients' THEN
   definition:=replace(r.definition,'organization_id','client_id');
   EXECUTE format('ALTER TABLE cadu_reports_customers ADD CONSTRAINT %I %s',r.conname,definition);
  ELSIF r.definition !~ '\(organization_id\)' THEN
   definition:=regexp_replace(r.definition,'organization_id,\s*','','g');
   EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I %s',r.table_name,r.conname,definition);
  END IF;
 END LOOP;
END $$;
CREATE OR REPLACE VIEW cadu_reports_import_metric_projection AS
WITH grouped AS (
    SELECT client_id,campaign_id,metric_date,metric_key,
        MAX(value_numeric) AS unanimous_value,
        MAX(currency) AS unanimous_currency,
        COUNT(*)::bigint AS observation_count,
        COUNT(DISTINCT (value_numeric,COALESCE(currency,'')))::bigint AS version_count,
        MAX(id) AS latest_observation_id
    FROM cadu_reports_import_observations
    GROUP BY client_id,campaign_id,metric_date,metric_key
), latest_decision AS (
    SELECT DISTINCT ON (client_id,campaign_id,metric_date,metric_key)
        client_id,campaign_id,metric_date,metric_key,
        selected_observation_id,seen_observation_id
    FROM cadu_reports_import_projection_decisions
    ORDER BY client_id,campaign_id,metric_date,metric_key,id DESC
)
SELECT g.client_id,g.campaign_id,g.metric_date,g.metric_key,
    CASE WHEN g.version_count=1 THEN g.unanimous_value
         WHEN d.seen_observation_id>=g.latest_observation_id THEN chosen.value_numeric
         ELSE NULL END AS value_numeric,
    CASE WHEN g.version_count=1 THEN g.unanimous_currency
         WHEN d.seen_observation_id>=g.latest_observation_id THEN chosen.currency
         ELSE NULL END AS currency,
    g.observation_count,g.version_count
FROM grouped g
LEFT JOIN latest_decision d ON d.client_id=g.client_id
    AND d.campaign_id=g.campaign_id AND d.metric_date=g.metric_date AND d.metric_key=g.metric_key
LEFT JOIN cadu_reports_import_observations chosen
    ON chosen.id=d.selected_observation_id AND chosen.client_id=g.client_id AND chosen.campaign_id=g.campaign_id
    AND chosen.metric_date=g.metric_date AND chosen.metric_key=g.metric_key;

DO $$ DECLARE r RECORD; definition TEXT; BEGIN
 FOR r IN SELECT indexdef FROM reports_v2_indexes LOOP
  definition:=replace(r.indexdef,'CREATE INDEX ','CREATE INDEX IF NOT EXISTS ');
  definition:=replace(definition,'CREATE UNIQUE INDEX ','CREATE UNIQUE INDEX IF NOT EXISTS ');
  IF definition LIKE '% ON public.cadu_reports_clients %' THEN
   definition:=replace(replace(definition,' ON public.cadu_reports_clients ',' ON public.cadu_reports_customers '),'organization_id','client_id');
  ELSE definition:=regexp_replace(definition,'organization_id,\s*','','g'); END IF;
  EXECUTE definition;
 END LOOP;
END $$;
CREATE TABLE cadu_reports_client_memberships (
 client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente),
 user_id BIGINT NOT NULL REFERENCES tbl_contato_cliente(id_contato_cliente),
 role TEXT NOT NULL CHECK(role IN ('admin','member','viewer')),
 access_scope TEXT NOT NULL DEFAULT 'all' CHECK(access_scope IN ('all','shared')),
 granted_by BIGINT REFERENCES tbl_contato_cliente(id_contato_cliente),
 revoked_at TIMESTAMPTZ, PRIMARY KEY(client_id,user_id)
);
INSERT INTO cadu_reports_client_memberships(client_id,user_id,role)
 SELECT u.pk_id_tbl_cliente,u.id_contato_cliente,
 CASE WHEN u.user_type IN ('admin','superadmin') THEN 'admin' WHEN u.user_type='viewer' THEN 'viewer' ELSE 'member' END
 FROM tbl_contato_cliente u JOIN tbl_cliente c ON c.id_cliente=u.pk_id_tbl_cliente
 WHERE u.status=TRUE AND c.status=TRUE AND NOT COALESCE(u.reports_only,FALSE);
ALTER TABLE cadu_reports_customers ALTER COLUMN id RESTART WITH 1;
ALTER TABLE cadu_reports_accounts ADD COLUMN customer_id BIGINT,
 ADD CONSTRAINT reports_account_customer_fk FOREIGN KEY(customer_id,client_id) REFERENCES cadu_reports_customers(id,client_id);
ALTER TABLE cadu_reports_campaigns ALTER COLUMN account_id DROP NOT NULL, ALTER COLUMN external_id DROP NOT NULL,
 ADD COLUMN customer_id BIGINT, ADD COLUMN origin TEXT NOT NULL DEFAULT 'platform',
 ADD CONSTRAINT reports_campaign_origin_check CHECK(origin IN ('manual','platform') AND (origin='manual' OR (account_id IS NOT NULL AND external_id IS NOT NULL))),
 ADD CONSTRAINT reports_campaign_customer_fk FOREIGN KEY(customer_id,client_id) REFERENCES cadu_reports_customers(id,client_id);
ALTER TABLE cadu_reports_supertag_sites ADD COLUMN customer_id BIGINT,
 ADD CONSTRAINT reports_site_customer_fk FOREIGN KEY(customer_id,client_id) REFERENCES cadu_reports_customers(id,client_id);
ALTER TABLE cadu_reports_flow_registry ADD COLUMN site_id UUID NOT NULL,
 ADD CONSTRAINT reports_flow_site_fk FOREIGN KEY(site_id,client_id) REFERENCES cadu_reports_supertag_sites(id,client_id);
CREATE TABLE cadu_reports_site_grants (
 client_id BIGINT NOT NULL,site_id UUID NOT NULL,user_id BIGINT NOT NULL,granted_by BIGINT NOT NULL,
 PRIMARY KEY(site_id,user_id),
 FOREIGN KEY(site_id,client_id) REFERENCES cadu_reports_supertag_sites(id,client_id),
 FOREIGN KEY(client_id,user_id) REFERENCES cadu_reports_client_memberships(client_id,user_id)
);
CREATE TABLE cadu_reports_flow_grants (
 client_id BIGINT NOT NULL,flow_id UUID NOT NULL,user_id BIGINT NOT NULL,granted_by BIGINT NOT NULL,
 PRIMARY KEY(flow_id,user_id),
 FOREIGN KEY(flow_id,client_id) REFERENCES cadu_reports_flow_registry(id,client_id),
 FOREIGN KEY(client_id,user_id) REFERENCES cadu_reports_client_memberships(client_id,user_id)
);
CREATE TABLE cadu_reports_customer_workspace_brand_links (
 client_id BIGINT NOT NULL,customer_id BIGINT NOT NULL,brand_ref TEXT NOT NULL,
 PRIMARY KEY(customer_id,brand_ref),
 FOREIGN KEY(customer_id,client_id) REFERENCES cadu_reports_customers(id,client_id)
);
CREATE TABLE cadu_reports_workspace_links (
 client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente),
 site_id UUID,flow_id UUID,campaign_id BIGINT,project_ref TEXT NOT NULL,created_by BIGINT NOT NULL,
 CHECK(num_nonnulls(site_id,flow_id,campaign_id)=1),
 FOREIGN KEY(site_id,client_id) REFERENCES cadu_reports_supertag_sites(id,client_id),
 FOREIGN KEY(flow_id,client_id) REFERENCES cadu_reports_flow_registry(id,client_id),
 FOREIGN KEY(campaign_id,client_id) REFERENCES cadu_reports_campaigns(id,client_id)
);
CREATE UNIQUE INDEX reports_workspace_site_unique ON cadu_reports_workspace_links(site_id,project_ref) WHERE site_id IS NOT NULL;
CREATE UNIQUE INDEX reports_workspace_flow_unique ON cadu_reports_workspace_links(flow_id,project_ref) WHERE flow_id IS NOT NULL;
CREATE UNIQUE INDEX reports_workspace_campaign_unique ON cadu_reports_workspace_links(campaign_id,project_ref) WHERE campaign_id IS NOT NULL;
CREATE TABLE cadu_reports_workspace_operations (
 client_id BIGINT NOT NULL REFERENCES tbl_cliente(id_cliente),operation_key TEXT NOT NULL,
 payload_hash TEXT NOT NULL,project_ref TEXT,completed BOOLEAN NOT NULL DEFAULT FALSE,
 PRIMARY KEY(client_id,operation_key)
);
-- Restore root-tenant foreign keys for all Reports tables with a client column.
DO $$ DECLARE r RECORD; BEGIN
 FOR r IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_attribute a ON a.attrelid=c.oid AND a.attname='client_id' AND NOT a.attisdropped
 WHERE n.nspname='public' AND c.relkind='r'
 AND (c.relname LIKE 'cadu_reports_%' OR c.relname='cadu_connect_report_workspaces')
 AND c.relname<>'cadu_reports_link_test_runs' LOOP
  EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY(client_id) REFERENCES tbl_cliente(id_cliente)',r.relname,r.relname||'_root_client_fk');
 END LOOP;
END $$;
ALTER TABLE cadu_reports_flow_events ADD COLUMN source_event_id UUID;
CREATE UNIQUE INDEX reports_flow_source_event_unique ON cadu_reports_flow_events(tag_id,source_event_id) WHERE source_event_id IS NOT NULL;
-- Platform imports inherit the advertiser from their media account.
CREATE FUNCTION reports_campaign_customer_scope() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner BIGINT;
BEGIN
 IF NEW.account_id IS NOT NULL THEN
  SELECT customer_id INTO owner FROM cadu_reports_accounts WHERE id=NEW.account_id AND client_id=NEW.client_id FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Media account outside Reports client'; END IF;
  IF NEW.customer_id IS NOT NULL AND NEW.customer_id IS DISTINCT FROM owner THEN
   RAISE EXCEPTION 'Campaign and media account must have the same customer';
  END IF;
  NEW.customer_id:=owner;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER reports_campaign_customer_guard BEFORE INSERT OR UPDATE OF account_id,customer_id,client_id
 ON cadu_reports_campaigns FOR EACH ROW EXECUTE FUNCTION reports_campaign_customer_scope();
-- Manual campaigns can also own Link Tester associations without a media account.
DO $$ DECLARE r RECORD; BEGIN
 FOR r IN SELECT conname FROM pg_constraint WHERE conrelid='cadu_reports_link_association_history'::regclass
 AND contype='c' AND pg_get_constraintdef(oid) LIKE '%action%' LOOP
  EXECUTE format('ALTER TABLE cadu_reports_link_association_history DROP CONSTRAINT %I',r.conname);
 END LOOP;
END $$;
ALTER TABLE cadu_reports_link_association_history ADD CONSTRAINT reports_link_association_action_check
 CHECK ((action='associate' AND campaign_id IS NOT NULL)
     OR (action='clear' AND campaign_id IS NULL AND account_id IS NULL AND report_id IS NULL));
INSERT INTO cadu_reports_schema_version(version) VALUES(2);
COMMIT;
