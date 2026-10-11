ALTER TABLE orders
ADD COLUMN IF NOT EXISTS payment_status TEXT NOT NULL DEFAULT 'unpaid'
CHECK(payment_status IN ('unpaid', 'paid', 'legacy_unrecorded'));

UPDATE orders
SET payment_status = 'legacy_unrecorded'
WHERE status = 'collected' AND payment_status = 'unpaid';

CREATE TABLE IF NOT EXISTS order_payments (
    id BIGSERIAL PRIMARY KEY,
    order_id UUID NOT NULL UNIQUE REFERENCES orders(id),
    amount NUMERIC(12,2) NOT NULL CHECK(amount >= 0),
    method TEXT NOT NULL CHECK(method IN ('cash', 'upi')),
    reference TEXT NOT NULL DEFAULT '',
    recorded_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    snapshot JSONB NOT NULL,
    CHECK(method <> 'upi' OR length(trim(reference)) >= 3)
);

CREATE UNIQUE INDEX IF NOT EXISTS unique_upi_payment_reference
ON order_payments(upper(reference))
WHERE method = 'upi';