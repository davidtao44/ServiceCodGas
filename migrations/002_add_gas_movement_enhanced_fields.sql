-- ================================================
-- MIGRATION: Add gas movement enhanced fields
-- Date: 2026-04-07
-- ================================================

-- Add columns to gas_movements table
ALTER TABLE gas_movements ADD COLUMN IF NOT EXISTS from_custom VARCHAR(255);
ALTER TABLE gas_movements ADD COLUMN IF NOT EXISTS to_custom VARCHAR(255);
ALTER TABLE gas_movements ADD COLUMN IF NOT EXISTS responsible VARCHAR(255);
ALTER TABLE gas_movements ADD COLUMN IF NOT EXISTS batch_id VARCHAR(36);

-- Create index for batch_id performance
CREATE INDEX IF NOT EXISTS idx_gas_movements_batch_id ON gas_movements(batch_id);

-- ================================================
-- MIGRATION: Add batch_id to filling_operation_details
-- Date: 2026-04-07
-- ================================================

ALTER TABLE filling_operation_details ADD COLUMN IF NOT EXISTS batch_id VARCHAR(36);

CREATE INDEX IF NOT EXISTS idx_filling_details_batch_id ON filling_operation_details(batch_id);

-- ================================================
-- DATA: Update existing Embasado movements with batch_id
-- Creates batches for existing movements to Embasado
-- ================================================

-- Generate batch IDs for existing movements to Embasado
-- This groups movements by date as a simple batch strategy
WITH embasado_movements AS (
    SELECT id, date::date as batch_date
    FROM gas_movements
    WHERE to_location_id = (SELECT id FROM locations WHERE name = 'Embasado')
    AND batch_id IS NULL
),
batch_groups AS (
    SELECT id, 'BATCH-' || batch_date || '-' || ROW_NUMBER() OVER (PARTITION BY batch_date ORDER BY id) as new_batch_id
    FROM embasado_movements
)
UPDATE gas_movements
SET batch_id = batch_groups.new_batch_id
FROM batch_groups
WHERE gas_movements.id = batch_groups.id;

COMMENT ON COLUMN gas_movements.from_custom IS 'Custom origin name when not using a predefined location';
COMMENT ON COLUMN gas_movements.to_custom IS 'Custom destination name when not using a predefined location';
COMMENT ON COLUMN gas_movements.responsible IS 'Person responsible for the gas transfer';
COMMENT ON COLUMN gas_movements.batch_id IS 'Batch identifier for tracking performance';
COMMENT ON COLUMN filling_operation_details.batch_id IS 'Batch ID from the gas movement that supplied this filling operation';
