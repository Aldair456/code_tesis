-- =============================================================================
-- Migration 002: Outputs por evaluador
-- Agrega evaluator_id a outputs y calculated_outputs para soporte multi-tenant.
-- Patrón idéntico a derived_cashflows (migration 001).
-- =============================================================================


-- 1. evaluator_id en outputs
--    Nullable por ahora para no romper filas existentes (outputs globales).
--    Se puede poblar y luego hacer NOT NULL en una migration posterior.
ALTER TABLE outputs
    ADD COLUMN IF NOT EXISTS evaluator_id UUID
        REFERENCES evaluators(id) ON DELETE CASCADE;

-- Índice para filtrar outputs por evaluador en get_outputs y cálculo async
CREATE INDEX IF NOT EXISTS idx_outputs_evaluator
    ON outputs (evaluator_id);
