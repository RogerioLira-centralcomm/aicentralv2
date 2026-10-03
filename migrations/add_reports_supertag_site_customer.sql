-- Optional advertiser for a Super Tag site; the Reports client remains its owner. Existing sites stay unassigned.
ALTER TABLE cadu_reports_supertag_sites
    ADD COLUMN IF NOT EXISTS customer_id BIGINT;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='reports_supertag_site_customer_fk') THEN
        ALTER TABLE cadu_reports_supertag_sites ADD CONSTRAINT reports_supertag_site_customer_fk
            FOREIGN KEY (customer_id,client_id) REFERENCES cadu_reports_customers(id,client_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS cadu_reports_supertag_sites_customer_idx
    ON cadu_reports_supertag_sites (client_id,customer_id) WHERE customer_id IS NOT NULL;
