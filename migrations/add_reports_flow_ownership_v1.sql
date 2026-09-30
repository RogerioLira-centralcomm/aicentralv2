-- Optional advertiser and campaign context for a flow; the Reports client remains its owner.
ALTER TABLE cadu_reports_flow_registry
    ADD COLUMN IF NOT EXISTS customer_id BIGINT,
    ADD COLUMN IF NOT EXISTS campaign_id BIGINT;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='reports_flow_customer_fk') THEN
        ALTER TABLE cadu_reports_flow_registry ADD CONSTRAINT reports_flow_customer_fk
            FOREIGN KEY (customer_id,client_id) REFERENCES cadu_reports_customers(id,client_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='reports_flow_campaign_fk') THEN
        ALTER TABLE cadu_reports_flow_registry ADD CONSTRAINT reports_flow_campaign_fk
            FOREIGN KEY (campaign_id,client_id) REFERENCES cadu_reports_campaigns(id,client_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS reports_flow_customer_idx ON cadu_reports_flow_registry(client_id,customer_id) WHERE customer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS reports_flow_campaign_idx ON cadu_reports_flow_registry(client_id,campaign_id) WHERE campaign_id IS NOT NULL;

CREATE OR REPLACE FUNCTION reports_flow_association_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE campaign_customer BIGINT;
BEGIN
    IF NEW.campaign_id IS NOT NULL THEN
        SELECT customer_id INTO campaign_customer FROM cadu_reports_campaigns
            WHERE id=NEW.campaign_id AND client_id=NEW.client_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Campanha indisponível neste cliente.';
        END IF;
        IF NEW.customer_id IS NOT NULL AND campaign_customer IS NOT NULL
            AND NEW.customer_id <> campaign_customer THEN
            RAISE EXCEPTION 'A campanha pertence a outro cliente/anunciante.';
        END IF;
        IF NEW.customer_id IS NULL THEN NEW.customer_id := campaign_customer; END IF;
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS reports_flow_association_guard ON cadu_reports_flow_registry;
CREATE TRIGGER reports_flow_association_guard BEFORE INSERT OR UPDATE OF customer_id,campaign_id,client_id
    ON cadu_reports_flow_registry FOR EACH ROW EXECUTE FUNCTION reports_flow_association_guard();

CREATE OR REPLACE FUNCTION reports_flow_campaign_owner_sync() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE cadu_reports_flow_registry SET customer_id=NEW.customer_id
        WHERE campaign_id=NEW.id AND client_id=NEW.client_id;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS reports_flow_campaign_owner_sync ON cadu_reports_campaigns;
CREATE TRIGGER reports_flow_campaign_owner_sync AFTER UPDATE OF customer_id,account_id
    ON cadu_reports_campaigns FOR EACH ROW
    WHEN (OLD.customer_id IS DISTINCT FROM NEW.customer_id)
    EXECUTE FUNCTION reports_flow_campaign_owner_sync();
