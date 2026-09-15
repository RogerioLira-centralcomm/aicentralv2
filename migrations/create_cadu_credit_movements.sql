CREATE TABLE IF NOT EXISTS cadu_credit_movements (
    id BIGSERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES cadu_client_plans(id) ON DELETE CASCADE,
    id_cliente INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    movement_type VARCHAR(20) NOT NULL CHECK (
        movement_type IN ('addition', 'withdrawal', 'bonus', 'usage', 'refund', 'purchase')
    ),
    amount INTEGER NOT NULL CHECK (amount > 0),
    reason VARCHAR(240) NOT NULL,
    reference VARCHAR(120),
    created_by INTEGER,
    created_by_name VARCHAR(160),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE cadu_credit_movements DROP CONSTRAINT IF EXISTS cadu_credit_movements_movement_type_check;
ALTER TABLE cadu_credit_movements ADD CONSTRAINT cadu_credit_movements_movement_type_check
    CHECK (movement_type IN ('addition', 'withdrawal', 'bonus', 'usage', 'refund', 'purchase'));

CREATE INDEX IF NOT EXISTS idx_cadu_credit_movements_plan_date
    ON cadu_credit_movements (plan_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_credit_movements_client_date
    ON cadu_credit_movements (id_cliente, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cadu_credit_movements_type_date
    ON cadu_credit_movements (movement_type, created_at DESC);

CREATE TABLE IF NOT EXISTS cadu_credit_packages (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0),
    price NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    description VARCHAR(240),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cadu_credit_purchases (
    id BIGSERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES cadu_client_plans(id) ON DELETE CASCADE,
    id_cliente INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    package_id INTEGER REFERENCES cadu_credit_packages(id) ON DELETE SET NULL,
    package_name VARCHAR(100) NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0),
    amount_paid NUMERIC(12,2) NOT NULL CHECK (amount_paid >= 0),
    payment_status VARCHAR(20) NOT NULL DEFAULT 'paid' CHECK (payment_status IN ('paid', 'pending', 'cancelled', 'refunded')),
    reference VARCHAR(120),
    notes VARCHAR(240),
    created_by INTEGER,
    created_by_name VARCHAR(160),
    purchased_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cadu_credit_purchases_plan_date
    ON cadu_credit_purchases (plan_id, purchased_at DESC);

INSERT INTO cadu_credit_packages (name, credits, price, description, display_order)
SELECT seed.name, seed.credits, seed.price, seed.description, seed.display_order
FROM (VALUES
    ('Pacote 25', 25, 250.00, 'Reposição pontual para demandas menores.', 10),
    ('Pacote 50', 50, 450.00, 'Créditos adicionais para campanhas em produção.', 20),
    ('Pacote 100', 100, 800.00, 'Volume adicional para operações recorrentes.', 30)
) AS seed(name, credits, price, description, display_order)
WHERE NOT EXISTS (SELECT 1 FROM cadu_credit_packages);
