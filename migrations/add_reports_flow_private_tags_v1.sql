-- Run before deploying the exclusive-tag contract. Ambiguous old events remain
-- attached to the old tag; never copy them into individual flow metrics.
BEGIN;
LOCK TABLE cadu_reports_flow_registry IN SHARE ROW EXCLUSIVE MODE;
CREATE TABLE IF NOT EXISTS cadu_reports_flow_tag_isolation_audit (
    flow_id UUID PRIMARY KEY REFERENCES cadu_reports_flow_registry(id),
    old_tag_id UUID NOT NULL,
    new_tag_id UUID NOT NULL,
    isolated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
DO $$
DECLARE item RECORD; private_id UUID;
BEGIN
    FOR item IN SELECT f.*, t.allowed_host, t.revoked_at
        FROM cadu_reports_flow_registry f JOIN cadu_reports_site_tags t ON t.id=f.tag_id
        WHERE f.tag_id IN (SELECT tag_id FROM cadu_reports_flow_registry GROUP BY tag_id HAVING COUNT(*)>1)
    LOOP
        private_id := gen_random_uuid();
        INSERT INTO cadu_reports_site_tags
            (id,organization_id,client_id,label,allowed_host,public_key,created_by,tag_kind,revoked_at)
        VALUES (private_id,item.organization_id,item.client_id,item.name,item.allowed_host,
                replace(gen_random_uuid()::text,'-',''),item.created_by,'flow',item.revoked_at);
        INSERT INTO cadu_reports_flow_steps
            (organization_id,client_id,tag_id,node_id,flow_revision,name,path_prefix,page_host,
             step_kind,is_entry,position,campaign_id,is_active,archived_at)
        SELECT s.organization_id,s.client_id,private_id,s.node_id,s.flow_revision,s.name,s.path_prefix,s.page_host,
               s.step_kind,s.is_entry,s.position,s.campaign_id,
               (s.flow_revision=item.published_revision AND item.status='published'),s.archived_at
        FROM cadu_reports_flow_steps s
        WHERE s.tag_id=item.tag_id AND EXISTS (
            SELECT 1 FROM cadu_reports_flow_versions v,
                LATERAL jsonb_array_elements(v.config->'nodes') n
            WHERE v.flow_id=item.id AND v.revision=s.flow_revision AND n->>'id'=s.node_id);
        UPDATE cadu_reports_flow_registry SET tag_id=private_id WHERE id=item.id;
        INSERT INTO cadu_reports_flow_tag_isolation_audit(flow_id,old_tag_id,new_tag_id)
            VALUES(item.id,item.tag_id,private_id);
    END LOOP;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS reports_flow_private_tag ON cadu_reports_flow_registry(tag_id);
COMMIT;
