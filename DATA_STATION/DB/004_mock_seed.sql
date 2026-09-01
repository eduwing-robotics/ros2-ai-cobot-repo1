-- Run after production_schema.sql against the Mock database only.

BEGIN;

CREATE TEMP TABLE mock_seed_parts (
    part_id text PRIMARY KEY,
    part_name text NOT NULL,
    part_category text NOT NULL,
    initial_stock integer NOT NULL
) ON COMMIT DROP;

-- part_name 은 데이터시트 Components 의 'MPN' 과 글자까지 같아야 한다. 그 일치로
-- 후보 3종 중 실제로 쓰는 부품을 골라 unit_price_selected 를 정한다.
-- part_category 는 데이터시트의 '부품 타입' 이자 Checklist 의 조회 키다.
INSERT INTO mock_seed_parts VALUES
    ('HBM', 'SK hynix HBM3E 12-Hi 36GB', 'HBM_MEMORY', 80),
    ('PM', 'Fabrikam FB-PM4424-15Q', 'POWER_MODULE', 40),
    ('GPU', 'NVIDIA GB200 GPU Module', 'GPU_MODULE', 10),
    ('CAP', 'Contoso CX-0603X7R104K100', 'MLCC', 50),
    ('IND', 'Contoso CX-XL7030-152M', 'POWER_INDUCTOR', 20),
    ('VRM', 'Fabrikam FB-VR546D24', 'VOLTAGE_REGULATOR', 50);

INSERT INTO production.parts (
    part_id, part_name, part_category, stock_quantity
)
SELECT part_id, part_name, part_category, initial_stock
FROM mock_seed_parts
ON CONFLICT (part_id) DO UPDATE
SET part_name = EXCLUDED.part_name,
    part_category = EXCLUDED.part_category;

INSERT INTO production.products (
    product_code, product_name, product_version, is_selectable
) VALUES (
    'HBM-ACCELERATOR-PACKAGE-BOARD',
    'HBM Accelerator Package Board (Mock)',
    'hbm-pkg-r1',
    true
)
ON CONFLICT (product_code, product_version) DO NOTHING;

CREATE TEMP TABLE mock_seed_slots (
    slot_code text PRIMARY KEY,
    part_id text NOT NULL
) ON COMMIT DROP;

INSERT INTO mock_seed_slots VALUES
    ('HBM-01', 'HBM'),
    ('HBM-02', 'HBM'),
    ('HBM-03', 'HBM'),
    ('HBM-04', 'HBM'),
    ('HBM-05', 'HBM'),
    ('HBM-06', 'HBM'),
    ('HBM-07', 'HBM'),
    ('HBM-08', 'HBM'),
    ('PM-01', 'PM'),
    ('PM-02', 'PM'),
    ('PM-03', 'PM'),
    ('PM-04', 'PM'),
    ('GPU-01', 'GPU'),
    ('CAP-01', 'CAP'),
    ('CAP-02', 'CAP'),
    ('CAP-03', 'CAP'),
    ('CAP-04', 'CAP'),
    ('CAP-05', 'CAP'),
    ('IND-01', 'IND'),
    ('IND-02', 'IND'),
    ('VRM-01', 'VRM'),
    ('VRM-02', 'VRM'),
    ('VRM-03', 'VRM'),
    ('VRM-04', 'VRM'),
    ('VRM-05', 'VRM');

DO $$
DECLARE
    mock_product_id bigint;
BEGIN
    SELECT product_id
      INTO STRICT mock_product_id
    FROM production.products
    WHERE product_code = 'HBM-ACCELERATOR-PACKAGE-BOARD'
      AND product_version = 'hbm-pkg-r1';

    INSERT INTO production.product_slots (product_id, slot_code, part_id)
    SELECT mock_product_id, slot_code, part_id
    FROM mock_seed_slots
    ON CONFLICT (product_id, slot_code) DO NOTHING;

    IF EXISTS (
        SELECT 1
        FROM (
            SELECT slot_code, part_id
            FROM production.product_slots
            WHERE product_id = mock_product_id
        ) actual
        FULL JOIN mock_seed_slots expected USING (slot_code)
        WHERE actual.slot_code IS NULL
           OR expected.slot_code IS NULL
           OR actual.part_id IS DISTINCT FROM expected.part_id
    ) THEN
        RAISE EXCEPTION
            'Mock product slot mapping differs from assembly-r1.yaml';
    END IF;
END
$$;

COMMIT;
