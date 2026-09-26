ALTER TABLE cadu_planner_portals
    ADD COLUMN IF NOT EXISTS discovered_pages_count INTEGER NOT NULL DEFAULT 0
        CHECK (discovered_pages_count >= 0),
    ADD COLUMN IF NOT EXISTS crawl_updates_count INTEGER NOT NULL DEFAULT 0
        CHECK (crawl_updates_count >= 0);

-- A recorded successful crawl is evidence of at least one catalog update.
UPDATE cadu_planner_portals
   SET crawl_updates_count = 1
 WHERE last_crawled_at IS NOT NULL AND crawl_updates_count = 0;
