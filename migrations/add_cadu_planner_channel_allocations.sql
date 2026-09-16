CREATE TABLE IF NOT EXISTS cadu_planner_channel_allocations (
    plan_id UUID NOT NULL REFERENCES cadu_planner_plans(id) ON DELETE CASCADE,
    resource_id TEXT NOT NULL,
    investment NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (investment >= 0),
    weight NUMERIC(5, 2) NOT NULL DEFAULT 0 CHECK (weight >= 0 AND weight <= 100),
    flight VARCHAR(120),
    notes VARCHAR(500),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (plan_id, resource_id)
);
