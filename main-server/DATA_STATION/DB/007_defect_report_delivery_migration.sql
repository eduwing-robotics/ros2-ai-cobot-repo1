BEGIN;

CREATE TABLE IF NOT EXISTS production.defect_report_deliveries (
    unit_defect_id bigint PRIMARY KEY
        REFERENCES production.unit_defects(unit_defect_id) ON DELETE CASCADE,
    delivery_status text NOT NULL DEFAULT 'PENDING',
    attempt_count integer NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    claimed_at timestamptz,
    sent_at timestamptz,
    message_id text,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_defect_report_delivery_status CHECK (
        delivery_status IN ('PENDING', 'PROCESSING', 'SENT', 'FAILED')
    ),
    CONSTRAINT ck_defect_report_delivery_attempts CHECK (attempt_count >= 0),
    CONSTRAINT ck_defect_report_delivery_sent CHECK (
        (delivery_status = 'SENT' AND sent_at IS NOT NULL
            AND message_id IS NOT NULL AND btrim(message_id) != '')
        OR (delivery_status != 'SENT' AND sent_at IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS ix_defect_report_deliveries_pending
    ON production.defect_report_deliveries(next_attempt_at, unit_defect_id)
    WHERE delivery_status = 'PENDING';

COMMIT;
