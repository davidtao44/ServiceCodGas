-- Migración para agregar viáticos y gastos a gas_movements

-- 1. Agregar columna viaticos a gas_movements
ALTER TABLE gas_movements ADD COLUMN IF NOT EXISTS viaticos FLOAT;

-- 2. Crear tabla gas_movement_expenses
CREATE TABLE IF NOT EXISTS gas_movement_expenses (
    id SERIAL PRIMARY KEY,
    movement_id INTEGER NOT NULL REFERENCES gas_movements(id) ON DELETE CASCADE,
    tipo VARCHAR(50) NOT NULL,
    monto FLOAT NOT NULL,
    descripcion TEXT,
    fecha TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Crear índice para mejorar rendimiento
CREATE INDEX IF NOT EXISTS idx_gas_movement_expenses_movement_id 
    ON gas_movement_expenses(movement_id);
